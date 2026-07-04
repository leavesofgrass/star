"""CaretMixin — free word-granularity caret browsing for the TUI reader.

The caret is a word-map index (``StarApp._caret_word``) with a sticky goal
column for vertical movement, mirroring the Qt GUI's caret browsing.  Arrow
keys move it freely (Left/Right by word, Up/Down by display line, PgUp/PgDn
by screen, Home/End to the document ends); Enter — and Ctrl+Space where the
terminal delivers NUL — starts reading aloud from it; while speech runs it
follows the spoken word (``tui_caret_follow_speech``) unless the user just
moved it deliberately.

Every mover degrades to the classic scroll behavior when no word map exists
yet (document still loading, or the splash fallback), so the keys are never
dead.  Methods run on the main thread; ``_caret_word`` is also written from
the TTS thread (see ``PlaybackMixin._on_highlight``) — plain int writes,
safe without a lock in CPython.

Mixed into StarApp in app.py; calls other groups via ``self``.
"""
import bisect

from .._runtime import *  # noqa: F401,F403

# Seconds after a manual caret move during which follow-speech and the
# speech auto-scroll leave the caret (and viewport) alone, so exploring the
# document mid-read does not fight the reading position.
_CARET_GRACE_S = 3.0


class CaretMixin:

    # ── caret primitives ─────────────────────────────────────────────

    def _caret_wp(self):
        """WordPos under the caret, or None when unplaced / no word map."""
        wm = self.doc.word_map if self.doc else None
        if wm and 0 <= self._caret_word < len(wm):
            return wm[self._caret_word]
        return None

    def _caret_sync(self) -> bool:
        """Place the caret at the current reading word if it is unplaced.

        Returns False when there is no word map to place it in (document
        still loading / splash fallback) — callers then fall back to the
        classic scroll behavior."""
        if not self.doc or not self.doc.word_map:
            return False
        if not (0 <= self._caret_word < len(self.doc.word_map)):
            cur = self._current_word_for_nav()
            self._caret_word = max(0, min(cur, len(self.doc.word_map) - 1))
        return True

    def _caret_scroll_into_view(self) -> None:
        """Keep the caret comfortably visible (same margin as SC mode)."""
        wp = self._caret_wp()
        if wp is None:
            return
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        margin = int(self.settings.get("scroll_margin", 3))
        line = wp.disp_line
        if line < self.scroll + margin:
            self.scroll = max(0, line - margin)
        elif line >= self.scroll + view_h - margin:
            self.scroll = max(0, line - view_h + margin + 1)

    def _caret_after_manual_move(self) -> None:
        self._caret_manual_ts = time.monotonic()
        self._caret_scroll_into_view()

    def _caret_word_at(self, line: int, goal_col: int, direction: int):
        """Index of the word nearest *goal_col* on the first display line at
        or beyond *line* in *direction* (>=0 down, <0 up); None if no words
        lie that way.  word_map is ordered by (disp_line, disp_col), so the
        line lookup is a binary search."""
        wm = self.doc.word_map
        if direction >= 0:
            i = bisect.bisect_left(wm, line, key=lambda wp: wp.disp_line)
            if i >= len(wm):
                return None
        else:
            i = bisect.bisect_left(wm, line + 1, key=lambda wp: wp.disp_line)
            if i == 0:
                return None
            i -= 1  # last word with disp_line <= line
            ln = wm[i].disp_line
            while i > 0 and wm[i - 1].disp_line == ln:
                i -= 1  # rewind to the first word of that line
        ln = wm[i].disp_line
        best, best_d = i, abs(wm[i].disp_col - goal_col)
        j = i + 1
        while j < len(wm) and wm[j].disp_line == ln:
            d = abs(wm[j].disp_col - goal_col)
            if d < best_d:
                best, best_d = j, d
            j += 1
        return best

    # ── caret movement (key handlers) ─────────────────────────────────

    def _caret_move_word(self, delta: int) -> None:
        """Left/Right: move the caret by whole words."""
        if not self._caret_sync():
            return  # nothing to move through yet
        wm = self.doc.word_map
        self._caret_word = max(0, min(self._caret_word + delta, len(wm) - 1))
        self._caret_goal_col = -1  # horizontal move resets the goal column
        self._caret_after_manual_move()

    def _caret_move_line(self, delta: int) -> None:
        """Up/Down: nearest word on an adjacent display line, keeping a
        sticky goal column like a text editor."""
        if not self._caret_sync():
            self._scroll_by(delta)  # classic scroll until a word map exists
            return
        wm = self.doc.word_map
        wp = wm[self._caret_word]
        if self._caret_goal_col < 0:
            self._caret_goal_col = wp.disp_col
        idx = self._caret_word_at(wp.disp_line + delta, self._caret_goal_col, delta)
        if idx is None:
            idx = 0 if delta < 0 else len(wm) - 1
        self._caret_word = idx
        self._caret_after_manual_move()

    def _caret_move_page(self, direction: int) -> None:
        """PgUp/PgDn: a screenful, caret landing near the same column."""
        if not self._caret_sync():
            (self._page_down if direction > 0 else self._page_up)()
            return
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        wm = self.doc.word_map
        wp = wm[self._caret_word]
        if self._caret_goal_col < 0:
            self._caret_goal_col = wp.disp_col
        target = max(0, wp.disp_line + direction * view_h)
        idx = self._caret_word_at(target, self._caret_goal_col, direction)
        if idx is None:
            idx = 0 if direction < 0 else len(wm) - 1
        self._caret_word = idx
        self._caret_after_manual_move()

    def _caret_home(self) -> None:
        if not self._caret_sync():
            self._goto_top()
            return
        self._caret_word = 0
        self._caret_goal_col = -1
        self._caret_after_manual_move()

    def _caret_end(self) -> None:
        if not self._caret_sync():
            self._goto_bottom()
            return
        self._caret_word = len(self.doc.word_map) - 1
        self._caret_goal_col = -1
        self._caret_after_manual_move()

    # ── speech from the caret ─────────────────────────────────────────

    def _caret_play(self) -> None:
        """Enter / Ctrl+Space: start reading aloud from the caret."""
        if not self._caret_sync():
            self._tts_play()  # no word map yet — classic from-viewport start
            return
        self._tts_stop()  # also clears the saved pause position
        self._tts_play_from_word(self._caret_word)
        self.notify("Reading from caret")
