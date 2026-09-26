"""Format detection and the load_document entry points."""
from .._runtime import *  # noqa: F401,F403
from ..cache import _cache_load, _cache_save
from ..settings import Settings
from ..stats import _settings_fingerprint
from ..ttstext import _strip_markdown_for_tts
from .ebook import _epub_extract_chapters, _load_dtbook, _load_epub
from .html import _load_html
from .misc import _load_image_ocr, _load_url, _process_footnotes, _record_archive_members
from .model import Document
from .audio import _load_audiobook_full
from .comics import _load_comic
from .daisy import _is_daisy_zip, _load_daisy_full
from .fb2 import _fb2_chapters, _load_fb2
from .manpage import _load_manpage, is_manual_page_name
from .mobi import _load_mobi_full
from .odf import _load_fodt, _load_odp
from .office import _load_csv_tsv, _load_doc, _load_docx, _load_odt_v2, _load_ppt, _load_pptx, _load_xlsx
from .ooxml import _ooxml_kind
from .rtf import _load_rtf, _load_wri
from .pandoc import _PANDOC_INPUT_EXTS, _load_pandoc_first, _load_via_pandoc, _pandoc_available, _pandoc_handles
from .pdf import _load_pdf
from .text_loaders import _load_asciidoc, _load_creole, _load_latex, _load_markdown, _load_mediawiki, _load_notebook, _load_orgmode, _load_plain_text, _load_r_code, _load_rmarkdown, _load_rst, _load_textile


#: Extension → internal format name.  The single source for both format
#: detection and :func:`supported_extensions` (the library scanner's filter).
_EXT_FORMAT_MAP: Dict[str, str] = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".mdown": "markdown",
        ".mdx": "markdown",
        ".mdwn": "markdown",
        ".mkd": "markdown",
        ".mkdn": "markdown",
        ".mkdown": "markdown",
        ".ronn": "markdown",
        ".txt": "text",
        ".text": "text",
        ".log": "text",
        ".html": "html",
        ".htm": "html",
        ".xhtml": "html",
        ".pdf": "pdf",
        ".docx": "docx",
        ".docm": "docx",  # macro-enabled Word — same package layout
        ".dotx": "docx",
        ".dotm": "docx",
        ".doc": "doc",
        ".dot": "doc",  # legacy Word template — same binary format
        ".pptx": "pptx",
        ".pptm": "pptx",  # macro-enabled PowerPoint — same package layout
        ".ppsx": "pptx",
        ".ppt": "ppt",  # legacy binary PowerPoint 97–2003 (OLE)
        ".pps": "ppt",
        ".odt": "odt",
        ".fodt": "fodt",
        ".odp": "odp",
        ".fodp": "odp",
        ".epub": "epub",
        ".fb2": "fb2",
        ".mobi": "mobi",
        ".prc": "mobi",
        ".azw": "mobi",
        ".azw3": "mobi",
        ".kf8": "mobi",
        ".chm": "chm",
        ".hlp": "winhelp",
        ".rtf": "rtf",
        ".wri": "wri",
        ".cbz": "comic",
        ".cbr": "comic",
        ".cb7": "comic",
        ".m4b": "audiobook",
        ".m4a": "audiobook",
        ".mp3": "audiobook",
        ".man": "man",
        ".roff": "man",
        ".gz": "gz",
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


#: Manual pages are named for their section (``ls.1``, ``printf.3.gz``); these
#: pseudo-extensions let the library scanner pick them up.
_MAN_SECTION_EXTS = frozenset({f".{i}" for i in range(1, 10)})


def _detect_format(path: str) -> str:
    """Detect document format from extension or magic bytes."""
    p = path.lower()
    if p.startswith(("http://", "https://", "ftp://")):
        return "url"
    name = Path(path).name.lower()
    if name == "ncc.html":
        return "daisy"  # a DAISY 2.02 book's master file, not an ordinary HTML page
    ext = Path(path).suffix.lower()
    if ext in _EXT_FORMAT_MAP:
        fmt = _EXT_FORMAT_MAP[ext]
        if fmt == "gz" and is_manual_page_name(path):
            return "man"
        return fmt
    if is_manual_page_name(path):
        return "man"
    if ext in _PANDOC_INPUT_EXTS:
        return "pandoc"
    return "text"


