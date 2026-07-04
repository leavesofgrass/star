"""PlaybackMixin — speak(), the word-highlight timer, stop(), and the small
backend passthroughs.

Carved verbatim from the former ``star/tts/manager.py`` module.  The threading,
timer-generation guards, SAPI5/eSpeak pacing constants, and monotonic-write
callback logic are byte-for-byte identical to the original; only the enclosing
class was split into cooperating mixins.
"""
from ..._runtime import *  # noqa: F401,F403
from ..pyttsx3 import Pyttsx3Backend
from ..espeak import ESpeakLibBackend
from ..cloud.base import CloudTTSError


class PlaybackMixin:
    """Playback: word-map plumbing, speak/stop, and the highlight timer."""

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

            # Cloud backends synthesize inside their worker thread, so a
            # present-but-invalid key (HTTP 401) or a mid-session outage fails
            # AFTER speak() returns — recorded on backend.last_error, not
            # raised.  Wrap on_done to detect that, fall back to a local
            # engine, and retry the same utterance once, so the document never
            # "reads" silently while the highlight advances.  The timer-gen
            # guard skips the retry if the user stopped or restarted speech.
            final_on_done = on_done
            if hasattr(self._backend, "last_error"):
                _cloud_gen = self._timer_gen

                def _on_done_cloud(orig: Callable[[], None] = on_done) -> None:
                    err = str(getattr(self._backend, "last_error", "") or "")
                    if err and self._timer_gen == _cloud_gen:
                        try:
                            self.last_engine_error = (
                                f"Cloud voice failed ({err}) — using a local voice"
                            )
                            self._select_backend("auto")
                            self._backend.speak(text, on_done=orig)
                            return  # speech continues on the fallback engine
                        except Exception:
                            pass  # fall through: end the utterance normally
                    orig()

                final_on_done = _on_done_cloud
            try:
                self._backend.speak(text, on_done=final_on_done)
            except CloudTTSError:
                # An opt-in cloud voice failed at synth time (missing key or a
                # network error).  Fall back to a local engine with timer-only
                # highlight so playback never dead-ends.  Cloud engines are in
                # _AUTO_SKIP, so "auto" resolves to a local backend (or the
                # SilentBackend floor); never re-raises into the reader.
                self._select_backend("auto")
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
