"""star.publish — options → Pandoc-flag assembly, templates, metadata, EPUB.

Everything up to the integration section runs without Pandoc: the flag
builder is a pure function, template discovery works on temp dirs, and the
``_pandoc_write`` plumbing is exercised against a captured fake.  The final
section publishes a real EPUB and asserts its *structure* via zipfile —
skipped when Pandoc is absent, like the other exporter integration tests.
"""
import zipfile

import pytest

from star import publish
from star.documents.model import Document
from star.export import EPUBExporter, _pandoc_write
from star.publish import (
    PublishOptions,
    available_templates,
    build_pandoc_args,
    resolve_metadata,
)


def _doc(**kw) -> Document:
    d = Document()
    for k, v in kw.items():
        setattr(d, k, v)
    return d


# ── PublishOptions defaults ──────────────────────────────────────────────────


def test_options_defaults_are_epub_with_toc():
    o = PublishOptions()
    assert o.fmt == "epub"
    assert o.template == ""
    assert o.toc is True and o.toc_depth == 3
    assert o.split_level == 1


# ── resolve_metadata ────────────────────────────────────────────────────────


def test_metadata_options_override_document():
    doc = _doc(title="Doc Title", metadata={"author": "Doc Author"})
    o = PublishOptions(title="Override", author="Override Author")
    m = resolve_metadata(doc, o)
    assert m["title"] == "Override"
    assert m["author"] == "Override Author"


def test_metadata_falls_through_to_document_fields():
    doc = _doc(
        title="Fallback Title",
        metadata={"Creator": "OPF Creator", "Lang": "fr", "date": "2026"},
    )
    m = resolve_metadata(doc, PublishOptions())
    assert m["title"] == "Fallback Title"  # doc.title when metadata lacks one
    assert m["author"] == "OPF Creator"  # 'creator' alias, case-insensitive
    assert m["language"] == "fr"  # 'lang' alias
    assert m["date"] == "2026"


def test_metadata_handles_missing_document():
    m = resolve_metadata(None, PublishOptions(author="A"))
    assert m == {"title": "", "author": "A", "language": "", "date": ""}


# ── build_pandoc_args ───────────────────────────────────────────────────────


def test_args_carry_all_metadata(monkeypatch):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    doc = _doc(title="T", metadata={"creator": "A", "lang": "es"})
    args = build_pandoc_args(PublishOptions(date="2026-08-08"), doc)
    assert ["--metadata", "title=T"] == args[0:2]
    assert "author=A" in args and "lang=es" in args and "date=2026-08-08" in args


def test_args_toc_flags_and_opt_out(monkeypatch):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    on = build_pandoc_args(PublishOptions(toc=True, toc_depth=2), None)
    assert "--toc" in on and "--toc-depth=2" in on
    off = build_pandoc_args(PublishOptions(toc=False), None)
    assert "--toc" not in off


def test_args_cover_and_split_are_epub_only(monkeypatch):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    epub = build_pandoc_args(
        PublishOptions(fmt="epub", cover_image="c.png", split_level=2), None
    )
    assert ["--epub-cover-image", "c.png"] == epub[-3:-1]
    assert "--split-level=2" in epub
    html = build_pandoc_args(
        PublishOptions(fmt="html", cover_image="c.png"), None
    )
    assert "--epub-cover-image" not in html
    assert not any(a.startswith("--split-level") for a in html)


def test_args_split_flag_tracks_pandoc_major(monkeypatch):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    assert "--split-level=1" in build_pandoc_args(PublishOptions(), None)
    monkeypatch.setattr(publish, "_pandoc_major_cache", 2)
    assert "--epub-chapter-level=1" in build_pandoc_args(PublishOptions(), None)