def supported_extensions() -> "frozenset[str]":
    """Lowercase file extensions (with dot) star can open as documents.

    The union of the native format map, the Pandoc-only input formats, and any
    extensions contributed by installed ``star.formats`` plugins.  Used by the
    library scanner to decide which files in a folder are documents.
    """
    exts = set(_EXT_FORMAT_MAP) | set(_PANDOC_INPUT_EXTS) | set(_MAN_SECTION_EXTS)
    try:
        from ..plugins import PluginRegistry

        exts |= set(getattr(PluginRegistry.get(), "_ext_map", {}))
    except Exception:  # noqa: BLE001 — plugin discovery must never break scanning
        pass
    return frozenset(exts)


def load_document(path: str, settings: Settings) -> Document:
    """Load any supported document format and return a Document object."""
    # ── Archive member ref: /abs/book.zip!inner/paper.pdf ─────────────────
    from ..archive import is_archive_ref, is_archive, parse_ref, list_members, open_member, build_index_markdown
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
    # A ``.zip`` is often a document in disguise (a DAISY/Bookshare download, a
    # renamed EPUB, DOCX or FB2, a folder of comic pages).  Sniff those first so
    # they open as the book they are rather than as a member index.
    zip_fmt = _sniff_zip(path) if path.lower().endswith(".zip") else ""
    if is_archive(path) and not zip_fmt and not path.lower().endswith((".epub", ".daisy")):
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
    fmt = zip_fmt or _detect_format(path)
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
    doc_from_handler: "Document | None" = None
    extra_chapters: "List[Tuple[str, str]]" = []
    extra_meta: "Dict[str, str]" = {}
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

    # Plugin dispatch: when Pandoc-first did not produce the document, prefer a
    # registered FormatHandler for this extension — this is what lets third-party
    # plugins add or override formats.  The legacy native branches below stay as
    # the fallback for every extension without a handler, and as a safety net if
    # entry-point discovery yields nothing (e.g. a frozen build), so behaviour is
    # unchanged when no extra plugins are installed.
    # A Pandoc-only format (no native loader) must still honor `prefer_pandoc`:
    # when it is off, skip the handler lookup so the format falls through to the
    # guidance note below rather than being converted by the registered
    # PandocHandler anyway (which would silently ignore the disabled preference).
    _handler = None
    _pandoc_only_disabled = fmt == "pandoc" and not settings.get("prefer_pandoc", True)
    # Files routed by *name* rather than suffix (ncc.html, ls.1, printf.3.gz, a
    # sniffed .zip) must not be claimed by the handler registered for their
    # suffix (HTML, Pandoc, …); their native branch below does the work.
    _name_routed = bool(zip_fmt) or fmt in ("daisy", "man", "gz") and Path(path).suffix.lower() not in (".daisy", ".opf", ".ncx", ".man", ".roff")
    if not md and not _pandoc_only_disabled and not _name_routed:
        from ..plugins import PluginRegistry
        _handler = PluginRegistry.get().handler_for(Path(path))

    if md:
        pass  # Pandoc produced the document; skip the native loaders
    elif _handler is not None:
        doc_from_handler = _handler.load(path, settings=settings)
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
    elif fmt == "daisy":
        md, extra_chapters, extra_meta = _load_daisy_full(path)
    elif fmt == "xml":
        md = _load_dtbook(path)
    elif fmt == "fb2":
        md = _load_fb2(path)
        extra_chapters = _fb2_chapters(path)
    elif fmt == "rtf":
        md = _load_rtf(path)
    elif fmt == "wri":
        md = _load_wri(path)
    elif fmt == "odp":
        md = _load_odp(path)
    elif fmt == "fodt":
        md = _load_fodt(path)
    elif fmt == "ppt":
        md = _load_ppt(path)
    elif fmt == "comic":
        md = _load_comic(path, lang=str(settings.get("ocr_lang", "eng") or "eng"))
    elif fmt == "mobi":
        md, extra_meta = _load_mobi_full(path)
    elif fmt == "audiobook":
        md, extra_chapters, extra_meta = _load_audiobook_full(path)
    elif fmt == "chm":
        from .chm import _load_chm_full
        md, extra_chapters, extra_meta = _load_chm_full(path)
    elif fmt == "winhelp":
        from .winhelp import _load_winhelp_full
        md, extra_chapters, extra_meta = _load_winhelp_full(path)
    elif fmt == "man":
        md = _load_manpage(path)
    elif fmt == "gz":
        inner = _load_gz(path, settings)
        if inner is not None:
            return inner
        md = _load_manpage(path)
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
            ocr_lang=str(settings.get("ocr_lang", "eng") or "eng"),
        )
    elif fmt == "image":
        md = _load_image_ocr(path, lang=str(settings.get("ocr_lang", "eng") or "eng"))
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

    if doc_from_handler is not None:
        # A plugin FormatHandler returned a complete Document — title, footnote
        # processing, plain-text, and any chapter list are already applied (see
        # _document_from_markdown and the handler classes).  Adopt its fields,
        # keeping the detected `fmt` and original `path` already set on `doc`.
        doc.markdown = doc_from_handler.markdown
        doc.plain_text = doc_from_handler.plain_text
        doc.title = doc.title or doc_from_handler.title
        if doc_from_handler.chapters:
            doc.chapters = doc_from_handler.chapters
        if doc_from_handler.metadata:
            doc.metadata = doc_from_handler.metadata
    else:
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
        elif extra_chapters and settings.get("epub_show_chapters", True):
            doc.chapters = [(t, h, 0) for t, h in extra_chapters]
        if extra_meta:
            doc.metadata = {**extra_meta, **(doc.metadata or {})}
            if extra_meta.get("title") and (not doc.title or doc.title == Path(path).name):
                doc.title = extra_meta["title"]
    if doc.chapters:
        _resolve_chapter_words(doc)

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


