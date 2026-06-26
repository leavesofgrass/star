"""Document model and the multi-format loaders (PDF, EPUB, DOCX, PPTX,
ODT, HTML, images/OCR, notebooks, code, URLs, ...)."""
from ._runtime import *  # noqa: F401,F403
from .cache import _cache_load, _cache_save
from .markup import _asciidoc_to_md, _creole_to_md, _latex_to_md, _mediawiki_to_md, _orgmode_to_md, _pandoc_convert, _rst_to_md, _textile_to_md
from .settings import Settings
from .stats import _settings_fingerprint
from .ttstext import _strip_markdown_for_tts


# =============================================================================
# Document data structures
# =============================================================================


@dataclass
class WordPos:
    """Maps one word in the TTS plain-text to a position in the display."""

    word: str  # the word text (stripped of punctuation)
    tts_offset: int  # char offset in the TTS plain-text string
    tts_len: int  # length in the TTS string
    disp_line: int  # rendered display line index
    disp_col: int  # starting column in that display line


@dataclass
class Document:
    path: str = ""
    title: str = ""
    markdown: str = ""  # markdown for display
    plain_text: str = ""  # clean text for TTS
    word_map: List[WordPos] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    format: str = ""  # detected format
    encoding: str = "utf-8"
    # Chapter list for EPUB/DAISY navigation: [(title, href, word_idx), ...]
    chapters: List[Tuple[str, str, int]] = field(default_factory=list)


# =============================================================================
# Document loaders
# =============================================================================


# Formats star routes through Pandoc (when it is available and prefer_pandoc is
# on) instead of its native loader, because Pandoc reads them at least as well.
# EPUB is deliberately kept native for its NCX/NAV chapter navigation;
# markdown/text need no conversion; PDF, images/OCR, code, DAISY, archives and
# URLs are not Pandoc-readable and always stay native.
_PANDOC_FIRST_FORMATS = frozenset({
    "docx", "odt", "pptx", "html", "csv", "tsv", "xlsx",
    "rst", "latex", "mediawiki", "textile", "creole", "orgmode", "notebook",
})

# Extensions only Pandoc can open (no native loader) → the "pandoc" format.
# Value is the explicit Pandoc input format, for robust conversion of the
# less-common types Pandoc may not infer from the extension alone.
_PANDOC_INPUT_EXTS = {
    ".rtf": "rtf", ".fb2": "fb2", ".docbook": "docbook", ".dbk": "docbook",
    ".jats": "jats", ".ris": "ris", ".bib": "biblatex", ".bibtex": "biblatex",
    ".opml": "opml", ".t2t": "t2t", ".muse": "muse", ".typ": "typst",
    ".typst": "typst", ".dokuwiki": "dokuwiki", ".tikiwiki": "tikiwiki",
    ".twiki": "twiki", ".vimwiki": "vimwiki", ".jira": "jira",
    ".man": "man", ".mdoc": "mdoc", ".pod": "pod", ".roff": "man",
}


def _pandoc_available() -> bool:
    """True if Pandoc can be invoked (pypandoc module or a pandoc binary)."""
    return bool(_PYPANDOC or _PANDOC_BIN)


def _pandoc_handles(fmt: str) -> bool:
    """Formats routed through Pandoc when it is enabled and available."""
    return fmt == "pandoc" or fmt in _PANDOC_FIRST_FORMATS


def _detect_format(path: str) -> str:
    """Detect document format from extension or magic bytes."""
    p = path.lower()
    if p.startswith(("http://", "https://", "ftp://")):
        return "url"
    ext_map = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".mdown": "markdown",
        ".txt": "text",
        ".text": "text",
        ".html": "html",
        ".htm": "html",
        ".xhtml": "html",
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "doc",
        ".dot": "doc",  # legacy Word template — same binary format
        ".pptx": "pptx",
        ".ppt": "pptx",  # legacy PowerPoint — same conversion path
        ".odt": "odt",
        ".epub": "epub",
        ".csv": "csv",
        ".tsv": "tsv",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".tex": "latex",
        ".ltx": "latex",
        ".rst": "rst",
        ".rest": "rst",
        ".adoc": "asciidoc",
        ".asciidoc": "asciidoc",
        ".asc": "asciidoc",
        ".wiki": "mediawiki",
        ".mediawiki": "mediawiki",
        ".textile": "textile",
        ".creole": "creole",
        ".r": "r",
        ".rmd": "rmarkdown",
        ".ipynb": "notebook",
        ".xml": "xml",
        ".daisy": "daisy",
        ".opf": "daisy",
        ".ncx": "daisy",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".gif": "image",
        ".bmp": "image",
        ".tiff": "image",
        ".webp": "image",
        ".py": "python",
        ".js": "javascript",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "c",
        ".h": "c",
        ".hpp": "c",
        ".brf": "braille",
        ".org": "orgmode",
    }
    ext = Path(path).suffix.lower()
    if ext in ext_map:
        return ext_map[ext]
    if ext in _PANDOC_INPUT_EXTS:
        return "pandoc"
    return "text"


def _build_word_map(plain_text: str, rendered_lines: List[str]) -> List[WordPos]:
    """Build a word map that links TTS character offsets to display positions.

    Strategy: tokenize plain text into words; for each word, scan the rendered
    lines to find a matching occurrence.  Uses a rolling search start to keep
    the match order correct even for repeated words.

    Words whose only occurrence in the display is *before* the current search
    position (e.g. column-header names repeated in structured table-row
    narration) are assigned the last confirmed forward position so the
    highlight advances linearly rather than jumping backward.
    """
    words: List[WordPos] = []
    token_re = re.compile(r"\b\w[\w'-]*")
    search_line = 0  # rolling hint: don't search lines before this
    search_col = 0  # column offset on search_line; avoids re-matching an
    # earlier occurrence of a repeated word on the same line
    last_good_line = 0  # last display line from a forward-matched word
    last_good_col = 0

    for m in token_re.finditer(plain_text):
        word = m.group()
        offset = m.start()
        word_lower = word.lower()

        found_line = last_good_line
        found_col = last_good_col
        matched = False

        # Primary forward search.  On the starting line we begin the column
        # search from search_col so we never match a word that appeared
        # earlier on the same line (prevents the highlight jumping backward
        # for common words like "the" / "a" that repeat within a line).
        for li in range(search_line, min(search_line + 80, len(rendered_lines))):
            start = search_col if li == search_line else 0
            col = rendered_lines[li].lower().find(word_lower, start)
            if col >= 0:
                found_line = li
                found_col = col
                matched = True
                break

        if not matched:
            # Extended forward scan beyond the 80-line window.
            for li in range(
                min(search_line + 80, len(rendered_lines)), len(rendered_lines)
            ):
                col = rendered_lines[li].lower().find(word_lower, 0)
                if col >= 0:
                    found_line = li
                    found_col = col
                    matched = True
                    break

        if not matched:
            # Backward-only fallback: word exists but only before the current
            # search position (e.g. a table column header repeated in row
            # narration).  Keep found_line/col at last_good_* so the highlight
            # does not regress.
            for li, rline in enumerate(rendered_lines):
                col = rline.lower().find(word_lower, 0)
                if col >= 0:
                    matched = True  # word exists — audio is fine
                    break  # found_line/found_col stay at last_good_*

        words.append(
            WordPos(
                word=word,
                tts_offset=offset,
                tts_len=len(word),
                disp_line=found_line,
                disp_col=found_col,
            )
        )
        # Only advance the search position for genuine forward matches.
        # Remove the old "-2" look-back: that was intended as a robustness
        # margin but it caused common words to cascade-match 2 lines before
        # their actual display position, making the highlight appear stuck.
        if matched and found_line >= search_line:
            search_line = found_line
            search_col = found_col + len(word)
            last_good_line = found_line
            last_good_col = found_col

    return words


# ── Loader functions ──────────────────────────────────────────────────────────


def _load_plain_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"


def _load_markdown(path: str) -> str:
    return _load_plain_text(path)


