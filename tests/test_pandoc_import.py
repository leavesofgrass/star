"""Pandoc-first import: format detection, routing membership, and (when Pandoc
is installed) an end-to-end conversion of a Pandoc-only format."""
import pytest

from star.documents import (
    _detect_format,
    _pandoc_available,
    _pandoc_handles,
    load_document,
)
from star.settings import Settings


@pytest.fixture
def settings():
    """A fresh Settings (the autouse conftest fixture sandboxes its file)."""
    return Settings()


def test_pandoc_only_extensions_detected():
    for ext in (".typst", ".typ", ".opml", ".bib", ".bibtex",
                ".docbook", ".muse", ".ris", ".jira", ".vimwiki", ".pod"):
        assert _detect_format("file" + ext) == "pandoc", ext
    # RTF, FB2 and man pages have native loaders since 0.1.32 but stay
    # Pandoc-first when Pandoc is installed.
    assert _detect_format("file.rtf") == "rtf"
    assert _detect_format("file.fb2") == "fb2"
    assert _detect_format("file.man") == "man"
    for fmt in ("rtf", "fb2", "man"):
        assert _pandoc_handles(fmt) is True, fmt


def test_native_formats_unchanged():
    # EPUB stays native (chapter nav); these are not Pandoc-routed by extension.
    assert _detect_format("a.epub") == "epub"
    assert _detect_format("a.docx") == "docx"
    assert _detect_format("a.pdf") == "pdf"
    assert _detect_format("a.md") == "markdown"
    assert _detect_format("a.png") == "image"
    assert _detect_format("a.weirdext") == "text"  # unknown → plain text, not Pandoc


def test_pandoc_handles_membership():
    routed = ("docx", "odt", "pptx", "html", "csv", "tsv", "xlsx", "rst",
              "latex", "mediawiki", "textile", "creole", "orgmode", "notebook",
              "pandoc")
    for f in routed:
        assert _pandoc_handles(f) is True, f
    # Kept native (EPUB for chapter nav; markdown/text need no conversion; the
    # rest aren't Pandoc-readable):
    for f in ("epub", "markdown", "text", "pdf", "image", "python", "r",
              "braille", "daisy", "url"):
        assert _pandoc_handles(f) is False, f


@pytest.mark.skipif(not _pandoc_available(), reason="Pandoc not installed")
def test_rtf_opens_via_pandoc(tmp_path, settings):
    p = tmp_path / "hello.rtf"
    p.write_text(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Times;}}\f0\fs24 Hello from RTF.\par}")
    doc = load_document(str(p), settings)
    text = doc.markdown + doc.plain_text
    assert "Hello from RTF" in text


@pytest.mark.skipif(not _pandoc_available(), reason="Pandoc not installed")
def test_prefer_pandoc_off_falls_back_to_guidance(tmp_path, settings):
    # With Pandoc disabled, a Pandoc-only format yields the install-guidance note
    # rather than garbled plain text.  (RTF has a native loader since 0.1.32, so
    # a RIS bibliography stands in as the Pandoc-only example.)
    p = tmp_path / "x.ris"
    p.write_text("TY  - JOUR\nTI  - Hi\nER  - \n")
    settings["prefer_pandoc"] = False  # safe: isolated tmp settings file
    doc = load_document(str(p), settings)
    assert "Pandoc" in doc.markdown


# ── Pandoc output is decoded as UTF-8 ──────────────────────────────────────

_UTF8_SAMPLE = "Café, Ángel and naïve résumé"


def _fake_pandoc_run(monkeypatch, module):
    """Route the module's Pandoc call to a child that writes UTF-8 bytes.

    The module's own keyword arguments (text mode, encoding) are kept, so
    the child's output is decoded exactly as real Pandoc output would be.
    "Á" is UTF-8 C3 81, and 0x81 has no cp1252 character: decoding with the
    Windows code page either mangled the text or returned nothing.
    """
    import subprocess
    import sys

    real_run = subprocess.run
    script = (
        "import sys; sys.stdout.buffer.write("
        + repr(_UTF8_SAMPLE)
        + ".encode('utf-8'))"
    )

    def run(argv, **kwargs):
        return real_run([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(module, "_PYPANDOC", False)
    monkeypatch.setattr(module, "_PANDOC_BIN", "pandoc")
    monkeypatch.setattr(subprocess, "run", run)


def test_document_pandoc_route_decodes_utf8(monkeypatch, tmp_path):
    import star.documents.pandoc as mod

    _fake_pandoc_run(monkeypatch, mod)
    assert mod._load_via_pandoc(str(tmp_path / "in.typ")) == _UTF8_SAMPLE


def test_markup_pandoc_route_decodes_utf8(monkeypatch, tmp_path):
    import star.markup.pandoc as mod

    _fake_pandoc_run(monkeypatch, mod)
    assert mod._pandoc_convert(str(tmp_path / "in.rst"), "rst") == _UTF8_SAMPLE
