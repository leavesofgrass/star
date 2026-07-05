"""Direct unit tests for :mod:`star.documents`.

``documents.py`` is the multi-format document model + loader hub (~2,100 lines)
and was only exercised incidentally (plus the PDF geometry helpers, which
``tests/test_pdf_layout.py`` already covers).  This module pins the pure /
deterministic surface that needs no real binary documents:

* format detection (``_detect_format``) and Pandoc routing (``_pandoc_handles``),
* the HTML→Markdown parser (``_HTML2MD`` via ``_load_html_str``),
* the word-map builder (``_build_word_map``),
* Markdown footnote handling (``_process_footnotes``), and
* the text-ish loaders (plain/markdown/CSV/TSV/notebook/R) over tiny temp files,
* plus ``load_document`` dispatch for the simple native formats.

The binary loaders (PDF/DOCX/EPUB/ODT/XLSX) and Pandoc paths are left to
integration coverage; they need real files or external tools.
"""
import json

import pytest

from star.documents import (
    Document,
    WordPos,
    _build_word_map,
    _detect_format,
    _load_csv_tsv,
    _load_html_str,
    _load_markdown,
    _load_notebook,
    _load_plain_text,
    _load_r_code,
    _load_rmarkdown,
    _pandoc_handles,
    _process_footnotes,
    load_document,
)
from star.settings import Settings


# ============================================================================
# _detect_format
# ============================================================================


@pytest.mark.parametrize(
    "path,fmt",
    [
        ("notes.md", "markdown"),
        ("notes.markdown", "markdown"),
        ("readme.txt", "text"),
        ("page.HTML", "html"),  # case-insensitive
        ("page.htm", "html"),
        ("/abs/path/doc.pdf", "pdf"),
        ("report.docx", "docx"),
        ("legacy.doc", "doc"),
        ("slides.pptx", "pptx"),
        ("sheet.odt", "odt"),
        ("book.epub", "epub"),
        ("data.csv", "csv"),
        ("data.tsv", "tsv"),
        ("data.xlsx", "xlsx"),
        ("paper.tex", "latex"),
        ("doc.rst", "rst"),
        ("notebook.ipynb", "notebook"),
        ("outline.org", "orgmode"),
        ("script.py", "python"),
        ("main.rs", "rust"),
        ("a.c", "c"),
        ("photo.jpg", "image"),
    ],
)
def test_detect_format_by_extension(path, fmt):
    assert _detect_format(path) == fmt


def test_detect_format_urls():
    assert _detect_format("http://example.com/x") == "url"
    assert _detect_format("https://example.com/y") == "url"
    assert _detect_format("ftp://host/z") == "url"


def test_detect_format_pandoc_only_extension():
    # .rtf has no native loader → routed to the "pandoc" format.
    assert _detect_format("memo.rtf") == "pandoc"
    assert _detect_format("book.fb2") == "pandoc"


def test_detect_format_unknown_defaults_to_text():
    assert _detect_format("mystery.zzz") == "text"
    assert _detect_format("no_extension") == "text"


# ============================================================================
# _pandoc_handles
# ============================================================================


def test_pandoc_handles_routed_formats():
    for fmt in ("docx", "odt", "pptx", "html", "csv", "rst", "notebook", "pandoc"):
        assert _pandoc_handles(fmt) is True


def test_pandoc_handles_native_only_formats():
    for fmt in ("pdf", "epub", "markdown", "text", "image", "daisy"):
        assert _pandoc_handles(fmt) is False


# ============================================================================
# _build_word_map
# ============================================================================


def test_build_word_map_single_line_offsets_and_columns():
    wm = _build_word_map("hello world", ["hello world"])
    assert [w.word for w in wm] == ["hello", "world"]
    assert (wm[0].tts_offset, wm[0].tts_len) == (0, 5)
    assert (wm[0].disp_line, wm[0].disp_col) == (0, 0)
    assert (wm[1].tts_offset, wm[1].disp_line, wm[1].disp_col) == (6, 0, 6)


def test_build_word_map_spans_multiple_lines():
    wm = _build_word_map("alpha beta", ["alpha", "beta"])
    assert wm[0].disp_line == 0 and wm[0].disp_col == 0
    assert wm[1].word == "beta" and wm[1].disp_line == 1 and wm[1].disp_col == 0