def test_args_template_resolves_to_css(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    css = tmp_path / "large-print.css"
    css.write_text("body { font-size: 1.4em; }", encoding="utf-8")
    monkeypatch.setattr(
        publish, "available_templates", lambda: {"large-print": css}
    )
    args = build_pandoc_args(PublishOptions(template="large-print"), None)
    i = args.index("--css")
    assert args[i + 1] == str(css)
    # Unknown template name: no --css, no crash.
    none = build_pandoc_args(PublishOptions(template="nope"), None)
    assert "--css" not in none


# ── template discovery + seeding ────────────────────────────────────────────


@pytest.fixture
def style_dirs(monkeypatch, tmp_path):
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    bundled.mkdir()
    monkeypatch.setattr(publish, "_BUNDLED_STYLES_DIR", bundled)
    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", user)
    return bundled, user


def test_templates_seed_into_user_folder(style_dirs):
    bundled, user = style_dirs
    (bundled / "large-print.css").write_text("b", encoding="utf-8")
    t = available_templates()
    assert (user / "large-print.css").is_file()
    assert t["large-print"] == user / "large-print.css"  # user copy wins


def test_templates_never_overwrite_user_edits(style_dirs):
    bundled, user = style_dirs
    (bundled / "x.css").write_text("bundled", encoding="utf-8")
    user.mkdir()
    (user / "x.css").write_text("edited", encoding="utf-8")
    t = available_templates()
    assert (user / "x.css").read_text(encoding="utf-8") == "edited"
    assert t["x"] == user / "x.css"


def test_templates_user_only_files_appear(style_dirs):
    _bundled, user = style_dirs
    user.mkdir()
    (user / "mine.css").write_text("me", encoding="utf-8")
    assert available_templates()["mine"].name == "mine.css"


def test_templates_missing_dirs_yield_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "_BUNDLED_STYLES_DIR", tmp_path / "nope")
    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path / "also-nope")
    assert available_templates() == {}


# ── the bundled accessibility templates (Batch 2) ───────────────────────────

_BUNDLED_NAMES = ("large-print", "dyslexia-friendly", "high-contrast")


def test_bundled_templates_ship_and_discover(monkeypatch, tmp_path):
    """The three a11y stylesheets exist in the package and discovery (with a
    clean user folder) seeds and returns every one of them."""
    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path / "user")
    t = available_templates()
    for name in _BUNDLED_NAMES:
        assert name in t, f"bundled template missing: {name}"
        assert (tmp_path / "user" / f"{name}.css").is_file()  # seeded


@pytest.mark.parametrize("name", _BUNDLED_NAMES)
def test_bundled_template_content_sanity(name):
    css = (publish._BUNDLED_STYLES_DIR / f"{name}.css").read_text(
        encoding="utf-8"
    )
    assert "body" in css and "line-height" in css
    # Every template keeps the underline link affordance (a11y: never
    # color-only), and explains the copy-and-edit workflow in its header.
    assert "text-decoration: underline" in css
    assert "never overwrites your edits" in css


def test_bundled_templates_mirror_their_aid():
    styles = publish._BUNDLED_STYLES_DIR
    lp = (styles / "large-print.css").read_text(encoding="utf-8")
    assert "1.5em" in lp  # ~18pt large-print body
    dys = (styles / "dyslexia-friendly.css").read_text(encoding="utf-8")
    assert "OpenDyslexic" in dys and "Atkinson Hyperlegible" in dys
    hc = (styles / "high-contrast.css").read_text(encoding="utf-8")
    # The exact on-screen high-contrast palette (star/themes.py).
    for color in ("#000000", "#ffffff", "#ffe14d", "#5fe3ff", "#8ac6ff"):
        assert color in hc


# ── _pandoc_write plumbing ──────────────────────────────────────────────────


def test_pandoc_write_appends_extra_args(monkeypatch):
    import star.export as ex

    captured = {}

    class _FakePypandoc:
        @staticmethod
        def convert_text(md, to, format, outputfile, extra_args):
            captured["extra"] = list(extra_args)

    monkeypatch.setattr(ex, "_PYPANDOC", True)
    monkeypatch.setattr(ex, "_pypandoc", _FakePypandoc, raising=False)
    _pandoc_write("# hi", "epub", "out.epub", extra_args=["--toc", "--css", "x"])
    assert captured["extra"][0] == "--standalone"
    assert captured["extra"][1:] == ["--toc", "--css", "x"]


def test_exporter_options_route_through_publish_args(monkeypatch):
    import star.export as ex

    captured = {}

    class _FakePypandoc:
        @staticmethod
        def convert_text(md, to, format, outputfile, extra_args):
            captured["to"] = to
            captured["extra"] = list(extra_args)

    monkeypatch.setattr(ex, "_PYPANDOC", True)
    monkeypatch.setattr(ex, "_pypandoc", _FakePypandoc, raising=False)
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    doc = _doc(title="T", markdown="# T\n\nbody")
    EPUBExporter().export(doc, "out.epub", options=PublishOptions(author="A"))
    assert captured["to"] == "epub"
    assert "author=A" in captured["extra"]
    # The options path carries the title exactly once (via extra_args; the
    # exporter must not ALSO pass title= to _pandoc_write).
    assert captured["extra"].count("title=T") == 1


# ── phase 2: DOCX reference docs + single-file HTML ─────────────────────────


