"""Format detection and the load_document entry points."""
from .._runtime import *  # noqa: F401,F403
from ..cache import _cache_load, _cache_save
from ..formats import UnsupportedFormatError
from ..settings import Settings
from ..stats import _settings_fingerprint
from ..ttstext import _strip_markdown_for_tts
from .ebook import _epub_extract_chapters, _load_dtbook, _load_epub
from .html import _load_html
from .misc import _load_image_ocr, _load_url, _process_footnotes, _record_archive_members
from .model import Document
from .office import _load_csv_tsv, _load_doc, _load_docx, _load_odt_v2, _load_pptx, _load_xlsx
from .pandoc import _PANDOC_INPUT_EXTS, _load_pandoc_first, _load_via_pandoc, _pandoc_available, _pandoc_handles
from .pdf import _load_pdf
from .text_loaders import _load_asciidoc, _load_creole, _load_latex, _load_markdown, _load_mediawiki, _load_notebook, _load_orgmode, _load_plain_text, _load_r_code, _load_rmarkdown, _load_rst, _load_textile


#: Extension → internal format name.  The single source for both format
#: detection and :func:`supported_extensions` (the library scanner's filter).
_EXT_FORMAT_MAP: Dict[str, str] = {
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


def _detect_format(path: str) -> str:
    """Detect document format from extension or magic bytes."""
    p = path.lower()
    if p.startswith(("http://", "https://", "ftp://")):
        return "url"
    ext = Path(path).suffix.lower()
    if ext in _EXT_FORMAT_MAP:
        return _EXT_FORMAT_MAP[ext]
    if ext in _PANDOC_INPUT_EXTS:
        return "pandoc"
    return "text"


def supported_extensions() -> "frozenset[str]":
    """Lowercase file extensions (with dot) star can open as documents.

    The union of the native format map, the Pandoc-only input formats, and any
    extensions contributed by installed ``star.formats`` plugins.  Used by the
    library scanner to decide which files in a folder are documents.
    """
    exts = set(_EXT_FORMAT_MAP) | set(_PANDOC_INPUT_EXTS)
    try:
        from ..plugins import PluginRegistry

        exts |= set(getattr(PluginRegistry.get(), "_ext_map", {}))
    except Exception:  # noqa: BLE001 — plugin discovery must never break scanning
        pass
    return frozenset(exts)


def load_document_via_plugins(path: "str | Path", **kwargs) -> Document:
    """Load *path* using the plugin registry.  Raises UnsupportedFormatError if
    no handler is registered and available for the file extension.

    Phase 2 scaffolding: this delegates format dispatch to
    :class:`star.plugins.PluginRegistry`.  It is **not** yet wired into the
    application's call sites — the legacy :func:`load_document` remains the
    production path until the Phase 2 switch.
    """
    from ..plugins import PluginRegistry

    p = Path(path)
    handler = PluginRegistry.get().handler_for(p)
    if handler is None:
        raise UnsupportedFormatError(p.suffix)
    return handler.load(p, **kwargs)


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
    doc_from_handler: "Document | None" = None
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
    if not md and not _pandoc_only_disabled:
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
