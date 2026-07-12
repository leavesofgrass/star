"""Tests for the TUI's speech-to-text + study-tool parity (sweep-4 items 3/4).

Follows the tests/test_tui_mixins.py pattern: compose the REAL mixins onto a
tiny fake app (no curses screen, no mic, no network) and exercise the flows —
M-x translate / summarize open their results as in-memory Documents through
_load_queue, dictate-note records until Enter and attaches the transcribed
note, and every background error lands in _bg_queue as a notify, never a
crash or a lost document.
"""
import importlib.util
import queue
import time

import pytest

from star.documents import Document

pytestmark = pytest.mark.skipif(
    not (importlib.util.find_spec("curses") or importlib.util.find_spec("_curses")),
    reason="curses not available",
)

from star.tui.mixin_annotations import AnnotationsMixin  # noqa: E402
from star.tui.mixin_docops import DocOpsMixin  # noqa: E402
from star.tui.mixin_transcription import TuiTranscriptionMixin  # noqa: E402
from star.tui.text import MX_COMMANDS  # noqa: E402


class _FakeSettings(dict):
    def get(self, k, d=None):  # dict.get, but also used via settings.get(...)
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


class _FakeTTS:
    def __init__(self, speaking=False):
        self.speaking = speaking
        self.current_word_idx = 5
        self.stopped = False

    def stop(self):
        self.stopped = True
        self.speaking = False


class _FakeScreen:
    """getch() replays a scripted key sequence (then Esc forever)."""

    def __init__(self, keys=()):
        self._keys = list(keys)

    def getch(self):
        return self._keys.pop(0) if self._keys else 27

    def getmaxyx(self):
        return (24, 80)


class _App(TuiTranscriptionMixin, DocOpsMixin, AnnotationsMixin):
    """Real mixins over minimal fake state."""

    def __init__(self, doc=None, keys=()):
        self.doc = doc
        self.rendered = []
        self.settings = _FakeSettings(annotations={})
        self.tts = _FakeTTS()
        self.scr = _FakeScreen(keys)
        self._load_queue = queue.Queue()
        self._bg_queue = queue.Queue()
        self._tts_paused_at_word = -1
        self.notices = []

    # surface fakes the mixins call
    def notify(self, msg, dur=4.0, error=False):
        self.notices.append((msg, error))

    def draw(self):
        pass

    def _tts_stop(self):
        self.tts.stop()

    def _current_word_for_nav(self):
        return 3

    def _enter_minibuffer(self, prompt, on_commit=None, completions=None, **kw):
        self.minibuffer = (prompt, on_commit, completions)


def _doc():
    d = Document(path="/tmp/b.md", title="Bio", markdown="# Bio\n\nhello world",
                 plain_text="hello world")
    d.word_map = [type("W", (), {"word": "hello", "disp_line": 0,
                                 "tts_offset": 0})()]
    return d


