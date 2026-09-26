"""Document model and multi-format loaders (package split from documents.py).

Re-exports the full surface of the former flat module so
``from star.documents import X`` and the ``star.formats`` entry-points keep
resolving."""
from .._runtime import *  # noqa: F401,F403
from ..formats import FormatHandler, UnsupportedFormatError  # noqa: F401
from ..settings import Settings  # noqa: F401
from .model import (Document, WordPos, _align_word_offsets, _build_word_map)
from .pdf import (_PDF_PAGENUM_RE, _PdfBox, _load_pdf, _pdf_detect_columns, _pdf_is_running, _pdf_mark_captions, _pdf_norm_margin, _pdf_order_boxes, _pdf_running_heads_feet)
from .html import (_HTML2MD, _load_html, _load_html_str)
from .ebook import (_epub_extract_chapters, _load_daisy_zip, _load_dtbook, _load_epub)
from .office import (_load_csv_tsv, _load_doc, _load_docx, _load_odt_raw_xml, _load_odt_v2, _load_odt_via_odfpy, _load_pptx, _load_xlsx, _odt_table_to_md)
from .text_loaders import (_load_asciidoc, _load_creole, _load_latex, _load_markdown, _load_mediawiki, _load_notebook, _load_orgmode, _load_plain_text, _load_r_code, _load_rmarkdown, _load_rst, _load_textile)
from .pandoc import (_PANDOC_FIRST_FORMATS, _PANDOC_INPUT_EXTS, _load_pandoc_first, _load_via_pandoc, _pandoc_available, _pandoc_handles)
from .misc import (_load_image_ocr, _load_url, _process_footnotes, _record_archive_members)
from .handlers import (AudiobookHandler, CHMHandler, ComicHandler, DAISYHandler, DocHandler, DocxHandler, EPUBHandler, FB2Handler, FODTHandler, HTMLHandler, ManPageHandler, MarkdownHandler, MobiHandler, ODPHandler, ODTHandler, OrgHandler, PDFHandler, PPTHandler, PPTXHandler, PandocHandler, PlainTextHandler, RSTHandler, RTFHandler, WinHelpHandler, WriHandler, XLSXHandler, _document_from_markdown)
from .fb2 import _fb2_chapters, _load_fb2
from .rtf import _load_rtf, _load_wri, looks_like_rtf
from .odf import _load_fodt, _load_odp
from .manpage import _load_manpage, is_manual_page_name
from .comics import _comic_page_names, _load_comic
from .ooxml import _load_docx_native, _load_pptx_native
from .daisy import _is_daisy_zip, _load_daisy, _load_daisy_full
from .audio import _load_audiobook, _load_audiobook_full
from .mobi import _load_mobi, _load_mobi_full
from .ole import OleFile, _load_doc_native, _load_ppt_native
from .chm import ChmFile, _load_chm, _load_chm_full
from .winhelp import HlpFile, _load_winhelp, _load_winhelp_full
from .office import _load_ppt
from .dispatch import (_detect_format, _sniff_zip, load_document, supported_extensions)

__all__ = [
    "Document",
    "AudiobookHandler", "CHMHandler", "ComicHandler", "DAISYHandler", "DocHandler",
    "FB2Handler", "FODTHandler", "ManPageHandler", "MobiHandler", "ODPHandler", "PPTHandler",
    "RTFHandler", "WinHelpHandler", "WriHandler", "ChmFile", "HlpFile", "OleFile",
    "_comic_page_names", "_fb2_chapters", "_is_daisy_zip", "_load_audiobook",
    "_load_audiobook_full", "_load_chm", "_load_chm_full", "_load_comic", "_load_daisy",
    "_load_daisy_full", "_load_doc_native", "_load_docx_native", "_load_fb2", "_load_fodt",
    "_load_manpage", "_load_mobi", "_load_mobi_full", "_load_odp", "_load_ppt",
    "_load_ppt_native", "_load_pptx_native", "_load_rtf", "_load_winhelp",
    "_load_winhelp_full", "_load_wri", "_sniff_zip", "is_manual_page_name", "looks_like_rtf",
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
    "_align_word_offsets",
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
    "_pdf_mark_captions",
    "_pdf_norm_margin",
    "_pdf_order_boxes",
    "_pdf_running_heads_feet",
    "_process_footnotes",
    "_record_archive_members",
    "load_document",
    "supported_extensions",
]
