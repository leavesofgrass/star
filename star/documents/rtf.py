"""Rich Text Format (``.rtf``) and Windows Write (``.wri``) → Markdown.

The RTF reader is a small self-contained tokenizer/state machine (no third
party package): it walks the ``{…}`` group tree, honours the document codepage
for ``\\'xx`` escapes and ``\\uN`` Unicode escapes (with the ``\\ucN``
skip-count), drops the non-text destinations (font/colour tables, pictures,
objects, headers/footers, field instructions …) and turns paragraphs, headings
(``heading N`` styles or ``\\outlinelevelN``), bold/italic runs, bullets and
numbered lists, tables (``\\trowd``/``\\cell``/``\\row``) and page breaks into
Markdown.  Pandoc reads RTF as well and is preferred when installed
(``prefer_pandoc``); this is the zero-dependency path.

``.wri`` files are nearly always RTF or plain text saved under the old Write
name; the genuine Windows 3.x Write binary (``BE 31`` / ``BE 32`` magic) is read
by taking the text run its header describes.  Mirrors Paperback's routing.
"""
from .._runtime import *  # noqa: F401,F403

# Destinations whose content is never document text.  ``\*`` marks any other
# ignorable destination and is handled generically.
_SKIP_DESTINATIONS = frozenset(
    {
        "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "objdata",
        "header", "footer", "headerl", "headerr", "headerf", "footerl", "footerr",
        "footerf", "fldinst", "xe", "tc", "txe", "listtable", "listoverridetable",
        "rsidtbl", "generator", "datafield", "themedata", "colorschememapping",
        "latentstyles", "pgptbl", "xmlnstbl", "userprops", "docvar", "mmathPr",
        "revtbl", "template", "wgrffmtfilter", "background", "shp", "shpinst",
        "shprslt", "nonshppict", "blipuid", "sp", "sn", "sv", "svb", "protusertbl",
        "operator", "author", "company", "title", "subject", "keywords", "doccomm",
        "creatim", "revtim", "printim", "buptim", "version", "vern", "nofpages",
        "nofwords", "nofchars", "nofcharsws", "category", "manager", "hlinkbase",
        "atnid", "atnauthor", "atndate", "annotation", "bkmkstart", "bkmkend",
        "fldtype", "datafield", "passwordhash", "upr", "ud", "mmath", "factoidname",
    }
)

# ``\\control`` symbols that stand for a character.
_SYMBOLS: Dict[str, str] = {
    "bullet": "\u2022", "endash": "\u2013", "emdash": "\u2014",
    "lquote": "\u2018", "rquote": "\u2019", "ldblquote": "\u201c",
    "rdblquote": "\u201d", "enspace": "\u2002", "emspace": "\u2003",
    "qmspace": "\u2005", "~": "\u00a0", "_": "\u2011", "-": "",
    "{": "{", "}": "}", "\\": "\\", "zwj": "", "zwnj": "", "zwbo": "", "zwnbo": "",
    "ltrmark": "", "rtlmark": "", "chdate": "", "chtime": "", "chpgn": "",
    "lbr": "\n",
}

_TOKEN_RE = re.compile(
    r"\\([a-zA-Z]+)(-?\d+)? ?"     # control word (+ optional numeric arg, optional delimiter space)
    r"|\\'([0-9a-fA-F]{2})"          # hex escape
    r"|\\([^a-zA-Z])"                # control symbol
    r"|([{}])"                       # group delimiters
    r"|([^\\{}]+)",                  # plain text run
    re.S,
)

_CODEPAGES: Dict[int, str] = {
    437: "cp437", 708: "cp720", 720: "cp720", 850: "cp850", 852: "cp852",
    855: "cp855", 857: "cp857", 860: "cp860", 861: "cp861", 862: "cp862",
    863: "cp863", 864: "cp864", 865: "cp865", 866: "cp866", 869: "cp869",
    874: "cp874", 932: "cp932", 936: "gbk", 949: "cp949", 950: "cp950",
    1250: "cp1250", 1251: "cp1251", 1252: "cp1252", 1253: "cp1253",
    1254: "cp1254", 1255: "cp1255", 1256: "cp1256", 1257: "cp1257",
    1258: "cp1258", 10000: "mac_roman", 65001: "utf-8",
}


def looks_like_rtf(data: bytes) -> bool:
    """True when *data* opens with the ``{\\rtf`` signature (BOM/whitespace allowed)."""
    head = data[:16].lstrip(b"\xef\xbb\xbf \t\r\n")
    return head[:5].lower() == b"{\\rtf"


class _Run:
    __slots__ = ("text", "bold", "italic")

    def __init__(self, text: str, bold: bool, italic: bool) -> None:
        self.text, self.bold, self.italic = text, bold, italic


