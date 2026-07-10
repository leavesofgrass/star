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


class _FakeTTS:
    """Stand-in tts_manager: attributes as given, every method a no-op (the
    window fixture's close() still calls .stop() etc. during teardown)."""

    def __init__(self, speaking=False, current_word_idx=-1):
        self.speaking = speaking
        self.current_word_idx = current_word_idx
        self.last_cb_word_idx = -1  # read by _qt_current_word_for_nav

    def __getattr__(self, _name):
        return lambda *a, **k: None


def test_dictate_pauses_tts_before_the_mic_opens(window, monkeypatch):
    """If star is reading aloud when the user hits Dictate, the voice must be
    paused BEFORE recording starts — otherwise the mic picks up star's own
    speech and Whisper transcribes it into the note."""
    _patch_dictate(window, monkeypatch, accepted=False)  # cancel; pause is the point
    monkeypatch.setattr(
        window, "tts_manager",
        _FakeTTS(speaking=True, current_word_idx=42),
        raising=False,
    )
    calls = {}
    monkeypatch.setattr(
        window, "_tts_stop",
        lambda announce_state=True: calls.setdefault("announce", announce_state),
    )
    window._qt_dictate_note()
    assert calls.get("announce") is False        # paused via the toggle's quiet path
    assert window._tts_paused_at_word == 42      # Space resumes at the same word
    rec = _FakeRecorder.instances[0]
    assert rec.started                           # and recording did still start


# ── Auto-play on open (tts_auto_play, GUI parity with the TUI) ───────────────


def test_auto_play_starts_reading_from_the_top(window, monkeypatch):
    window._auto_play_pending = True
    monkeypatch.setattr(window, "tts_manager", _FakeTTS(), raising=False)
    monkeypatch.setattr(window, "_qt_current_word_for_nav", lambda: 0)
    started = {}
    monkeypatch.setattr(window, "_tts_play", lambda: started.setdefault("top", True))
    window._qt_maybe_auto_play()
    assert started.get("top")
    assert window._auto_play_pending is False


def test_auto_play_resumes_from_the_restored_position(window, monkeypatch):
    window._auto_play_pending = True
    monkeypatch.setattr(window, "tts_manager", _FakeTTS(), raising=False)
    monkeypatch.setattr(window, "_qt_current_word_for_nav", lambda: 7)
    played = {}
    monkeypatch.setattr(
        window, "_tts_play_from_word", lambda w: played.setdefault("word", w)
    )
    window._qt_maybe_auto_play()
    assert played.get("word") == 7


def test_auto_play_is_one_shot_and_off_by_default(window, monkeypatch):
    # Default: no pending flag → no playback call at all.
    called = {}
    monkeypatch.setattr(window, "_tts_play", lambda: called.setdefault("play", True))
    window._auto_play_pending = False
    window._qt_maybe_auto_play()
    assert "play" not in called


# ── _qt_on_dictated: the result handler, driven with its real emit shapes ────


def test_dictated_note_is_stored_with_the_dictated_tag(window):
    """Success shape: the note lands in the annotations store, anchored and
    tagged 'dictated' — the whole point of the feature."""
    window._qt_on_dictated("remember the mitochondria", "5", "hola mundo")
    items = window._qt_load_annotations()
    assert len(items) == 1
    note = items[0]
    assert note["note"] == "remember the mitochondria"
    assert note["tags"] == ["dictated"]
    assert note["char_pos"] == 5 and note["anchor"] == "hola mundo"


def test_dictation_error_shape_is_surfaced_not_stored(window):
    """Error shape ('', 'ERROR', <message>): the user hears what failed and
    no phantom annotation is created."""
    window._qt_on_dictated("", "ERROR", "model exploded")
    assert "model exploded" in window.statusBar().currentMessage()
    assert window._qt_load_annotations() == []


def test_dictation_empty_text_is_reported_not_stored(window):
    window._qt_on_dictated("", "5", "anchor")
    assert "no text" in window.statusBar().currentMessage().lower()
    assert window._qt_load_annotations() == []


# ── Voice typing: dictate INTO the document ──────────────────────────────────


