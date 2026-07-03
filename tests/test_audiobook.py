"""Unit tests for chaptered audiobook (M4B) export.

Exercises the *pure* logic in :mod:`star.audiobook` — chapter derivation from a
document's Markdown headings (and the no-heading fallback), the ffmpeg
metadata/argument construction, and cover-art discovery — plus the
``M4BExporter`` availability gating and its ffmpeg-absent error path.  No real
ffmpeg render is performed unless ffmpeg is present; the exporter's synthesis is
driven with a fake WAV-writing backend so no speech engine is needed.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from star import audiobook
from star.audiobook import (
    Chapter,
    build_chapters_metadata,
    build_concat_list,
    build_ffmpeg_m4b_args,
    cover_path_from_document,
    derive_chapters,
    find_ffmpeg,
)
from star.documents import Document
from star.formats import Exporter
from star.tts.exporters import M4BExporter


# ── chapter derivation ──────────────────────────────────────────────────────────

def test_derive_chapters_from_multiple_headings():
    md = (
        "# Introduction\nWelcome.\n\n"
        "## Chapter One\nThe first body.\n\n"
        "## Chapter Two\nThe second body."
    )
    doc = Document(markdown=md, plain_text="…", title="My Book")
    chapters = derive_chapters(doc)
    assert [c.title for c in chapters] == ["Introduction", "Chapter One", "Chapter Two"]
    # Each chapter's spoken text includes its heading title as the first line.
    assert chapters[1].text.startswith("Chapter One")
    assert "first body" in chapters[1].text


def test_derive_chapters_leading_text_before_first_heading():
    md = "A preface paragraph.\n\n# Real Chapter\nBody."
    doc = Document(markdown=md, plain_text="…", title="Titled")
    chapters = derive_chapters(doc)
    # The lead paragraph becomes its own chapter, titled from the document title.
    assert chapters[0].title == "Titled"
    assert "preface" in chapters[0].text
    assert chapters[1].title == "Real Chapter"


def test_derive_chapters_no_heading_fallback_single_chapter():
    doc = Document(
        markdown="Just plain prose, no headings at all.",
        plain_text="Just plain prose, no headings at all.",
        title="Plain",
    )
    chapters = derive_chapters(doc)
    assert len(chapters) == 1
    assert chapters[0].title == "Plain"
    assert "plain prose" in chapters[0].text


def test_derive_chapters_empty_document_yields_nothing():
    assert derive_chapters(Document(markdown="", plain_text="", title="")) == []


def test_derive_chapters_fallback_title_used_when_untitled():
    doc = Document(markdown="Some body.", plain_text="Some body.", title="")
    chapters = derive_chapters(doc, fallback_title="From Caller")
    assert chapters[0].title == "From Caller"


# ── ffmetadata construction ─────────────────────────────────────────────────────

def test_build_chapters_metadata_cumulative_timestamps():
    chapters = [Chapter("One", "a"), Chapter("Two", "b")]
    meta = build_chapters_metadata(chapters, [2.0, 3.0], album="Alb", artist="Art")
    assert meta.startswith(";FFMETADATA1")
    assert "album=Alb" in meta
    assert "artist=Art" in meta
    # Two chapter blocks with cumulative millisecond boundaries.
    assert meta.count("[CHAPTER]") == 2
    assert "START=0" in meta
    assert "END=2000" in meta
    assert "START=2000" in meta
    assert "END=5000" in meta
    assert "title=One" in meta and "title=Two" in meta


def test_build_chapters_metadata_length_mismatch_raises():
    with pytest.raises(ValueError):
        build_chapters_metadata([Chapter("One", "a")], [1.0, 2.0])


def test_build_chapters_metadata_escapes_special_chars():
    meta = build_chapters_metadata([Chapter("A=B; #C", "x")], [1.0])
    # Each ffmetadata special char in the title is backslash-escaped.
    assert "title=A\\=B\\; \\#C" in meta


def test_build_concat_list_quotes_and_escapes():
    body = build_concat_list(["/tmp/a.wav", "/tmp/o'brien.wav"])
    assert "file '/tmp/a.wav'" in body
    assert "o'\\''brien" in body  # single quote escaped for the concat demuxer


# ── ffmpeg argument construction ────────────────────────────────────────────────

def test_build_ffmpeg_args_without_cover():
    argv = build_ffmpeg_m4b_args("FFMPEG", "concat.txt", "meta.txt", "out.m4b")
    assert argv[0] == "FFMPEG"
    assert argv[-1] == "out.m4b"
    # Two inputs (concat audio + metadata), AAC audio, chapters mapped, MP4 muxer.
    assert argv.count("-i") == 2
    assert "-map_chapters" in argv
    assert "-map_metadata" in argv
    assert "aac" in argv
    assert "-c:v" not in argv  # no cover → no video stream
    # The output muxer is forced to mp4 (the last '-f', not the concat input '-f').
    last_f = len(argv) - 1 - argv[::-1].index("-f")
    assert argv[last_f + 1] == "mp4"


def test_build_ffmpeg_args_with_cover_and_bitrate():
    argv = build_ffmpeg_m4b_args(
        "ffmpeg", "c.txt", "m.txt", "out.m4b", cover_path="cover.jpg", bitrate="96k"
    )
    assert argv.count("-i") == 3  # audio + metadata + cover
    assert "cover.jpg" in argv
    assert "mjpeg" in argv
    assert "attached_pic" in argv
    assert argv[argv.index("-b:a") + 1] == "96k"


# ── cover-art discovery ─────────────────────────────────────────────────────────

def test_cover_path_from_document_finds_existing_file(tmp_path):
    img = tmp_path / "cover.png"
    img.write_bytes(b"\x89PNG")
    doc = Document(metadata={"cover": str(img)})
    assert cover_path_from_document(doc) == str(img)


def test_cover_path_from_document_missing_returns_none(tmp_path):
    doc = Document(metadata={"cover": str(tmp_path / "nope.png")})
    assert cover_path_from_document(doc) is None
    assert cover_path_from_document(Document()) is None


# ── exporter contract + availability gating ─────────────────────────────────────

def test_m4b_exporter_contract():
    assert issubclass(M4BExporter, Exporter)
    assert M4BExporter.name == "m4b"
    exts = M4BExporter.extensions()
    assert exts == frozenset({".m4b"})
    assert all(e.startswith(".") and e == e.lower() for e in exts)
    assert isinstance(M4BExporter.available(), bool)


def test_m4b_available_true_when_ffmpeg_present(monkeypatch):
    monkeypatch.setattr(audiobook, "find_ffmpeg", lambda: "/usr/bin/ffmpeg")
    assert M4BExporter.available() is True


def test_m4b_available_false_when_ffmpeg_absent(monkeypatch):
    monkeypatch.setattr(audiobook, "find_ffmpeg", lambda: None)
    assert M4BExporter.available() is False


def test_m4b_export_without_ffmpeg_raises_clear_message(monkeypatch, tmp_path):
    monkeypatch.setattr(audiobook, "find_ffmpeg", lambda: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        M4BExporter().export(
            Document(plain_text="hi", markdown="# Hi\nhi"), tmp_path / "out.m4b"
        )


def test_m4b_export_empty_document_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(audiobook, "find_ffmpeg", lambda: "/usr/bin/ffmpeg")
    with pytest.raises(ValueError, match="no readable text"):
        M4BExporter().export(Document(plain_text="   ", markdown="   "), tmp_path / "o.m4b")


def test_m4b_export_synthesizes_each_chapter_and_invokes_ffmpeg(monkeypatch, tmp_path):
    """With a fake backend + stubbed ffmpeg, export writes one WAV per chapter
    and hands the built argv to subprocess — no real engine or ffmpeg needed."""
    import wave

    monkeypatch.setattr(audiobook, "find_ffmpeg", lambda: "ffmpeg")

    synth: list[str] = []

    class _FakeBackend:
        def export_to_wav(self, text: str, wav_path: str) -> None:
            synth.append(text)
            # Write a minimal valid 0.1s WAV so _wav_duration_seconds succeeds.
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                wf.writeframes(b"\x00\x00" * 800)

    captured: dict = {}

    class _Result:
        returncode = 0
        stderr = b""

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _Result()

    import star.tts.exporters as exp_mod

    monkeypatch.setattr(exp_mod.subprocess, "run", _fake_run)

    md = "# One\nFirst.\n\n## Two\nSecond."
    doc = Document(markdown=md, plain_text="One First. Two Second.", title="Bk")
    dest = tmp_path / "book.m4b"
    M4BExporter().export(doc, dest, backend=_FakeBackend())

    # One synthesis call per derived chapter.
    assert len(synth) == 2
    argv = captured["argv"]
    assert argv[0] == "ffmpeg"
    assert str(dest) == argv[-1]
    assert "-map_chapters" in argv


def test_m4b_export_cancel_stops_before_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(audiobook, "find_ffmpeg", lambda: "ffmpeg")

    class _NeverCalledBackend:
        def export_to_wav(self, text, wav_path):
            raise AssertionError("should not synthesize when cancelled up-front")

    ran = {"ffmpeg": False}

    def _fake_run(argv, **kwargs):
        ran["ffmpeg"] = True

    import star.tts.exporters as exp_mod

    monkeypatch.setattr(exp_mod.subprocess, "run", _fake_run)

    doc = Document(markdown="# A\nx", plain_text="A x", title="T")
    with pytest.raises(RuntimeError, match="cancel"):
        M4BExporter().export(
            doc, tmp_path / "c.m4b", backend=_NeverCalledBackend(), cancel=lambda: True
        )
    assert ran["ffmpeg"] is False


# ── real ffmpeg render (skipped when ffmpeg is absent) ──────────────────────────

@pytest.mark.skipif(not find_ffmpeg(), reason="ffmpeg not installed")
def test_m4b_real_render_produces_mp4_container(tmp_path):
    import wave

    class _ToneBackend:
        def export_to_wav(self, text: str, wav_path: str) -> None:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x01" * 16000)  # ~1s

    doc = Document(
        markdown="# Alpha\nHello.\n\n# Beta\nWorld.",
        plain_text="Alpha Hello. Beta World.",
        title="Real",
    )
    dest = tmp_path / "real.m4b"
    M4BExporter().export(doc, dest, backend=_ToneBackend())
    assert dest.is_file()
    assert dest.stat().st_size > 0
    # MP4/M4B files carry an 'ftyp' box near the start of the file.
    assert b"ftyp" in dest.read_bytes()[:64]