class _Group:
    __slots__ = ("skip", "uc", "bold", "italic", "dest", "listtext", "field_result")

    def __init__(self, parent: "Optional[_Group]" = None) -> None:
        if parent is None:
            self.skip = False
            self.uc = 1
            self.bold = False
            self.italic = False
            self.dest = ""
            self.listtext = False
            self.field_result = False
        else:
            self.skip = parent.skip
            self.uc = parent.uc
            self.bold = parent.bold
            self.italic = parent.italic
            self.dest = ""
            self.listtext = parent.listtext
            self.field_result = parent.field_result


class _RtfToMarkdown:
    """One-pass RTF → Markdown converter (see the module docstring)."""

    def __init__(self) -> None:
        self.codepage = "cp1252"
        self.out: List[str] = []
        self.runs: List[_Run] = []          # current paragraph's runs
        self.list_prefix = ""               # from \listtext / \pntext
        self.heading = 0                    # 1..6 for the current paragraph
        self.in_table = False
        self.cells: List[str] = []
        self.rows: List[List[str]] = []
        self.styles: Dict[int, str] = {}    # \sN → style name (from stylesheet)
        self._skip_chars = 0                # \uN fallback chars still to drop
        self._stack: List[_Group] = [_Group()]
        self._pending_bytes = bytearray()   # multi-byte \'xx sequences (CJK codepages)

    # ── helpers ──────────────────────────────────────────────────────────

    @property
    def g(self) -> _Group:
        return self._stack[-1]

    def _flush_bytes(self) -> None:
        if self._pending_bytes:
            try:
                s = self._pending_bytes.decode(self.codepage, errors="replace")
            except LookupError:
                s = self._pending_bytes.decode("cp1252", errors="replace")
            self._pending_bytes = bytearray()
            self._emit(s)

    def _emit(self, text: str) -> None:
        if not text:
            return
        if self._skip_chars:
            n = min(self._skip_chars, len(text))
            self._skip_chars -= n
            text = text[n:]
            if not text:
                return
        g = self.g
        if g.skip:
            return
        if g.listtext:
            self.list_prefix += text
            return
        if self.runs and self.runs[-1].bold == g.bold and self.runs[-1].italic == g.italic:
            self.runs[-1].text += text
        else:
            self.runs.append(_Run(text, g.bold, g.italic))

    def _para_text(self) -> str:
        parts: List[str] = []
        for r in self.runs:
            t = r.text
            if not t:
                continue
            core = t.strip()
            if not core:
                parts.append(t)
                continue
            lead = t[: len(t) - len(t.lstrip())]
            trail = t[len(t.rstrip()):]
            if r.bold and r.italic:
                core = f"***{core}***"
            elif r.bold:
                core = f"**{core}**"
            elif r.italic:
                core = f"*{core}*"
            parts.append(lead + core + trail)
        text = "".join(parts)
        # Collapse runs of spaces but keep intentional line breaks (\line).
        text = re.sub(r"[ \t]+", " ", text)
        text = "\n".join(ln.strip() for ln in text.split("\n"))
        return text.strip()

    def _end_paragraph(self) -> None:
        text = self._para_text()
        prefix = self.list_prefix.strip()
        self.runs = []
        self.list_prefix = ""
        heading, self.heading = self.heading, 0
        if self.in_table:
            # Paragraph breaks inside a cell become a space within the cell text.
            if text:
                self.cells.append(text)
            return
        if self.rows:
            self._flush_table()  # prose after a table: emit the table first
        if not text and not prefix:
            return
        if prefix:
            if re.match(r"^\(?[0-9a-zA-Z]{1,4}[.)]?$", prefix) and prefix[-1] in ".)":
                text = f"{prefix} {text}" if prefix[-1] == "." and prefix[:-1].isdigit() else f"- {text}"
            else:
                text = f"- {text}"
        elif heading:
            text = f"{'#' * heading} {text}"
        if text:
            is_item = text.startswith("- ") or re.match(r"^\d+\. ", text) is not None
            if is_item and len(self.out) >= 2 and self.out[-1] == "" and (
                self.out[-2].startswith("- ") or re.match(r"^\d+\. ", self.out[-2])
            ):
                self.out.pop()  # keep list items tight
            self.out += [text, ""]

    def _end_cell(self) -> None:
        text = self._para_text()
        self.runs = []
        self.list_prefix = ""
        cell = " ".join(self.cells + ([text] if text else [])).strip()
        self.cells = []
        if not self.rows:
            self.rows.append([])
        self.rows[-1].append(cell.replace("|", "\\|").replace("\n", " "))

    def _end_row(self) -> None:
        if self.cells or self.runs:
            self._end_cell()
        if self.rows and not self.rows[-1]:
            self.rows.pop()
        if self.rows:
            self.rows.append([])
        self.in_table = False

    def _flush_table(self) -> None:
        rows = [r for r in self.rows if r]
        self.rows = []
        if not rows:
            return
        nc = max(len(r) for r in rows)
        self.out.append("| " + " | ".join((rows[0] + [""] * nc)[:nc]) + " |")
        self.out.append("|" + "|".join([" --- "] * nc) + "|")
        for r in rows[1:]:
            self.out.append("| " + " | ".join((r + [""] * nc)[:nc]) + " |")
        self.out.append("")

    # ── stylesheet ───────────────────────────────────────────────────────

    def _parse_stylesheet(self, body: str) -> None:
        """Map ``\\sN`` numbers to their names ("heading 1", …)."""
        depth = 0
        cur_num: Optional[int] = None
        cur_name: List[str] = []
        for m in _TOKEN_RE.finditer(body):
            word, arg, hexc, sym, brace, text = m.groups()
            if brace == "{":
                depth += 1
                if depth == 1:
                    cur_num, cur_name = None, []
            elif brace == "}":
                if depth == 1 and cur_num is not None:
                    name = "".join(cur_name).strip().rstrip(";").strip().lower()
                    if name:
                        self.styles[cur_num] = name
                depth -= 1
                if depth < 0:
                    return
            elif word:
                if word == "s" and depth == 1 and arg is not None:
                    cur_num = int(arg)
                elif word in ("cs", "ds", "ts") and depth == 1:
                    cur_num = None
            elif text and depth == 1:
                cur_name.append(text)

    # ── main loop ────────────────────────────────────────────────────────

    def feed(self, src: str) -> str:
        pos = 0
        n = len(src)
        while pos < n:
            m = _TOKEN_RE.match(src, pos)
            if not m:
                pos += 1
                continue
            pos = m.end()
            word, arg, hexc, sym, brace, text = m.groups()
            if brace == "{":
                self._flush_bytes()
                self._stack.append(_Group(self.g))
                # Peek: "{\*\dest" or "{\dest" for a skip destination.
                peek = src[pos:pos + 40]
                pm = re.match(r"\\\*\\([a-zA-Z]+)|\\([a-zA-Z]+)", peek)
                if pm:
                    dest = pm.group(1) or pm.group(2)
                    starred = pm.group(1) is not None
                    if dest == "stylesheet":
                        end = self._group_end(src, pos)
                        self._parse_stylesheet(src[pos:end])
                        self._stack.pop()
                        pos = end + 1
                        continue
                    if dest in ("listtext", "pntext"):
                        self.g.listtext = True
                        self.list_prefix = ""
                    elif dest == "fldrslt":
                        self.g.field_result = True
                    elif dest in ("fldinst",):
                        self.g.skip = True
                    elif dest == "footnote":
                        # Keep footnote text, marked inline for the reader.
                        self._emit(" (footnote: ")
                        self.g.dest = "footnote"
                    elif dest in _SKIP_DESTINATIONS:
                        self.g.skip = True
                    elif starred:
                        self.g.skip = True
                continue
            if brace == "}":
                self._flush_bytes()
                if len(self._stack) > 1:
                    g = self._stack.pop()
                    if g.dest == "footnote" and not g.skip:
                        self._emit(")")
                continue
            if hexc is not None:
                if self._skip_chars:
                    self._skip_chars -= 1
                    continue
                self._pending_bytes.append(int(hexc, 16))
                continue
            if sym is not None:
                self._flush_bytes()
                if sym == "\n" or sym == "\r":
                    self._end_paragraph()
                elif sym == "*":
                    pass  # handled at group open
                elif sym == "|" or sym == ":":
                    pass
                elif sym in _SYMBOLS:
                    self._emit(_SYMBOLS[sym])
                else:
                    self._emit(sym)
                continue
            if word is not None:
                self._flush_bytes()
                self._control(word, arg)
                continue
            if text is not None:
                self._flush_bytes()
                t = text.replace("\r", "").replace("\n", "")
                if t:
                    self._emit(t)
        self._flush_bytes()
        self._end_paragraph()
        if self.rows:
            self._flush_table()
        md = "\n".join(self.out)
        return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"

    @staticmethod
    def _group_end(src: str, pos: int) -> int:
        depth = 1
        i = pos
        n = len(src)
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return n

    def _control(self, word: str, arg: Optional[str]) -> None:
        g = self.g
        num = int(arg) if arg is not None else None
        if word == "ansicpg" and num is not None:
            self.codepage = _CODEPAGES.get(num, f"cp{num}")
        elif word == "mac":
            self.codepage = "mac_roman"
        elif word == "pc":
            self.codepage = "cp437"
        elif word == "pca":
            self.codepage = "cp850"
        elif word == "uc":
            g.uc = num or 0
        elif word == "u" and num is not None:
            code = num if num >= 0 else num + 65536
            if 0 <= code < 0x110000:
                self._emit(chr(code))
            self._skip_chars = g.uc
        elif g.skip:
            return
        elif word == "par" or word == "sect":
            self._end_paragraph()
        elif word == "line":
            self._emit("\n")
        elif word == "tab":
            self._emit("\t")
        elif word == "page":
            self._end_paragraph()
            if self.rows:
                self._flush_table()
            self.out += ["---", ""]
        elif word == "pard":
            self.heading = 0  # resets paragraph formatting; character formatting stays
        elif word == "plain":
            g.bold = False
            g.italic = False
        elif word == "b":
            g.bold = num != 0
        elif word == "i":
            g.italic = num != 0
        elif word == "s" and num is not None:
            name = self.styles.get(num, "")
            hm = re.match(r"heading\s*(\d)", name)
            if hm:
                self.heading = max(1, min(6, int(hm.group(1))))
            elif name == "title":
                self.heading = 1
        elif word == "outlinelevel" and num is not None:
            self.heading = max(1, min(6, num + 1))
        elif word == "trowd":
            if not self.in_table and self.runs:
                self._end_paragraph()
            self.in_table = True
            if not self.rows:
                self.rows = [[]]
            elif self.rows[-1]:
                self.rows.append([])
        elif word == "intbl":
            if not self.in_table:
                self.in_table = True
                if not self.rows:
                    self.rows = [[]]
        elif word == "cell" or word == "nestcell":
            if self.in_table:
                self._end_cell()
            else:
                self._emit(" ")
        elif word == "row" or word == "nestrow":
            self._end_row()
        elif word == "pntext":
            g.listtext = True
        elif word in _SYMBOLS:
            self._emit(_SYMBOLS[word])
        elif word in ("ls", "ilvl", "pn", "pnlvlblt", "pnlvlbody"):
            pass
        elif word == "fldrslt":
            pass
        # every other control word is formatting we do not render


