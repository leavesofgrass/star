"""Pyttsx3Backend (system TTS: SAPI5 / NSSpeech / eSpeak)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


class Pyttsx3Backend(TTSBackend):
    """pyttsx3 backend — uses SAPI5 (Windows), NSSpeechSynthesizer (macOS),
    or eSpeak-NG (Linux) via the pyttsx3 wrapper.

    Windows/SAPI5 note: calling engine.stop() corrupts the engine's internal
    state so that subsequent say() + runAndWait() calls are silently dropped.
    The fix is to create a *fresh* pyttsx3.init() engine inside every speech
    thread — each call is entirely self-contained.  The active engine is
    stored in self._active_engine so stop() can interrupt it at any time.
    """

    name = "pyttsx3"
    priority = 20

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = ""):
        self._rate = rate
        self._volume = volume
        self._voice = voice
        self._thread: Optional[threading.Thread] = None
        self._speaking = False
        self._stop_requested = False
        # Monotonically-increasing counter incremented on every speak() call.
        # Each _run closure captures the value at launch time; only the thread
        # whose generation matches the current counter is allowed to write
        # _speaking=False.  This prevents an old thread's finally-block from
        # overwriting the True set by a newer speak() call (Windows race).
        self._gen: int = 0
        # Reference to the engine currently being used by the speech thread.
        # Stored so stop() can call engine.stop() on the right object.
        self._active_engine = None
        self._available = self._probe()

    def _probe(self) -> bool:
        """Check once at startup that pyttsx3 can create an engine."""
        if not _PYTTSX3:
            return False
        try:
            eng = _load_pyttsx3().Engine()
            eng.stop()
            return True
        except Exception:
            return False

    def _make_engine(self):
        """Create and configure a brand-new pyttsx3 engine.

        We call ``pyttsx3.Engine()`` directly instead of ``pyttsx3.init()``.
        ``init()`` caches the engine in a WeakValueDictionary and returns the
        same object on every call as long as any thread still holds a strong
        reference to it.  After a ``stop()``-while-speaking the cached engine
        has corrupted SAPI5 internal state and silently drops every subsequent
        ``say()`` + ``runAndWait()`` call on Windows.  ``Engine()`` constructs
        a fresh COM object unconditionally and never touches the cache, so each
        speech session always gets a clean SAPI5 voice.
        """
        eng = _load_pyttsx3().Engine()
        eng.setProperty("rate", self._rate)
        eng.setProperty("volume", self._volume)
        if self._voice:
            try:
                eng.setProperty("voice", self._voice)
            except Exception:
                pass
        return eng

    def available(self) -> bool:
        return self._available

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        if not self._available:
            if on_done:
                on_done()
            return

        # Signal any running thread to stop, then clear the flag for the new one.
        self._stop_requested = True
        self._speaking = False
        if self._active_engine is not None:
            try:
                self._active_engine.stop()
            except Exception:
                pass
            self._active_engine = None

        self._stop_requested = False
        self._gen += 1
        my_gen = self._gen
        self._speaking = True

        def _run() -> None:
            eng = None
            try:
                eng = self._make_engine()
                self._active_engine = eng  # expose to stop()

                if on_word is not None:
                    # Wrap in a guard so a bad callback never kills the engine.
                    def _word_cb(name: str, location: int, length: int) -> None:
                        try:
                            if not self._stop_requested:
                                on_word(location, length)
                        except Exception:
                            pass

                    eng.connect("started-word", _word_cb)

                eng.say(text)
                if not self._stop_requested:
                    eng.runAndWait()
            except Exception:
                pass
            finally:
                # Do NOT unconditionally clear self._active_engine here.
                # A newer speak() call may have already stored its own engine
                # in self._active_engine; clearing it would prevent stop()
                # from being able to interrupt that newer engine (Bug A:
                # Space stops setting _active_engine to None, so pause breaks).
                # Ownership of _active_engine is managed exclusively by
                # stop() and the top of speak().
                if self._active_engine is eng:
                    # Only clear if it's still *our* engine — no newer thread
                    # has replaced it yet.
                    self._active_engine = None
                # Stop our local engine object (no-op if already stopped).
                if eng is not None:
                    try:
                        eng.stop()
                    except Exception:
                        pass
                # Only the most-recently launched thread may clear _speaking
                # or fire on_done.  An older thread whose generation no longer
                # matches must not overwrite the True set by a newer speak()
                # call, and must not fire on_done (which would set
                # _current_word_idx=-1 and stop the newer thread's timer,
                # making replay always jump to word 0 — Bug B).
                if self._gen == my_gen:
                    self._speaking = False
                    if on_done is not None and not self._stop_requested:
                        on_done()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested = True
        self._speaking = False
        eng = self._active_engine
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass
            self._active_engine = None

    def set_rate(self, wpm: int) -> None:
        self._rate = wpm
        eng = self._active_engine
        if eng is not None:
            try:
                eng.setProperty("rate", wpm)
            except Exception:
                pass

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        eng = self._active_engine
        if eng is not None:
            try:
                eng.setProperty("volume", self._volume)
            except Exception:
                pass

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        if not self._available:
            return []
        try:
            eng = self._make_engine()
            voices = [
                {"id": v.id, "name": v.name, "lang": getattr(v, "languages", ["?"])[0]}
                for v in eng.getProperty("voices")
            ]
            eng.stop()
            return voices
        except Exception:
            return []

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using pyttsx3's ``save_to_file``."""
        if not self._available:
            raise RuntimeError("pyttsx3 is not available (pip install pyttsx3)")
        eng = self._make_engine()
        try:
            eng.save_to_file(text, wav_path)
            eng.runAndWait()
        finally:
            try:
                eng.stop()
            except Exception:
                pass

    @property
    def speaking(self) -> bool:
        return self._speaking
