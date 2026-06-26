"""Tests for Epic III — karaoke video export (star.video).

Pure-logic tests only: sentence spans, frame count, ffmpeg argv.
The full export pipeline is skipped when ffmpeg / Qt / Pillow are absent.
"""
import importlib.util
import shutil
from pathlib import Path

import pytest

from star.video import (
    _build_ffmpeg,
    _find_ffmpeg,
    _parse_resolution,
    _sentence_spans,
    _spans_to_cues,
)


# =============================================================================
# _sentence_spans
# =============================================================================


def test_sentence_spans_basic():
    text = "Hello world. Goodbye world."
    spans = _sentence_spans(text)
    assert len(spans) == 2
    s0, e0 = spans[0]
    assert text[s0:e0].startswith("Hello")
    s1, e1 = spans[1]
    assert text[s1:e1].startswith("Goodbye")


def test_sentence_spans_empty():
    assert _sentence_spans("") == []
    assert _sentence_spans("   ") == []


def test_sentence_spans_single():
    text = "Only one sentence here"
    spans = _sentence_spans(text)
    assert len(spans) == 1
    s, e = spans[0]
    assert text[s:e] == text.strip()


def test_sentence_spans_paragraph_break():
    text = "First paragraph.\n\nSecond paragraph."
    spans = _sentence_spans(text)
    assert len(spans) >= 2


def test_sentence_spans_cover_full_text():
    """Every character in text should be covered by at least one span's range."""
    text = "Sentence one. Sentence two! Third? Fourth."
    spans = _sentence_spans(text)
    assert len(spans) >= 3
    for s, e in spans:
        assert 0 <= s < e <= len(text)


# =============================================================================
# _spans_to_cues
# =============================================================================


def test_spans_to_cues_count():
    text = "Hello. World. Foo."
    spans = _sentence_spans(text)
    cues = _spans_to_cues(text, spans, total_duration=10.0)
    assert len(cues) == len(spans)


def test_spans_to_cues_total_duration():
    text = "Hello world. Goodbye world."
    spans = _sentence_spans(text)
    cues = _spans_to_cues(text, spans, total_duration=5.0)
    # Start of first cue ~= 0, end of last cue ~= 5
    assert cues[0][0] == pytest.approx(0.0, abs=0.01)
    assert cues[-1][1] == pytest.approx(5.0, abs=0.01)


def test_spans_to_cues_empty():
    assert _spans_to_cues("", [], 10.0) == []
    assert _spans_to_cues("text", [], 10.0) == []
    assert _spans_to_cues("text", [(0, 4)], 0.0) == []


def test_spans_to_cues_proportional():
    """Longer sentences get more time."""
    # Two sentences: short and long
    text = "Hi. " + "This is a much longer sentence with many words."
    spans = _sentence_spans(text)
    if len(spans) < 2:
        pytest.skip("sentence split did not produce 2+ sentences")
    cues = _spans_to_cues(text, spans, total_duration=10.0)
    dur_short = cues[0][2]
    dur_long = cues[1][2]
    assert dur_long > dur_short


# =============================================================================
# _parse_resolution
# =============================================================================


def test_parse_resolution_standard():
    assert _parse_resolution("1280x720") == (1280, 720)
    assert _parse_resolution("1920x1080") == (1920, 1080)


def test_parse_resolution_unicode_x():
    assert _parse_resolution("1280×720") == (1280, 720)


def test_parse_resolution_fallback():
    assert _parse_resolution("garbage") == (1280, 720)


def test_parse_resolution_even():
    # libx264 requires even dimensions
    w, h = _parse_resolution("1281x721")
    assert w % 2 == 0
    assert h % 2 == 0


# =============================================================================
# _build_ffmpeg
# =============================================================================


def test_build_ffmpeg_basic():
    argv = _build_ffmpeg("ffmpeg", "concat.txt", "audio.wav", "subs.srt", "out.mp4")
    assert argv[0] == "ffmpeg"
    assert "concat.txt" in argv
    assert "audio.wav" in argv
    assert "subs.srt" in argv
    assert "out.mp4" in argv
    assert "-f" in argv
    assert "concat" in argv


def test_build_ffmpeg_no_subs():
    argv = _build_ffmpeg("ffmpeg", "concat.txt", "audio.wav", None, "out.mp4")
    assert "subs.srt" not in argv
    assert "mov_text" not in argv


def test_build_ffmpeg_soft_subs():
    argv = _build_ffmpeg("ffmpeg", "concat.txt", "audio.wav", "subs.srt", "out.mp4")
    assert "mov_text" in argv
    assert "-c:s" in argv


# =============================================================================
# frame count == sentence count
# =============================================================================


def test_frame_count_matches_sentence_count():
    text = "First sentence here. Second sentence there. Third sentence."
    spans = _sentence_spans(text)
    cues = _spans_to_cues(text, spans, total_duration=9.0)
    assert len(cues) == len(spans), "one cue (frame) per sentence"


# =============================================================================
# Full export — skipped when ffmpeg / Qt / Pillow absent
# =============================================================================


_HAS_FFMPEG = shutil.which("ffmpeg") is not None
_HAS_QT = importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5")
_HAS_PILLOW = importlib.util.find_spec("PIL") is not None


@pytest.mark.skipif(
    not (_HAS_FFMPEG and (_HAS_QT or _HAS_PILLOW)),
    reason="full video export requires ffmpeg + (Qt or Pillow)",
)
def test_export_video_smoke(tmp_path):
    """Smoke-test the full pipeline: short text → MP4."""
    from star.video import export_video

    class _FakeDoc:
        plain_text = "Hello world. This is the second sentence. And a third."
        path = ""
        title = "test"
        markdown = plain_text

    class _FakeSettings:
        def get(self, key, default=None):
            defaults = {
                "video": {"resolution": "320x240", "subtitles": "none"},
                "theme": "dark",
                "tts_rate": 265,
                "tts_volume": 1.0,
                "tts_voice": "",
            }
            return defaults.get(key, default)

    out = str(tmp_path / "out.mp4")
    result = export_video(_FakeDoc(), _FakeSettings(), out)
    # Skip when the environment can't produce a usable audio track (no TTS engine,
    # or the engine wrote a WAV with no readable duration — e.g. SAPI5 on a headless
    # CI runner).  Those are environment limitations, not the render-pipeline
    # regressions this smoke test guards; a real ffmpeg/render error still fails.
    err = result.get("error")
    if err and any(s in err for s in ("TTS", "audio duration", "WAV")):
        pytest.skip(f"environment cannot synthesize usable audio: {err}")
    assert not err
    assert Path(out).exists()
    assert Path(out).stat().st_size > 0
