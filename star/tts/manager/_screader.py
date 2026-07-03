"""_SCReader — persistent single-line pyttsx3 reader for Speech Cursor mode.

Carved verbatim from the former ``star/tts/manager.py`` module; behaviour,
threading, and SAPI5 rebuild logic are unchanged.
"""
from ..._runtime import *  # noqa: F401,F403


class _SCReader:
    """Persistent single-line TTS reader for Speech Cursor mode.

    Problem being solved
    --------------------
    ``_sc_read_line`` used to call ``pyttsx3.Engine()`` on *every* line.  On
    Windows that COM initialization takes 200–500 ms, creating a window where
    ``_active_engine`` is ``None``.  If the user exits SC mode during that
    window ``Pyttsx3Backend.stop()`` cannot reach the engine via
    ``eng.stop()``; the ``_stop_requested`` flag may also lose the race,
    allowing ``runAndWait()`` to start — speech continues after the mode is
    gone.

    Solution
    --------
    One ``pyttsx3.Engine`` is built when SC mode is entered and reused for
    every line.  ``stop()`` always has a live COM object to call
    ``eng.stop()`` on, so SAPI5 is interrupted in under a frame.  If a
    mid-speech stop corrupts SAPI5 state (the known Windows issue), the next
    ``speak()`` call rebuilds the engine *inside its own background thread*
    so the curses UI never blocks.
    """

    def __init__(self, rate: int, volume: float) -> None:
        self._rate = rate
        self._volume = volume
        self._eng = None  # persistent pyttsx3 Engine
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()  # signals _run to abort
        self._needs_rebuild = False  # engine may be corrupt

    # ── internal ──────────────────────────────────────────────────────

    def _build(self) -> Any:
        eng = _load_pyttsx3().Engine()
        eng.setProperty("rate", self._rate)
        eng.setProperty("volume", self._volume)
        return eng

    @property
    def _busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── public API ────────────────────────────────────────────────────

    def start(self) -> None:
        """Build the persistent engine (call once when SC mode is entered)."""
        if not _PYTTSX3:
            return
        try:
            self._eng = self._build()
        except Exception:
            self._eng = None

    def speak(self, text: str) -> None:
        """Stop current speech (if any) and read *text*.

        Always returns immediately — never blocks the UI thread.
        If a mid-speech stop corrupted the engine the rebuild happens
        inside the new speech thread, not on the caller.
        """
        if not _PYTTSX3:
            return

        if self._busy:
            # Signal old thread to abort and interrupt SAPI5.
            # Engine state may be corrupt after stop-while-busy.
            self._stop_flag.set()
            if self._eng:
                try:
                    self._eng.stop()
                except Exception:
                    pass
            self._needs_rebuild = True

        self._stop_flag.clear()
        rate = self._rate
        volume = self._volume
        needs_rebuild = self._needs_rebuild
        eng_ref = [self._eng]  # mutable cell so _run can update it
        stop_flag = self._stop_flag
        reader = self

        def _run() -> None:
            eng = eng_ref[0]
            try:
                if needs_rebuild or eng is None:
                    eng = _load_pyttsx3().Engine()
                    eng.setProperty("rate", rate)
                    eng.setProperty("volume", volume)
                    eng_ref[0] = eng
                    reader._eng = eng
                    reader._needs_rebuild = False
                if stop_flag.is_set():
                    return
                eng.say(text)
                if stop_flag.is_set():
                    return
                eng.runAndWait()
            except Exception:
                reader._needs_rebuild = True
            finally:
                if stop_flag.is_set():
                    reader._needs_rebuild = True  # interrupted → may be corrupt

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Interrupt speech immediately.  Non-blocking — safe to call from
        the curses main loop."""
        self._stop_flag.set()
        eng = self._eng
        if eng:
            try:
                eng.stop()  # SAPI5 Skip — takes effect in < one audio frame
            except Exception:
                pass
        if self._busy:
            self._needs_rebuild = True

    def update_rate(self, rate: int) -> None:
        """Propagate a speech-rate change to the live engine."""
        self._rate = rate
        eng = self._eng
        if eng and not self._busy:
            try:
                eng.setProperty("rate", rate)
            except Exception:
                pass

    def close(self) -> None:
        """Stop speech and release the engine on SC mode exit."""
        self.stop()
        self._eng = None