def test_args_docx_uses_reference_doc_not_css(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    ref = tmp_path / "large-print.docx"
    ref.write_bytes(b"stub")
    monkeypatch.setattr(
        publish, "available_reference_docs", lambda: {"large-print": ref}
    )
    args = build_pandoc_args(
        PublishOptions(fmt="docx", template="large-print", cover_image="c.png"),
        None,
    )
    i = args.index("--reference-doc")
    assert args[i + 1] == str(ref)
    assert "--css" not in args
    assert "--epub-cover-image" not in args  # cover is EPUB-only
    assert not any(a.startswith("--split-level") for a in args)
    assert "--toc" in args  # TOC applies to DOCX too


def test_args_html_is_single_file(monkeypatch):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    html = build_pandoc_args(PublishOptions(fmt="html"), None)
    assert "--embed-resources" in html
    monkeypatch.setattr(publish, "_pandoc_major_cache", 2)
    old = build_pandoc_args(PublishOptions(fmt="html"), None)
    assert "--self-contained" in old and "--embed-resources" not in old
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    epub = build_pandoc_args(PublishOptions(fmt="epub"), None)
    assert "--embed-resources" not in epub


def test_reference_docs_generate_seed_and_discover(monkeypatch, tmp_path):
    """First discovery generates the two a11y reference .docx files with the
    styles Pandoc's writer needs, and never regenerates over an edit."""
    pytest.importorskip("docx", reason="python-docx not installed")
    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path)

    refs = publish.available_reference_docs()
    assert set(refs) >= {"large-print", "dyslexia-friendly"}

    with zipfile.ZipFile(refs["large-print"]) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
    assert 'w:val="36"' in styles  # 18 pt Normal = 36 half-points
    assert "Body Text" in styles  # pandoc's body-paragraph style exists

    # A user-dropped reference appears; an existing file is never regenerated.
    (tmp_path / "mine.docx").write_bytes(b"user")
    marker = tmp_path / "large-print.docx"
    marker.write_bytes(b"edited")
    refs = publish.available_reference_docs()
    assert "mine" in refs
    assert marker.read_bytes() == b"edited"


# ── citations: CSL styles, auto-bibliography, citeproc flags ────────────────


def test_bundled_citation_styles_ship_and_seed(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path / "user")
    styles = publish.available_citation_styles()
    assert set(styles) >= {"apa", "american-medical-association", "vancouver"}
    assert (tmp_path / "user" / "apa.csl").is_file()  # seeded like the CSS
    # A user-dropped .csl appears too.
    (tmp_path / "user" / "my-program.csl").write_text("<style/>", encoding="utf-8")
    assert "my-program" in publish.available_citation_styles()


