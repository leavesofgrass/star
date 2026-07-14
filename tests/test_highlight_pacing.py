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
    time.sleep(1.0)
    mgr.stop()
    assert paints and max(paints) > 20, (
        f"highlight froze on a dead callback stream: {paints[:10]}"
    )


def test_no_callbacks_ever_free_runs(mgr):
    """SSML mode / non-event backends (_last_cb_word_idx == -1): the timer
    is the only mechanism and must advance freely — unchanged behavior."""
    paints = []
    mgr._last_cb_word_idx = -1
    mgr._last_cb_time = 0.0

    _run_timer(mgr, paints)
    time.sleep(1.0)
    mgr.stop()
    assert paints and max(paints) > 10


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
