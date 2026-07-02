"""Document-fidelity tests (roadmap area 4).

Covers the four fidelity features added to the render path:

* **Visual math** — ``star.mathrender`` LaTeX→Unicode conversion (pure).
* **Accessible tables** — header scope/emphasis + alignment in the GUI HTML.
* **Footnote anchors/backlinks** — reference markers become anchored links with
  a return backlink in a Footnotes section.
* **Semantic image metadata** — alt/caption/figure/long-description extraction
  in the HTML, PDF, DOCX and PPTX loaders, with an alt-missing fallback.

The math and loader tests are pure (no Qt).  The GUI-render tests build a
``StarWindow`` under the offscreen QPA (as ``tests/test_gui_smoke.py`` does) and
are skipped when PyQt is unavailable.
"""
import importlib.util
import os

import pytest

from star.documents import _load_html_str, _pdf_mark_captions
from star.mathrender import has_math, render_math_to_unicode

# ---------------------------------------------------------------------------
# Visual math — star.mathrender (pure, no Qt)
# ---------------------------------------------------------------------------


def test_math_superscript_digits():
    assert render_math_to_unicode(r"$x^2$") == "x²"
    assert render_math_to_unicode(r"$x^{10}$") == "x¹⁰"
    assert render_math_to_unicode(r"$E = mc^2$") == "E = mc²"


def test_math_subscript():
    assert render_math_to_unicode(r"$x_1$") == "x₁"
    assert render_math_to_unicode(r"$x_{ij}$") == "xᵢⱼ"


def test_math_greek_letters():
    assert render_math_to_unicode(r"$\alpha + \beta = \gamma$") == "α + β = γ"
    assert render_math_to_unicode(r"$\Omega$") == "Ω"


def test_math_vulgar_fractions():
    assert render_math_to_unicode(r"$\frac{1}{2}$") == "½"
    assert render_math_to_unicode(r"$\frac{3}{4}$") == "¾"


def test_math_generic_fraction_uses_fraction_slash():
    # No dedicated glyph → fall back to the fraction-slash form, still readable.
    assert render_math_to_unicode(r"$\frac{a}{b}$") == "a⁄b"


def test_math_roots():
    assert render_math_to_unicode(r"$\sqrt{2}$") == "√2"
    assert render_math_to_unicode(r"$\sqrt[3]{x}$") == "³√x"


def test_math_operators_and_relations():
    assert render_math_to_unicode(r"$a \leq b \times c$") == "a ≤ b × c"
    assert render_math_to_unicode(r"$x \in S$") == "x ∈ S"


def test_math_accents():
    assert render_math_to_unicode(r"$\hat{x}$") == "x̂"
    assert render_math_to_unicode(r"$\bar{y}$") == "ȳ"


def test_math_font_wrappers_unwrap():
    # \mathbf / \text carry no visual math meaning → inner text is exposed.
    assert render_math_to_unicode(r"$\mathbf{v}$") == "v"
    assert render_math_to_unicode(r"$\text{if } x$").startswith("if")


def test_math_display_delimiters():
    assert render_math_to_unicode(r"$$a^2$$") == "a²"
    assert render_math_to_unicode(r"\(y^2\)") == "y²"
    assert render_math_to_unicode(r"\[z^2\]") == "z²"


def test_math_leaves_non_math_untouched():
    # Bare ^ and _ outside math delimiters must not be rewritten.
    assert render_math_to_unicode("a_b and c^d, no dollars") == "a_b and c^d, no dollars"
    assert render_math_to_unicode("plain prose") == "plain prose"


def test_math_inline_within_prose():
    out = render_math_to_unicode(r"The formula $a^2 + b^2 = c^2$ is famous.")
    assert out == "The formula a² + b² = c² is famous."


def test_has_math_detection():
    assert has_math(r"a $x^2$ b")
    assert has_math(r"\(x\)")
    assert has_math(r"\frac{1}{2}")
    assert not has_math("no math at all")
    assert not has_math("")


def test_math_does_not_raise_on_garbage():
    # Best-effort: malformed input must degrade to readable text, never raise.
    for junk in (r"$\frac{1}$", r"$x^{$", r"$\$", r"$}{$", r"$\unknowncmd{x}$"):
        assert isinstance(render_math_to_unicode(junk), str)


def test_math_tts_normalization_still_works():
    # The TTS math path is independent and must be unaffected: raw LaTeX in,
    # spoken English out.
    from star.ttstext import _normalize_math_inline

    assert _normalize_math_inline(r"$E = mc^2$") == "E = mc squared"
    assert _normalize_math_inline(r"$\frac{1}{2}$") == "1 over 2"


# ---------------------------------------------------------------------------
# Semantic image metadata — HTML loader (pure)
# ---------------------------------------------------------------------------


def test_html_img_alt_preserved():
    md = _load_html_str('<p><img src="cat.png" alt="A cat"></p>')
    assert "![A cat](cat.png)" in md


def test_html_img_title_fallback_when_no_alt():
    md = _load_html_str('<p><img src="d.png" title="Diagram"></p>')
    assert "![Diagram](d.png)" in md


def test_html_img_longdesc_noted():
    md = _load_html_str('<img src="c.png" alt="Chart" longdesc="desc.html">')
    assert "Chart" in md
    assert "long description" in md.lower()
    assert "desc.html" in md


def test_html_figure_figcaption():
    html = (
        "<figure><img src='p.png' alt='Plot'>"
        "<figcaption>Figure 1: results</figcaption></figure>"
    )
    md = _load_html_str(html)
    assert "![Plot](p.png)" in md
    # Caption emitted as an emphasised line.
    assert "*Figure 1: results*" in md


def test_html_img_empty_alt_still_referenced():
    md = _load_html_str('<img src="x.png">')
    # No alt: the reference is still present so nothing is silently dropped.
    assert "![](x.png)" in md


# ---------------------------------------------------------------------------
# PDF figure/caption detection (pure)
# ---------------------------------------------------------------------------


def test_pdf_mark_captions_wraps_figure_lines():
    text = "Body paragraph.\nFigure 3. The apparatus setup.\nMore body."
    out = _pdf_mark_captions(text)
    assert "*Figure 3. The apparatus setup.*" in out
    # Body prose is untouched.
    assert "Body paragraph." in out
    assert "*Body paragraph.*" not in out


def test_pdf_mark_captions_handles_table_and_fig_abbrev():
    assert "*Table 2: Summary of results*" in _pdf_mark_captions("Table 2: Summary of results")
    assert "*Fig. 4 Overview*" in _pdf_mark_captions("Fig. 4 Overview")


def test_pdf_mark_captions_ignores_non_captions():
    text = "Figure it out yourself.\nThe figure below shows."
    out = _pdf_mark_captions(text)
    # "Figure" not followed by a number is not a caption.
    assert "*" not in out


# ---------------------------------------------------------------------------
# DOCX / PPTX alt-text helpers (pure, exercised without the binary libs)
# ---------------------------------------------------------------------------


def test_docx_para_images_extracts_descr():
    import xml.etree.ElementTree as ET

    from star.documents.office import _DOCX_WP_NS, _docx_para_images

    # Build a minimal <w:p> containing a drawing docPr with alt text.
    xml = (
        f'<p xmlns:wp="{_DOCX_WP_NS[1:-1]}">'
        '<wp:docPr id="1" name="Picture 1" descr="A histogram" title="Hist"/>'
        "</p>"
    )
    p_elem = ET.fromstring(xml)

    class _FakePara:
        _p = p_elem

    lines = _docx_para_images(_FakePara(), [0])
    joined = "\n".join(lines)
    assert "![A histogram]()" in joined
    assert "*Figure 1: A histogram*" in joined


def test_docx_para_images_fallback_without_descr():
    import xml.etree.ElementTree as ET

    from star.documents.office import _DOCX_WP_NS, _docx_para_images

    xml = (
        f'<p xmlns:wp="{_DOCX_WP_NS[1:-1]}">'
        '<wp:docPr id="2" name="Picture 2"/>'
        "</p>"
    )

    class _FakePara:
        _p = ET.fromstring(xml)

    lines = _docx_para_images(_FakePara(), [0])
    joined = "\n".join(lines)
    # No descr/title → name is used as alt; a figure line is still emitted.
    assert "![Picture 2]()" in joined
    assert "Figure 1" in joined


