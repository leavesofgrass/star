"""The highlight timer's pacing guard must track engine truth, not run away.

Drives ``PlaybackMixin._start_timer_highlight`` directly with simulated
callback state (no audio engine, no Qt).  Pins the three regimes the guard
now implements — clamp-to-truth while callbacks are fresh, hold during a
mid-utterance pause, free-run only when the callback stream is genuinely
dead — and the always-recorded callback position that feeds them.

The old behavior failed two ways Jon hit while reading: (1) callback
positions were only recorded when at/ahead of the timer estimate, so once
the timer crept ahead every accurate callback was discarded and the guard
starved; (2) the guard then free-ran after only 1.5 s of silence, so every
heading/paragraph pause sent the highlight sprinting ahead with nothing to
pull it back.
"""
import threading
import time

import pytest

from star.settings import Settings
from star.tts import TTSManager


@pytest.fixture
def mgr():
    settings = Settings()
    settings._data["tts_backend"] = "silent"
    settings._data["tts_rate"] = 1200  # 50 ms timer ticks — fast tests
    settings._data["highlight_speed"] = 1.0
    m = TTSManager(settings)
    m.set_word_map(list(range(400)))  # timer only needs len()
    yield m
    m.stop()


def _run_timer(mgr, paints, start_idx=0):
    mgr.set_on_highlight(lambda idx: paints.append(idx))
    mgr._timer_gen += 1
    mgr._timer_stop.set()
    mgr._expect_callbacks = False  # skip the first-audio anchor wait
    mgr._paced_playback = False    # _MAX_AHEAD = 4
    mgr._start_timer_highlight(start_idx)


def test_overshot_estimate_clamps_back_to_engine_truth(mgr):
    """Timer estimate far ahead + fresh callbacks: the next paints must come
    back down to (confirmed audio + 4), not stay ahead forever."""
    paints = []
    mgr._current_word_idx = 60          # the estimate raced ahead
    mgr._last_cb_word_idx = 20          # …but the engine says word 20
    mgr._last_cb_time = time.monotonic()

    stop = threading.Event()

    def engine():  # keep confirming ~word 20 like a real callback stream
        while not stop.is_set():
            mgr._last_cb_word_idx = 20
            mgr._last_cb_time = time.monotonic()
            time.sleep(0.03)

    t = threading.Thread(target=engine, daemon=True)
    t.start()
    _run_timer(mgr, paints)
    time.sleep(0.8)
    stop.set()
    mgr.stop()
    assert paints, "timer painted nothing"
    # Fresh callbacks clamp the paint to the confirmed word itself (+1 of
    # slack for the tick/engine-thread race).
    assert max(paints) <= 21, f"highlight stayed ahead of audio: {paints[:10]}"


def test_pause_holds_instead_of_running_away(mgr):
    """Callbacks stop mid-utterance (a heading/paragraph pause): the timer
    holds near the last confirmed word instead of sprinting ahead."""
    paints = []
    mgr._current_word_idx = 10
    mgr._last_cb_word_idx = 10
    mgr._last_cb_time = time.monotonic()  # last event just fired, then silence

    _run_timer(mgr, paints, start_idx=10)
    time.sleep(2.5)  # well past the old 1.5 s runaway threshold
    mgr.stop()
    assert paints, "timer painted nothing"
    assert max(paints) <= 14, (
        f"highlight ran away during a pause: reached {max(paints)}"
    )


def test_dead_callback_stream_still_free_runs(mgr):
    """A backend that stops firing events entirely must not freeze the
    highlight: after _CB_DEAD the timer advances again."""
    paints = []
    mgr._current_word_idx = 10
    mgr._last_cb_word_idx = 10
    mgr._last_cb_time = time.monotonic() - 10.0  # stream long dead

    _run_timer(mgr, paints, start_idx=10)
    time.sleep(1.5)
    mgr.stop()
    # The property under test is breaking PAST the pause hold cap
    # (last_cb + 4 = 14) — not any particular speed: slow CI runners tick
    # the 50 ms timer at 2x+ the nominal interval.
    assert paints and max(paints) > 14, (
        f"highlight froze on a dead callback stream: {paints[:10]}"
    )


def test_no_callbacks_ever_free_runs(mgr):
    """SSML mode / non-event backends (_last_cb_word_idx == -1): the timer
    is the only mechanism and must advance freely — unchanged behavior."""
    paints = []
    mgr._last_cb_word_idx = -1
    mgr._last_cb_time = 0.0

    _run_timer(mgr, paints)
    time.sleep(1.5)
    mgr.stop()
    assert paints and max(paints) > 5  # advancing; loose for slow CI runners


