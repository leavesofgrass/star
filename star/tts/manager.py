"""TTSManager — active backend selection + word-position tracking; _SCReader."""
from .._runtime import *  # noqa: F401,F403
from ..settings import Settings
from .base import TTSBackend
from .silent import SilentBackend
from .pyttsx3 import Pyttsx3Backend
from .espeak import ESpeakLibBackend
from .audio import _convert_audio_format
from .subtitles import _generate_subtitles


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


class TTSManager:
    """Manages the active TTS backend and word-position tracking."""

    #: Engine names never chosen in ``auto`` mode: piper/coqui need an explicit
    #: opt-in (downloaded model), and ``silent`` is the last-resort fallback.
    _AUTO_SKIP = frozenset({"silent", "piper", "coqui"})

    def __init__(self, settings: Settings):
        self._settings = settings
        self._backend: TTSBackend = SilentBackend()
        self._word_map: List["WordPos"] = []
        self._current_word_idx: int = -1
        self._on_highlight: Optional[Callable[[int], None]] = None  # callback(word_idx)
        self._on_done: Optional[Callable[[], None]] = None
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
        self._select_backend(settings["tts_backend"])

    def _select_backend(self, preference: str) -> None:
        """Pick the active backend from the plugin registry.

        Backend classes are discovered via the ``star.backends`` entry-points
        (built-ins and any installed third-party plugins) and walked in
        ``priority`` order.  An explicit *preference* tries only the engines
        registered under that name — ``"espeak"`` and ``"dectalk"`` each map to
        two implementations (in-process then CLI), tried in priority order.
        ``"auto"`` walks every auto-eligible engine and takes the first that
        reports itself available; everything falls back to :class:`SilentBackend`.
        """
        from ..plugins import PluginRegistry

        rate = int(self._settings["tts_rate"])
        vol = float(self._settings["tts_volume"])

        classes = sorted(PluginRegistry.get().backends, key=lambda c: c.priority)

        chosen: Optional[TTSBackend] = None
        if preference and preference != "auto":
            # Explicit engine: try only the implementations registered under
            # this name, lowest priority first (e.g. libespeak-ng before the
            # eSpeak CLI; DECtalk.dll before the say/dtalk CLI).
            for cls in classes:
                if cls.name != preference:
                    continue
                cand = self._construct_backend(cls)
                if cand.available():
                    chosen = cand
                    break
        else:
            # Auto: walk every auto-eligible engine in priority order.  The
            # bundled DECtalk.dll ("Perfect Paul") sorts first, then pyttsx3,
            # the macOS `say` voice (ranked above eSpeak so a Mac never falls to
            # the robotic eSpeak voice), eSpeak, Festival, and the DECtalk CLI.
            for cls in classes:
                if cls.name in self._AUTO_SKIP:
                    continue
                cand = self._construct_backend(cls)
                if cand.available():
                    chosen = cand
                    break

        self._backend = chosen or SilentBackend()
        self._backend.set_rate(rate)
        self._backend.set_volume(vol)
        self._resolve_default_voice()

    def _construct_backend(self, cls: "type[TTSBackend]") -> TTSBackend:
        """Instantiate *cls* with the per-engine constructor arguments derived
        from settings.  Engines that share a ``name`` (eSpeak's and DECtalk's two
        implementations each) take identical arguments, so keying on ``name`` is
        safe.  Unknown / third-party backends are tried with the common
        ``(rate, volume, voice)`` signature, then with no arguments.
        """
        rate = int(self._settings["tts_rate"])
        vol = float(self._settings["tts_volume"])
        voice = str(self._settings["tts_voice"])
        name = cls.name
        if name == "espeak":
            return cls(rate=rate, voice=voice or "en-us")
        if name == "dectalk":
            return cls(rate=rate, voice=voice)
        if name == "piper":
            # A `tts_voice` ending in .onnx wins; otherwise the dedicated
            # `piper_model` setting supplies the model path.
            piper_voice = (
                voice
                if voice.lower().endswith(".onnx")
                else str(self._settings.get("piper_model", ""))
            )
            return cls(rate=rate, volume=vol, voice=piper_voice)
        try:
            return cls(rate=rate, volume=vol, voice=voice)
        except TypeError:
            return cls()

    def _resolve_default_voice(self) -> None:
        """Pick a sensible default voice when the user hasn't chosen one.

        When ``tts_voice`` is empty, prefer a voice whose name contains the
        ``tts_prefer_voice`` substring (default ``"eloquence"``), favoring a
        US-English variant.  This makes the bundled Eloquence voices the
        default on macOS while leaving the engine default untouched when no
        match is found.  The user's explicit voice choice always wins.
        """
        if str(self._settings.get("tts_voice", "")):
            return  # user has an explicit voice; never override it
        prefer = str(self._settings.get("tts_prefer_voice", "")).strip().lower()
        if not prefer:
            return
        try:
            voices = self._backend.list_voices()
        except Exception:
            voices = []
        if not voices:
            return
        matches = [
            v
            for v in voices
            if prefer in (v.get("name", "") + " " + v.get("id", "")).lower()
        ]
        if not matches:
            return
        # Favor a US-English variant of the preferred voice family.
        best = next(
            (m for m in matches if "us" in str(m.get("lang", "")).lower()),
            matches[0],
        )
        vid = best.get("id") or best.get("name")
        if vid:
            self._backend.set_voice(vid)

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def speaking(self) -> bool:
        return self._backend.speaking

    @property
    def current_word_idx(self) -> int:
        return self._current_word_idx

    def set_word_map(self, word_map: List["WordPos"]) -> None:
        self._word_map = word_map

    def set_on_highlight(self, cb: Optional[Callable[[int], None]]) -> None:
        self._on_highlight = cb

    def set_on_done(self, cb: Optional[Callable[[], None]]) -> None:
        self._on_done = cb

    def speak(
        self,
        text: str,
        start_word_idx: int = 0,
        text_offset: int = 0,
    ) -> None:
        """Begin speaking *text*.

        Parameters
        ----------
        text:
            The string actually passed to the TTS engine.  This may be a
            *slice* of the full document plain text (everything from the
            desired start position to the end) so that the engine does not
            re-read content that has already been heard.
        start_word_idx:
            Index into the full word_map of the first word in *text*.  Used
            to seed the highlight timer at the right position.
        text_offset:
            Character offset of the first character of *text* within the
            full plain-text string.  Used to translate the byte offsets that
            pyttsx3 reports back into absolute word-map indices.
        """
        # Increment the timer generation BEFORE signalling the old timer to
        # stop.  This ensures that an old timer currently mid-loop-body will
        # see the new generation on its very next gen-check and return without
        # calling _on_highlight, preventing a stray high-word flash followed
        # by the new timer's start-word snap (the "snap back" bug).
        self._timer_gen += 1
        self._timer_stop.set()
        self._current_word_idx = max(0, start_word_idx)
        self._last_cb_word_idx = -1  # no confirmed position yet for this utterance
        self._last_cb_time = 0.0  # reset callback timestamp for this utterance

        def on_done() -> None:
            self._timer_stop.set()
            self._current_word_idx = -1
            if self._on_highlight:
                self._on_highlight(-1)
            if self._on_done:
                self._on_done()

        # pyttsx3 word callbacks supplement the timer when they fire reliably
        # (they may not on all Windows/SAPI5 configurations).  The timer is
        # always started as the primary highlight mechanism.
        if isinstance(self._backend, (Pyttsx3Backend, ESpeakLibBackend)):
            # The in-process eSpeak-NG backend paces its callbacks to real audio
            # position, so they are playback-accurate (unlike SAPI5's, which lag
            # and burst).  Flag that for the timer, and keep the backend's
            # latency-compensation offset in sync with the user setting so the
            # highlight is not painted slightly before the word is heard.
            self._paced_playback = isinstance(self._backend, ESpeakLibBackend)
            if self._paced_playback:
                self._backend.set_highlight_offset_ms(
                    int(self._settings.get("espeak_highlight_offset_ms", 120))
                )

            def on_word_cb(location: int, length: int) -> None:
                """Translate TTS-relative location back to a word-map index.

                *location* is relative to the *text* slice passed to speak().
                Adding *text_offset* converts it to an absolute offset in the
                full plain-text string, which is what word_map stores.

                We update *_current_word_idx* here so the timer can adopt the
                accurate engine position on its next tick, but we deliberately
                do NOT call *_on_highlight* directly.  SAPI5 callbacks arrive
                asynchronously and can lag or burst; calling _on_highlight from
                the callback caused the highlight to snap backward to an older
                word while the timer had already advanced forward.
                """
                # text_offset == -1 means SSML mode: character offsets in
                # the callback point into the SSML string, not the plain
                # text.  Skip the lookup and let the timer handle highlight.
                if text_offset < 0:
                    return
                abs_loc = location + text_offset
                for i, wp in enumerate(self._word_map):
                    if wp.tts_offset <= abs_loc < wp.tts_offset + wp.tts_len + 1:
                        # Monotonic write: only advance, never retreat.
                        # Delayed or out-of-order SAPI5 callbacks for earlier
                        # words must not clobber a later confirmed position
                        # (which would make _tts_toggle save the wrong pause
                        # word and cause a backward snap on resume).
                        if i >= self._current_word_idx:
                            self._current_word_idx = i
                            self._last_cb_word_idx = i
                            self._last_cb_time = time.monotonic()
                        break

            self._expect_callbacks = True
            self._backend.speak(text, on_word=on_word_cb, on_done=on_done)
        else:
            self._expect_callbacks = False
            self._paced_playback = False
            self._backend.speak(text, on_done=on_done)

        # Always start the timer — it is the reliable baseline for all backends.
        self._start_timer_highlight(start_word_idx)

    def _start_timer_highlight(self, start_idx: int) -> None:
        """Timer-based word highlight advance.  Works for every backend.

        If the word map is not yet built (async loading still running), the
        timer waits up to 10 s for it to appear before advancing.

        A monotonic *_timer_gen* counter is captured at launch.  Every loop
        iteration confirms its value still matches; if a newer timer has been
        started (via a new speak() call) the old thread exits immediately.
        This prevents multiple stale timers from racing to call _on_highlight
        with different word indices, which was the primary cause of the
        highlight jumping all over the place.
        """
        self._timer_stop.clear()
        # _timer_gen was already incremented by speak() or stop() before
        # this method was called; just capture the current value.
        my_gen = self._timer_gen
        rate = int(self._settings["tts_rate"])
        # Timer interval: run at the nominal speech rate (1.0 × wpm) so the
        # highlight tracks audio as closely as possible.  The _MAX_AHEAD guard
        # below is the true throttle for pyttsx3/SAPI5; slowing the timer
        # (< 1.0) only causes the highlight to fall behind.
        hl_speed = float(self._settings.get("highlight_speed", 1.0))
        interval = 60.0 / max(1.0, rate * max(0.1, hl_speed))
        # How many words ahead of the last callback-confirmed position the
        # timer is allowed to advance before it pauses for one tick.
        # Only active when pyttsx3 word callbacks are firing; _last_cb_word_idx
        # stays -1 in SSML mode and for non-pyttsx3 backends (guard inactive).
        #
        # 4 words of slack covers the typical SAPI5 callback delay (1-3 words
        # late) without letting the highlight race too far ahead of audio.  The
        # in-process eSpeak-NG backend paces its callbacks to actual playback
        # position, so its confirmed index is itself accurate: cap the lead at a
        # single word so the highlight sits on the word being spoken rather than
        # drifting up to four ahead.
        _MAX_AHEAD = 1 if self._paced_playback else 4
        # If no callback has arrived within this many seconds the guard is
        # bypassed entirely: SAPI5 sometimes stops firing callbacks mid-text,
        # and without this escape the highlight would freeze while speech
        # continues.  1.5 s ≈ 6 words at 240 wpm — long enough to ride out
        # normal punctuation pauses, short enough to feel responsive.
        _CB_TIMEOUT = 1.5
        # First-audio anchor window.  When the backend reports real per-word
        # events, the timer holds its first paint until the first event arrives
        # (≈ audio onset) so the highlight does not start counting from the
        # speak() call — which precedes audible output by the engine's start-up
        # latency and gives the highlight a constant head start.  Bounded so the
        # highlight can never stall if events fail to arrive (e.g. a SAPI5
        # configuration that delivers no word callbacks): after this long the
        # timer proceeds in free-running mode, exactly as before.
        _ANCHOR_TIMEOUT = 0.75

        def _tick() -> None:
            # Wait for the word map to be populated (built asynchronously).
            deadline = time.monotonic() + 10.0
            while not self._timer_stop.is_set():
                if self._word_map:
                    break
                if time.monotonic() > deadline:
                    return  # gave up waiting
                time.sleep(0.05)

            # Exit immediately if a newer timer was started while we waited.
            if self._timer_gen != my_gen:
                return

            # First-audio anchor: when the backend emits real per-word events,
            # wait for the first one before painting anything so the highlight
            # clock aligns to audible output rather than to the speak() call.
            # This removes the constant head start the highlight otherwise has
            # from the engine's start-up latency.  Only pyttsx3 sets
            # _expect_callbacks today, so every other backend skips this and
            # behaves exactly as before.  _last_cb_word_idx is a single int
            # written by the engine callback thread; reading it here is atomic
            # under the GIL, so this advisory check needs no lock.
            if self._expect_callbacks:
                anchor_deadline = time.monotonic() + _ANCHOR_TIMEOUT
                while not self._timer_stop.is_set():
                    if self._timer_gen != my_gen:
                        return
                    if self._last_cb_word_idx >= 0:
                        break  # first real word event seen — anchored
                    if time.monotonic() > anchor_deadline:
                        break  # no events arriving — proceed free-running
                    time.sleep(0.01)

            idx = max(0, start_idx)
            while not self._timer_stop.wait(interval):
                # Bail out as soon as a newer timer generation takes over.
                if self._timer_gen != my_gen:
                    return
                # Adopt the engine's position when it has run ahead of the
                # timer estimate (e.g. fast speech or SSML pauses consumed).
                # Never go backward — that would cause the highlight to jump
                # back to a word that was already spoken.
                if self._current_word_idx > idx:
                    idx = self._current_word_idx
                # Pacing guard: keep the highlight within _MAX_AHEAD words
                # of the last callback-confirmed audio position.  Only active
                # while callbacks are both firing AND recent; if SAPI5 stops
                # sending callbacks (_CB_TIMEOUT exceeded) the guard is
                # bypassed so the highlight never freezes mid-document.
                if (
                    self._last_cb_word_idx >= 0
                    and idx >= self._last_cb_word_idx + _MAX_AHEAD
                    and (time.monotonic() - self._last_cb_time) < _CB_TIMEOUT
                ):
                    continue  # hold briefly — callbacks are active but lagging
                if idx < len(self._word_map):
                    # Second gen-check immediately before the display call.
                    # Closes the narrow window between the first check above
                    # and this point where a new speak() could have bumped
                    # the generation, avoiding a stray _on_highlight flash.
                    if self._timer_gen != my_gen:
                        return
                    self._current_word_idx = idx
                    if self._on_highlight:
                        self._on_highlight(idx)
                    idx += 1
                # Don't break when we reach the end — the backend may still
                # be speaking padding/trailing punctuation.

        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()

    def stop(self) -> None:
        # Same ordering as speak(): bump generation first so any running timer
        # exits cleanly before the stop event is processed.
        self._timer_gen += 1
        self._timer_stop.set()
        self._backend.stop()
        self._current_word_idx = -1
        self._last_cb_word_idx = -1
        self._last_cb_time = 0.0

    @property
    def last_cb_word_idx(self) -> int:
        """Last word index confirmed by a pyttsx3 word-boundary callback.
        -1 when no callback has fired for the current utterance (SSML mode
        or before the engine has produced the first word).  More accurate
        than *current_word_idx* for pause/resume because it reflects the
        actual audio position rather than the timer\'s forward estimate.
        """
        return self._last_cb_word_idx

    def set_rate(self, wpm: int) -> None:
        self._settings["tts_rate"] = wpm
        self._backend.set_rate(wpm)

    def set_volume(self, vol: float) -> None:
        self._settings["tts_volume"] = vol
        self._backend.set_volume(vol)

    def change_backend(self, name: str) -> None:
        self.stop()
        self._settings["tts_backend"] = name
        self._select_backend(name)

    def list_voices(self) -> List[Dict[str, str]]:
        return self._backend.list_voices()

    def export_audio(
        self,
        text: str,
        dest_path: str,
        subtitle_path: Optional[str] = None,
        subtitle_format: str = "srt",
        subtitle_word_level: bool = False,
    ) -> None:
        """Synthesize *text* and save it to *dest_path*.

        The output format is inferred from the file extension:

        * ``.wav``  — written directly by the backend (no extras needed).
        * ``.mp3``  — requires **ffmpeg** or **pydub**.
        * ``.ogg``  — requires **ffmpeg** or **pydub**.
        * ``.mp4``  — requires **ffmpeg** or **pydub** (audio-only AAC).

        When *subtitle_path* is given a synchronized SRT/VTT caption track is
        written there using the same synthesized audio, so no second synthesis
        is needed.  *subtitle_format* is ``"srt"`` or ``"vtt"``
        and *subtitle_word_level* emits one cue per word instead of grouping
        tokens into sentence-length caption lines.

        This method **blocks** until synthesis and conversion are complete.
        Call it from a background thread when used in a GUI to avoid
        freezing the interface.
        """
        ext = Path(dest_path).suffix.lower()
        if ext == ".wav":
            self._backend.export_to_wav(text, dest_path)
            if subtitle_path:
                self._write_subtitles(
                    text,
                    dest_path,
                    subtitle_path,
                    subtitle_format,
                    subtitle_word_level,
                )
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            self._backend.export_to_wav(text, tmp_wav)
            if subtitle_path:
                self._write_subtitles(
                    text,
                    tmp_wav,
                    subtitle_path,
                    subtitle_format,
                    subtitle_word_level,
                )
            _convert_audio_format(tmp_wav, dest_path)
        finally:
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _write_subtitles(
        text: str,
        wav_path: str,
        sub_path: str,
        fmt: str = "srt",
        word_level: bool = False,
    ) -> None:
        """Generate and write an SRT/VTT caption track for the synthesized WAV."""
        subs = _generate_subtitles(text, wav_path, fmt=fmt, word_level=word_level)
        if subs:
            Path(sub_path).write_text(subs, encoding="utf-8")

    def export_subtitles(
        self,
        text: str,
        sub_path: str,
        fmt: str = "srt",
        word_level: bool = False,
    ) -> None:
        """Synthesize *text* to a temporary WAV solely to measure its duration,
        then write a synchronized SRT/VTT caption track to *sub_path*.

        Use this when only captions are wanted (no audio file).  **Blocks**
        until synthesis is complete.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            self._backend.export_to_wav(text, tmp_wav)
            self._write_subtitles(text, tmp_wav, sub_path, fmt, word_level)
        finally:
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass
