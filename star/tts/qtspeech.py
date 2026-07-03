"""QtSpeechBackend (system TTS via Qt's QTextToSpeech).

Qt ships a cross-platform speech synthesis API — ``QTextToSpeech`` — that
drives the platform's native engine (WinRT / SAPI on Windows,
``NSSpeechSynthesizer`` / AVSpeech on macOS, speech-dispatcher / Flite on
Linux).  It is bundled with the same PyQt6 wheel star already depends on for
the GUI, so it needs no extra native library or Python package, and — unlike
the ``pyttsx3`` SAPI5 path — it delivers real per-word boundary events
(``sayingWord``) that carry the exact character offset of each spoken word,
which the reading highlight can follow precisely.

Threading
---------
``QTextToSpeech`` is **signal-based and asynchronous**: :meth:`speak` returns
immediately and the ``sayingWord`` / ``stateChanged`` signals are delivered on
the thread whose ``QApplication`` event loop owns the object.  The object must
therefore be created and driven on the GUI main thread, which is exactly where
:meth:`TTSManager.speak` invokes the active backend in the Qt GUI.  If no
``QApplication`` / event loop is running (e.g. the TUI or a plain script),
``say()`` produces no signals and speech never starts; :meth:`speak` detects
that case and degrades cleanly by firing ``on_done`` synchronously instead of
hanging.
"""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


def _load_qt_speech():
    """Import and return the ``QTextToSpeech`` class, or ``None``.

    The import is lazy and fully defensive: the ``QtTextToSpeech`` submodule is
    a separate ``.pyd``/``.so`` inside the PyQt6 wheel and may be absent on a
    trimmed install, so a failure here must never break importing this module.
    """
    try:
        from PyQt6.QtTextToSpeech import QTextToSpeech

        return QTextToSpeech
    except Exception:
        try:
            from PyQt5.QtTextToSpeech import QTextToSpeech  # type: ignore

            return QTextToSpeech
        except Exception:
            return None


def _load_qapp():
    """Return the ``QApplication`` class, or ``None`` if Qt widgets are absent."""
    try:
        from PyQt6.QtWidgets import QApplication

        return QApplication
    except Exception:
        try:
            from PyQt5.QtWidgets import QApplication  # type: ignore

            return QApplication
        except Exception:
            return None


# Rate mapping: star exposes speech rate as words-per-minute; QTextToSpeech
# expresses it as a float in [-1, 1] where 0 is the engine's normal speed.
# We centre the star default (~200 wpm) on 0.0 and clamp the usable range to
# roughly 50–400 wpm so a slider extreme maps to the Qt extreme.
_WPM_MIN = 50.0
_WPM_DEFAULT = 200.0
_WPM_MAX = 400.0


def _wpm_to_rate(wpm: float) -> float:
    """Map words-per-minute (~50..400, default ~200) to QTextToSpeech rate.

    Returns a float in ``[-1.0, 1.0]``: the default rate maps to ``0.0``,
    ``_WPM_MIN`` to ``-1.0`` and ``_WPM_MAX`` to ``1.0``, with a piecewise
    linear ramp on either side of the default so the whole slider range is
    usable.  Kept a module-level pure function so it can be unit-tested without
    constructing a Qt engine.
    """
    try:
        w = float(wpm)
    except (TypeError, ValueError):
        return 0.0
    if w <= _WPM_MIN:
        return -1.0
    if w >= _WPM_MAX:
        return 1.0
    if w <= _WPM_DEFAULT:
        # 50..200 → -1..0
        return (w - _WPM_DEFAULT) / (_WPM_DEFAULT - _WPM_MIN)
    # 200..400 → 0..1
    return (w - _WPM_DEFAULT) / (_WPM_MAX - _WPM_DEFAULT)