def _drain(app, timeout=3.0):
    """Wait for a background thread to queue something, then run/return it."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return app._load_queue.get_nowait(), None
        except queue.Empty:
            pass
        try:
            cb = app._bg_queue.get_nowait()
            cb()
            return None, cb
        except queue.Empty:
            time.sleep(0.02)
    raise AssertionError("background thread produced nothing")


# ── Palette advertising ──────────────────────────────────────────────────────


def test_palette_advertises_the_new_study_commands():
    for cmd in ("translate", "summarize", "dictate-note", "transcribe-file"):
        assert cmd in MX_COMMANDS


# ── Translate ────────────────────────────────────────────────────────────────


def test_tui_translate_opens_result_as_document(monkeypatch):
    import star.translate as t

    app = _App(doc=_doc())
    monkeypatch.setattr(t, "translate_text",
                        lambda text, target_lang, progress=None: "hola mundo")
    app._translate_pick("Spanish")
    doc, _ = _drain(app)
    assert doc is not None and doc.format == "translation"
    assert doc.plain_text == "hola mundo"
    assert doc.path == "" and "translated to Spanish" in doc.title


def test_tui_translate_error_notifies_and_keeps_document(monkeypatch):
    import star.translate as t

    app = _App(doc=_doc())

    def _boom(text, target_lang, progress=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(t, "translate_text", _boom)
    app._translate_pick("French")
    doc, cb = _drain(app)
    assert doc is None and cb is not None            # error went to _bg_queue…
    assert any("network down" in m for m, err in app.notices if err)
    assert app.doc.title == "Bio"                    # …and the doc survived


def test_tui_translate_rejects_unknown_language():
    app = _App(doc=_doc())
    app._translate_pick("Klingon")
    assert any("Unknown language" in m for m, err in app.notices if err)


def test_tui_translate_prompts_with_language_completions(monkeypatch):
    import star.tui.mixin_docops as mod

    app = _App(doc=_doc())
    monkeypatch.setattr(
        "star.translate._DEEP_TRANSLATOR", True, raising=False
    )
    app._translate_cmd("")
    prompt, _cb, completions = app.minibuffer
    assert "Translate to" in prompt
    assert completions and "Spanish" in completions
    assert mod is not None  # silence unused-import style checkers


# ── Summarize ────────────────────────────────────────────────────────────────


def test_tui_summarize_opens_result_as_document(monkeypatch):
    import star.summarize as s

    app = _App(doc=_doc())
    monkeypatch.setattr(s, "_SUMY", True)
    monkeypatch.setattr(s, "summarize_document",
                        lambda text, sentence_count=7: "the gist")
    app._summarize_cmd()
    doc, _ = _drain(app)
    assert doc is not None and doc.format == "summary"
    assert doc.plain_text == "the gist" and doc.path == ""


# ── Dictate note ─────────────────────────────────────────────────────────────


class _FakeRecorder:
    instances = []

    def __init__(self, *a, **k):
        self.started = self.stopped = self.cancelled = False
        self.elapsed = 1.0
        _FakeRecorder.instances.append(self)

    def start(self):
        self.started = True

    def stop_samples(self):
        self.stopped = True
        return [1, 2, 3]

    def cancel(self):
        self.cancelled = True


def _patch_dictate(monkeypatch, transcript="note text"):
    import star.tui.mixin_transcription as mod

    _FakeRecorder.instances = []
    monkeypatch.setattr(mod, "StreamRecorder", _FakeRecorder)
    monkeypatch.setattr(mod, "_transcribe_samples", lambda *a, **k: transcript)
    # The dictate gate detects the mic + backend FRESH (not the import-time
    # _AUDIO_IN / _WHISPER snapshots), so patch those detectors — otherwise the
    # command bails with "requires Whisper" wherever no backend is installed (CI).
    monkeypatch.setattr(mod, "_audio_in_now", lambda: True, raising=False)
    monkeypatch.setattr(mod, "_whisper_backend_now", lambda: "openai", raising=False)


def test_tui_dictate_records_until_enter_then_attaches_note(monkeypatch):
    _patch_dictate(monkeypatch)
    app = _App(doc=_doc(), keys=[10])  # Enter on the first tick
    app._dictate_note_cmd()
    rec = _FakeRecorder.instances[0]
    assert rec.started and rec.stopped and not rec.cancelled
    _doc_none, cb = _drain(app)
    assert cb is not None
    notes = app.settings["annotations"]["/tmp/b.md"]
    assert notes[0]["note"] == "note text"
    assert notes[0]["tags"] == ["dictated"]
    assert notes[0]["word_idx"] == 3  # anchored at the caret when Enter was hit


def test_tui_dictate_esc_cancels_without_transcribing(monkeypatch):
    _patch_dictate(monkeypatch)
    app = _App(doc=_doc(), keys=[27])  # Esc immediately
    app._dictate_note_cmd()
    rec = _FakeRecorder.instances[0]
    assert rec.started and rec.cancelled and not rec.stopped
    assert app._bg_queue.empty() and app._load_queue.empty()
    assert app.settings["annotations"] == {}


def test_tui_dictate_pauses_tts_first(monkeypatch):
    _patch_dictate(monkeypatch)
    app = _App(doc=_doc(), keys=[27])
    app.tts.speaking = True
    app._dictate_note_cmd()
    assert app.tts.stopped                     # voice off before the mic opened
    assert app._tts_paused_at_word == 5        # toggle resumes where it stopped