def _rtf_to_markdown(data: bytes) -> str:
    """Convert raw RTF bytes to Markdown (the file is 7-bit ASCII by design)."""
    src = data.decode("latin-1")
    # A table that is not followed by anything else still needs flushing when the
    # next paragraph starts — the converter handles that as rows accumulate.
    conv = _RtfToMarkdown()
    md = conv.feed(src)
    # Tables are emitted when a non-table paragraph arrives or at the end; make
    # sure a table immediately followed by prose renders in order.
    return md


def _load_rtf(path: str) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"
    if not looks_like_rtf(data):
        return data.decode("utf-8", errors="replace")
    try:
        md = _rtf_to_markdown(data)
    except Exception as e:  # noqa: BLE001
        return f"# RTF Error\n\n```\n{e}\n```\n"
    if not md.strip():
        return f"# {Path(path).stem}\n\n*(empty document)*\n"
    return md


# ── Windows Write ───────────────────────────────────────────────────────────

_WRITE_MAGIC = (0x31BE, 0x32BE)  # plain / with OLE objects (little-endian on disk)
_WRITE_TEXT_START = 128
_WRITE_FCMAC_OFFSET = 0x0E


def _write_binary_text(data: bytes) -> Optional[str]:
    """Text of a genuine Windows Write binary, or None when *data* is not one."""
    if len(data) < _WRITE_TEXT_START:
        return None
    magic = int.from_bytes(data[0:2], "little")
    if magic not in _WRITE_MAGIC:
        return None
    fc_mac = int.from_bytes(data[_WRITE_FCMAC_OFFSET:_WRITE_FCMAC_OFFSET + 4], "little")
    if fc_mac <= _WRITE_TEXT_START or fc_mac > len(data):
        return None
    raw = data[_WRITE_TEXT_START:fc_mac]
    text = raw.decode("cp1252", errors="replace")
    # Write ends paragraphs with CR LF and marks page breaks with form feed.
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n\n---\n\n")
    text = text.replace("\x00", "")
    paras = [p.strip() for p in text.split("\n")]
    return "\n\n".join(p for p in paras if p) + "\n"


def _load_wri(path: str) -> str:
    """Windows Write: RTF in disguise → RTF loader; Write binary → text run;
    anything else → plain text."""
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"
    if looks_like_rtf(data):
        return _load_rtf(path)
    text = _write_binary_text(data)
    if text is not None:
        return f"# {Path(path).stem}\n\n{text}"
    return data.decode("utf-8", errors="replace")
