"""FormatHandler plugin classes + the shared Document builder."""
from .._runtime import *  # noqa: F401,F403
from ..formats import FormatHandler
from ..settings import Settings
from ..ttstext import _strip_markdown_for_tts
from .ebook import _epub_extract_chapters, _load_epub
from .html import _load_html
from .misc import _process_footnotes
from .model import Document
from .office import _load_docx, _load_odt_v2, _load_pptx, _load_xlsx
from .pandoc import _PANDOC_INPUT_EXTS, _load_via_pandoc
from .pdf import _load_pdf
from .text_loaders import _load_markdown, _load_orgmode, _load_plain_text, _load_rst


def _document_from_markdown(
    path: "str | Path", fmt: str, md: str, settings: "Settings | None" = None
) -> Document:
    """Build a :class:`Document` from already-loaded *md*, mirroring the tail of
    :func:`load_document` (title extraction, optional footnote processing, and the
    markdown→plain-text strip).  Used by the plugin :class:`FormatHandler` classes
    so the per-format ``load`` methods do not duplicate that boilerplate.
    """
    doc = Document(path=str(path), format=fmt)
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    doc.title = m.group(1).strip() if m else (Path(path).name if path else APP_TITLE)
    if settings is not None:
        footnote_mode = str(settings.get("footnote_mode", "inline"))
        if footnote_mode != "inline":
            md = _process_footnotes(md, mode=footnote_mode)
    doc.markdown = md
    skip_code = bool(settings["tts_skip_code"]) if settings is not None else False
    table_mode = (
        str(settings.get("table_reading_mode", "structured"))
        if settings is not None
        else "structured"
    )
    doc.plain_text = _strip_markdown_for_tts(md, skip_code=skip_code, table_mode=table_mode)
    return doc


class PDFHandler(FormatHandler):
    """PDF loader (pdfminer.six)."""

    name = "pdf"
    priority = 10

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".pdf"})

    @classmethod
    def available(cls) -> bool:
        from .._runtime import _PDF
        return bool(_PDF)

    def load(self, path, **kwargs) -> Document:
        settings = kwargs.get("settings")
        reconstruct = True
        if settings is not None:
            reconstruct = str(settings.get("pdf_reading_order", "reconstruct")) != "raw"
        md = _load_pdf(str(path), reconstruct=reconstruct)
        return _document_from_markdown(path, "pdf", md, settings)


class EPUBHandler(FormatHandler):
    """EPUB loader (native — stdlib zipfile + NCX/NAV chapter navigation)."""

    name = "epub"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".epub"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        settings = kwargs.get("settings")
        md = _load_epub(str(path))
        doc = _document_from_markdown(path, "epub", md, settings)
        if settings is None or settings.get("epub_show_chapters", True):
            try:
                doc.chapters = [(t, h, 0) for t, h in _epub_extract_chapters(str(path))]
            except Exception:
                doc.chapters = []
        return doc


class DocxHandler(FormatHandler):
    """Word (.docx) loader (python-docx)."""

    name = "docx"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".docx"})

    @classmethod
    def available(cls) -> bool:
        from .._runtime import _DOCX
        return bool(_DOCX)

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "docx", _load_docx(str(path)), kwargs.get("settings"))


class ODTHandler(FormatHandler):
    """OpenDocument Text (.odt) loader (odfpy)."""

    name = "odt"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".odt"})

    @classmethod
    def available(cls) -> bool:
        from .._runtime import _ODT
        return bool(_ODT)

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "odt", _load_odt_v2(str(path)), kwargs.get("settings"))


class PPTXHandler(FormatHandler):
    """PowerPoint (.pptx) loader (python-pptx)."""

    name = "pptx"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".pptx"})

    @classmethod
    def available(cls) -> bool:
        from .._runtime import _PPTX
        return bool(_PPTX)

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "pptx", _load_pptx(str(path)), kwargs.get("settings"))


class XLSXHandler(FormatHandler):
    """Excel (.xlsx) loader (openpyxl)."""

    name = "xlsx"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".xlsx"})

    @classmethod
    def available(cls) -> bool:
        from .._runtime import _XLSX
        return bool(_XLSX)

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "xlsx", _load_xlsx(str(path)), kwargs.get("settings"))


class HTMLHandler(FormatHandler):
    """HTML loader (built-in HTMLParser → markdown)."""

    name = "html"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".html", ".htm"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "html", _load_html(str(path)), kwargs.get("settings"))


class MarkdownHandler(FormatHandler):
    """Markdown loader (read as-is)."""

    name = "markdown"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".md", ".markdown"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(
            path, "markdown", _load_markdown(str(path)), kwargs.get("settings")
        )


class PlainTextHandler(FormatHandler):
    """Plain-text loader."""

    name = "txt"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".txt"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(
            path, "text", _load_plain_text(str(path)), kwargs.get("settings")
        )


class RSTHandler(FormatHandler):
    """reStructuredText (.rst) loader."""

    name = "rst"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".rst"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "rst", _load_rst(str(path)), kwargs.get("settings"))


class OrgHandler(FormatHandler):
    """Org-mode (.org) loader."""

    name = "org"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".org"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(
            path, "orgmode", _load_orgmode(str(path)), kwargs.get("settings")
        )


class PandocHandler(FormatHandler):
    """Catch-all loader for the Pandoc-only input formats (RTF, FB2, RIS, …)."""

    name = "pandoc"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset(_PANDOC_INPUT_EXTS)

    @classmethod
    def available(cls) -> bool:
        from .._runtime import _PYPANDOC
        return bool(_PYPANDOC)

    def load(self, path, **kwargs) -> Document:
        md = _load_via_pandoc(str(path)) or ""
        return _document_from_markdown(path, "pandoc", md, kwargs.get("settings"))
