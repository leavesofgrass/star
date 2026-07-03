"""CoreNavMixin — sentence / paragraph / heading / table navigation.

Split out of the former ``mixin_navigation.py`` monolith; methods moved
verbatim.  Mixed into StarWindow via ``NavigationMixin``; holds no state of
its own, operating on StarWindow instance state via ``self``.

IMPORT SAFETY: references Qt at module scope — imported lazily by
main_window.py (itself imported by runner.py after the _QT guard).
"""
from ..._runtime import *  # noqa: F401,F403


class CoreNavMixin:
    # ── Navigation (sentence · paragraph · heading) ────────────────────────

    # ─ helpers ─────────────────────────────────────────────────────────

    def _qt_current_word_for_nav(self) -> int:
        """Best estimate of the current reading position (word index).

        Priority:
        1. Callback-confirmed audio word (most accurate when speaking).
        2. Timer estimate (when speaking but no callback yet).
        3. QTextEdit text-cursor position (when TTS is idle).
           The editor cursor is moved by _apply_word_highlight during TTS
           and by _qt_navigate_to_word during manual navigation, so it
           always reflects the last reading or navigation point.  This
           ensures _qt_save_reading_position records a useful position
           even after TTS has been stopped.
        """
        if self.tts_manager.speaking:
            cb = self.tts_manager.last_cb_word_idx
            if cb >= 0:
                return cb
            idx = self.tts_manager.current_word_idx
            if idx >= 0:
                return idx
        # TTS idle: derive position from the editor’s text cursor.
        qwm = self._qt_word_map
        if qwm:
            char_pos = self.editor.textCursor().position()
            for i, off in enumerate(qwm):
                if off >= char_pos:
                    return i
            return len(qwm) - 1  # cursor is past the last mapped word
        return 0

    def _qt_find_sentence_idx(self, word_idx: int) -> int:
        """Binary-search _qt_sentence_starts for the sentence containing
        *word_idx* (same algorithm as StarApp._find_sentence_idx)."""
        ss = self._qt_sentence_starts
        lo, hi, result = 0, len(ss) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if ss[mid] <= word_idx:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def _qt_navigate_to_word(
        self, word_idx: int, always_play: bool = False
    ) -> None:
        """Stop TTS, scroll the editor to *word_idx*, and restart speech
        if it was already running (or if *always_play* is True)."""
        was_speaking = self.tts_manager.speaking
        self.tts_manager.stop()
        self.editor.setExtraSelections([])
        wm = getattr(self.doc, "word_map", []) if self.doc else []
        if not wm or word_idx >= len(wm):
            return
        # Pagination: advance the rendered window to the target if it is off
        # screen so its char offset exists (no-op when pagination is off).
        if getattr(self, "_paginator", None) is not None:
            self._page_ensure_word_visible(word_idx)
        qwm = self._qt_word_map
        if word_idx < len(qwm) and qwm[word_idx] >= 0:
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(qwm[word_idx])
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        if was_speaking or always_play:
            self._tts_play_from_word(word_idx)

    def _qt_block_to_word(self, block_num: int) -> int:
        """Return the word-map index of the first word inside QTextBlock
        *block_num*, searching forward through _qt_word_map."""
        block = self.editor.document().findBlockByNumber(block_num)
        if not block.isValid():
            return 0
        char_pos = block.position()
        for i, off in enumerate(self._qt_word_map):
            if off >= char_pos:
                return i
        return 0

    def _qt_current_block(self) -> int:
        """Block number that best represents the current reading position.
        Uses the word map when speaking, otherwise the text cursor."""
        cur_word = self._qt_current_word_for_nav()
        qwm = self._qt_word_map
        if cur_word < len(qwm):
            char_pos = qwm[cur_word]
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(char_pos)
            return cursor.blockNumber()
        return self.editor.textCursor().blockNumber()

    def _qt_is_heading_block(self, block_num: int) -> bool:
        """Return True if the QTextBlock at *block_num* is a heading."""
        block = self.editor.document().findBlockByNumber(block_num)
        if not block.isValid():
            return False
        try:
            return block.blockFormat().headingLevel() > 0
        except AttributeError:
            return False  # Qt < 5.12 — heading level API unavailable

    # ─ sentence ──────────────────────────────────────────────────────────

    def _qt_skip_next_sentence(self) -> None:
        """Jump to the next sentence; restart speech if it was playing."""
        if not self.doc or not self.doc.word_map:
            return
        cur = self._qt_current_word_for_nav()
        si = self._qt_find_sentence_idx(cur)
        nsi = si + 1
        if nsi >= len(self._qt_sentence_starts):
            self.statusBar().showMessage("No next sentence")
            return
        dest = self._qt_sentence_starts[nsi]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        total = len(self._qt_sentence_starts)
        self._qt_navigate_to_word(dest)
        self.statusBar().showMessage(f"→ Sentence {nsi + 1}/{total}: “{preview}…”")

    def _qt_skip_prev_sentence(self) -> None:
        """Jump to the previous sentence (or replay the current one if
        more than 3 words in); restart speech if it was playing."""
        if not self.doc or not self.doc.word_map:
            return
        cur = self._qt_current_word_for_nav()
        si = self._qt_find_sentence_idx(cur)
        psi = si if cur - self._qt_sentence_starts[si] > 3 else max(0, si - 1)
        dest = self._qt_sentence_starts[psi]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        total = len(self._qt_sentence_starts)
        self._qt_navigate_to_word(dest)
        self.statusBar().showMessage(f"← Sentence {psi + 1}/{total}: “{preview}…”")

    def _qt_replay_sentence(self) -> None:
        """Jump to the start of the current sentence and *always* begin
        reading, matching the TUI\'s ’;’ key behavior."""
        if not self.doc or not self.doc.word_map:
            return
        cur = self._qt_current_word_for_nav()
        si = self._qt_find_sentence_idx(cur)
        dest = self._qt_sentence_starts[si]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        self._qt_navigate_to_word(dest, always_play=True)
        self.statusBar().showMessage(f"↺ Replaying: “{preview}…”")

    # ─ paragraph ─────────────────────────────────────────────────────────

    def _qt_skip_next_paragraph(self) -> None:
        """Jump to the next paragraph; restart speech if it was playing."""
        doc_obj = self.editor.document()
        n = doc_obj.blockCount()
        cur_block = self._qt_current_block()
        i = cur_block + 1
        # Skip through any remaining content of the current paragraph
        while i < n and doc_obj.findBlockByNumber(i).text().strip():
            i += 1
        # Skip blank separator blocks
        while i < n and not doc_obj.findBlockByNumber(i).text().strip():
            i += 1
        if i >= n:
            self.statusBar().showMessage("No next paragraph")
            return
        self._qt_navigate_to_word(self._qt_block_to_word(i))
        self.statusBar().showMessage(f"¶  Next paragraph — block {i + 1}")

    def _qt_skip_prev_paragraph(self) -> None:
        """Jump to the previous paragraph; restart speech if it was playing."""
        doc_obj = self.editor.document()
        cur_block = self._qt_current_block()
        i = cur_block - 1
        # Skip blank lines backward
        while i > 0 and not doc_obj.findBlockByNumber(i).text().strip():
            i -= 1
        # Walk back through the previous paragraph’s content
        while i > 0 and doc_obj.findBlockByNumber(i - 1).text().strip():
            i -= 1
        i = max(0, i)
        self._qt_navigate_to_word(self._qt_block_to_word(i))
        self.statusBar().showMessage(f"¶  Prev paragraph — block {i + 1}")

    def _qt_replay_paragraph(self) -> None:
        """Jump to the start of the current paragraph and *always* begin
        reading, matching the TUI\'s ’r’ key behavior."""
        doc_obj = self.editor.document()
        cur_block = self._qt_current_block()
        # Walk back to the first block of this paragraph
        i = cur_block
        while i > 0 and doc_obj.findBlockByNumber(i - 1).text().strip():
            i -= 1
        # Step forward past any leading blank lines
        n = doc_obj.blockCount()
        while i < n - 1 and not doc_obj.findBlockByNumber(i).text().strip():
            i += 1
        self._qt_navigate_to_word(self._qt_block_to_word(i), always_play=True)
        self.statusBar().showMessage(f"↺ Replaying paragraph from block {i + 1}")

    # ─ heading ───────────────────────────────────────────────────────────

    def _qt_skip_next_heading(self) -> None:
        """Scroll to next heading; restart speech if it was playing."""
        doc_obj = self.editor.document()
        n = doc_obj.blockCount()
        start = self._qt_current_block() + 1
        for i in range(start, n):
            if self._qt_is_heading_block(i):
                heading_text = doc_obj.findBlockByNumber(i).text().strip()
                self._qt_navigate_to_word(self._qt_block_to_word(i))
                self.statusBar().showMessage(f"↓ Heading: {heading_text[:60]}")
                return
        self.statusBar().showMessage("No heading below current position")

    def _qt_skip_prev_heading(self) -> None:
        """Scroll to previous heading; restart speech if it was playing."""
        doc_obj = self.editor.document()
        start = self._qt_current_block() - 1
        for i in range(start, -1, -1):
            if self._qt_is_heading_block(i):
                heading_text = doc_obj.findBlockByNumber(i).text().strip()
                self._qt_navigate_to_word(self._qt_block_to_word(i))
                self.statusBar().showMessage(f"↑ Heading: {heading_text[:60]}")
                return
        self.statusBar().showMessage("No heading above current position")

    def _qt_read_next_heading(self) -> None:
        """Jump to next heading and *always* begin reading (TUI ’>’)."""
        doc_obj = self.editor.document()
        n = doc_obj.blockCount()
        start = self._qt_current_block() + 1
        for i in range(start, n):
            if self._qt_is_heading_block(i):
                heading_text = doc_obj.findBlockByNumber(i).text().strip()
                self._qt_navigate_to_word(
                    self._qt_block_to_word(i), always_play=True
                )
                self.statusBar().showMessage(
                    f"⏩ Reading from: {heading_text[:60]}"
                )
                return
        self.statusBar().showMessage("No heading below current position")

    def _qt_read_prev_heading(self) -> None:
        """Jump to previous heading and *always* begin reading (TUI '<')."""
        doc_obj = self.editor.document()
        start = self._qt_current_block() - 1
        for i in range(start, -1, -1):
            if self._qt_is_heading_block(i):
                heading_text = doc_obj.findBlockByNumber(i).text().strip()
                self._qt_navigate_to_word(
                    self._qt_block_to_word(i), always_play=True
                )
                self.statusBar().showMessage(
                    f"⏪ Reading from: {heading_text[:60]}"
                )
                return
        self.statusBar().showMessage("No heading above current position")

    # ─ table ──────────────────────────────────────────────────────────────

    def _qt_is_table_block(self, block_num: int) -> bool:
        """Return True when block *block_num* is a markdown table line.

        In the current renderer, table rows appear as plain paragraphs
        whose text starts with the pipe character '|'.
        """
        block = self.editor.document().findBlockByNumber(block_num)
        if not block.isValid():
            return False
        return block.text().lstrip().startswith("|")

    def _qt_skip_next_table(self) -> None:
        """Jump to the first row of the next table (Ctrl+T)."""
        doc_obj = self.editor.document()
        n = doc_obj.blockCount()
        cur = self._qt_current_block()
        # Skip out of any table we're currently inside.
        i = cur + 1
        while (
            i < n and self._qt_is_table_block(i - 1) and self._qt_is_table_block(i)
        ):
            i += 1
        # Skip non-table blocks to find the next table start.
        while i < n and not self._qt_is_table_block(i):
            i += 1
        if i >= n:
            self.statusBar().showMessage("No table below current position")
            return
        self._qt_navigate_to_word(self._qt_block_to_word(i))
        preview = doc_obj.findBlockByNumber(i).text()[:60]
        self.statusBar().showMessage(f"▼ Table: {preview}")

    def _qt_skip_prev_table(self) -> None:
        """Jump to the first row of the previous table (Ctrl+Shift+T)."""
        doc_obj = self.editor.document()
        cur = self._qt_current_block()
        # Skip back through the current table (if any).
        i = cur - 1
        while i > 0 and self._qt_is_table_block(i):
            i -= 1
        # Skip non-table blocks backward to find the end of the prev table.
        while i > 0 and not self._qt_is_table_block(i):
            i -= 1
        if i < 0 or not self._qt_is_table_block(i):
            self.statusBar().showMessage("No table above current position")
            return
        # Walk to the first row of that table.
        while i > 0 and self._qt_is_table_block(i - 1):
            i -= 1
        self._qt_navigate_to_word(self._qt_block_to_word(i))
        preview = doc_obj.findBlockByNumber(i).text()[:60]
        self.statusBar().showMessage(f"▲ Table: {preview}")
