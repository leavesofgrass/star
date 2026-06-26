"""Sentence / paragraph / heading / table navigation, scrolling, reading position, goto.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from .theming import _HEADING_ROLES, _TABLE_ROLES


class NavigationMixin:

    # ── Sentence / paragraph navigation ──────────────────────────────────

    def _sentence_jump(
        self, dest_word: int, label: str, always_play: bool = False
    ) -> None:
        """Stop TTS, scroll to dest_word's display line, and restart speech.

        Restarts if speech was already active *or* if *always_play* is True
        (used by replay commands that must always begin reading).
        """
        self._history_push()  # record position before jump
        if not self.doc or not self.doc.word_map:
            return
        dest_word = max(0, min(dest_word, len(self.doc.word_map) - 1))
        dest_line = self.doc.word_map[dest_word].disp_line
        was_speaking = self.tts.speaking
        self.tts.stop()
        self._tts_paused_at_word = -1  # navigation breaks the pause/resume chain
        self._highlight_line = self._highlight_col_start = self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        if was_speaking or always_play:
            self._tts_play_from_word(dest_word)
        self.notify(label)

    def _skip_next_sentence(self) -> None:
        if not self.doc or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        si = self._find_sentence_idx(cur)
        nsi = si + 1
        if nsi >= len(self._sentence_starts):
            self.notify("No next sentence")
            return
        dest = self._sentence_starts[nsi]
        # Preview the first few words of the destination sentence
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        total = len(self._sentence_starts)
        self._sentence_jump(dest, f"→ Sentence {nsi + 1}/{total}: “{preview}…”")

    def _skip_prev_sentence(self) -> None:
        if not self.doc or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        si = self._find_sentence_idx(cur)
        # If we are well into the current sentence, jump to its start first.
        # A "well into" threshold of 3 words feels natural (like double-tap rewind).
        if cur - self._sentence_starts[si] > 3:
            psi = si
        else:
            psi = max(0, si - 1)
        dest = self._sentence_starts[psi]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        total = len(self._sentence_starts)
        self._sentence_jump(dest, f"← Sentence {psi + 1}/{total}: “{preview}…”")

    def _replay_sentence(self) -> None:
        """Jump to the start of the current sentence and always begin reading.

        Uses *always_play=True* so that a single, authoritative
        _tts_play_from_word call is made inside _sentence_jump regardless of
        whether speech was already active.  The old pattern of checking
        ``self.tts.speaking`` after the jump caused a Windows/SAPI5 race: the
        previous speech thread\'s finally-block could set _speaking=False
        after the new thread had already set it to True, making the guard fire
        a second _tts_play_from_word call that killed the first thread.
        """
        if not self.doc or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        si = self._find_sentence_idx(cur)
        dest = self._sentence_starts[si]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        self._sentence_jump(
            dest, f"↺ Replaying sentence: “{preview}…”", always_play=True
        )

    def _find_current_paragraph_start(self) -> int:
        """Return the first display line of the paragraph that contains
        the current scroll position."""
        i = self.scroll
        n = len(self.rendered)
        # If we landed on a blank line, step forward to content first
        while i < n - 1 and not self.rendered[i]:
            i += 1
        # Walk backward while the previous line is content (non-blank)
        while i > 0 and self.rendered[i - 1]:
            i -= 1
        return max(0, i)

    def _replay_paragraph(self) -> None:
        """Jump to the start of the current paragraph and always begin reading."""
        if not self.doc or not self.doc.word_map:
            return
        dest_line = self._find_current_paragraph_start()
        self.tts.stop()
        self._tts_paused_at_word = -1  # navigation breaks the pause/resume chain
        self._highlight_line = self._highlight_col_start = self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        # Find the word at dest_line
        dest_word = 0
        if self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= dest_line:
                    dest_word = i
                    break
        self._tts_play_from_word(dest_word)
        self.notify(f"↺ Replaying paragraph from line {dest_line + 1}")

    # ── Reading position memory ──────────────────────────

    def _save_reading_position(self) -> None:
        """Persist the current reading offset for the open document."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        if cur < 0 or cur >= len(self.doc.word_map):
            return
        offset = self.doc.word_map[cur].tts_offset
        total_chars = len(self.doc.plain_text)
        pct = int(100 * offset / max(1, total_chars))
        positions = dict(self.settings.get("reading_positions", {}))
        positions[self.doc.path] = {
            "offset": offset,
            "pct": pct,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if len(positions) > 200:
            evict = sorted(positions, key=lambda k: positions[k].get("ts", ""))[:50]
            for k in evict:
                del positions[k]
        self.settings.set("reading_positions", positions)

    def _restore_reading_position(self, force: bool = False) -> bool:
        """Scroll to the saved position for the current document.
        Safe to call from a background thread (only writes plain attributes)."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return False
        if not force and not self.settings.get("tts_auto_resume", True):
            return False
        saved = self.settings.get("reading_positions", {}).get(self.doc.path)
        if not saved:
            return False
        target_offset = int(saved.get("offset", 0))
        pct = int(saved.get("pct", 0))
        ts = str(saved.get("ts", ""))[:10]
        wm = self.doc.word_map
        best = len(wm) - 1
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        dest_line = wm[best].disp_line if best < len(wm) else 0
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        self.notify(f"Resumed at {pct}%  (saved {ts})", dur=5.0)
        return True

    def _clear_reading_position(self) -> None:
        """Delete the saved position for the current document."""
        if not self.doc or not self.doc.path:
            return
        positions = dict(self.settings.get("reading_positions", {}))
        if self.doc.path in positions:
            del positions[self.doc.path]
            self.settings.set("reading_positions", positions)
            self.notify("Reading position cleared")
        else:
            self.notify("No saved position for this document")

    # ── Skip navigation (paragraph / heading) ────────────────────────────────────────────────────

    def _navigate_to(self, line: int) -> None:
        """Scroll to *line* and, if TTS was already playing, restart speech
        from the new position so the reader continues without interruption."""
        was_speaking = self.tts.speaking
        if was_speaking:
            self.tts.stop()
            self._highlight_line = -1
            self._highlight_col_start = -1
            self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(line, total - 1) if total else 0)
        if was_speaking:
            self._tts_play()

    def _is_heading_line(self, line_idx: int) -> bool:
        """Return True if the rendered line at *line_idx* is a heading."""
        if 0 <= line_idx < len(self.rendered):
            return any(role in _HEADING_ROLES for _, role in self.rendered[line_idx])
        return False

    def _find_next_paragraph(self, from_line: int) -> int:
        """Return the first line of the paragraph that starts after the one
        containing *from_line*.  Falls back to the last line if none found."""
        n = len(self.rendered)
        i = from_line + 1
        # Walk forward through the current paragraph
        while i < n and self.rendered[i]:
            i += 1
        # Skip blank separator lines
        while i < n and not self.rendered[i]:
            i += 1
        return min(i, n - 1)

    def _find_prev_paragraph(self, from_line: int) -> int:
        """Return the first line of the paragraph that starts before the one
        containing *from_line*.  Falls back to line 0 if none found."""
        i = from_line - 1
        # Skip blank lines backward
        while i > 0 and not self.rendered[i]:
            i -= 1
        # Walk back through the previous paragraph's content
        while i > 0 and self.rendered[i]:
            i -= 1
        # Now i is on a blank line (or 0) — step forward to the first content line
        if not self.rendered[i]:  # blank
            i += 1
        return max(0, i)

    def _find_next_heading(self, from_line: int) -> Optional[int]:
        """Return the line index of the next heading after *from_line*, or
        None if there is no heading below the current position."""
        for i in range(from_line + 1, len(self.rendered)):
            if self._is_heading_line(i):
                return i
        return None

    def _find_prev_heading(self, from_line: int) -> Optional[int]:
        """Return the line index of the previous heading before *from_line*,
        or None if there is no heading above the current position."""
        for i in range(from_line - 1, -1, -1):
            if self._is_heading_line(i):
                return i
        return None

    def _skip_next_paragraph(self) -> None:
        if not self.rendered:
            return
        dest = self._find_next_paragraph(self.scroll)
        self._navigate_to(dest)
        self.notify(f"Paragraph →  line {dest + 1}")

    def _skip_prev_paragraph(self) -> None:
        if not self.rendered:
            return
        dest = self._find_prev_paragraph(self.scroll)
        self._navigate_to(dest)
        self.notify(f"Paragraph ←  line {dest + 1}")

    def _is_table_line(self, line_idx: int) -> bool:
        """Return True if the rendered line at *line_idx* contains table content."""
        if 0 <= line_idx < len(self.rendered):
            return any(role in _TABLE_ROLES for _, role in self.rendered[line_idx])
        return False

    def _find_next_table(self, from_line: int) -> Optional[int]:
        """Return the first line of the next table after *from_line*, or None."""
        n = len(self.rendered)
        i = from_line + 1
        # Skip through any table we're currently inside
        while i < n and self._is_table_line(i):
            i += 1
        for j in range(i, n):
            if self._is_table_line(j):
                return j
        return None

    def _find_prev_table(self, from_line: int) -> Optional[int]:
        """Return the first line of the previous table before *from_line*, or None."""
        i = from_line - 1
        # Skip through any table we're currently inside
        while i >= 0 and self._is_table_line(i):
            i -= 1
        # Scan backward for any table line
        while i >= 0 and not self._is_table_line(i):
            i -= 1
        if i < 0:
            return None
        # Walk back to the start of this table block
        while i > 0 and self._is_table_line(i - 1):
            i -= 1
        return i

    def _skip_next_table(self) -> None:
        dest = self._find_next_table(self.scroll)
        if dest is None:
            self.notify("No table below current position")
            return
        self._navigate_to(dest)
        self.notify(f"▼ Table — line {dest + 1}")

    def _skip_prev_table(self) -> None:
        dest = self._find_prev_table(self.scroll)
        if dest is None:
            self.notify("No table above current position")
            return
        self._navigate_to(dest)
        self.notify(f"▲ Table — line {dest + 1}")

    def _skip_next_heading(self) -> None:
        if not self.rendered:
            return
        dest = self._find_next_heading(self.scroll)
        if dest is None:
            self.notify("No heading below current position")
            return
        self._navigate_to(dest)
        # Show the heading text in the notification
        heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
        self.notify(f"↓ Heading: {heading_text[:50]}")

    def _skip_prev_heading(self) -> None:
        if not self.rendered:
            return
        dest = self._find_prev_heading(self.scroll)
        if dest is None:
            self.notify("No heading above current position")
            return
        self._navigate_to(dest)
        heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
        self.notify(f"↑ Heading: {heading_text[:50]}")

    # ── Read-from-heading  (’>’ / ’<’) ──────────────────────────────────────

    def _line_to_word(self, line: int) -> int:
        """Return the word-map index of the first word at or after *line*.
        Returns 0 when the word map is unavailable."""
        if self.doc and self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= line:
                    return i
        return 0

    def _read_next_heading(self) -> None:
        """Jump to the next heading and *always* begin TTS reading from it.

        Unlike ’}’ (which only resumes speech if it was already playing),
        this command starts the engine unconditionally so the user can
        move through headings while the document is stopped.
        """
        if not self.rendered:
            return
        dest_line = self._find_next_heading(self.scroll)
        if dest_line is None:
            self.notify("No heading below current position")
            return
        dest_word = self._line_to_word(dest_line)
        heading_text = "".join(t for t, _ in self.rendered[dest_line]).strip()
        self._sentence_jump(
            dest_word,
            f"⏩ Reading from: {heading_text[:60]}",
            always_play=True,
        )

    def _read_prev_heading(self) -> None:
        """Jump to the previous heading and *always* begin TTS reading from it.

        Unlike ’{’ (which only resumes speech if it was already playing),
        this command starts the engine unconditionally.
        """
        if not self.rendered:
            return
        dest_line = self._find_prev_heading(self.scroll)
        if dest_line is None:
            self.notify("No heading above current position")
            return
        dest_word = self._line_to_word(dest_line)
        heading_text = "".join(t for t, _ in self.rendered[dest_line]).strip()
        self._sentence_jump(
            dest_word,
            f"⏪ Reading from: {heading_text[:60]}",
            always_play=True,
        )

    # ── Scrolling ─────────────────────────────────────────────────────────

    def _scroll_by(self, delta: int) -> None:
        total = len(self.rendered)
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        self.scroll = max(0, min(total - 1, self.scroll + delta))

    def _page_down(self) -> None:
        h, _ = self.scr.getmaxyx()
        self._scroll_by(max(1, h - 5))

    def _page_up(self) -> None:
        h, _ = self.scr.getmaxyx()
        self._scroll_by(-max(1, h - 5))

    def _goto_top(self) -> None:
        self.scroll = 0

    def _goto_bottom(self) -> None:
        self.scroll = max(0, len(self.rendered) - 1)

    def _scroll_to_line(self, display_line: int) -> None:
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        margin = int(self.settings["scroll_margin"])
        self.scroll = max(0, min(len(self.rendered) - 1, display_line - view_h // 3))

    def _goto_line_prompt(self) -> None:
        self._enter_minibuffer("Go to line: ", on_commit=self._goto_line_cb)

    def _goto_line_cb(self, s: str) -> None:
        try:
            ln = max(1, int(s.strip())) - 1
            self._scroll_to_line(min(ln, len(self.rendered) - 1))
        except ValueError:
            self.notify(f"Invalid line: {s}", error=True)