def test_build_word_map_empty_text():
    assert _build_word_map("", []) == []


def test_build_word_map_word_absent_from_display_is_still_emitted():
    # No rendered lines: the word is still mapped (audio plays), parked at 0/0.
    wm = _build_word_map("orphan", [])
    assert len(wm) == 1 and wm[0].word == "orphan"
    assert wm[0].disp_line == 0 and wm[0].disp_col == 0


def test_build_word_map_does_not_regress_on_repeated_words():
    # "the" repeats; the second occurrence must not jump the highlight backward.
    wm = _build_word_map("the cat the dog", ["the cat", "the dog"])
    lines = [w.disp_line for w in wm]
    assert lines == sorted(lines)  # monotonic, never regresses


# ============================================================================
# _load_html_str  (the _HTML2MD parser)
# ============================================================================


def test_html_headings():
    assert _load_html_str("<h1>Title</h1>").startswith("# Title")
    assert "## Sub" in _load_html_str("<h2>Sub</h2>")


def test_html_title_becomes_top_heading():
    out = _load_html_str("<html><head><title>Doc</title></head><body><p>x</p></body></html>")
    assert out.startswith("# Doc")


def test_html_inline_emphasis_and_code():
    out = _load_html_str("<p>a <b>bold</b> <i>it</i> <code>cd</code></p>")
    assert "**bold**" in out
    assert "*it*" in out
    assert "`cd`" in out


def test_html_links():
    out = _load_html_str('<p><a href="http://x.com">link</a></p>')
    assert "[link](http://x.com)" in out


def test_html_unordered_list():
    out = _load_html_str("<ul><li>one</li><li>two</li></ul>")
    assert "* one" in out and "* two" in out


def test_html_ordered_list_numbers():
    out = _load_html_str("<ol><li>a</li><li>b</li></ol>")
    assert "1. a" in out and "2. b" in out


def test_html_preformatted_code_block_fenced():
    out = _load_html_str('<pre><code class="language-python">x = 1</code></pre>')
    assert "```" in out and "x = 1" in out


def test_html_table_cells_present():
    out = _load_html_str(
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    )
    assert "|" in out
    for cell in ("A", "B", "1", "2"):
        assert cell in out


def test_html_skips_script_and_style():
    out = _load_html_str("<p>keep</p><script>var x=1;</script><style>.a{}</style>")
    assert "keep" in out
    assert "var x" not in out and ".a{" not in out


# ============================================================================
# _process_footnotes
# ============================================================================


_FN = "See this[^1] and that[^note].\n\n[^1]: first note\n[^note]: second note\n"


def test_footnotes_inline_inserts_text():
    out = _process_footnotes(_FN, "inline")
    assert "(footnote: first note)" in out
    assert "(footnote: second note)" in out
    assert "[^1]:" not in out  # definition stripped


def test_footnotes_skip_removes_markers_and_text():
    out = _process_footnotes(_FN, "skip")
    assert "[^1]" not in out and "[^note]" not in out
    assert "first note" not in out  # definition text gone too
    assert "See this" in out and "and that" in out


def test_footnotes_deferred_appends_section():
    out = _process_footnotes(_FN, "deferred")
    assert "## Footnotes" in out
    # The note text must survive as PLAIN content, never as a bare
    # "[^label]:" definition — with the in-text references stripped, Pandoc
    # treats reference-less definitions as unused and silently drops them,
    # so HTML/EPUB exports shipped an empty "Footnotes" heading.
    assert "first note" in out
    assert "[^1]:" not in out
    # the inline reference markers are removed from the body
    assert "this[^1]" not in out


# ============================================================================
# text-ish loaders over tiny temp files
# ============================================================================