def test_pptx_shape_descr_reads_cnvpr():
    import xml.etree.ElementTree as ET

    from star.documents.office import _pptx_shape_descr

    xml = '<pic xmlns:p="x"><p:cNvPr id="3" name="Image" descr="A map"/></pic>'

    class _FakeShape:
        _element = ET.fromstring(xml)

    assert _pptx_shape_descr(_FakeShape()) == "A map"


def test_pptx_shape_descr_empty_on_missing():
    import xml.etree.ElementTree as ET

    from star.documents.office import _pptx_shape_descr

    class _FakeShape:
        _element = ET.fromstring("<pic></pic>")

    assert _pptx_shape_descr(_FakeShape()) == ""


# ===========================================================================
# GUI render path (Qt-gated) — tables / footnotes / images / math in HTML
# ===========================================================================

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

qt = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    for ttf in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ttf):
            QFontDatabase.addApplicationFont(ttf)
    return app


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


# ── Accessible tables ───────────────────────────────────────────────────────


@qt
def test_table_header_scope_and_emphasis(window):
    md = "| Name | Age |\n| --- | --- |\n| Alice | 30 |\n"
    html = window._md_body_to_html(md)
    assert "<thead>" in html and "<tbody>" in html
    # Column headers get scope="col"; the first body cell is a row header.
    assert 'scope="col"' in html
    assert 'scope="row"' in html
    assert ">Name<" in html and ">Alice<" in html


@qt
def test_table_alignment_from_separator(window):
    md = "| L | R | C |\n|:---|---:|:---:|\n| a | b | c |\n"
    html = window._md_body_to_html(md)
    assert 'align="left"' in html
    assert 'align="right"' in html
    assert 'align="center"' in html


@qt
def test_table_default_alignment_omitted(window):
    md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    html = window._md_body_to_html(md)
    # A plain --- column carries no align attribute.
    assert "align=" not in html.split("<tbody>")[0].replace('scope="col"', "")


# ── Footnote anchors + backlinks ────────────────────────────────────────────


@qt
def test_footnote_reference_becomes_anchor(window):
    md = "See here.[^1]\n\n[^1]: The note.\n"
    html = window._md_body_to_html(md)
    # Reference marker → superscript anchored link into the footnote.
    assert 'class="fnref"' in html
    assert 'name="fnref-1"' in html
    assert 'href="#fn-1"' in html
    assert "<sup" in html


@qt
def test_footnote_definition_has_backlink(window):
    md = "See here.[^1]\n\n[^1]: The note.\n"
    html = window._md_body_to_html(md)
    assert "Footnotes" in html
    assert 'name="fn-1"' in html
    assert 'href="#fnref-1"' in html
    assert "The note." in html
    # The return backlink glyph.
    assert "↩" in html


@qt
def test_footnote_numbering_by_reference_order(window):
    md = "A[^b] then B[^a].\n\n[^a]: note a\n[^b]: note b\n"
    html = window._md_body_to_html(md)
    # [^b] is referenced first → numbered [1], [^a] → [2].
    assert 'href="#fn-b">[1]' in html
    assert 'href="#fn-a">[2]' in html


@qt
def test_dangling_footnote_reference_left_alone(window):
    # A reference without a matching definition must not crash or anchor.
    md = "text with a stray[^x] marker.\n"
    html = window._md_body_to_html(md)
    assert "fnref-x" not in html
    assert "Footnotes" not in html


# ── Image metadata surfacing ────────────────────────────────────────────────


@qt
def test_image_alt_rendered_as_label(window):
    html = window._md_body_to_html("![A red square](img.png)\n")
    assert 'class="imgalt"' in html
    assert "A red square" in html


@qt
def test_image_missing_alt_uses_filename_fallback(window):
    html = window._md_body_to_html("![](my_diagram.png)\n")
    # Empty alt → readable fallback derived from the file name.
    assert 'class="imgalt"' in html
    assert "my diagram" in html


# ── Visual math in the HTML body ────────────────────────────────────────────


@qt
def test_math_rendered_in_html_body(window):
    html = window._md_body_to_html("The identity $e^2$ and $\\alpha$.\n")
    assert "e²" in html
    assert "α" in html
    # Raw LaTeX delimiters are gone from the display HTML.
    assert "$e^2$" not in html


@qt
def test_full_html_has_fidelity_css(window):
    html = window._md_to_html("text.[^1]\n\n[^1]: n\n")
    for selector in ("sup.fnref", "a.fnback", "span.imgalt"):
        assert selector in html