class QtSpeechBackend(TTSBackend):
    """System TTS driven through Qt's ``QTextToSpeech``.

    Available whenever the ``QtTextToSpeech`` module imports *and* the platform
    exposes at least one real synthesis engine (any engine other than Qt's
    built-in ``"mock"`` test engine).  The engine is created lazily on first
    use so merely constructing the backend — which the manager does while
    probing availability — never spins up a native voice.
    """

    name = "qtspeech"
    # Sits between the macOS ``say`` backend (30) and the in-process
    # libespeak-ng backend (40).  This is deliberately *after* the current auto
    # defaults (in-process DECtalk 10, pyttsx3 20), so adding this backend does
    # not change which engine ``auto`` selects on any existing platform; it is
    # only reached when those higher-priority engines are unavailable.
    priority = 35

    def __init__(self, rate: int = 200, volume: float = 1.0, voice: str = "") -> None:
        self._rate = int(rate)
        self._volume = max(0.0, min(1.0, float(volume)))
        self._voice = voice or ""
        self._engine: Any = None  # QTextToSpeech, built lazily
        self._on_done: Optional[Callable[[], None]] = None
        self._on_word: Optional[Callable[[int, int], None]] = None
        # True only while an utterance is in flight, so the stateChanged
        # handler can tell a real end-of-speech (Speaking → Ready) apart from
        # the idle Ready the engine reports before anything is spoken.
        self._active = False
        self._qtts = _load_qt_speech()

    # ── engine lifecycle ────────────────────────────────────────────────────

    @staticmethod
    def _real_engines(qtts: Any) -> List[str]:
        """Engine names excluding Qt's built-in ``"mock"`` test engine."""
        try:
            return [e for e in qtts.availableEngines() if e != "mock"]
        except Exception:
            return []

    def _ensure_engine(self) -> Any:
        """Build (once) and return the QTextToSpeech engine, or ``None``.

        Uses the platform default engine (``QTextToSpeech()`` with no name) so
        the OS picks its best available voice.  Requires a live
        ``QApplication`` — the object parents to it and its signals ride that
        event loop — so this returns ``None`` when no app exists.
        """
        if self._engine is not None:
            return self._engine
        if self._qtts is None:
            return None
        qapp = _load_qapp()
        if qapp is None or qapp.instance() is None:
            return None  # no event loop → signals would never fire
        try:
            eng = self._qtts()  # platform default engine
        except Exception:
            return None
        self._engine = eng
        self._apply_rate(eng)
        self._apply_volume(eng)
        if self._voice:
            self._apply_voice(eng, self._voice)
        try:
            eng.stateChanged.connect(self._on_state_changed)
            eng.sayingWord.connect(self._on_saying_word)
        except Exception:
            pass
        return eng

    def _apply_rate(self, eng: Any) -> None:
        try:
            eng.setRate(_wpm_to_rate(self._rate))
        except Exception:
            pass

    def _apply_volume(self, eng: Any) -> None:
        try:
            eng.setVolume(self._volume)
        except Exception:
            pass

    def _apply_voice(self, eng: Any, voice_id: str) -> None:
        """Select the available voice whose name matches *voice_id*."""
        try:
            for v in eng.availableVoices():
                if v.name() == voice_id:
                    eng.setVoice(v)
                    return
        except Exception:
            pass

    # ── Qt signal handlers ──────────────────────────────────────────────────

    def _on_saying_word(self, *args: Any) -> None:
        """Translate ``sayingWord(word, id, start, length)`` into ``on_word``.

        Star's highlighter is fed ``on_word(char_offset, char_length)`` — the
        same ``(location, length)`` convention every other backend uses (see
        ``Pyttsx3Backend`` and ``ESpeakBackend``) — where *char_offset* is
        relative to the text passed to :meth:`speak`.  ``sayingWord`` gives us
        exactly that pair as its last two arguments, so no arithmetic on the
        offsets is needed.  The signal's arity has varied across Qt versions,
        so the two trailing ints are read positionally and defensively.
        """
        cb = self._on_word
        if cb is None or len(args) < 2:
            return
        try:
            start = int(args[-2])
            length = int(args[-1])
        except (TypeError, ValueError):
            return
        try:
            cb(start, length)
        except Exception:
            pass

    def _on_state_changed(self, state: Any) -> None:
        """Fire ``on_done`` once speech finishes (state returns to Ready)."""
        if not self._active or self._qtts is None:
            return
        try:
            ready = self._qtts.State.Ready
            error = self._qtts.State.Error
        except Exception:
            return
        if state == ready or state == error:
            self._active = False
            done = self._on_done
            self._on_done = None
            self._on_word = None
            if done is not None:
                try:
                    done()
                except Exception:
                    pass

    # ── TTSBackend interface ────────────────────────────────────────────────

    def available(self) -> bool:
        """True iff QtTextToSpeech imports and a real (non-mock) engine exists."""
        if self._qtts is None:
            return False
        return bool(self._real_engines(self._qtts))

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        eng = self._ensure_engine()
        if eng is None:
            # No engine / no event loop: cannot speak asynchronously.  Degrade
            # cleanly so the caller's completion logic still runs.
            if on_done:
                on_done()
            return
        self._on_word = on_word
        self._on_done = on_done
        self._active = True
        try:
            eng.say(text)
        except Exception:
            self._active = False
            self._on_word = None
            self._on_done = None
            if on_done:
                on_done()

    def stop(self) -> None:
        # Drop callbacks first so the impending Speaking → Ready transition the
        # engine reports for the cancelled utterance does not fire on_done.
        self._active = False
        self._on_word = None
        self._on_done = None
        eng = self._engine
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass

    def set_rate(self, wpm: int) -> None:
        self._rate = int(wpm)
        if self._engine is not None:
            self._apply_rate(self._engine)

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, float(vol)))
        if self._engine is not None:
            self._apply_volume(self._engine)

    def set_voice(self, voice_id: str) -> None:
        """Select the ``availableVoices()`` entry whose name is *voice_id*."""
        self._voice = voice_id or ""
        if self._engine is not None and self._voice:
            self._apply_voice(self._engine, self._voice)

    def list_voices(self) -> List[Dict[str, str]]:
        """Enumerate installed system voices as ``{"id","name","lang"}`` dicts.

        Uses the running engine when one exists; otherwise a throwaway engine
        is built solely to read its voice list (and disposed immediately) so
        the voice picker works before playback has started.  ``id`` and
        ``name`` are both the voice's display name — ``QTextToSpeech`` selects
        voices by :class:`QVoice`, matched back by name in :meth:`set_voice`.
        """
        if self._qtts is None:
            return []
        eng = self._engine
        throwaway = None
        if eng is None:
            qapp = _load_qapp()
            if qapp is None or qapp.instance() is None:
                return []
            try:
                eng = throwaway = self._qtts()
            except Exception:
                return []
        voices: List[Dict[str, str]] = []
        try:
            for v in eng.availableVoices():
                try:
                    lang = v.locale().bcp47Name() or v.locale().name()
                except Exception:
                    lang = ""
                voices.append({"id": v.name(), "name": v.name(), "lang": lang})
        except Exception:
            voices = []
        if throwaway is not None:
            try:
                throwaway.deleteLater()
            except Exception:
                pass
        return voices

    @property
    def speaking(self) -> bool:
        eng = self._engine
        if eng is None or self._qtts is None:
            return False
        try:
            st = eng.state()
            return st in (self._qtts.State.Speaking, self._qtts.State.Synthesizing)
        except Exception:
            return False