def test_word_callback_always_records_engine_position(mgr):
    """on_word_cb must record the confirmed position even when it is BEHIND
    the shared estimate — recording only forward positions was the guard
    starvation that made runaways permanent."""
    recorded = {}

    from star.documents import _build_word_map
    from star.tts.pyttsx3 import Pyttsx3Backend

    plain = "alpha beta gamma delta epsilon zeta eta theta"
    mgr.set_word_map(_build_word_map(plain, [plain]))
    # A real Pyttsx3Backend (so manager.speak wires the word callback), with
    # its speak instance-patched to capture the callback and drive no engine.
    backend = Pyttsx3Backend()
    backend.speak = lambda text, on_word=None, on_done=None: recorded.update(
        on_word=on_word
    )
    mgr._backend = backend

    mgr.speak(plain, start_word_idx=0, text_offset=0)
    on_word = recorded["on_word"]
    mgr._timer_stop.set()  # freeze the timer; we drive state by hand

    mgr._current_word_idx = 6            # estimate far ahead
    on_word(plain.index("beta"), 4)      # engine is actually at word 1
    assert mgr._last_cb_word_idx == 1    # recorded (old code discarded it)
    assert mgr._current_word_idx == 6    # estimate not snapped backward here
    mgr.stop()


# ---------------------------------------------------------------------------
# Word callbacks by capability, and the event → word lookup
# ---------------------------------------------------------------------------

# The built-in backends whose speak() really calls on_word.  A new entry here
# is a deliberate decision: the manager wires on_word for exactly these.
_EMITTING_BUILTINS = {
    "EloquenceBackend",
    "QtSpeechBackend",
    "Pyttsx3Backend",
    "ESpeakLibBackend",
}


def test_builtin_backends_declare_word_events_as_documented():
    from star.plugins import PluginRegistry

    builtins = [
        cls for cls in PluginRegistry.get().backends
        if cls.__module__.startswith("star.")
    ]
    names = {cls.__name__ for cls in builtins}
    assert _EMITTING_BUILTINS <= names, "a word-event backend is not registered"
    declared = {cls.__name__ for cls in builtins if cls.emits_word_events}
    assert declared == _EMITTING_BUILTINS


def test_speak_wires_on_word_for_exactly_the_backends_that_declare_it(mgr):
    """speak() hands on_word to a backend iff it declares emits_word_events.

    Every registered built-in is tried with its __init__ skipped and its
    speak/stop replaced, so no engine is ever reached.
    """
    from star.plugins import PluginRegistry

    tried = 0
    for cls in PluginRegistry.get().backends:
        if not cls.__module__.startswith("star."):
            continue
        calls = []
        inst = cls.__new__(cls)
        inst.speak = lambda text, on_word=None, on_done=None, _c=calls: _c.append(
            on_word
        )
        inst.stop = lambda: None
        mgr._backend = inst
        mgr.speak("alpha beta", start_word_idx=0, text_offset=0)
        mgr.stop()
        assert len(calls) == 1, cls.__name__
        wired = calls[0] is not None
        assert wired == cls.emits_word_events, cls.__name__
        assert mgr._expect_callbacks == cls.emits_word_events, cls.__name__
        tried += 1
    assert tried >= len(_EMITTING_BUILTINS)


def test_word_lookup_takes_the_first_word_the_event_intersects():
    """Eloquence speaks whitespace tokens, so leading punctuation is part of
    the event's span; the event must still land on its word.  The old point
    rule (event start inside a word, or one past its end) dropped '"Hello"'
    because its quote sits in the gap before the word."""
    from star.documents import _build_word_map
    from star.tts.eloquence import _split_words
    from star.tts.manager._playback import _word_index_for_event

    plain = 'He said "Hello" to Dr. Smith at 3:45 p.m.'
    wm = _build_word_map(plain, [plain])
    found = [
        wm[_word_index_for_event(wm, off, len(tok))].word
        for tok, off in _split_words(plain)
    ]
    assert found == ["He", "said", "Hello", "to", "Dr", "Smith", "at", "3", "p"]


def test_word_lookup_keeps_the_gap_rule_and_rejects_strays():
    from star.documents import _build_word_map
    from star.tts.manager._playback import _word_index_for_event

    plain = "alpha  beta"
    wm = _build_word_map(plain, [plain])
    assert _word_index_for_event(wm, 0, 5) == 0
    assert _word_index_for_event(wm, 5, 0) == 0   # one past "alpha": still alpha
    assert _word_index_for_event(wm, 6, 0) == -1  # inside the gap: no word
    assert _word_index_for_event(wm, 6, 5) == 1   # a span reaching into beta
    assert _word_index_for_event(wm, 40, 3) == -1  # past the end
    assert _word_index_for_event([], 0, 1) == -1


def test_eloquence_word_events_reach_the_manager(mgr):
    """The Eloquence backend's on_word now feeds the confirmed position."""
    from star.documents import _build_word_map
    from star.tts.eloquence import EloquenceBackend

    plain = 'Read "this" now'
    mgr.set_word_map(_build_word_map(plain, [plain]))
    recorded = {}
    backend = EloquenceBackend.__new__(EloquenceBackend)
    backend.speak = lambda text, on_word=None, on_done=None: recorded.update(
        on_word=on_word
    )
    backend.stop = lambda: None
    mgr._backend = backend
    mgr.speak(plain, start_word_idx=0, text_offset=0)
    mgr._timer_stop.set()
    assert mgr._paced_playback is True
    recorded["on_word"](plain.index('"this"'), len('"this"'))
    assert mgr._last_cb_word_idx == 1
    mgr.stop()
