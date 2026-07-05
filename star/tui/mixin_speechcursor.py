"""Speech Cursor (SC) mode: per-unit browse-and-read navigation.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..tts import Pyttsx3Backend, _SCReader
from ..ttstext import _preprocess_tts_text


class SpeechCursorMixin:

    # ── Speech Cursor (SC) mode ───────────────────────────────────────────

    def _sc_enter(self) -> None:
        """Activate Speech Cursor mode.

        Stops any running speech, positions the reading cursor at the last
        highlighted word (or the current scroll line) and switches to 'sc'
        mode where every navigation keystroke moves the cursor and reads
        just that single line.
        """
        self._tts_stop()
        if self._highlight_line >= 0:
            self._sc_line = self._highlight_line
        else:
            self._sc_line = self.scroll
        # Build the persistent engine now so the first line has no startup lag.
        if _PYTTSX3 and isinstance(self.tts._backend, Pyttsx3Backend):
            self._sc_reader = _SCReader(
                rate=int(self.settings["tts_rate"]),
                volume=float(self.settings["tts_volume"]),
            )
            self._sc_reader.start()
        else:
            self._sc_reader = None
        self.mode = "sc"
        self.notify(
            "Speech Cursor ON  ↑↓:line  ,/.:sent  [/]:para  {/}:head  t/T:table"
            "  Enter:read-on  Space:pause  Esc:exit",
            dur=7.0,
        )

    def _sc_exit(self, start_reading: bool = False) -> None:
        """Exit Speech Cursor mode.  Speech is **always** stopped first.

        If *start_reading* is True (Enter key), continuous TTS then starts
        from the cursor position so the user can resume full reading from
        wherever they browsed to.  Every other exit leaves the engine silent.
        """
        self.mode = "normal"
        # Stop the persistent SC reader first — this reaches the live SAPI5
        # engine directly without the 200–500 ms Engine() construction race.
        if self._sc_reader is not None:
            self._sc_reader.close()
            self._sc_reader = None
        self._tts_stop()  # also silence the main TTS backend
        # Hand the position to the normal-mode caret so Enter/Space continue
        # from where the user browsed to — leaving the caret where it was
        # before SC mode made the two cursors silently disagree.
        dest_word = self._line_to_word(self._sc_line)
        if self.doc and self.doc.word_map and 0 <= dest_word < len(self.doc.word_map):
            self._caret_word = dest_word
            self._caret_goal_col = -1
        if start_reading:
            self.scroll = self._sc_line
            self._tts_paused_at_word = -1
            self._tts_play_from_word(dest_word)
            self.notify(f"Reading from line {self._sc_line + 1}")

    def _sc_read_line(self, line_idx: int) -> None:
        """Stop current speech and read exactly one rendered line.

        This is the fundamental SC mode action: the cursor sits on a line,
        the engine reads that line and stops, then waits for the next
        navigation keystroke.  Blank lines are announced as \"blank\" so
        the user knows they have crossed a paragraph boundary.

        Plain text is always used regardless of the global *use_ssml* setting
        — SSML is unnecessary for a single short line and plain text keeps
        word-boundary callbacks active for accurate highlighting.
        """
        if not self.rendered or not (0 <= line_idx < len(self.rendered)):
            return
        self.tts.stop()  # stop the main TTS backend / timer
        text = "".join(t for t, _ in self.rendered[line_idx]).strip()
        if not text:
            # Announce blank lines so the user knows they've crossed a
            # paragraph boundary.
            if self._sc_reader is not None:
                self._sc_reader.speak("blank")
            else:
                self.tts._backend.speak("blank")
            return
        text = _preprocess_tts_text(text, self.settings)
        if self._sc_reader is not None:
            # Use the persistent reader: engine already warm, stop() is
            # always effective (no Engine() construction race on exit).
            self._sc_reader.speak(text)
        else:
            # Fallback for non-pyttsx3 backends (eSpeak, DECtalk).
            self.tts._backend.speak(text)

    def _sc_move(self, dest_line: int, label: str = "") -> None:
        """Move the SC cursor to *dest_line*, scroll it into view, and read
        just that single line — no continuous document reading."""
        total = len(self.rendered)
        if not total:
            return
        dest_line = max(0, min(dest_line, total - 1))
        self._sc_line = dest_line
        # Keep cursor comfortably visible (margin clamped so an oversized
        # scroll_margin cannot make the two branches fight — see CaretMixin).
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        margin = min(int(self.settings.get("scroll_margin", 3)), (view_h - 1) // 2)
        margin = max(0, margin)
        if dest_line < self.scroll + margin:
            self.scroll = max(0, dest_line - margin)
        elif dest_line >= self.scroll + view_h - margin:
            self.scroll = max(0, dest_line - view_h + margin + 1)
        # Speak only this line
        self._sc_read_line(dest_line)
        if label:
            self.notify(label)

    def _handle_sc_key(self, ch: int) -> None:  # noqa: C901
        """Key handler for Speech Cursor (sc) mode."""
        # ── Exit / speech-control ─────────────────────────────────────────
        if ch == 27:  # Escape — exit + stop
            self._sc_exit(start_reading=False)
            return
        if ch == 9:  # Tab — exit SC mode and stop speech
            self._sc_exit(start_reading=False)
            return
        if ch in (curses.KEY_ENTER, 10, 13):  # Enter — exit + continuous read
            self._sc_exit(start_reading=True)
            return
        if ch == ord(" "):
            self._tts_toggle()
            return
        if ch == 0:  # Ctrl+Space — read on from the cursor (like Enter)
            self._sc_exit(start_reading=True)
            return
        if ch == 24:  # Ctrl+X — full stop (Esc also stops)
            self._tts_stop()
            return

        if not self.rendered:
            return
        total = len(self.rendered)

        # ── Line navigation ───────────────────────────────────────────────
        if ch in (curses.KEY_DOWN, ord("j")):
            dest = min(self._sc_line + 1, total - 1)
            text = "".join(t for t, _ in self.rendered[dest]).strip()
            self._sc_move(dest, f"Line {dest + 1}: {text[:60]}")

        elif ch in (curses.KEY_UP, ord("k")):
            dest = max(self._sc_line - 1, 0)
            text = "".join(t for t, _ in self.rendered[dest]).strip()
            self._sc_move(dest, f"Line {dest + 1}: {text[:60]}")

        # ── Sentence navigation ───────────────────────────────────────────
        elif ch == ord("."):
            if not self.doc or not self.doc.word_map:
                return
            cur = self._line_to_word(self._sc_line)
            si = self._find_sentence_idx(cur)
            nsi = si + 1
            if nsi >= len(self._sentence_starts):
                self.notify("No next sentence")
                return
            dest_word = self._sentence_starts[nsi]
            dest_line = self.doc.word_map[dest_word].disp_line
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest_word, min(dest_word + 5, len(self.doc.word_map)))
            )
            total_s = len(self._sentence_starts)
            self._sc_move(
                dest_line,
                f"→ Sentence {nsi + 1}/{total_s}: “{preview}…”",
            )

        elif ch == ord(","):
            if not self.doc or not self.doc.word_map:
                return
            cur = self._line_to_word(self._sc_line)
            si = self._find_sentence_idx(cur)
            psi = si if cur - self._sentence_starts[si] > 3 else max(0, si - 1)
            dest_word = self._sentence_starts[psi]
            dest_line = self.doc.word_map[dest_word].disp_line
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest_word, min(dest_word + 5, len(self.doc.word_map)))
            )
            total_s = len(self._sentence_starts)
            self._sc_move(
                dest_line,
                f"← Sentence {psi + 1}/{total_s}: “{preview}…”",
            )

        # ── Paragraph navigation ──────────────────────────────────────────
        elif ch in (ord("]"), curses.KEY_NPAGE):
            dest = self._find_next_paragraph(self._sc_line)
            self._sc_move(dest, f"\u00b6 Next paragraph \u2014 line {dest + 1}")

        elif ch in (ord("["), curses.KEY_PPAGE):
            dest = self._find_prev_paragraph(self._sc_line)
            self._sc_move(dest, f"\u00b6 Prev paragraph \u2014 line {dest + 1}")

        # ── Heading navigation ────────────────────────────────────────────
        elif ch in (ord("}"), ord(">")):
            dest = self._find_next_heading(self._sc_line)
            if dest is None:
                self.notify("No heading below")
            else:
                heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
                self._sc_move(dest, f"\u23e9 Heading: {heading_text[:60]}")

        elif ch in (ord("{"), ord("<")):
            dest = self._find_prev_heading(self._sc_line)
            if dest is None:
                self.notify("No heading above")
            else:
                heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
                self._sc_move(dest, f"\u23ea Heading: {heading_text[:60]}")

        # ── Table navigation ──────────────────────────────────────────────
        elif ch == ord("t"):
            dest = self._find_next_table(self._sc_line)
            if dest is None:
                self.notify("No table below")
            else:
                self._sc_move(dest, f"Table at line {dest + 1}")

        elif ch == ord("T"):
            dest = self._find_prev_table(self._sc_line)
            if dest is None:
                self.notify("No table above")
            else:
                self._sc_move(dest, f"Table at line {dest + 1}")

        # ── Re-read current line ──────────────────────────────────────────
        elif ch == ord("r"):
            line_text = "".join(t for t, _ in self.rendered[self._sc_line]).strip()
            self._sc_read_line(self._sc_line)
            self.notify(f"↺ Line {self._sc_line + 1}: {line_text[:60]}")

        # ── Document boundaries ───────────────────────────────────────────
        elif ch == curses.KEY_HOME:
            self._sc_move(0, "Top of document")

        elif ch == curses.KEY_END:
            self._sc_move(total - 1, "End of document")