def test_voice_typing_inserts_recognized_text_at_the_cursor(window):
    """The result handler inserts the recognized speech into the editor at the
    cursor (this is what makes it 'type into the document', not a note)."""
    window._qt_enter_edit_mode()          # editor becomes editable plain text
    window.editor.setPlainText("Hello")
    cur = window.editor.textCursor()
    cur.setPosition(len("Hello"))         # caret at end, after a non-space char
    window.editor.setTextCursor(cur)
    window._qt_vt_busy = True

    window._qt_on_voice_typed("world", "")

    text = window.editor.toPlainText()
    assert "Hello world " in text          # smart space inserted before "world"
    assert window._qt_vt_busy is False     # busy flag cleared for the next round


def test_voice_typing_error_is_surfaced_not_inserted(window):
    window._qt_enter_edit_mode()
    window.editor.setPlainText("keep me")
    window._qt_vt_busy = True
    window._qt_on_voice_typed("", "mic exploded")
    assert "mic exploded" in window.statusBar().currentMessage()
    assert window.editor.toPlainText() == "keep me"   # nothing inserted
    assert window._qt_vt_busy is False


def test_speech_errors_never_show_a_pip_command(window):
    """The 'no pip ever' promise: a backend RuntimeError that mentions pip is
    rewritten to a restart hint before it ever reaches the student."""
    pip_err = "Microphone capture requires sounddevice + numpy:\n  pip install sounddevice numpy"
    for phase in ("start", "result"):
        out = window._speech_failure_message(pip_err, phase)
        assert "pip" not in out.lower()
        assert "restart" in out.lower()
    # A real device error (no pip) still reaches the user in the start phase.
    dev = window._speech_failure_message("PortAudioError: no default device", "start")
    assert "pip" not in dev.lower() and "microphone" in dev.lower()


def test_voice_typing_result_pip_error_becomes_a_restart_hint(window):
    window._qt_enter_edit_mode()
    window._qt_vt_busy = True
    window._qt_on_voice_typed("", "Speech recognition requires Whisper:\n  pip install openai-whisper")
    msg = window.statusBar().currentMessage()
    assert "pip" not in msg.lower() and "restart" in msg.lower()


def test_voice_typing_toggle_is_ignored_while_transcribing(window, monkeypatch):
    """A toggle press while a transcription is still running must not start a
    second recorder — it just reminds the user to wait."""
    started = {"n": 0}
    monkeypatch.setattr(window, "_qt_voice_typing_start",
                        lambda: started.__setitem__("n", started["n"] + 1))
    window._qt_vt_busy = True
    window._qt_voice_typing_toggle()
    assert started["n"] == 0
    assert "transcrib" in window.statusBar().currentMessage().lower()


def test_voice_typing_menu_action_tracks_state(window):
    """The checkable menu item reflects whether recording is active."""
    window._qt_vt_active = True
    window._qt_vt_sync_action()
    assert window._qt_vt_action.isChecked() is True
    window._qt_vt_active = False
    window._qt_vt_sync_action()
    assert window._qt_vt_action.isChecked() is False


def test_voice_typing_toolbar_button_exists_and_tracks_state(window):
    """A visible, checkable toolbar button (for visual users) toggles its
    highlight with the recording state, in lockstep with the menu item."""
    tb = window._toolbar_actions.get("Voice Typing")
    assert tb is not None and tb.isCheckable()
    window._qt_vt_active = True
    window._qt_vt_sync_action()
    assert tb.isChecked() is True and window._qt_vt_action.isChecked() is True
    window._qt_vt_active = False
    window._qt_vt_sync_action()
    assert tb.isChecked() is False


def test_dictated_note_lands_on_the_dictated_doc_after_a_switch(window):
    """If the user opens a different document while Whisper runs, the note
    must be keyed to the document it was dictated on (captured at record
    time), not whichever one is open when the result arrives."""
    from star.documents import Document

    orig_key = window._annot_key()          # "/tmp/orig.md" from the fixture
    # User switches to another document mid-transcription.
    window.doc = Document(path="/tmp/other.md", title="Other",
                          markdown="# Other", plain_text="other text")
    # Result lands, carrying the ORIGINAL key + word index captured at record.
    window._qt_on_dictated("keep this", "5", "anchor", orig_key, "2")
    # Stored under the original document…
    assert [n["note"] for n in window._qt_load_annotations(orig_key)] == ["keep this"]
    # …and NOT under the document that happens to be open now.
    assert window._qt_load_annotations() == []


# ── Modal-on-closing-window guard (the suite-hang class) ─────────────────────