def test_args_citation_style_enables_citeproc(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    csl = tmp_path / "apa.csl"
    csl.write_text("<style/>", encoding="utf-8")
    monkeypatch.setattr(
        publish, "available_citation_styles", lambda: {"apa": csl}
    )
    args = build_pandoc_args(
        PublishOptions(citation_style="apa", bibliography="refs.json"), None
    )
    assert "--citeproc" in args
    i = args.index("--csl")
    assert args[i + 1] == str(csl)
    j = args.index("--bibliography")
    assert args[j + 1] == "refs.json"
    assert "link-citations=true" in args
    # No style chosen → no citeproc; unknown style name → no citeproc.
    assert "--citeproc" not in build_pandoc_args(PublishOptions(), None)
    none = build_pandoc_args(PublishOptions(citation_style="nope"), None)
    assert "--citeproc" not in none


def test_export_bibliography_writes_library_csl_json(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "CACHE_DIR", tmp_path / "cache")

    class _S(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    s = _S(citations=[{"id": "smith2020", "title": "T", "author": "Smith, A.",
                       "year": "2020", "type": "article-journal"}])
    path = publish.export_bibliography(s)
    assert path and path.endswith(".json")
    import json as _json

    data = _json.loads(open(path, encoding="utf-8").read())
    assert isinstance(data, list) and data  # CSL-JSON array with the entry
    # Empty library → None (publish proceeds without a bibliography).
    assert publish.export_bibliography(_S(citations=[])) is None


def test_academic_reference_docs_generate(monkeypatch, tmp_path):
    """The APA student paper carries TNR 12 double-spaced with a hanging-indent
    Bibliography; the AMA manuscript exists with a flush reference list."""
    pytest.importorskip("docx", reason="python-docx not installed")
    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path)
    refs = publish.available_reference_docs()
    assert {"apa-student-paper", "ama-manuscript"} <= set(refs)

    with zipfile.ZipFile(refs["apa-student-paper"]) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
    assert "Times New Roman" in styles
    assert 'w:val="24"' in styles  # 12 pt = 24 half-points
    assert 'w:line="480"' in styles  # double spacing = 480 twentieths
    assert "Bibliography" in styles
    assert 'w:hanging="720"' in styles  # 0.5" hanging indent on References

    with zipfile.ZipFile(refs["ama-manuscript"]) as z:
        ama = z.read("word/styles.xml").decode("utf-8")
    assert "Times New Roman" in ama and "Bibliography" in ama


# ── integration: a real EPUB, structurally verified ─────────────────────────


@pytest.mark.skipif(not EPUBExporter.available(), reason="Pandoc not installed")
def test_published_epub_structure(tmp_path, monkeypatch):
    css = tmp_path / "style.css"
    css.write_text("body { font-size: 1.4em; }", encoding="utf-8")
    monkeypatch.setattr(publish, "available_templates", lambda: {"style": css})

    doc = _doc(
        title="Structure Test",
        markdown="# One\n\nAlpha beta.\n\n# Two\n\nGamma delta.\n",
        metadata={"creator": "Test Author", "lang": "en"},
    )
    out = tmp_path / "book.epub"
    EPUBExporter().export(
        doc, str(out), options=PublishOptions(template="style", toc=True)
    )

    assert out.is_file() and out.stat().st_size > 0
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        infos = zf.infolist()
        # EPUB OCF: the mimetype entry comes first and is stored uncompressed.
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"
        assert "META-INF/container.xml" in names
        # A navigation document exists (pandoc writes nav.xhtml; accept any).
        assert any("nav" in n.lower() or n.endswith(".ncx") for n in names)
        # The chosen stylesheet was embedded.
        assert any(n.endswith(".css") for n in names)
        joined = b"".join(
            zf.read(n) for n in names if n.endswith((".opf", ".xhtml"))
        )
        assert b"Test Author" in joined
        assert b"Structure Test" in joined


@pytest.mark.skipif(not EPUBExporter.available(), reason="Pandoc not installed")
def test_published_docx_structure(tmp_path, monkeypatch):
    """A real DOCX publish: the generated large-print reference doc's styling
    lands in the output (pandoc copies the reference styles.xml), and the
    document metadata reaches docProps."""
    pytest.importorskip("docx", reason="python-docx not installed")
    from star.export import DOCXExporter

    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path / "styles")
    refs = publish.available_reference_docs()
    assert "large-print" in refs

    doc = _doc(
        title="Docx Test",
        markdown="# One\n\nAlpha beta.\n\n## Two\n\nGamma.\n",
        metadata={"creator": "Docx Author"},
    )
    out = tmp_path / "paper.docx"
    DOCXExporter().export(
        doc, str(out),
        options=PublishOptions(fmt="docx", template="large-print"),
    )

    assert out.is_file() and out.stat().st_size > 0
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names
        styles = zf.read("word/styles.xml").decode("utf-8")
        assert 'w:val="36"' in styles  # the 18 pt large-print Normal came through
        core = zf.read("docProps/core.xml").decode("utf-8")
        assert "Docx Author" in core


@pytest.mark.skipif(not EPUBExporter.available(), reason="Pandoc not installed")
def test_published_docx_with_apa_citations(tmp_path, monkeypatch):
    """End-to-end citeproc: a [@key] citation in the markdown plus a CSL-JSON
    bibliography and the bundled APA style produce a formatted author–year
    citation and a reference entry in the real pandoc output."""
    from star.export import DOCXExporter

    monkeypatch.setattr(publish, "PUBLISH_STYLES_DIR", tmp_path / "user")
    bib = tmp_path / "refs.json"
    bib.write_text(
        '[{"id": "okoro2021", "type": "article-journal",'
        ' "title": "Community health outreach",'
        ' "author": [{"family": "Okoro", "given": "Ada"}],'
        ' "container-title": "Journal of Public Health Nursing",'
        ' "issued": {"date-parts": [[2021]]}}]',
        encoding="utf-8",
    )
    doc = _doc(
        title="Cite Test",
        markdown="# Intro\n\nOutreach works [@okoro2021].\n\n# References\n",
    )
    out = tmp_path / "cited.docx"
    DOCXExporter().export(
        doc, str(out),
        options=PublishOptions(
            fmt="docx", citation_style="apa", bibliography=str(bib), toc=False
        ),
    )
    with zipfile.ZipFile(out) as zf:
        body = zf.read("word/document.xml").decode("utf-8")
    assert "Okoro" in body and "2021" in body  # in-text (Okoro, 2021)
    assert "Community health outreach" in body  # reference list entry
    assert "Journal of Public Health Nursing" in body
