"""Direct unit tests for :mod:`star.tts.qtspeech` (the QtTextToSpeech backend).

The backend wraps Qt's ``QTextToSpeech``.  Qt ships a built-in ``"mock"``
engine that synthesizes no audio but still emits the real ``sayingWord`` and
``stateChanged`` signals, so these tests drive it headless (``offscreen``)
without any OS voice, sound card, or network.  Everything that does not need a
Qt object — the WPM→rate mapping and ``available()`` gating — is tested purely.

The suite skips gracefully when the ``QtTextToSpeech`` module or its ``"mock"``
engine is unavailable (e.g. a PyQt build without the speech plugin), and it
disposes every QTextToSpeech object it creates so no timer or native handle is
left running into Qt teardown.
"""
import os

import pytest

# Force headless Qt before any Qt import so the platform plugin never needs a
# display; matches how the rest of the Qt-touching tests run under CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from star.tts.qtspeech import (  # noqa: E402
    QtSpeechBackend,
    _wpm_to_rate,
)


# ── Qt availability probe ────────────────────────────────────────────────────


def _load_qtts():
    """Return the QTextToSpeech class, or ``None`` when it cannot be imported."""
    try:
        from PyQt6.QtTextToSpeech import QTextToSpeech

        return QTextToSpeech
    except Exception:
        try:
            from PyQt5.QtTextToSpeech import QTextToSpeech  # type: ignore

            return QTextToSpeech
        except Exception:
            return None


_QTTS = _load_qtts()
_HAVE_MOCK = bool(_QTTS is not None and "mock" in (_QTTS.availableEngines() or []))

