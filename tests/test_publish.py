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


# ── _pandoc_write plumbing ──────────────────────────────────────────────────


def test_pandoc_write_appends_extra_args(monkeypatch):
    import star.export as ex

    captured = {}

    class _FakePypandoc:
        @staticmethod
        def convert_text(md, to, format, outputfile, extra_args):
            captured["extra"] = list(extra_args)

    monkeypatch.setattr(ex, "_PYPANDOC", True)
    monkeypatch.setattr(ex, "_pypandoc", _FakePypandoc)
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
    monkeypatch.setattr(ex, "_pypandoc", _FakePypandoc)
    monkeypatch.setattr(publish, "_pandoc_major_cache", 3)
    doc = _doc(title="T", markdown="# T\n\nbody")
    EPUBExporter().export(doc, "out.epub", options=PublishOptions(author="A"))
    assert captured["to"] == "epub"
    assert "author=A" in captured["extra"]
    # The options path carries the title exactly once (via extra_args; the
    # exporter must not ALSO pass title= to _pandoc_write).
    assert captured["extra"].count("title=T") == 1


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
