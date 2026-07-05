"""Offscreen tests for the reworked Translate and Dictate GUI flows (0.1.22).

Translate now opens its result AS A SPEAKABLE DOCUMENT (not a read-only pane),
and Dictate records until the user presses Stop (no fixed-seconds prompt).
Both network/audio calls are mocked; the module is skipped without PyQt.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
# numpy ships only with the audio/whisper extra; the one test that exercises the
# int16→float32 conversion needs it, the rest (mocked) do not.
_HAS_NUMPY = importlib.util.find_spec("numpy") is not None
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    # Give it a real open document to translate / anchor a note against.
    from star.documents import Document

    win.doc = Document(
        path="/tmp/orig.md", title="Orig", markdown="# Orig\n\nhola mundo",
        plain_text="hola mundo",
    )
    yield win
    win.close()


# ── Translate → speakable document ───────────────────────────────────────────


def test_translation_opens_as_a_document(window, monkeypatch):
    """A completed translation becomes the live, in-memory document — so the
    reader's speech/nav features work on it — instead of a read-only pane."""
    loaded = {}
    # _on_doc_loaded is the real "make this the live doc" path; spy it.
    monkeypatch.setattr(
        window, "_on_doc_loaded", lambda: loaded.setdefault("doc", window._pending_doc)
    )
    window._translate_lang = "French"
    window._translate_src_title = "Orig"
    window._translate_truncated = False

    window._qt_on_translation("bonjour le monde", "")

    doc = loaded.get("doc")
    assert doc is not None, "translation did not open as a document"
    assert doc.plain_text == "bonjour le monde"      # speakable text, verbatim
    assert doc.path == ""                            # in-memory → not in recents
    assert "translated to French" in doc.title
    assert doc.format == "translation"


def test_translation_error_is_surfaced_not_swallowed(window, monkeypatch):
    seen = {}
    monkeypatch.setattr(window, "_status_error", lambda m: seen.setdefault("err", m))
    monkeypatch.setattr(window, "_on_doc_loaded", lambda: seen.setdefault("loaded", True))
    window._qt_on_translation("", "network down")
    assert "network down" in seen.get("err", "")
    assert "loaded" not in seen  # a failed translation must not replace the doc


def test_translate_picker_kicks_off_with_language(window, monkeypatch):
    """The menu command asks only for a target language, then translates."""
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(window, "_qt_require_optional_feature", lambda *a: True)
    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: ("French", True))
    )
    calls = {}
    monkeypatch.setattr(
        window, "_qt_do_translate", lambda code, name: calls.update(code=code, name=name)
    )
    window._qt_translate()
    assert calls.get("name") == "French" and calls.get("code") == "fr"


# ── Dictate → start/stop, no fixed seconds ───────────────────────────────────


class _FakeRecorder:
    instances = []

    def __init__(self, *a, **k):
        self.started = self.stopped = self.cancelled = False
        self.elapsed = 3.0
        _FakeRecorder.instances.append(self)

    def start(self):
        self.started = True

    def stop_samples(self):
        self.stopped = True
        return [1, 2, 3]  # non-empty "audio" so transcription runs

    def cancel(self):
        self.cancelled = True


def _patch_dictate(window, monkeypatch, accepted, transcript="hello note"):
    import star.gui.mixin_transcription as mod
    from PyQt6.QtWidgets import QDialog

    _FakeRecorder.instances = []
    monkeypatch.setattr(mod, "StreamRecorder", _FakeRecorder)
    # Dictation transcribes the samples directly (no WAV / ffmpeg).
    monkeypatch.setattr(mod, "_transcribe_samples", lambda *a, **k: transcript)
    monkeypatch.setattr(window, "_qt_require_optional_feature", lambda *a: True)
    monkeypatch.setattr(window, "_qt_current_anchor", lambda: (0, "anchor"))
    # Don't block on a modal; simulate the user's Stop (accept) or Cancel.
    monkeypatch.setattr(
        QDialog, "exec",
        lambda self: (QDialog.DialogCode.Accepted if accepted
                      else QDialog.DialogCode.Rejected),
        raising=False,
    )


def test_dictate_records_until_stop_then_transcribes(window, monkeypatch):
    """No seconds prompt: start recorder → user Stops → transcribe once."""
    _patch_dictate(window, monkeypatch, accepted=True)
    dictated = {}
    monkeypatch.setattr(
        window, "_dictate_signal",
        type("S", (), {"emit": lambda _s, *a: dictated.update(args=a)})(),
    )
    window._qt_dictate_note()
    # The transcription runs on a daemon thread; wait briefly for the emit.
    import time
    for _ in range(50):
        if dictated.get("args"):
            break
        time.sleep(0.05)
    rec = _FakeRecorder.instances[0]
    assert rec.started and rec.stopped and not rec.cancelled
    assert dictated["args"][0] == "hello note"   # transcript flows to the note


def test_dictate_cancel_discards_recording(window, monkeypatch):
    _patch_dictate(window, monkeypatch, accepted=False)
    emitted = {}
    monkeypatch.setattr(
        window, "_dictate_signal",
        type("S", (), {"emit": lambda _s, *a: emitted.update(args=a)})(),
    )
    window._qt_dictate_note()
    rec = _FakeRecorder.instances[0]
    assert rec.started and rec.cancelled and not rec.stopped
    assert "args" not in emitted  # nothing transcribed / added on cancel


@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed (audio extra)")
def test_transcribe_samples_needs_no_ffmpeg(monkeypatch):
    """Dictation transcribes an in-memory array — Whisper gets a float32
    ndarray, so no WAV is written and no ffmpeg subprocess is spawned (which
    would flash a console window in the windowed exe)."""
    import numpy as np

    import star.transcribe as t

    captured = {}

    def _fake_transcribe(audio):
        captured["audio"] = audio
        return {"text": " hi "}

    monkeypatch.setattr(t, "_WHISPER", "openai")
    monkeypatch.setattr(
        t, "_load_whisper",
        lambda: type("W", (), {"load_model": staticmethod(
            lambda _m: type("M", (), {"transcribe": staticmethod(_fake_transcribe)})()
        )})(),
    )
    out = t._transcribe_samples(np.array([16384, -16384], dtype="int16"), "base")
    assert out == "hi"
    a = captured["audio"]
    assert a.dtype == np.float32 and abs(a[0] - 0.5) < 1e-3  # int16 → [-1,1]