requires_mock = pytest.mark.skipif(
    not _HAVE_MOCK,
    reason="QtTextToSpeech module or its built-in 'mock' engine is unavailable",
)


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the module (Qt permits only one per process)."""
    if _QTTS is None:
        pytest.skip("QtTextToSpeech unavailable")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def mock_backend(qapp):
    """A QtSpeechBackend whose engine is forced to Qt's ``mock`` engine.

    Wiring the mock engine into a real backend instance exercises the backend's
    own signal handlers (``_on_saying_word`` / ``_on_state_changed``) rather
    than re-implementing them.  The engine is disposed on teardown.
    """
    if not _HAVE_MOCK:
        pytest.skip("mock engine unavailable")
    b = QtSpeechBackend()
    eng = _QTTS("mock")
    b._engine = eng
    eng.stateChanged.connect(b._on_state_changed)
    eng.sayingWord.connect(b._on_saying_word)
    try:
        yield b
    finally:
        try:
            eng.stop()
        except Exception:
            pass
        b._engine = None
        eng.deleteLater()
        qapp.processEvents()


def _pump(app, predicate, timeout_ms=4000):
    """Spin the Qt event loop until *predicate()* is true or *timeout_ms* passes."""
    from PyQt6.QtCore import QDeadlineTimer, QEventLoop

    loop = QEventLoop()
    deadline = QDeadlineTimer(timeout_ms)
    while not predicate() and not deadline.hasExpired():
        loop.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    return predicate()


# ── pure logic: WPM → rate mapping ───────────────────────────────────────────


def test_wpm_to_rate_default_is_zero():
    assert _wpm_to_rate(200) == 0.0


def test_wpm_to_rate_extremes_clamp_to_unit_range():
    assert _wpm_to_rate(50) == -1.0
    assert _wpm_to_rate(400) == 1.0
    # Beyond the range still clamps, never exceeds [-1, 1].
    assert _wpm_to_rate(10) == -1.0
    assert _wpm_to_rate(1000) == 1.0


def test_wpm_to_rate_is_monotonic_and_bounded():
    prev = -2.0
    for wpm in range(40, 420, 5):
        r = _wpm_to_rate(wpm)
        assert -1.0 <= r <= 1.0
        assert r >= prev  # non-decreasing across the whole slider range
        prev = r


def test_wpm_to_rate_midpoints():
    # 125 wpm is halfway between 50 and 200 → halfway between -1 and 0.
    assert _wpm_to_rate(125) == pytest.approx(-0.5)
    # 300 wpm is halfway between 200 and 400 → halfway between 0 and 1.
    assert _wpm_to_rate(300) == pytest.approx(0.5)


def test_wpm_to_rate_bad_input_is_neutral():
    assert _wpm_to_rate("nope") == 0.0
    assert _wpm_to_rate(None) == 0.0


# ── available() gating ───────────────────────────────────────────────────────


def test_available_false_without_qtts():
    """When the QtTextToSpeech import failed, the backend reports unavailable."""
    b = QtSpeechBackend()
    b._qtts = None
    assert b.available() is False


@requires_mock
def test_available_ignores_mock_only(qapp):
    """A stub whose *only* engine is ``mock`` must not count as available."""

    class _MockOnly:
        State = _QTTS.State

        @staticmethod
        def availableEngines():
            return ["mock"]

    b = QtSpeechBackend()
    b._qtts = _MockOnly
    assert b.available() is False


@requires_mock
def test_available_true_with_real_engine(qapp):
    """A stub reporting a real (non-mock) engine counts as available."""

    class _WithReal:
        State = _QTTS.State

        @staticmethod
        def availableEngines():
            return ["mock", "sapi"]

    b = QtSpeechBackend()
    b._qtts = _WithReal
    assert b.available() is True


# ── metadata ─────────────────────────────────────────────────────────────────


def test_name_and_priority_do_not_displace_defaults():
    # Must not out-rank the current auto defaults (dectalk 10, pyttsx3 20).
    assert QtSpeechBackend.name == "qtspeech"
    assert QtSpeechBackend.priority > 20


# ── list_voices ──────────────────────────────────────────────────────────────


@requires_mock
def test_list_voices_from_running_engine(mock_backend):
    voices = mock_backend.list_voices()
    assert voices, "mock engine should expose at least one voice"
    for v in voices:
        assert set(v) == {"id", "name", "lang"}
        assert v["id"] and v["name"]
    names = {v["name"] for v in voices}
    # Qt's mock engine ships the fixed voices "Bob" and "Anne".
    assert "Bob" in names


# ── speak() drives on_word / on_done via the mock engine ─────────────────────


@requires_mock
def test_speak_emits_word_offsets_and_done(mock_backend, qapp):
    words = []
    done = []
    mock_backend.speak(
        "Hello world foo",
        on_word=lambda start, length: words.append((start, length)),
        on_done=lambda: done.append(True),
    )
    assert _pump(qapp, lambda: bool(done)), "on_done never fired"

    # on_word must use the (char_offset, length) convention every backend uses.
    assert words == [(0, 5), (6, 5), (12, 3)]
    assert done == [True]
    # State has returned to Ready → not speaking.
    assert mock_backend.speaking is False


@requires_mock
def test_stop_suppresses_pending_on_done(mock_backend, qapp):
    done = []
    mock_backend.speak("Hello world foo", on_done=lambda: done.append(True))
    mock_backend.stop()
    qapp.processEvents()
    # Cancelling before completion must not fire on_done.
    assert done == []


@requires_mock
def test_speak_replaces_previous_callbacks(mock_backend, qapp):
    """A second speak() must not fire the first utterance's on_done."""
    first_done = []
    second_done = []
    mock_backend.speak("first utterance here", on_done=lambda: first_done.append(True))
    mock_backend.speak("second utterance now", on_done=lambda: second_done.append(True))
    assert _pump(qapp, lambda: bool(second_done)), "second on_done never fired"
    assert first_done == []
    assert second_done == [True]


# ── no-event-loop degradation ────────────────────────────────────────────────


def test_speak_without_engine_calls_on_done():
    """With no engine available, speak() must still fire on_done (never hang)."""
    b = QtSpeechBackend()
    b._qtts = None  # guarantees _ensure_engine() returns None
    done = []
    b.speak("anything", on_done=lambda: done.append(True))
    assert done == [True]


def test_stop_is_safe_before_any_speak():
    b = QtSpeechBackend()
    b._qtts = None
    b.stop()  # must not raise even though no engine was ever built
