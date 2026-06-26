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
    for ext in (".rtf", ".fb2", ".typst", ".typ", ".opml", ".bib", ".bibtex",
                ".docbook", ".muse", ".ris", ".jira", ".vimwiki", ".pod"):
        assert _detect_format("file" + ext) == "pandoc", ext


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
    # rather than garbled plain text.
    p = tmp_path / "x.rtf"
    p.write_text(r"{\rtf1 hi}")
    settings["prefer_pandoc"] = False  # safe: isolated tmp settings file
    doc = load_document(str(p), settings)
    assert "Pandoc" in doc.markdown
