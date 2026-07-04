"""TTS playback controls and the word-highlight callback.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..ttstext import _preprocess_tts_text, _text_to_ssml
from .mixin_caret import _CARET_GRACE_S


class PlaybackMixin:

    # ── Highlight callback from TTS ────────────────────────────────────────

    def _on_highlight(self, word_idx: int) -> None:
        """Called from the TTS/timer background thread — must NOT call any
        curses functions (not thread-safe).  Only update plain attributes;
        the main draw loop reads them on the next tick and adjusts scroll."""
        if not self.settings["highlight_current_word"]:
            return
        if self.doc and 0 <= word_idx < len(self.doc.word_map):
            wp = self.doc.word_map[word_idx]
            self._highlight_line = wp.disp_line
            self._highlight_col_start = wp.disp_col
            self._highlight_col_end = wp.disp_col + wp.tts_len
            # Caret follows the spoken word (so Enter always resumes "from
            # here") — unless the user just moved it deliberately, which gets
            # a grace window.  Plain attribute write from the TTS thread,
            # same convention as the fields above.
            if (
                self.settings.get("tui_caret_follow_speech", True)
                and time.monotonic() - self._caret_manual_ts > _CARET_GRACE_S
            ):
                self._caret_word = word_idx
            # Sentence-level highlight: resolve the span of the sentence that
            # contains this word so the draw loop can band-highlight it.
            gran = str(self.settings.get("highlight_granularity", "word"))
            if gran in ("sentence", "both"):
                ss = self._sentence_starts
                si = self._find_sentence_idx(word_idx)
                start_w = ss[si] if si < len(ss) else word_idx
                end_w = (
                    ss[si + 1] - 1 if si + 1 < len(ss) else len(self.doc.word_map) - 1
                )
                self._highlight_sent = (start_w, max(start_w, end_w))
            else:
                self._highlight_sent = None
        else:
            self._highlight_line = -1
            self._highlight_col_start = -1
            self._highlight_col_end = -1
            self._highlight_sent = None

        # Update RSVP words (safe — plain attribute writes only).
        if self._rsvp_mode and self.doc:
            wm = self.doc.word_map
            n = len(wm)
            self._rsvp_curr_word = wm[word_idx].word if 0 <= word_idx < n else ""
            self._rsvp_prev_word = wm[word_idx - 1].word if word_idx > 0 else ""
            self._rsvp_next_word = wm[word_idx + 1].word if word_idx + 1 < n else ""

    # ── TTS controls ──────────────────────────────────────────────────

    def _tts_play(self) -> None:
        """Start speaking from the current reading position.

        Uses _current_word_for_nav, so a placed caret wins (caret browsing),
        falling back to the first word on-screen — the engine never re-reads
        content that is already above the viewport."""
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        start_word = 0
        if self.doc.word_map:
            start_word = max(
                0, min(self._current_word_for_nav(), len(self.doc.word_map) - 1)
            )
        self._tts_play_from_word(start_word)
        self.notify(
            f"Reading at {self.settings['tts_rate']} wpm via {self.tts.backend_name}"
        )

    def _tts_play_from_word(self, word_idx: int) -> None:
        """Start or restart TTS from a specific word-map index.

        Slices ``plain_text`` so the engine only reads from *word_idx*
        onwards.  When SSML is enabled the slice is wrapped with prosody
        markup; ``text_offset=-1`` tells TTSManager to skip word-callback
        offset arithmetic (the timer provides highlight accuracy instead).
        """
        if not self.doc:
            return
        wm = self.doc.word_map
        if wm and word_idx < len(wm):
            text_offset = wm[word_idx].tts_offset
        else:
            text_offset = 0
            word_idx = 0
        text_slice = self.doc.plain_text[text_offset:]

        # Apply speak-time normalizations (abbrev expansion, number words).
        text_slice = _preprocess_tts_text(text_slice, self.settings)

        if self.settings.get("use_ssml", False):
            text_for_engine = _text_to_ssml(
                text_slice,
                backend=self.tts.backend_name,
                sentence_ms=int(self.settings.get("ssml_sentence_pause_ms", 350)),
                clause_ms=int(self.settings.get("ssml_clause_pause_ms", 150)),
            )
            # SSML shifts char offsets — use -1 sentinel, rely on timer only.
            self.tts.speak(text_for_engine, start_word_idx=word_idx, text_offset=-1)
        else:
            self.tts.speak(text_slice, start_word_idx=word_idx, text_offset=text_offset)

    def _tts_stop(self) -> None:
        """Full stop — clears both speech and any saved pause position."""
        self.tts.stop()
        self._highlight_line = -1
        self._highlight_col_start = -1
        self._highlight_col_end = -1
        self._tts_paused_at_word = -1

    def _tts_toggle(self) -> None:
        """Pause/resume speech.

        * While speaking  → pause and remember the current word index so that
          the next press resumes from exactly that word.
        * While paused    → resume from the saved word index.
        * While stopped   → start from the current scroll position (same as
          before, so opening a fresh file and pressing Space still works).
        """
        if self.tts.speaking:
            # Save the last callback-confirmed position when available — it
            # reflects actual audio position rather than the timer's forward
            # estimate.  Pausing at the timer's ahead position would cause
            # resume to skip words; pausing at the callback position may
            # repeat a word or two but is far less disorienting.
            cb = self.tts.last_cb_word_idx
            saved = cb if cb >= 0 else self.tts.current_word_idx
            self._tts_stop()  # resets _tts_paused_at_word to -1
            if saved >= 0:
                self._tts_paused_at_word = saved  # restore the paused position
        elif self._tts_paused_at_word >= 0:
            w = self._tts_paused_at_word
            self._tts_paused_at_word = -1
            self._tts_play_from_word(w)
            self.notify(
                f"Resuming at {self.settings['tts_rate']} wpm via {self.tts.backend_name}"
            )
        else:
            self._tts_play()

    def _tts_speak_current_line(self) -> None:
        if not self.rendered or self.scroll >= len(self.rendered):
            return
        line = self.rendered[self.scroll]
        text = "".join(t for t, _ in line).strip()
        if text:
            self.tts.stop()
            text = _preprocess_tts_text(text, self.settings)
            if self.settings.get("use_ssml", False):
                text = _text_to_ssml(
                    text,
                    backend=self.tts.backend_name,
                    sentence_ms=int(self.settings.get("ssml_sentence_pause_ms", 350)),
                    clause_ms=int(self.settings.get("ssml_clause_pause_ms", 150)),
                )
            self.tts._backend.speak(text)

    def _ssml_toggle(self) -> None:
        val = not bool(self.settings.get("use_ssml", False))
        state = "ON" if val else "OFF"
        self.settings.set("use_ssml", val)
        self.notify(f"SSML prosody: {state}")

    def _rate_change(self, delta: int) -> None:
        new_rate = max(50, min(600, int(self.settings["tts_rate"]) + delta))
        self.tts.set_rate(new_rate)
        if self._sc_reader is not None:
            self._sc_reader.update_rate(new_rate)
        self.notify(f"Speech rate: {new_rate} wpm")

    def _volume_change(self, delta: float) -> None:
        new_vol = max(0.0, min(1.0, float(self.settings["tts_volume"]) + delta))
        self.tts.set_volume(new_vol)
        self.notify(f"Volume: {int(new_vol * 100)}%")
