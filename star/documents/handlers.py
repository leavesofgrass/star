"""FormatHandler plugin classes + the shared Document builder."""
from .._runtime import *  # noqa: F401,F403
from ..formats import FormatHandler
from ..settings import Settings
from ..ttstext import _strip_markdown_for_tts
from .ebook import _epub_extract_chapters, _load_epub
from .html import _load_html
from .misc import _process_footnotes
from .model import Document
from .office import _load_doc, _load_docx, _load_odt_v2, _load_ppt, _load_pptx, _load_xlsx
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


# ── Formats added for Paperback parity (0.1.32) ──────────────────────────────
# Each wraps a stdlib-only loader from its sibling module; ``priority`` 40 puts
# them ahead of the Pandoc catch-all (50) for the extensions both claim
# (.rtf/.fb2/.man) when ``prefer_pandoc`` is off, while the Pandoc-first path in
# ``dispatch`` still wins when Pandoc is installed and enabled.


def _with_chapters(doc: Document, chapters: "list", meta: "dict") -> Document:
    if chapters:
        doc.chapters = [(t, h, 0) for t, h in chapters]
    if meta:
        doc.metadata = dict(meta)
        if meta.get("title"):
            doc.title = meta["title"]
    return doc


class FB2Handler(FormatHandler):
    """FictionBook 2 loader (native XML walker)."""

    name = "fb2"
    priority = 40

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".fb2"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .fb2 import _fb2_chapters, _load_fb2

        doc = _document_from_markdown(path, "fb2", _load_fb2(str(path)), kwargs.get("settings"))
        return _with_chapters(doc, _fb2_chapters(str(path)), {})


class RTFHandler(FormatHandler):
    """Rich Text Format loader (native tokenizer)."""

    name = "rtf"
    priority = 40

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".rtf"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .rtf import _load_rtf

        return _document_from_markdown(path, "rtf", _load_rtf(str(path)), kwargs.get("settings"))


class WriHandler(FormatHandler):
    """Windows Write (.wri) loader — RTF/plain text in disguise, or the Write binary."""

    name = "wri"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".wri"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .rtf import _load_wri

        return _document_from_markdown(path, "wri", _load_wri(str(path)), kwargs.get("settings"))


class ODPHandler(FormatHandler):
    """OpenDocument presentation (.odp / flat .fodp) loader."""

    name = "odp"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".odp", ".fodp"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .odf import _load_odp

        return _document_from_markdown(path, "odp", _load_odp(str(path)), kwargs.get("settings"))


class FODTHandler(FormatHandler):
    """Flat OpenDocument Text (.fodt) loader."""

    name = "fodt"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".fodt"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .odf import _load_fodt

        return _document_from_markdown(path, "fodt", _load_fodt(str(path)), kwargs.get("settings"))


class DocHandler(FormatHandler):
    """Legacy Word (.doc/.dot) loader — python-docx, antiword, LibreOffice, Pandoc, then the native OLE reader."""

    name = "doc"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".doc", ".dot"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "doc", _load_doc(str(path)), kwargs.get("settings"))


class PPTHandler(FormatHandler):
    """Legacy PowerPoint (.ppt/.pps) loader — LibreOffice when present, else the native OLE reader."""

    name = "ppt"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".ppt", ".pps"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        return _document_from_markdown(path, "ppt", _load_ppt(str(path)), kwargs.get("settings"))


class ComicHandler(FormatHandler):
    """Comic book archive (.cbz/.cbr/.cb7) loader — page list, OCR text when available."""

    name = "comic"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".cbz", ".cbr", ".cb7"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .comics import _load_comic

        settings = kwargs.get("settings")
        lang = str(settings.get("ocr_lang", "eng") or "eng") if settings is not None else "eng"
        return _document_from_markdown(path, "comic", _load_comic(str(path), lang=lang), settings)


class MobiHandler(FormatHandler):
    """Mobipocket / Kindle (.mobi/.prc/.azw/.azw3) loader (native PalmDOC + HUFF/CDIC)."""

    name = "mobi"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".mobi", ".prc", ".azw", ".azw3", ".kf8"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .mobi import _load_mobi_full

        md, meta = _load_mobi_full(str(path))
        return _with_chapters(_document_from_markdown(path, "mobi", md, kwargs.get("settings")), [], meta)


class CHMHandler(FormatHandler):
    """Compiled HTML Help (.chm) loader (native ITSF + LZX)."""

    name = "chm"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".chm"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .chm import _load_chm_full

        md, chapters, meta = _load_chm_full(str(path))
        return _with_chapters(_document_from_markdown(path, "chm", md, kwargs.get("settings")), chapters, meta)


class WinHelpHandler(FormatHandler):
    """WinHelp (.hlp) loader (native |TOPIC walker)."""

    name = "winhelp"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".hlp"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .winhelp import _load_winhelp_full

        md, chapters, meta = _load_winhelp_full(str(path))
        return _with_chapters(_document_from_markdown(path, "winhelp", md, kwargs.get("settings")), chapters, meta)


class AudiobookHandler(FormatHandler):
    """M4B / MP3 audiobook loader — metadata and chapter list (native MP4/ID3 parsing)."""

    name = "audiobook"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".m4b", ".m4a", ".mp3"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .audio import _load_audiobook_full

        md, chapters, meta = _load_audiobook_full(str(path))
        return _with_chapters(_document_from_markdown(path, "audiobook", md, kwargs.get("settings")), chapters, meta)


class ManPageHandler(FormatHandler):
    """Manual page (.man/.roff) loader (native roff → Markdown)."""

    name = "man"
    priority = 40

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".man", ".roff"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .manpage import _load_manpage

        return _document_from_markdown(path, "man", _load_manpage(str(path)), kwargs.get("settings"))


class DAISYHandler(FormatHandler):
    """DAISY 3 package (.opf) / NCX / DTBook (.daisy) loader."""

    name = "daisy"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".opf", ".ncx", ".daisy"})

    @classmethod
    def available(cls) -> bool:
        return True

    def load(self, path, **kwargs) -> Document:
        from .daisy import _load_daisy_full

        md, chapters, meta = _load_daisy_full(str(path))
        return _with_chapters(_document_from_markdown(path, "daisy", md, kwargs.get("settings")), chapters, meta)
