"""Unit tests for the built-in document exporters (``star.exporters`` group).

Covers the always-available text exporter (Markdown) directly, the WAV/Anki
exporters' input validation and availability gating, and the Pandoc-backed
HTML/EPUB exporters when Pandoc is present (skipped otherwise so the suite stays
dependency-light).
"""
from __future__ import annotations

import pytest

from star.documents import Document
from star.export import EPUBExporter, HTMLExporter, MarkdownExporter
from star.flashcards import AnkiExporter
from star.formats import Exporter
from star.tts import WAVExporter
from star.video import MP4Exporter

ALL_EXPORTERS = [
    MarkdownExporter, HTMLExporter, EPUBExporter, AnkiExporter, WAVExporter, MP4Exporter,
]


# ── contract ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_exporter_contract(cls):
    assert issubclass(cls, Exporter)
    assert cls.name
    exts = cls.extensions()
    assert isinstance(exts, frozenset) and exts
    assert all(e.startswith(".") and e == e.lower() for e in exts)
    assert isinstance(cls.available(), bool)


# ── Markdown (always available) ────────────────────────────────────────────────

def test_markdown_exporter_writes_markdown_verbatim(tmp_path):
    out = tmp_path / "doc.md"
    MarkdownExporter().export(Document(markdown="# Hi\n\nBody text."), out)
    assert out.read_text(encoding="utf-8") == "# Hi\n\nBody text."


def test_markdown_exporter_is_always_available():
    assert MarkdownExporter.available() is True


# ── WAV — input validation without touching a real engine ───────────────────────

def test_wav_exporter_rejects_empty_document(tmp_path):
    with pytest.raises(ValueError, match="no readable text"):
        WAVExporter().export(Document(plain_text="   "), tmp_path / "out.wav")


def test_wav_exporter_uses_supplied_backend(tmp_path):
    calls = {}

    class _FakeBackend:
        def export_to_wav(self, text, wav_path):
            calls["text"] = text
            calls["path"] = wav_path

    dest = tmp_path / "out.wav"
    WAVExporter().export(Document(plain_text="Hello there."), dest, backend=_FakeBackend())
    assert calls["text"] == "Hello there."
    assert calls["path"] == str(dest)


# ── Anki — availability gating + annotation routing ─────────────────────────────

def test_anki_exporter_availability_matches_genanki():
    from star import flashcards
    assert AnkiExporter.available() is bool(flashcards._GENANKI)


def test_anki_exporter_empty_annotations(tmp_path):
    if not AnkiExporter.available():
        with pytest.raises(RuntimeError, match="genanki"):
            AnkiExporter().export(Document(title="D"), tmp_path / "d.apkg")
    else:
        # genanki present: an export with no card content raises ValueError.
        with pytest.raises(ValueError):
            AnkiExporter().export(Document(title="D"), tmp_path / "d.apkg", annotations=[])


# ── HTML / EPUB — only when Pandoc is available ─────────────────────────────────

@pytest.mark.skipif(not HTMLExporter.available(), reason="Pandoc not installed")
def test_html_exporter_produces_standalone_html(tmp_path):
    out = tmp_path / "doc.html"
    HTMLExporter().export(Document(markdown="# Title\n\nHello.", title="Title"), out)
    assert "<html" in out.read_text(encoding="utf-8").lower()


@pytest.mark.skipif(not EPUBExporter.available(), reason="Pandoc not installed")
def test_epub_exporter_produces_zip_container(tmp_path):
    out = tmp_path / "doc.epub"
    EPUBExporter().export(Document(markdown="# Title\n\nHello.", title="Title"), out)
    assert out.read_bytes()[:2] == b"PK"  # EPUB is a ZIP container


def test_mp4_exporter_requires_settings(tmp_path):
    with pytest.raises(ValueError, match="settings"):
        MP4Exporter().export(Document(plain_text="hi"), tmp_path / "out.mp4")


# ── GUI export-menu wiring (registry-driven section) ────────────────────────────

import importlib.util  # noqa: E402

from star.plugins import override_plugins  # noqa: E402

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))


class _FancyExporter(Exporter):
    name = "fancy"
    @classmethod
    def extensions(cls): return frozenset({".fancy"})
    @classmethod
    def available(cls): return True
    def export(self, document, path, **kwargs): ...


class _UnavailableExporter(Exporter):
    name = "nope"
    @classmethod
    def extensions(cls): return frozenset({".nope"})
    @classmethod
    def available(cls): return False
    def export(self, document, path, **kwargs): ...


class _CoveredExporter(Exporter):
    name = "markdown"  # has a dedicated bespoke menu item → must be filtered out
    @classmethod
    def extensions(cls): return frozenset({".md"})
    @classmethod
    def available(cls): return True
    def export(self, document, path, **kwargs): ...


@pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")
def test_plugin_exporters_filters_covered_and_unavailable():
    """The dynamic File ▸ Export section excludes exporters that already have a
    bespoke menu item, and excludes unavailable ones."""
    from star.gui.mixin_export import ExportMixin

    stub = ExportMixin.__new__(ExportMixin)
    with override_plugins(
        exporters=[_FancyExporter, _UnavailableExporter, _CoveredExporter]
    ):
        got = [c.name for c in ExportMixin._plugin_exporters(stub)]
    assert got == ["fancy"]