def _sniff_zip(path: str) -> str:
    """Format of a ``.zip`` that is really a document, or ``""`` for a plain archive.

    Checks the EPUB ``mimetype`` entry, an Office Open XML package, a DAISY
    book (``ncc.html`` / OPF / DTBook), a single ``.fb2`` member, and an
    image-only archive (a comic without its ``.cbz`` name).
    """
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            lower = [n.lower() for n in names]
            if "mimetype" in lower:
                try:
                    if b"epub" in zf.read(names[lower.index("mimetype")])[:64]:
                        return "epub"
                except Exception:  # noqa: BLE001
                    pass
            if "meta-inf/container.xml" in lower and any(n.endswith(".opf") for n in lower):
                return "epub"
    except Exception:  # noqa: BLE001
        return ""
    kind = _ooxml_kind(path)
    if kind == "word":
        return "docx"
    if kind == "ppt":
        return "pptx"
    if kind == "xl":
        return "xlsx"
    if _is_daisy_zip(path):
        return "daisy"
    fb2 = [n for n in lower if n.endswith(".fb2")]
    if len(fb2) == 1 and len(names) <= 3:
        return "fb2"
    from .comics import _is_page
    docs = [n for n in names if not n.rsplit("/", 1)[-1].startswith(".") and "__MACOSX" not in n]
    if docs and all(_is_page(n) or n.lower().endswith((".xml", ".txt", ".nfo")) for n in docs) \
            and any(_is_page(n) for n in docs):
        return "comic"
    return ""


def _load_gz(path: str, settings: Settings) -> "Document | None":
    """Open a gzipped document (``paper.txt.gz``, ``page.html.gz`` …) by
    unpacking it to a temp file named for the inner extension and loading that.
    Returns None when the inner name has no recognised extension (the caller
    then treats it as a manual page / plain text)."""
    import gzip

    inner = Path(Path(path).stem)
    if not inner.suffix or inner.suffix.lower() == ".tar":
        return None
    if _detect_format(str(inner)) in ("text", "gz") and inner.suffix.lower() not in (".txt", ".text", ".log"):
        return None
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=inner.suffix)
    os.close(tmp_fd)
    try:
        with gzip.open(path, "rb") as fh:
            Path(tmp_path).write_bytes(fh.read())
        doc = load_document(tmp_path, settings)
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    doc.path = path
    if not doc.title or doc.title == Path(tmp_path).name:
        doc.title = inner.name
    return doc


def _resolve_chapter_words(doc: Document) -> None:
    """Give each ``Document.chapters`` entry a word index by locating its title
    in the spoken text, so chapter-next/prev in the terminal UI lands on the
    chapter rather than at word 0.  Entries whose title cannot be found keep
    their existing index."""
    from .model import _WORD_TOKEN_RE

    text = doc.plain_text or ""
    if not text or not doc.chapters:
        return
    low = text.lower()
    tokens = [m.start() for m in _WORD_TOKEN_RE.finditer(text)]
    if not tokens:
        return
    import bisect

    cursor = 0
    resolved: List[Tuple[str, str, int]] = []
    for title, href, widx in doc.chapters:
        key = re.sub(r"\s+", " ", title.strip().lower())
        pos = low.find(key, cursor) if key else -1
        if pos < 0 and key:
            pos = low.find(key)
        if pos >= 0:
            widx = bisect.bisect_left(tokens, pos)
            cursor = pos + len(key)
        resolved.append((title, href, widx))
    doc.chapters = resolved
