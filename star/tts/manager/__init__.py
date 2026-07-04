"""TTSManager — active backend selection + word-position tracking; _SCReader.

Package split of the former single-file ``star/tts/manager.py``.  ``TTSManager``
is assembled here from three cooperating mixins carved out **verbatim** — the
threading, the word-highlight timer's generation guards, and the SAPI5/eSpeak
pacing constants are byte-for-byte identical to the pre-split module:

* :class:`~star.tts.manager._selection.SelectionMixin` — active-backend and
  default/UI-language voice resolution.
* :class:`~star.tts.manager._playback.PlaybackMixin` — ``speak()``, the
  highlight timer, ``stop()``, and the small backend passthroughs.
* :class:`~star.tts.manager._export.ExportMixin` — Piper catalog helpers and
  WAV/audio/subtitle export.

The shared instance state (``self._timer_gen``, ``self._current_word_idx`` …)
is created by ``TTSManager.__init__`` below and lives on ``self`` exactly as
before; the mixins only supply behaviour.  ``_SCReader`` and the module
constant ``_LANG_NAME_TO_CODE`` keep their identity via re-export, so
``from star.tts.manager import TTSManager, _SCReader`` (and anything the old
flat module exposed) resolves unchanged.
"""
from ..._runtime import *  # noqa: F401,F403
from ...settings import Settings
from ..base import TTSBackend
from ..silent import SilentBackend
from ..pyttsx3 import Pyttsx3Backend
from ..espeak import ESpeakLibBackend
from ..cloud.base import CloudTTSError
from ..audio import _convert_audio_format
from ..subtitles import _generate_subtitles

from ._screader import _SCReader
from ._selection import SelectionMixin, _LANG_NAME_TO_CODE
from ._playback import PlaybackMixin
from ._export import ExportMixin


class TTSManager(SelectionMixin, PlaybackMixin, ExportMixin):
    """Manages the active TTS backend and word-position tracking."""

    #: Engine names never chosen in ``auto`` mode: piper/coqui need an explicit
    #: opt-in (downloaded model), and ``silent`` is the last-resort fallback.
    _AUTO_SKIP = frozenset({"silent", "piper", "coqui", "elevenlabs"})

    def __init__(self, settings: Settings):
        self._settings = settings
        self._backend: TTSBackend = SilentBackend()
        self._word_map: List["WordPos"] = []
        self._current_word_idx: int = -1
        self._on_highlight: Optional[Callable[[int], None]] = None  # callback(word_idx)
        self._on_done: Optional[Callable[[], None]] = None
        # One-shot, user-facing engine-failure note (e.g. a cloud voice dying
        # mid-session with HTTP 401 and being swapped for a local engine).
        # The UIs poll it on their status tick, show it once, and clear it.
        self.last_engine_error: str = ""
        self._timer_thread: Optional[threading.Thread] = None
        self._timer_stop = threading.Event()
        # Monotonically-increasing counter, incremented every time a new timer
        # thread is started.  Each _tick closure captures its own value so it
        # can detect that a newer timer has taken over and exit immediately.
        # This prevents multiple stale timers from calling _on_highlight
        # simultaneously, which caused the highlight to jump erratically.
        self._timer_gen: int = 0
        # Last word index confirmed by a pyttsx3 word-boundary callback.
        # -1 means no callback has fired yet for the current utterance
        # (either SSML mode where callbacks are skipped, or engine still
        # starting up).  The timer uses this to pace itself: it won't run
        # more than _MAX_AHEAD words ahead of the confirmed position.
        self._last_cb_word_idx: int = -1
        # Monotonic timestamp of the most recent pyttsx3 word callback.
        # 0.0 means no callback has fired for this utterance.  Used by the
        # timer's pacing guard: if no callback has arrived for longer than
        # _CB_TIMEOUT seconds the guard is bypassed so the highlight never
        # stalls while speech continues (SAPI5 callbacks can go silent).
        self._last_cb_time: float = 0.0
        # True only while the active backend emits real per-word events that
        # track audio progress (currently just pyttsx3's SAPI5 word callbacks;
        # eSpeak-NG's CLI does not emit mark events, so its marks cannot be
        # used as a signal here).  The highlight timer reads this to anchor its
        # first paint to the first real event (≈ audio onset) instead of to the
        # speak() call, which precedes audible output by the engine's start-up
        # latency and otherwise gives the highlight a constant head start.
        self._expect_callbacks: bool = False
        # True when the active backend paces its word callbacks to real audio
        # position (the in-process eSpeak-NG backend).  Those callbacks are
        # playback-accurate, so the highlight timer can track them tightly
        # instead of allowing the looser slack SAPI5's lagging callbacks need.
        self._paced_playback: bool = False
        # Preferred spoken-language tag (ISO-639-1, e.g. "es"), used to bias
        # automatic voice selection toward a voice that speaks the UI language.
        # Seeded from the persisted UI-language setting; the GUI/TUI can update
        # it live via set_language().  Empty string means "no preference"
        # (English/platform default), which is the historical behaviour.
        raw_lang = str(settings.get("ui_language", "") or "").strip().lower()
        self._pref_lang: str = "" if raw_lang in ("", "en") else raw_lang
        self._select_backend(settings["tts_backend"])


# Re-export surface.  Besides the two names ``star/tts/__init__.py`` imports
# (``TTSManager``, ``_SCReader``), the pre-split flat module also exposed these
# backend/helper symbols as module attributes (via its own top-level imports);
# they are kept here so ``star.tts.manager``'s public surface is unchanged and
# ``import *`` still rehydrates them.
__all__ = [
    "TTSManager",
    "_SCReader",
    "_LANG_NAME_TO_CODE",
    "Settings",
    "TTSBackend",
    "SilentBackend",
    "Pyttsx3Backend",
    "ESpeakLibBackend",
    "CloudTTSError",
    "_convert_audio_format",
    "_generate_subtitles",
]
