"""Document model and multi-format loaders (package split from documents.py).

Re-exports the full surface of the former flat module so
``from star.documents import X`` and the ``star.formats`` entry-points keep
resolving."""
from .._runtime import *  # noqa: F401,F403
from ..formats import FormatHandler, UnsupportedFormatError  # noqa: F401
from ..settings import Settings  # noqa: F401
from .model import (Document, WordPos, _build_word_map)
from .pdf import (_PDF_PAGENUM_RE, _PdfBox, _load_pdf, _pdf_detect_columns, _pdf_is_running, _pdf_norm_margin, _pdf_order_boxes, _pdf_running_heads_feet)
from .html import (_HTML2MD, _load_html, _load_html_str)
from .ebook import (_epub_extract_chapters, _load_daisy_zip, _load_dtbook, _load_epub)
from .office import (_load_csv_tsv, _load_doc, _load_docx, _load_odt_raw_xml, _load_odt_v2, _load_odt_via_odfpy, _load_pptx, _load_xlsx, _odt_table_to_md)
from .text_loaders import (_load_asciidoc, _load_creole, _load_latex, _load_markdown, _load_mediawiki, _load_notebook, _load_orgmode, _load_plain_text, _load_r_code, _load_rmarkdown, _load_rst, _load_textile)
from .pandoc import (_PANDOC_FIRST_FORMATS, _PANDOC_INPUT_EXTS, _load_pandoc_first, _load_via_pandoc, _pandoc_available, _pandoc_handles)
from .misc import (_load_image_ocr, _load_url, _process_footnotes, _record_archive_members)
from .handlers import (DocxHandler, EPUBHandler, HTMLHandler, MarkdownHandler, ODTHandler, OrgHandler, PDFHandler, PPTXHandler, PandocHandler, PlainTextHandler, RSTHandler, XLSXHandler, _document_from_markdown)
from .dispatch import (_detect_format, load_document, load_document_via_plugins, supported_extensions)

__all__ = [
    "Document",
    "DocxHandler",
    "EPUBHandler",
    "HTMLHandler",
    "MarkdownHandler",
    "ODTHandler",
    "OrgHandler",
    "PDFHandler",
    "PPTXHandler",
    "PandocHandler",
    "PlainTextHandler",
    "RSTHandler",
    "WordPos",
    "XLSXHandler",
    "_HTML2MD",
    "_PANDOC_FIRST_FORMATS",
    "_PANDOC_INPUT_EXTS",
    "_PDF_PAGENUM_RE",
    "_PdfBox",
    "_build_word_map",
    "_detect_format",
    "_document_from_markdown",
    "_epub_extract_chapters",
    "_load_asciidoc",
    "_load_creole",
    "_load_csv_tsv",
    "_load_daisy_zip",
    "_load_doc",
    "_load_docx",
    "_load_dtbook",
    "_load_epub",
    "_load_html",
    "_load_html_str",
    "_load_image_ocr",
    "_load_latex",
    "_load_markdown",
    "_load_mediawiki",
    "_load_notebook",
    "_load_odt_raw_xml",
    "_load_odt_v2",
    "_load_odt_via_odfpy",
    "_load_orgmode",
    "_load_pandoc_first",
    "_load_pdf",
    "_load_plain_text",
    "_load_pptx",
    "_load_r_code",
    "_load_rmarkdown",
    "_load_rst",
    "_load_textile",
    "_load_url",
    "_load_via_pandoc",
    "_load_xlsx",
    "_odt_table_to_md",
    "_pandoc_available",
    "_pandoc_handles",
    "_pdf_detect_columns",
    "_pdf_is_running",
    "_pdf_norm_margin",
    "_pdf_order_boxes",
    "_pdf_running_heads_feet",
    "_process_footnotes",
    "_record_archive_members",
    "load_document",
    "supported_extensions",
    "load_document_via_plugins",
]