class _HTML2MD(HTMLParser):
    """Minimal HTML → Markdown converter (no third-party dependencies)."""

    _SKIP = frozenset(
        {
            "script",
            "style",
            "nav",
            "footer",
            "aside",
            "noscript",
            "svg",
            "canvas",
            "meta",
            "link",
            "base",
            "iframe",
            "template",
            "button",
            "form",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: List[str] = []
        self._buf: List[str] = []
        self._skip = 0
        self._pre = 0
        self._bold = 0
        self._italic = 0
        self._code = 0
        self._heading = 0
        self._list: List[Tuple[str, int]] = []
        self._bq = 0
        self._trows: List[List[str]] = []
        self._trow: List[str] = []
        self._tcell: List[str] = []
        self._in_cell = False
        self._link_href = ""
        self._link_buf: List[str] = []
        self._in_link = False
        self._title_buf: List[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "pre":
            self._emit()
            self._pre += 1
            if self._pre == 1:
                lang = next(
                    (
                        c.split("-", 1)[1]
                        for c in a.get("class", "").split()
                        if c.startswith(("language-", "lang-"))
                    ),
                    "",
                )
                self._out.append(f"```{lang}")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._emit()
            self._heading = int(tag[1])
        elif tag == "title":
            self._in_title = True
        elif tag in ("p", "div", "section", "article", "main", "header"):
            self._emit()
        elif tag in ("b", "strong"):
            self._bold += 1
        elif tag in ("i", "em"):
            self._italic += 1
        elif tag == "code" and not self._pre:
            self._code += 1
        elif tag == "a":
            self._in_link = True
            self._link_href = a.get("href", "")
            self._link_buf = []
        elif tag == "br":
            self._buf.append("\n")
        elif tag == "hr":
            self._emit()
            self._out += ["---", ""]
        elif tag == "ul":
            self._emit()
            self._list.append(("ul", 0))
        elif tag == "ol":
            self._emit()
            self._list.append(("ol", 0))
        elif tag == "li":
            self._emit()
        elif tag == "blockquote":
            self._emit()
            self._bq += 1
        elif tag == "table":
            self._emit()
            self._trows = []
        elif tag == "tr":
            self._trow = []
        elif tag in ("th", "td"):
            self._tcell = []
            self._in_cell = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == "pre":
            self._pre = max(0, self._pre - 1)
            if self._pre == 0:
                self._out += ["```", ""]
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            t = "".join(self._buf).strip()
            if t:
                self._out += ["#" * self._heading + " " + t, ""]
            self._buf = []
            self._heading = 0
        elif tag == "title":
            self._in_title = False
        elif tag in ("p", "section", "article", "main", "header", "div"):
            self._emit_para()
        elif tag in ("b", "strong"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("i", "em"):
            self._italic = max(0, self._italic - 1)
        elif tag == "code" and not self._pre:
            self._code = max(0, self._code - 1)
        elif tag == "a":
            lt = "".join(self._link_buf).strip()
            frag = f"[{lt}]({self._link_href})" if lt and self._link_href else lt
            (self._tcell if self._in_cell else self._buf).append(frag)
            self._in_link = False
        elif tag == "li":
            t = "".join(self._buf).strip()
            if t and self._list:
                ltype, n = self._list[-1]
                pad = "  " * (len(self._list) - 1)
                if ltype == "ol":
                    n += 1
                    self._list[-1] = ("ol", n)
                    self._out.append(f"{pad}{n}. {t}")
                else:
                    self._out.append(f"{pad}* {t}")
            self._buf = []
        elif tag in ("ul", "ol"):
            if self._list:
                self._list.pop()
            if not self._list:
                self._out.append("")
        elif tag == "blockquote":
            self._emit_para()
            self._bq = max(0, self._bq - 1)
        elif tag in ("th", "td"):
            self._trow.append("".join(self._tcell).strip())
            self._tcell = []
            self._in_cell = False
            self._buf = []
        elif tag == "tr":
            if self._trow:
                self._trows.append(self._trow[:])
        elif tag == "table":
            self._flush_table()

    def handle_data(self, data: str) -> None:
        if self._skip or (not data.strip() and not self._pre):
            return
        t = data if self._pre else re.sub(r"\s+", " ", data.replace("\u00a0", " "))
        if self._pre:
            self._out.append(data.rstrip("\n"))
            return
        if self._code:
            t = f"`{t.strip()}`"
        elif self._bold and self._italic:
            t = f"***{t.strip()}***"
        elif self._bold:
            t = f"**{t.strip()}**"
        elif self._italic:
            t = f"*{t.strip()}*"
        if self._in_title:
            self._title_buf.append(t)
        elif self._in_link:
            self._link_buf.append(t)
        elif self._in_cell:
            self._tcell.append(t)
        else:
            self._buf.append(t)

    def _emit(self) -> None:
        t = "".join(self._buf).strip()
        if t:
            self._out.append(t)
        self._buf = []

    def _emit_para(self) -> None:
        t = "".join(self._buf).strip()
        if t:
            bq = "> " * self._bq
            self._out += [bq + t, ""]
        self._buf = []

    def _flush_table(self) -> None:
        rows = self._trows
        if not rows:
            return
        nc = max(len(r) for r in rows)
        hdr = (rows[0] + [""] * nc)[:nc]
        self._out.append("| " + " | ".join(hdr) + " |")
        self._out.append("|" + "|".join([" --- "] * nc) + "|")
        for row in rows[1:]:
            self._out.append("| " + " | ".join((row + [""] * nc)[:nc]) + " |")
        self._out.append("")
        self._trows = []

    def result(self) -> str:
        self._emit()
        title = "".join(self._title_buf).strip()
        lines = ([f"# {title}", ""] if title else []) + self._out
        out: List[str] = []
        prev_blank = False
        for ln in lines:
            blank = not ln.strip()
            if blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = blank
        return "\n".join(out).strip()


def _load_html(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        p = _HTML2MD()
        p.feed(text)
        p.close()
        return p.result()
    except Exception as e:
        return f"# Error loading HTML\n\n```\n{e}\n```\n"


def _load_html_str(html: str) -> str:
    p = _HTML2MD()
    p.feed(html)
    p.close()
    return p.result()


def _load_epub(path: str) -> str:
    """Load EPUB via zipfile + HTML converter (no third-party package needed)."""
    import posixpath
    from urllib.parse import unquote

    _HTML_MT = frozenset({"application/xhtml+xml", "text/html"})

    def _local(elem: ET.Element) -> str:
        t = elem.tag
        return t.split("}")[-1] if "}" in t else t

    try:
        with zipfile.ZipFile(path, "r") as zf:
            try:
                container = ET.fromstring(zf.read("META-INF/container.xml"))
            except (KeyError, ET.ParseError) as e:
                return f"# EPUB Error\n\n```\n{e}\n```\n"

            opf_path = next(
                (
                    e.get("full-path")
                    for e in container.iter()
                    if _local(e) == "rootfile"
                ),
                None,
            )
            if not opf_path:
                return "# EPUB Error\n\nCould not locate OPF rootfile.\n"

            opf_root = ET.fromstring(zf.read(opf_path))
            opf_dir = (opf_path.rsplit("/", 1)[0] + "/") if "/" in opf_path else ""

            title = author = ""
            for e in opf_root.iter():
                tl = _local(e)
                if tl == "title" and not title and e.text:
                    title = e.text.strip()
                elif tl == "creator" and not author and e.text:
                    author = e.text.strip()

            manifest: Dict[str, Tuple[str, str, str]] = {}
            for e in opf_root.iter():
                if _local(e) == "item":
                    iid = e.get("id", "")
                    href = unquote(e.get("href", ""))
                    mt = e.get("media-type", "")
                    props = e.get("properties", "")
                    if iid and href:
                        manifest[iid] = (href, mt, props)

            spine = [
                e.get("idref", "")
                for e in opf_root.iter()
                if _local(e) == "itemref" and e.get("idref")
            ]

            znames = {n.lower(): n for n in zf.namelist()}

            def read_item(item_path: str) -> Optional[bytes]:
                try:
                    return zf.read(item_path)
                except KeyError:
                    canon = znames.get(item_path.lower())
                    return zf.read(canon) if canon else None

            parts: List[str] = []
            if title:
                parts += [f"# {title}", ""]
            if author:
                parts += [f"*{author}*", ""]
            if title or author:
                parts += ["---", ""]

            seen: set = set()
            for idref in spine:
                if idref not in manifest:
                    continue
                href, mt, props = manifest[idref]
                if mt not in _HTML_MT:
                    continue
                if "nav" in props.split():
                    continue
                href = href.split("#")[0]
                if not href:
                    continue
                raw = href if href.startswith("/") else opf_dir + href
                item_path = posixpath.normpath(raw).lstrip("/")
                if item_path in seen:
                    continue
                seen.add(item_path)
                data = read_item(item_path)
                if not data:
                    continue
                html_text = re.sub(
                    r"<title\b[^>]*>.*?</title>",
                    "",
                    data.decode("utf-8", "replace"),
                    flags=re.I | re.S,
                )
                ch = _load_html_str(html_text).strip()
                if ch:
                    parts += [ch, "", "---", ""]

            while parts and parts[-1] in ("", "---"):
                parts.pop()
            return (
                "\n".join(parts) + "\n"
                if parts
                else f"# {Path(path).name}\n\n*(empty EPUB)*\n"
            )
    except zipfile.BadZipFile:
        return "# EPUB Error\n\nNot a valid ZIP/EPUB file.\n"
    except Exception as e:
        return f"# EPUB Error\n\n```\n{e}\n```\n"


def _load_dtbook(path: str) -> str:
    """Load DTBook XML (DAISY digital talking book) into markdown.
    Supports DTBook 2005-3 and DAISY 3 NCX navigation."""
    _NS = {
        "dtb": "http://www.daisy.org/z3986/2005/dtbook/",
        "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    }

    def _text(elem: ET.Element) -> str:
        return "".join(elem.itertext()).strip()

    def _walk(elem: ET.Element, depth: int = 0) -> List[str]:
        out: List[str] = []
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in (
            "dtbook",
            "book",
            "frontmatter",
            "bodymatter",
            "rearmatter",
            "pagenum",
        ):
            for child in elem:
                out.extend(_walk(child, depth))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            out.append("#" * level + " " + _text(elem))
            out.append("")
        elif tag in ("p",):
            t = _text(elem)
            if t:
                out.append(t)
                out.append("")
        elif tag in ("list",):
            for li in elem:
                li_tag = li.tag.split("}")[-1] if "}" in li.tag else li.tag
                if li_tag == "li":
                    out.append("* " + _text(li))
            out.append("")
        elif tag in ("imggroup",):
            for child in elem:
                ct = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if ct == "caption":
                    out.append(f"*{_text(child)}*")
                elif ct == "img":
                    alt = child.get("alt", "")
                    out.append(f"![{alt}]({child.get('src', '')})")
            out.append("")
        elif tag in ("sidebar", "prodnote", "annotation"):
            out.append("> " + _text(elem).replace("\n", "\n> "))
            out.append("")
        elif tag in ("level", "level1", "level2", "level3", "level4", "section", "div"):
            for child in elem:
                out.extend(_walk(child, depth + 1))
        elif tag in ("note", "footnote"):
            out.append(f"[^note]: {_text(elem)}")
        else:
            for child in elem:
                out.extend(_walk(child, depth))
        return out

    try:
        tree = ET.parse(path)
        root = tree.getroot()
        lines = _walk(root)
        # Collapse runs of blank lines
        result: List[str] = []
        blank = 0
        for ln in lines:
            if not ln.strip():
                blank += 1
                if blank <= 1:
                    result.append("")
            else:
                blank = 0
                result.append(ln)
        return "\n".join(result).strip()
    except Exception as e:
        return f"# DTBook Error\n\n```\n{e}\n```\n"


def _load_daisy_zip(path: str) -> str:
    """Load a DAISY book from a ZIP archive (Bookshare format).
    Tries DTBook XML first, then EPUB-style HTML chapters."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            # Priority: DTBook XML
            for n in names:
                if n.lower().endswith((".xml", ".dtbook")) and "book" in n.lower():
                    tmp = CACHE_DIR / ("daisy_" + Path(n).name)
                    tmp.parent.mkdir(parents=True, exist_ok=True)
                    tmp.write_bytes(zf.read(n))
                    return _load_dtbook(str(tmp))
            # Fall back: any .html / .xhtml
            html_parts = []
            for n in sorted(names):
                if n.lower().endswith((".html", ".xhtml", ".htm")):
                    html_parts.append(
                        _load_html_str(zf.read(n).decode("utf-8", "replace"))
                    )
            if html_parts:
                return "\n\n---\n\n".join(html_parts)
            return "# DAISY Error\n\nNo readable content found in this ZIP.\n"
    except zipfile.BadZipFile:
        return "# DAISY Error\n\nNot a valid ZIP file.\n"
    except Exception as e:
        return f"# DAISY Error\n\n```\n{e}\n```\n"


def _load_csv_tsv(path: str, delim: str = ",") -> str:
    """Render CSV or TSV as a Markdown table."""
    try:
        rows: List[List[str]] = []
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh, delimiter=delim)
            for row in reader:
                rows.append(row)
        if not rows:
            return "*(empty file)*\n"
        nc = max(len(r) for r in rows)
        out: List[str] = [f"# {Path(path).name}", ""]
        hdr = (rows[0] + [""] * nc)[:nc]
        out.append("| " + " | ".join(h.replace("|", "\\|") for h in hdr) + " |")
        out.append("|" + "|".join([" --- "] * nc) + "|")
        for row in rows[1:]:
            cells = (row + [""] * nc)[:nc]
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        return "\n".join(out)
    except Exception as e:
        return f"# Error loading {Path(path).suffix.upper()}\n\n```\n{e}\n```\n"


def _load_xlsx(path: str) -> str:
    """Render XLSX spreadsheet as Markdown tables, one per sheet."""
    if not _XLSX:
        return (
            "# XLSX support not available\n\n"
            "Install openpyxl:  `pip install openpyxl`\n"
        )
    try:
        wb = _load_openpyxl().load_workbook(path, read_only=True, data_only=True)
        parts: List[str] = [f"# {Path(path).name}", ""]
        for ws in wb.worksheets:
            parts.append(f"## {ws.title}")
            parts.append("")
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                parts.append("*(empty sheet)*")
                parts.append("")
                continue
            nc = max(len(r) for r in rows)

            def _cell(v: Any) -> str:
                return str(v) if v is not None else ""

            hdr = [_cell(c) for c in (rows[0] + (None,) * nc)[:nc]]
            parts.append("| " + " | ".join(hdr) + " |")
            parts.append("|" + "|".join([" --- "] * nc) + "|")
            for row in rows[1:]:
                cells = [_cell(c) for c in (list(row) + [None] * nc)[:nc]]
                parts.append("| " + " | ".join(cells) + " |")
            parts.append("")
        return "\n".join(parts)
    except Exception as e:
        return f"# XLSX Error\n\n```\n{e}\n```\n"


def _load_docx(path: str) -> str:
    if not _DOCX:
        return (
            "# DOCX support not available\n\n"
            "Install python-docx:  `pip install python-docx`\n"
        )
    try:
        doc = _load_docx().Document(path)
        out: List[str] = []
        for para in doc.paragraphs:
            sn = para.style.name.lower()
            txt = para.text
            if not txt.strip():
                out.append("")
                continue
            if "heading 1" in sn:
                out.append(f"# {txt}")
            elif "heading 2" in sn:
                out.append(f"## {txt}")
            elif "heading 3" in sn:
                out.append(f"### {txt}")
            elif "heading 4" in sn:
                out.append(f"#### {txt}")
            elif "heading" in sn:
                out.append(f"##### {txt}")
            elif "list" in sn:
                out.append(f"* {txt}")
            elif "code" in sn or "preformat" in sn:
                out.append(f"    {txt}")
            else:
                rich = ""
                for run in para.runs:
                    rt = run.text
                    if not rt:
                        continue
                    if run.bold and run.italic:
                        rt = f"***{rt}***"
                    elif run.bold:
                        rt = f"**{rt}**"
                    elif run.italic:
                        rt = f"*{rt}*"
                    rich += rt
                out.append(rich)
        for tbl in doc.tables:
            out.append("")
            for ri, row in enumerate(tbl.rows):
                cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                out.append("| " + " | ".join(cells) + " |")
                if ri == 0:
                    out.append("|" + "|".join([" --- "] * len(cells)) + "|")
            out.append("")
        return "\n".join(out)
    except Exception as e:
        return f"# DOCX Error\n\n```\n{e}\n```\n"


def _load_doc(path: str) -> str:
    """Load a legacy binary Word (.doc / .dot) file as Markdown.

    Tries four approaches in order of preference:

    1. **python-docx** — works when the file is actually OOXML saved with a
       .doc extension (common with modern versions of Word on Windows).
    2. **antiword** subprocess — the lightweight dedicated converter for the
       true binary Word 97-2003 format.  Free binary available for Windows at
       https://www.winfield.demon.nl/  — add to PATH to enable.
    3. **LibreOffice headless** — converts .doc → .docx in a temp directory,
       then loads with python-docx.  Works if LibreOffice is installed.
    4. **Pandoc** — delegates to the existing _load_via_pandoc() helper.

    If none of these succeed a human-readable error with install instructions
    is returned.
    """
    title = Path(path).stem

    # ── 1. python-docx (file may be OOXML despite the .doc extension) ───────
    if _DOCX:
        try:
            md = _load_docx(path)
            if not md.startswith(("# DOCX Error", "# DOCX support")):
                return md
        except Exception:
            pass

    # ── 2. antiword ───────────────────────────────────────────────────
    antiword_bin = shutil.which("antiword") or shutil.which("antiword.exe")
    if antiword_bin:
        try:
            result = subprocess.run(
                [antiword_bin, "-w", "0", path],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                text = result.stdout.decode("utf-8", errors="replace").strip()
                if text:
                    return f"# {title}\n\n{text}\n"
        except Exception:
            pass

    # ── 3. LibreOffice headless (doc → docx → python-docx) ─────────────────
    lo_candidates: List[str] = ["soffice", "libreoffice"]
    if sys.platform == "win32":
        lo_candidates += [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    lo_bin = next(
        (b for b in lo_candidates if shutil.which(b) or Path(b).exists()),
        None,
    )
    if lo_bin and _DOCX:
        try:
            import tempfile as _tmpmod

            with _tmpmod.TemporaryDirectory() as tmpdir:
                result = subprocess.run(
                    [
                        lo_bin,
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        tmpdir,
                        path,
                    ],
                    capture_output=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    docx_path = Path(tmpdir) / (Path(path).stem + ".docx")
                    if docx_path.exists():
                        md = _load_docx(str(docx_path))
                        if not md.startswith(("# DOCX Error", "# DOCX support")):
                            return md
        except Exception:
            pass

    # ── 4. Pandoc ──────────────────────────────────────────────────────
    pandoc_md = _load_via_pandoc(path)
    if pandoc_md:
        return pandoc_md

    # ── Nothing worked ──────────────────────────────────────────────────
    return (
        f"# {title}\n\n"
        "**Could not load this binary Word (.doc) file.**\n\n"
        "Install one of the following to add .doc support:\n\n"
        "- **antiword** (lightest option): "
        "download the Windows binary from https://www.winfield.demon.nl/ "
        "and add it to your PATH\n"
        "- **LibreOffice** (also enables ODT/ODP/ODS conversion): "
        "https://www.libreoffice.org/\n"
        "- **Pandoc** + LibreOffice: `pip install pypandoc` then install "
        "Pandoc from https://pandoc.org/\n"
    )


# =============================================================================
# PDF reading-order reconstruction (multi-column layout, running heads/feet)
# =============================================================================
#
# pdfminer emits text boxes in layout order, which interleaves columns on
# multi-column pages — so a two-column journal article reads as "row 1 of
# column A, row 1 of column B, ...", i.e. gibberish for TTS.  These helpers
# rebuild a sane reading order from box geometry (column-by-column,
# top-to-bottom) and drop running headers/footers and page numbers.  They work
# on plain geometry (`_PdfBox`), independent of pdfminer, so they unit-test
# without a real PDF.  Guarded behind the `pdf_reading_order` setting
# ("reconstruct" default; "raw" falls back to pdfminer's native box order).


@dataclass(frozen=True)
class _PdfBox:
    """A laid-out text box in pdfminer coordinates (origin bottom-left, y up)."""

    text: str
    x0: float  # left
    y0: float  # bottom
    x1: float  # right
    y1: float  # top


# A bare/decorated page number in a margin: "12", "Page 12", "12 of 340", "iv".
_PDF_PAGENUM_RE = re.compile(
    r"^(?:page\s+)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?$|^[ivxlcdm]{1,7}$",
    re.IGNORECASE,
)


def _pdf_norm_margin(text: str) -> str:
    """Normalize a margin line so it matches across pages: lowercased,
    whitespace collapsed, digit runs → '#' (so 'Page 3' == 'Page 4')."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"\d+", "#", t)


def _pdf_running_heads_feet(pages: List[List["_PdfBox"]], page_height: float) -> set:
    """Normalized text that recurs in the top/bottom margin across pages —
    i.e. running headers/footers worth suppressing."""
    if page_height <= 0 or len(pages) < 3:
        return set()
    top, bot = 0.90 * page_height, 0.10 * page_height
    counts: Dict[str, int] = {}
    for boxes in pages:
        seen = set()
        for b in boxes:
            if b.y0 >= top or b.y1 <= bot:
                key = _pdf_norm_margin(b.text)
                if key and key not in seen:
                    counts[key] = counts.get(key, 0) + 1
                    seen.add(key)
    threshold = max(3, (len(pages) + 1) // 2)
    return {k for k, c in counts.items() if c >= threshold}


def _pdf_is_running(box: "_PdfBox", page_height: float, repeating: set) -> bool:
    """True if `box` sits in a margin and is a running head/foot or page number."""
    if page_height <= 0:
        return False
    if not (box.y0 >= 0.90 * page_height or box.y1 <= 0.10 * page_height):
        return False
    if _PDF_PAGENUM_RE.match(box.text.strip()):
        return True
    return _pdf_norm_margin(box.text) in repeating


def _pdf_detect_columns(boxes: List["_PdfBox"], page_width: float) -> List[tuple]:
    """The page's column x-ranges, left→right, from a vertical projection of
    box x-extents.  A single range means single-column."""
    if not boxes or page_width <= 0:
        return [(0.0, page_width)]
    n = 200
    binw = page_width / n
    covered = [False] * n
    for b in boxes:
        lo = max(0, min(n - 1, int(b.x0 / binw)))
        hi = max(0, min(n - 1, int(b.x1 / binw)))
        for i in range(lo, hi + 1):
            covered[i] = True
    regions: List[list] = []
    i = 0
    while i < n:
        if covered[i]:
            j = i
            while j < n and covered[j]:
                j += 1
            regions.append([i * binw, j * binw])
            i = j
        else:
            i += 1
    if not regions:
        return [(0.0, page_width)]
    gutter = 0.04 * page_width  # a real column gutter is at least this wide
    merged = [regions[0]]
    for lo, hi in regions[1:]:
        if lo - merged[-1][1] < gutter:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged]


def _pdf_order_boxes(boxes: List["_PdfBox"], page_width: float) -> List["_PdfBox"]:
    """Reading order for one page: column-by-column, top-to-bottom.  Full-width
    boxes (titles, spanning figures) act as band dividers that interrupt the
    column flow at their vertical position."""
    boxes = [b for b in boxes if b.text.strip()]
    if len(boxes) <= 1:
        return sorted(boxes, key=lambda b: (-b.y1, b.x0))
    full_w = 0.55 * page_width if page_width > 0 else float("inf")
    full = [b for b in boxes if (b.x1 - b.x0) >= full_w]
    cols = [b for b in boxes if (b.x1 - b.x0) < full_w]
    ranges = _pdf_detect_columns(cols, page_width)
    if len(ranges) <= 1:
        return sorted(boxes, key=lambda b: (-b.y1, b.x0))  # single column
    centers = [(lo + hi) / 2 for lo, hi in ranges]

    def col_index(b: "_PdfBox") -> int:
        cx = (b.x0 + b.x1) / 2
        for i, (lo, hi) in enumerate(ranges):
            if lo <= cx <= hi:
                return i
        return min(range(len(ranges)), key=lambda i: abs(cx - centers[i]))

    div_centers = sorted(((b.y0 + b.y1) / 2 for b in full), reverse=True)

    def band(b: "_PdfBox") -> int:
        cy = (b.y0 + b.y1) / 2
        return sum(1 for dc in div_centers if dc > cy)

    full_ids = {id(b) for b in full}

    def key(b: "_PdfBox") -> tuple:
        is_div = id(b) in full_ids
        # (band, dividers-after-their-band's-columns, column, top→bottom, left→right)
        return (band(b), 1 if is_div else 0, 0 if is_div else col_index(b), -b.y1, b.x0)

    return sorted(boxes, key=key)


def _load_pdf(path: str, reconstruct: bool = True) -> str:
    if not _PDF and not (_OCR and _PYMUPDF):
        return (
            "# PDF support not available\n\n"
            "Install pdfminer.six:  `pip install pdfminer.six`\n"
            "For image/scanned PDFs also install:  `pip install pytesseract pymupdf`\n"
        )
    try:
        if _PDF == "layout":
            extract_pages, LTTextBoxHorizontal = _load_pdf_pages()
            # First pass: collect each page's boxes (+ OCR text for image pages).
            collected: List[dict] = []
            for pnum, page in enumerate(extract_pages(path), 1):
                boxes = [
                    _PdfBox(
                        el.get_text().strip(),
                        float(el.x0), float(el.y0), float(el.x1), float(el.y1),
                    )
                    for el in page
                    if isinstance(el, LTTextBoxHorizontal) and el.get_text().strip()
                ]
                ocr_text = None
                if not boxes and _OCR and _PYMUPDF:
                    fitz = _load_fitz()
                    pytesseract, Image = _load_ocr()
                    doc = fitz.open(path)
                    pix = doc[pnum - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    doc.close()
                    ocr_text = pytesseract.image_to_string(img).strip()
                collected.append({
                    "pnum": pnum,
                    "boxes": boxes,
                    "w": float(getattr(page, "width", 0) or 0),
                    "h": float(getattr(page, "height", 0) or 0),
                    "ocr": ocr_text,
                })
            heights = [c["h"] for c in collected if c["h"] > 0]
            rep_h = max(heights) if heights else 0.0
            repeating = (
                _pdf_running_heads_feet([c["boxes"] for c in collected], rep_h)
                if reconstruct else set()
            )
            # Second pass: assemble text.  reconstruct → column-aware order with
            # running heads/feet stripped; raw → pdfminer's native box order.
            parts: List[str] = []
            for c in collected:
                parts.append(f"\n---\n*Page {c['pnum']}*\n")
                if c["ocr"] is not None:
                    parts.append(c["ocr"])
                    continue
                page_boxes = c["boxes"]
                if reconstruct:
                    h = c["h"] or rep_h
                    page_boxes = [
                        b for b in page_boxes if not _pdf_is_running(b, h, repeating)
                    ]
                    page_boxes = _pdf_order_boxes(page_boxes, c["w"])
                parts.extend(b.text for b in page_boxes)
            return "\n".join(parts)
        elif _PDF == "simple":
            extract_text = _load_pdf_text()
            return _strip_markdown_for_tts(extract_text(path) or "")
        elif _OCR and _PYMUPDF:
            fitz = _load_fitz()
            pytesseract, Image = _load_ocr()
            doc = fitz.open(path)
            parts = []
            for pnum, page in enumerate(doc, 1):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                parts.append(
                    f"\n---\n*Page {pnum}*\n\n"
                    + pytesseract.image_to_string(img).strip()
                )
            doc.close()
            return "\n".join(parts)
    except Exception as e:
        return f"# PDF Error\n\n```\n{e}\n```\n"
    return "# PDF Error\n\nUnknown failure.\n"


def _load_image_ocr(path: str) -> str:
    if not _OCR:
        return (
            "# OCR support not available\n\n"
            "Install pytesseract:  `pip install pytesseract`\n"
            "Also install Tesseract binary: https://github.com/tesseract-ocr/tesseract\n"
        )
    try:
        pytesseract, Image = _load_ocr()
        img = Image.open(path).convert("RGB")
        text = pytesseract.image_to_string(img)
        return f"# {Path(path).name}\n\n{text.strip()}\n"
    except Exception as e:
        return f"# OCR Error\n\n```\n{e}\n```\n"


def _load_r_code(path: str) -> str:
    """Load R source with fenced code block for syntax highlighting."""
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"
    return f"# {Path(path).name}\n\n```r\n{src}\n```\n"


def _load_rmarkdown(path: str) -> str:
    """R Markdown: strip YAML front matter and render as markdown."""
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"
    src = re.sub(r"^---\s*\n.*?\n---\s*\n", "", src, flags=re.S)
    # Code chunks — wrap in fenced blocks with language tag
    src = re.sub(r"```\{r([^}]*)\}", r"```r", src)
    src = re.sub(r"```\{python([^}]*)\}", r"```python", src)
    return src


def _load_notebook(path: str) -> str:
    """Jupyter notebook: extract markdown and code cells."""
    try:
        nb = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
        cells = nb.get("cells", [])
        parts: List[str] = [f"# {Path(path).name}", ""]
        for cell in cells:
            ct = cell.get("cell_type", "")
            src = "".join(cell.get("source", []))
            if ct == "markdown":
                parts.append(src)
                parts.append("")
            elif ct == "code":
                lang = (
                    nb.get("metadata", {})
                    .get("kernelspec", {})
                    .get("language", "python")
                )
                parts.append(f"```{lang}")
                parts.append(src)
                parts.append("```")
                parts.append("")
        return "\n".join(parts)
    except Exception as e:
        return f"# Notebook Error\n\n```\n{e}\n```\n"


def _load_orgmode(path: str) -> str:
    """Load an Org-mode file as Markdown.

    Strategy: Pandoc → orgparse library → built-in _orgmode_to_md().
    """
    # 1. Pandoc (handles the full Org spec including exports, macros, etc.)
    md = _pandoc_convert(path, "org")
    if md:
        return md
    # 2. orgparse (pip install orgparse) — Python-native Org parser
    try:
        import orgparse as _op  # type: ignore[import]

        doc = _op.load(path)
        # Convert the orgparse tree to plain text lines then run through
        # the Markdown converter for any residual markup.
        lines_out: List[str] = []
        for node in doc.children:
            lines_out.extend(str(node).splitlines())
        return _orgmode_to_md("\n".join(lines_out))
    except Exception:
        pass
    # 3. Built-in comprehensive heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _orgmode_to_md(src)
    except Exception as e:
        return f"# Org-mode Error\n\n```\n{e}\n```\n"


def _load_rst(path: str) -> str:
    """Load a reStructuredText file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "rst")
    if md:
        return md
    # 2. docutils (canonical Python RST library)
    try:
        from docutils.core import publish_parts  # type: ignore[import]

        src = Path(path).read_text(encoding="utf-8", errors="replace")
        html = publish_parts(src, writer_name="html")["html_body"]
        return _load_html_str(html)
    except Exception:
        pass
    # 3. Built-in heuristic converter
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _rst_to_md(src)
    except Exception as e:
        return f"# RST Error\n\n```\n{e}\n```\n"


def _load_mediawiki(path: str) -> str:
    """Load a MediaWiki markup file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "mediawiki")
    if md:
        return md
    # 2. mwparserfromhell (optional pure-Python MediaWiki parser)
    try:
        import mwparserfromhell as _mwp  # type: ignore[import]

        src = Path(path).read_text(encoding="utf-8", errors="replace")
        wikicode = _mwp.parse(src)
        # Strip templates and extract plain wikitext, then apply basic converter
        plain = wikicode.strip_code(normalize=True, collapse=True)
        return _mediawiki_to_md(plain)
    except Exception:
        pass
    # 3. Built-in heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _mediawiki_to_md(src)
    except Exception as e:
        return f"# MediaWiki Error\n\n```\n{e}\n```\n"


def _load_asciidoc(path: str) -> str:
    """Load an AsciiDoc file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "asciidoc")
    if md:
        return md
    # 2. asciidoctor CLI  (renders to HTML, then convert)
    asciidoctor = shutil.which("asciidoctor") or shutil.which("asciidoc")
    if asciidoctor:
        try:
            r = subprocess.run(
                [asciidoctor, "-b", "html5", "-o", "-", path],
                capture_output=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout:
                return _load_html_str(r.stdout.decode("utf-8", errors="replace"))
        except Exception:
            pass
    # 3. Built-in heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _asciidoc_to_md(src)
    except Exception as e:
        return f"# AsciiDoc Error\n\n```\n{e}\n```\n"


def _load_textile(path: str) -> str:
    """Load a Textile markup file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "textile")
    if md:
        return md
    # 2. textile Python library (pip install textile)
    try:
        import textile as _textile_lib  # type: ignore[import]

        src = Path(path).read_text(encoding="utf-8", errors="replace")
        html = _textile_lib.textile(src)
        return _load_html_str(html)
    except Exception:
        pass
    # 3. Built-in heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _textile_to_md(src)
    except Exception as e:
        return f"# Textile Error\n\n```\n{e}\n```\n"


def _load_creole(path: str) -> str:
    """Load a Wiki Creole 1.0 file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "creole")
    if md:
        return md
    # 2. Built-in converter (Creole is simple and self-contained)
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _creole_to_md(src)
    except Exception as e:
        return f"# Creole Error\n\n```\n{e}\n```\n"


def _load_latex(path: str) -> str:
    """Load a LaTeX (.tex / .ltx) file as Markdown.

    Strategy: Pandoc → built-in _latex_to_md() stripper.

    Pandoc produces the best output for well-formed LaTeX (it handles
    cross-references, bibliographies, custom macros from \\newcommand, etc.).
    The built-in fallback covers the 80–90% case for typical academic papers
    and lecture notes without requiring any external tools.
    """
    # 1. Pandoc — also handles BibTeX references if they are inlined
    md = _pandoc_convert(path, "latex")
    if md:
        return md
    # 2. Built-in converter
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _latex_to_md(src)
    except Exception as e:
        return f"# LaTeX Error\n\n```\n{e}\n```\n"


def _load_url(url: str) -> str:
    """Fetch a URL and convert to markdown."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"star/{APP_VERSION} (text reader; {sys.platform})"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get("Content-Type", "text/html")
            raw = resp.read()
            encoding = "utf-8"
            enc_m = re.search(r"charset=([^\s;]+)", ct)
            if enc_m:
                encoding = enc_m.group(1).strip("\"'")
            text = raw.decode(encoding, errors="replace")

        if "text/html" in ct or "xhtml" in ct:
            return _load_html_str(text)
        elif "text/plain" in ct or "markdown" in ct:
            return text
        elif "application/pdf" in ct:
            tmp = CACHE_DIR / "download.pdf"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(raw)
            return _load_pdf(str(tmp))
        else:
            return text
    except urllib.error.URLError as e:
        return f"# URL Error\n\n```\n{e}\n```\n"
    except Exception as e:
        return f"# Fetch Error\n\n```\n{e}\n```\n"


def _load_pandoc_first(path: str) -> Optional[str]:
    """Convert via Pandoc for a Pandoc-handled format: an explicit input format
    for the uncommon Pandoc-only extensions, auto-detection for the rest.
    Returns None if Pandoc fails or is unavailable."""
    pf = _PANDOC_INPUT_EXTS.get(Path(path).suffix.lower())
    return _pandoc_convert(path, pf) if pf else _load_via_pandoc(path)


def _load_via_pandoc(path: str) -> Optional[str]:
    """Use Pandoc binary or pypandoc to convert a file to Markdown.
    Returns None if Pandoc is not available."""
    if _PYPANDOC:
        try:
            return _pypandoc.convert_file(path, "markdown")
        except Exception:
            pass
    if _PANDOC_BIN:
        try:
            result = subprocess.run(
                [_PANDOC_BIN, "--to", "markdown", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
    return None


def load_document(path: str, settings: Settings) -> Document:
    """Load any supported document format and return a Document object."""
    # ── Archive member ref: /abs/book.zip!inner/paper.pdf ─────────────────
    from .archive import is_archive_ref, is_archive, parse_ref, list_members, open_member, build_index_markdown
    if is_archive_ref(path):
        parsed = parse_ref(path)
        if parsed:
            archive_path, member = parsed
            try:
                with open_member(archive_path, member) as tmp:
                    tmp_doc = load_document(tmp, settings)
                tmp_doc.path = path
                tmp_doc.title = tmp_doc.title or Path(member).name
                return tmp_doc
            except Exception as e:
                doc = Document(path=path, format="text")
                doc.markdown = f"# Archive Error\n\n```\n{e}\n```\n"
                doc.plain_text = str(e)
                doc.title = Path(path).name
                return doc

    # ── Opening an archive directly → build member index ─────────────────
    if is_archive(path) and not path.lower().endswith((".epub", ".daisy")):
        try:
            members = list_members(path)
        except Exception:
            members = []
        md = build_index_markdown(path, members)
        doc = Document(path=path, format="archive")
        doc.markdown = md
        doc.plain_text = md
        doc.title = Path(path).name
        _record_archive_members(path, members, settings)
        return doc

    doc = Document(path=path)
    fmt = _detect_format(path)
    doc.format = fmt

    # Check document cache before doing any parsing work
    if (
        settings.get("document_cache", True)
        and not path.startswith(("http://", "https://"))
        and fmt not in ("url",)
    ):
        fp = _settings_fingerprint(settings)
        cached = _cache_load(path, fp)
        if cached:
            doc.markdown = cached.get("markdown", "")
            doc.plain_text = cached.get("plain_text", "")
            doc.title = cached.get("title", Path(path).name)
            doc.format = cached.get("format", fmt)
            doc.metadata = cached.get("metadata", {})
            return doc

    # Dispatch table covers all registered formats; the else-branch below
    # is a last-resort Pandoc attempt for any extension we don't recognize.

    md: str = ""
    # Pandoc-first: when Pandoc is present and enabled, it imports the formats it
    # handles well (offices, markup, and the Pandoc-only types) in preference to
    # the native loader; star falls back to the native loader if Pandoc fails.
    if (
        settings.get("prefer_pandoc", True)
        and _pandoc_available()
        and _pandoc_handles(fmt)
    ):
        _pm = _load_pandoc_first(path)
        if _pm and _pm.strip():
            md = _pm

    if md:
        pass  # Pandoc produced the document; skip the native loaders
    elif fmt == "url":
        doc.title = path
        md = _load_url(path)
    elif fmt in ("text",):
        md = _load_plain_text(path)
    elif fmt == "pandoc":
        md = (
            f"# {Path(path).name}\n\n"
            "This format requires **Pandoc**, which isn't available "
            "(or `prefer_pandoc` is disabled).\n\n"
            "Install it from https://pandoc.org/ (or `pip install pypandoc`) "
            "and reopen the file.\n"
        )
    elif fmt in ("markdown", "rmarkdown"):
        md = _load_rmarkdown(path) if fmt == "rmarkdown" else _load_markdown(path)
    elif fmt == "html":
        md = _load_html(path)
    elif fmt == "epub":
        md = _load_epub(path)
    elif fmt in ("daisy", "xml") and path.lower().endswith(".xml"):
        md = _load_dtbook(path)
    elif fmt == "csv":
        md = _load_csv_tsv(path, ",")
    elif fmt == "tsv":
        md = _load_csv_tsv(path, "\t")
    elif fmt == "xlsx":
        md = _load_xlsx(path)
    elif fmt == "pptx":
        md = _load_pptx(path)
    elif fmt == "doc":
        md = _load_doc(path)
    elif fmt == "docx":
        md = _load_docx(path)
    elif fmt == "rst":
        md = _load_rst(path)
    elif fmt == "mediawiki":
        md = _load_mediawiki(path)
    elif fmt == "asciidoc":
        md = _load_asciidoc(path)
    elif fmt == "textile":
        md = _load_textile(path)
    elif fmt == "creole":
        md = _load_creole(path)
    elif fmt == "odt":
        md = _load_odt_v2(path)
    elif fmt == "pdf":
        md = _load_pdf(
            path,
            reconstruct=str(settings.get("pdf_reading_order", "reconstruct")) != "raw",
        )
    elif fmt == "image":
        md = _load_image_ocr(path)
    elif fmt == "r":
        md = _load_r_code(path)
    elif fmt == "notebook":
        md = _load_notebook(path)
    elif fmt == "latex":
        md = _load_latex(path)
    elif fmt == "orgmode":
        md = _load_orgmode(path)
    elif fmt in ("python", "javascript", "rust", "c"):
        lang_map = {
            "python": "python",
            "javascript": "javascript",
            "rust": "rust",
            "c": "c",
        }
        lang = lang_map.get(fmt, "")
        try:
            src = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            src = str(e)
        md = f"# {Path(path).name}\n\n```{lang}\n{src}\n```\n"
    else:
        # Try Pandoc
        pandoc_md = _load_via_pandoc(path)
        if pandoc_md:
            md = pandoc_md
        else:
            md = _load_plain_text(path)

    # Extract title from first heading if not set
    if not doc.title:
        m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
        doc.title = m.group(1).strip() if m else Path(path).name if path else APP_TITLE

    # Apply footnote processing to markdown before stripping
    footnote_mode = str(settings.get("footnote_mode", "inline"))
    if footnote_mode != "inline":  # "inline" is already the default behavior
        md = _process_footnotes(md, mode=footnote_mode)

    doc.markdown = md
    doc.plain_text = _strip_markdown_for_tts(
        md,
        skip_code=settings["tts_skip_code"],
        table_mode=str(settings.get("table_reading_mode", "structured")),
    )

    # Extract EPUB chapter list (only for epub format)
    if fmt == "epub" and settings.get("epub_show_chapters", True):
        try:
            raw_chapters = _epub_extract_chapters(path)
            # Map hrefs to word indices via word map (built later); store titles+hrefs for now
            doc.chapters = [(t, h, 0) for t, h in raw_chapters]
        except Exception:
            doc.chapters = []

    # Cache the result
    if (
        settings.get("document_cache", True)
        and not path.startswith(("http://", "https://"))
        and len(doc.plain_text) > 1024
    ):
        fp = _settings_fingerprint(settings)
        try:
            _cache_save(
                path,
                {
                    "markdown": doc.markdown,
                    "plain_text": doc.plain_text,
                    "title": doc.title,
                    "format": doc.format,
                    "metadata": doc.metadata,
                },
                fp,
            )
        except Exception:
            pass

    return doc


# =============================================================================
# New document loaders and utilities
# =============================================================================

# ---------------------------------------------------------------------------
# PowerPoint (.pptx) loader
# ---------------------------------------------------------------------------


def _load_pptx(path: str) -> str:
    """Load a PowerPoint .pptx file as Markdown.

    Each slide becomes a section with its title as a heading.
    Body text, bullet points, and speaker notes are included.
    Requires: pip install python-pptx
    """
    if not _PPTX:
        return (
            "Could not load PowerPoint file: python-pptx is not installed.\n"
            "Install it with: pip install python-pptx"
        )

    prs = _load_pptx().Presentation(path)
    sections = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        title_text = ""
        body_parts = []

        for shape in slide.shapes:
            # Images (MSO_SHAPE_TYPE.PICTURE == 13)
            if shape.shape_type == 13:
                alt = getattr(shape, "name", f"slide {slide_num} image")
                body_parts.append(f"[Image: {alt}]")
                continue

            # Tables
            if hasattr(shape, "table"):
                tbl = shape.table
                md_rows = []
                for row_idx, row in enumerate(tbl.rows):
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    md_rows.append("| " + " | ".join(cells) + " |")
                    if row_idx == 0:
                        md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
                body_parts.append("\n".join(md_rows))
                continue

            if not shape.has_text_frame:
                continue

            is_title = (
                hasattr(shape, "placeholder_format")
                and shape.placeholder_format is not None
                and shape.placeholder_format.idx == 0
            )

            if is_title:
                title_text = shape.text_frame.text.strip()
            else:
                for para in shape.text_frame.paragraphs:
                    txt = para.text.strip()
                    if not txt:
                        continue
                    indent = "  " * para.level if para.level else ""
                    body_parts.append(f"{indent}- {txt}")

        heading = (
            f"## Slide {slide_num}: {title_text}"
            if title_text
            else f"## Slide {slide_num}"
        )
        slide_md = [heading]
        if body_parts:
            slide_md.append("")
            slide_md.extend(body_parts)

        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()
            if notes_text:
                slide_md.append("")
                slide_md.append(f"> Note: {notes_text}")

        sections.append("\n".join(slide_md))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Improved ODT loader
# ---------------------------------------------------------------------------


def _load_odt_v2(path: str) -> str:
    """Load an ODT (OpenDocument Text) file to Markdown.

    Uses odfpy if available for full fidelity; otherwise falls back to
    Pandoc (if installed) or raw XML extraction.
    Supports headings, paragraphs, lists, tables, footnotes.
    """
    if _ODT:
        return _load_odt_via_odfpy(path)

    # Pandoc fallback (prefer the bundled binary, then PATH)
    try:
        import subprocess

        result = subprocess.run(
            [_PANDOC_BIN or "pandoc", "-f", "odt", "-t", "markdown", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, OSError):
        pass

    return _load_odt_raw_xml(path)


def _load_odt_via_odfpy(path: str) -> str:
    """Parse an ODT document via the odfpy library, converting to Markdown."""
    from odf.element import Element  # type: ignore  # noqa: F401
    from odf.opendocument import load as odf_load  # type: ignore

    doc = odf_load(path)
    lines: list = []
    footnotes: dict = {}
    fn_counter = [0]

    def get_text(elem) -> str:
        if not hasattr(elem, "childNodes"):
            return getattr(elem, "data", "")
        tag = elem.qname[1] if hasattr(elem, "qname") else ""
        if tag == "s":
            return " " * int(elem.getAttribute("text:c") or 1)
        if tag == "tab":
            return "\t"
        if tag == "line-break":
            return "\n"
        return "".join(get_text(c) for c in elem.childNodes)

    def walk(node, list_depth: int = 0):
        if not hasattr(node, "qname"):
            return
        tag = node.qname[1]

        if tag == "h":
            level = int(node.getAttribute("text:outline-level") or 1)
            lines.append("#" * level + " " + get_text(node).strip())
            lines.append("")

        elif tag == "p":
            txt = get_text(node).strip()
            if txt:
                if list_depth:
                    lines.append("  " * (list_depth - 1) + "- " + txt)
                else:
                    lines.append(txt)
                    lines.append("")

        elif tag == "list":
            for child in node.childNodes:
                if hasattr(child, "qname") and child.qname[1] == "list-item":
                    for sub in child.childNodes:
                        walk(sub, list_depth + 1)

        elif tag == "table":
            _odt_table_to_md(node, lines, get_text)

        elif tag == "note":
            fn_counter[0] += 1
            label = str(fn_counter[0])
            body_text = ""
            for child in node.childNodes:
                if hasattr(child, "qname") and child.qname[1] == "note-body":
                    body_text = get_text(child).strip()
            footnotes[label] = body_text
            if lines:
                lines[-1] = lines[-1] + f"[^{label}]"

        else:
            for child in node.childNodes:
                walk(child, list_depth)

    for child in doc.text.childNodes:
        walk(child)

    if footnotes:
        lines += ["", "## Footnotes", ""]
        for label, note_text in footnotes.items():
            lines.append(f"[^{label}]: {note_text}")

    return "\n".join(lines)


def _odt_table_to_md(table_node, lines: list, get_text_fn) -> None:
    """Convert an ODF table element to Markdown table rows, appended to lines."""
    rows = []
    for child in table_node.childNodes:
        if not hasattr(child, "qname"):
            continue
        if child.qname[1] == "table-row":
            cells = []
            for cell in child.childNodes:
                if hasattr(cell, "qname") and cell.qname[1] in (
                    "table-cell",
                    "covered-table-cell",
                ):
                    cells.append(get_text_fn(cell).strip().replace("\n", " "))
            rows.append(cells)

    if not rows:
        return
    col_count = max(len(r) for r in rows)
    lines.append("")
    for i, row in enumerate(rows):
        padded = row + [""] * (col_count - len(row))
        lines.append("| " + " | ".join(padded) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * col_count) + " |")
    lines.append("")


def _load_odt_raw_xml(path: str) -> str:
    """Fallback ODT reader: extract text via raw ZIP + regex XML stripping."""
    import zipfile

    try:
        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("content.xml").decode("utf-8", errors="replace")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"[Could not read ODT file: {exc}]"

    text = re.sub(
        r"<text:h[^>]*>(.*?)</text:h[^>]*>", r"\n\n\1\n", content, flags=re.DOTALL
    )
    text = re.sub(r"<text:p[^>]*/>", "\n", text)
    text = re.sub(r"<text:p[^>]*>(.*?)</text:p>", r"\1\n", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Markdown footnote processing
# ---------------------------------------------------------------------------


def _process_footnotes(md: str, mode: str = "inline") -> str:
    """Handle Pandoc/GitHub-style Markdown footnotes for TTS.

    mode="inline":   insert footnote text at point of reference
    mode="deferred": collect footnotes and append at end of document
    mode="skip":     remove all footnote markers and content silently

    Supported syntax:
      Definitions:  [^1]: footnote text here
      References:   word[^1]  or  word[^label]
      Multi-line:   [^label]: First line
                        continuation
    """
    definitions: dict = {}

    def _strip_definitions(text: str) -> str:
        def _replace(m):
            definitions[m.group(1)] = m.group(2).strip()
            return ""

        return re.sub(r"^\[\^([^\]]+)\]:\s*(.+)$", _replace, text, flags=re.MULTILINE)

    md = _strip_definitions(md)

    if mode == "skip":
        return re.sub(r"\[\^[^\]]+\]", "", md).strip()

    if mode == "inline":

        def _inline_sub(m):
            note = definitions.get(m.group(1), "")
            return f" (footnote: {note})" if note else ""

        return re.sub(r"\[\^([^\]]+)\]", _inline_sub, md).strip()

    if mode == "deferred":
        md = re.sub(r"\[\^[^\]]+\]", "", md).strip()
        if definitions:
            md += "\n\n## Footnotes\n\n"
            for label, text in definitions.items():
                md += f"[^{label}]: {text}\n"
        return md

    return md


# ---------------------------------------------------------------------------
# EPUB chapter extraction
# ---------------------------------------------------------------------------


def _epub_extract_chapters(path: str) -> "List[Tuple[str, str]]":
    """Extract chapter/navigation data from an EPUB file.

    Reads the NCX (EPUB 2) or NAV document (EPUB 3) to return an ordered
    list of (chapter_title, href) pairs representing the book\'s structure.
    Returns an empty list if the EPUB has no navigation data.
    """
    import zipfile
    from xml.etree import ElementTree as ET

    OPF = "http://www.idpf.org/2007/opf"
    NCX = "http://www.daisy.org/z3986/2005/ncx/"
    EPUB = "http://www.idpf.org/2007/ops"
    XHTML = "http://www.w3.org/1999/xhtml"

    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile:
        return []

    with zf:
        try:
            container = zf.read("META-INF/container.xml")
        except KeyError:
            return []

        cont_root = ET.fromstring(container)
        rf = cont_root.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        )
        if rf is None:
            return []
        opf_path = rf.get("full-path", "")
        opf_dir = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""

        try:
            opf_tree = ET.fromstring(zf.read(opf_path))
        except (KeyError, ET.ParseError):
            return []

        # Build manifest: id -> (href, media-type, properties)
        manifest = {
            item.get("id", ""): (
                item.get("href", ""),
                item.get("media-type", ""),
                item.get("properties", ""),
            )
            for item in opf_tree.findall(f"{{{OPF}}}manifest/{{{OPF}}}item")
        }

        chapters: list = []

        # --- EPUB3 NAV ---
        nav_id = next(
            (k for k, (h, t, p) in manifest.items() if "nav" in p.split()), None
        )
        if nav_id:
            try:
                nav_tree = ET.fromstring(zf.read(opf_dir + manifest[nav_id][0]))
                for nav_elem in nav_tree.iter(f"{{{XHTML}}}nav"):
                    if "toc" in nav_elem.get(f"{{{EPUB}}}type", ""):
                        for li in nav_elem.iter(f"{{{XHTML}}}li"):
                            a = li.find(f"{{{XHTML}}}a")
                            if a is not None:
                                title = "".join(a.itertext()).strip()
                                href = a.get("href", "").split("#")[0]
                                if title and href:
                                    chapters.append((title, opf_dir + href))
                        break
            except (KeyError, ET.ParseError):
                pass

        # --- NCX (EPUB2 fallback) ---
        if not chapters:
            spine = opf_tree.find(f"{{{OPF}}}spine")
            toc_id = (spine.get("toc", "") if spine is not None else "") or next(
                (
                    k
                    for k, (h, t, p) in manifest.items()
                    if t == "application/x-dtbncx+xml"
                ),
                "",
            )
            if toc_id and toc_id in manifest:
                try:
                    ncx_tree = ET.fromstring(zf.read(opf_dir + manifest[toc_id][0]))
                    for np in ncx_tree.iter(f"{{{NCX}}}navPoint"):
                        label = np.find(f"{{{NCX}}}navLabel/{{{NCX}}}text")
                        content = np.find(f"{{{NCX}}}content")
                        if label is not None and content is not None:
                            title = (label.text or "").strip()
                            href = content.get("src", "").split("#")[0]
                            if title and href:
                                chapters.append((title, opf_dir + href))
                except (KeyError, ET.ParseError):
                    pass

    # Deduplicate by href, preserving first occurrence
    seen: set = set()
    unique: list = []
    for title, href in chapters:
        if href not in seen:
            seen.add(href)
            unique.append((title, href))
    return unique


# ---------------------------------------------------------------------------
# Archive helpers (called from load_document)
# ---------------------------------------------------------------------------


def _record_archive_members(archive_path: str, members: List[str], settings: Any) -> None:
    """Register archive members in the library under their ref keys."""
    from .archive import make_ref
    try:
        library: Dict[str, Any] = settings.get("library") or {}
        changed = False
        for member in members:
            ref = make_ref(archive_path, member)
            if ref not in library:
                library[ref] = {
                    "title": Path(member).name,
                    "format": _detect_format(member),
                    "added": str(Path(archive_path).stat().st_mtime),
                    "last_opened": "",
                    "source": f"archive:{archive_path}",
                }
                changed = True
        if changed:
            settings.set("library", library)
    except Exception:
        pass