def test_load_plain_text_roundtrip(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("line one\nline two\n", encoding="utf-8")
    assert _load_plain_text(str(p)) == "line one\nline two\n"


def test_load_plain_text_missing_file_returns_error_block():
    out = _load_plain_text("/no/such/file-xyz.txt")
    assert out.startswith("# Error")


def test_load_markdown_is_passthrough(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# Heading\n\ntext\n", encoding="utf-8")
    assert _load_markdown(str(p)) == "# Heading\n\ntext\n"


def test_load_csv_renders_markdown_table(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("name,age\nAda,36\n", encoding="utf-8")
    out = _load_csv_tsv(str(p), ",")
    assert "| name | age |" in out
    assert "| Ada | 36 |" in out
    assert "---" in out  # header separator row


def test_load_tsv_uses_tab_delimiter(tmp_path):
    p = tmp_path / "d.tsv"
    p.write_text("a\tb\n1\t2\n", encoding="utf-8")
    out = _load_csv_tsv(str(p), "\t")
    assert "| a | b |" in out and "| 1 | 2 |" in out


def test_load_csv_escapes_pipes(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("a|b,c\n", encoding="utf-8")
    out = _load_csv_tsv(str(p), ",")
    assert "a\\|b" in out  # literal pipe escaped for Markdown


def test_load_csv_empty_file(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    assert _load_csv_tsv(str(p), ",") == "*(empty file)*\n"


def test_load_notebook_extracts_markdown_and_code(tmp_path):
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Notebook Title\n"]},
            {"cell_type": "code", "source": ["print('hi')\n"]},
        ],
        "metadata": {"kernelspec": {"language": "python"}},
    }
    p = tmp_path / "nb.ipynb"
    p.write_text(json.dumps(nb), encoding="utf-8")
    out = _load_notebook(str(p))
    assert "# Notebook Title" in out
    assert "```python" in out
    assert "print('hi')" in out


def test_load_notebook_bad_json_returns_error(tmp_path):
    p = tmp_path / "bad.ipynb"
    p.write_text("{not valid json", encoding="utf-8")
    assert _load_notebook(str(p)).startswith("# Notebook Error")


def test_load_r_code_wraps_in_r_fence(tmp_path):
    p = tmp_path / "s.r"
    p.write_text("x <- 1\n", encoding="utf-8")
    out = _load_r_code(str(p))
    assert "```r" in out and "x <- 1" in out


def test_load_rmarkdown_strips_yaml_and_converts_chunks(tmp_path):
    p = tmp_path / "doc.Rmd"
    p.write_text(
        "---\ntitle: My Doc\n---\n# Heading\n\n```{r cars}\nsummary(cars)\n```\n",
        encoding="utf-8",
    )
    out = _load_rmarkdown(str(p))
    assert "title: My Doc" not in out  # YAML front matter stripped
    assert "# Heading" in out
    assert "```r" in out and "{r" not in out  # chunk header normalized


# ============================================================================
# Document / WordPos dataclasses
# ============================================================================


def test_document_defaults():
    d = Document()
    assert d.path == "" and d.title == "" and d.format == ""
    assert d.encoding == "utf-8"
    assert d.word_map == [] and d.metadata == {} and d.chapters == []
    # default factories are independent instances
    assert Document().word_map is not d.word_map


def test_wordpos_fields():
    w = WordPos(word="hi", tts_offset=3, tts_len=2, disp_line=1, disp_col=4)
    assert (w.word, w.tts_offset, w.tts_len, w.disp_line, w.disp_col) == ("hi", 3, 2, 1, 4)


# ============================================================================
# load_document dispatch (native loaders; caching + Pandoc disabled)
# ============================================================================


def _native_settings():
    s = Settings()
    s["document_cache"] = False  # exercise the real parse path, no cache file
    s["prefer_pandoc"] = False  # force the native loaders, not Pandoc
    return s


def test_load_document_text(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("plain words here", encoding="utf-8")
    doc = load_document(str(p), _native_settings())
    assert doc.format == "text"
    assert "plain words here" in doc.plain_text
    assert doc.title  # title populated from the filename


def test_load_document_markdown(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nbody text\n", encoding="utf-8")
    doc = load_document(str(p), _native_settings())
    assert doc.format == "markdown"
    assert "body text" in doc.plain_text


def test_load_document_html_native(tmp_path):
    p = tmp_path / "doc.html"
    p.write_text("<h1>Hello</h1><p>world body</p>", encoding="utf-8")
    doc = load_document(str(p), _native_settings())
    assert doc.format == "html"
    assert "Hello" in doc.markdown
    assert "world body" in doc.plain_text


def test_load_document_csv_native(tmp_path):
    p = tmp_path / "doc.csv"
    p.write_text("x,y\n1,2\n", encoding="utf-8")
    doc = load_document(str(p), _native_settings())
    assert doc.format == "csv"
    assert "x" in doc.plain_text and "y" in doc.plain_text