def test_queued_results_never_open_modals_on_a_closing_window(window, monkeypatch):
    """A background result (summary/definition/…) that lands after closeEvent
    must not open a modal dialog — offscreen there is nobody to dismiss it,
    which wedged the xdist GUI worker (the suite 'hang at 93%')."""
    from PyQt6.QtWidgets import QDialog, QMessageBox

    opened = []
    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append("dlg"),
                        raising=False)
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: opened.append("warn")))
    assert window._modal_ok()          # live window: modals allowed
    window.close()                     # closeEvent sets _closing
    assert not window._modal_ok()
    window._qt_on_summary("a summary", "")
    window._qt_on_summary("", "an error")
    window._qt_on_definition(None, "word", "")
    assert opened == []                # nothing modal after close


# ── StreamRecorder lifecycle (no mic, fake sounddevice) ──────────────────────


class _FakeStream:
    def __init__(self, samplerate, channels, dtype, callback):
        self.callback = callback
        self.started = self.stopped = self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


def _fake_recorder_env(monkeypatch):
    import star.transcribe as t

    holder = {}

    class _SD:
        @staticmethod
        def InputStream(**kw):
            holder["stream"] = _FakeStream(**kw)
            return holder["stream"]

    # StreamRecorder gates on the FRESH _audio_in_now() check (not the
    # import-time _AUDIO_IN snapshot), so patch that too — otherwise on a host
    # where sounddevice is pip-installed but unimportable (e.g. the CI full-fat
    # leg: numpy present, but no system libportaudio) the constructor raises and
    # these hermetic fake-stream tests fail for reasons unrelated to their logic.
    monkeypatch.setattr(t, "_AUDIO_IN", True)
    monkeypatch.setattr(t, "_audio_in_now", lambda: True)
    monkeypatch.setattr(t, "_load_sounddevice", lambda: _SD())
    return t, holder


@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed (audio extra)")
def test_stream_recorder_captures_blocks_until_stopped(monkeypatch):
    import numpy as np

    t, holder = _fake_recorder_env(monkeypatch)
    rec = t.StreamRecorder()
    rec.start()
    stream = holder["stream"]
    assert stream.started
    # Feed blocks the way sounddevice's audio thread would.
    stream.callback(np.array([[1], [2]], dtype="int16"), 2, None, None)
    stream.callback(np.array([[3]], dtype="int16"), 1, None, None)
    out = rec.stop_samples()
    assert stream.stopped and stream.closed          # mic released
    assert list(out.flatten()) == [1, 2, 3]          # blocks in order
    assert rec.stop_samples() is None                # idempotent second stop


@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed (audio extra)")
def test_stream_recorder_immediate_stop_returns_none(monkeypatch):
    t, _holder = _fake_recorder_env(monkeypatch)
    rec = t.StreamRecorder()
    rec.start()
    assert rec.stop_samples() is None  # no blocks arrived → "no audio"


@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed (audio extra)")
def test_stream_recorder_cancel_releases_the_mic_and_discards(monkeypatch):
    import numpy as np

    t, holder = _fake_recorder_env(monkeypatch)
    rec = t.StreamRecorder()
    rec.start()
    holder["stream"].callback(np.array([[9]], dtype="int16"), 1, None, None)
    rec.cancel()
    assert holder["stream"].closed     # mic is not left captured
    assert rec.stop_samples() is None  # recording discarded


def test_stream_recorder_refuses_without_audio_stack(monkeypatch):
    import star.transcribe as t

    # Availability is now checked FRESH (not the import-time _AUDIO_IN
    # snapshot), so a same-session install works and the GUI gate can never
    # disagree with the recorder.  Simulate the stack being unavailable.
    monkeypatch.setattr(t, "_audio_in_now", lambda: False)
    with pytest.raises(RuntimeError, match="sounddevice"):
        t.StreamRecorder()


def test_stream_recorder_available_check_is_fresh_not_stale(monkeypatch):
    """A stale import-time _AUDIO_IN=False must NOT block a recorder once the
    packages are actually importable — this is the bug that surfaced a raw
    'pip install' message after a same-session install."""
    import star.transcribe as t

    monkeypatch.setattr(t, "_AUDIO_IN", False)          # stale snapshot
    monkeypatch.setattr(t, "_module_available", lambda name: True)  # really present
    assert t._audio_in_now() is True                    # fresh check wins


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
