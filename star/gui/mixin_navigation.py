"""NavigationMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(NavigationMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import _build_word_map
from ..i18n import tr
from ..spellcheck import _SPELL, SpellHighlighter, misspelled_words
from ..library import (
    progress_for,
    record_progress,
)
from ..tts import Pyttsx3Backend, _SCReader
from ..ttstext import _preprocess_tts_text, _strip_markdown_for_tts


class NavigationMixin:
    # ── Speech Cursor mode (Qt) ─────────────────────────────────────

    def _key_enums(self) -> Tuple[Any, ...]:
        """Resolve and cache the Qt event-type / Control-key enums once.

        Returns ``(KeyPress, KeyRelease, ShortcutOverride, Shortcut,
        Key_Control)`` for whichever PyQt binding is active.
        """
        if self._key_enum_cache is not None:
            return self._key_enum_cache
        try:
            from PyQt6.QtCore import QEvent

            ET = QEvent.Type
            vals = (
                ET.KeyPress,
                ET.KeyRelease,
                ET.ShortcutOverride,
                ET.Shortcut,
                Qt.Key.Key_Control,
            )
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            vals = (
                QEvent.KeyPress,  # type: ignore[attr-defined]
                QEvent.KeyRelease,  # type: ignore[attr-defined]
                QEvent.ShortcutOverride,  # type: ignore[attr-defined]
                QEvent.Shortcut,  # type: ignore[attr-defined]
                Qt.Key_Control,  # type: ignore[attr-defined]
            )
        self._key_enum_cache = vals
        return vals

    def _ctrl_tap_track(self, event: Any) -> None:
        """JAWS-style bare-Ctrl tap → play/pause.

        Tracks Ctrl key presses/releases on the editor.  A clean tap
        (Ctrl pressed and released with no other key, shortcut-override,
        or fired shortcut in between) toggles speech.  Using Ctrl as a
        modifier in a chord never triggers it.  Opt out via the
        ``qt_ctrl_pause`` setting.
        """
        if not self.settings.get("qt_ctrl_pause", True):
            return
        kp, kr, so, sh, k_ctrl = self._key_enums()
        et = event.type()
        if et == sh:
            # A shortcut fired — Ctrl was part of a chord, not a tap.
            self._ctrl_solo = False
            return
        if et in (kp, so):
            try:
                k = event.key()
                repeat = event.isAutoRepeat()
            except Exception:
                return
            if et == kp and k == k_ctrl and not repeat:
                self._ctrl_solo = True
                self._ctrl_press_t = time.monotonic()
            elif k != k_ctrl:
                # Any other key (or shortcut-override) cancels the tap.
                self._ctrl_solo = False
        elif et == kr:
            try:
                k = event.key()
                repeat = event.isAutoRepeat()
            except Exception:
                return
            if k == k_ctrl and not repeat:
                tap = (
                    self._ctrl_solo
                    and (time.monotonic() - self._ctrl_press_t) < 0.6
                )
                self._ctrl_solo = False
                if tap and not self._qt_edit_mode:
                    self._tts_toggle()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """Intercept keyboard events on the editor.

        Ctrl (tapped alone) — play / pause speech (JAWS habit)
        Tab    — enter / exit Speech Cursor mode
        While in SC mode:
          ↑ / ↓  — previous / next block, read it
          Enter  — exit SC mode and start continuous reading
          Esc    — exit SC mode, stop speech
        """
        # Find bar input: Escape closes it; F3 / Shift+F3 and Shift+Enter walk
        # matches even while the line edit holds focus.  Handled before the
        # editor branch because the find input is a different widget.
        if obj is getattr(self, "_find_input", None):
            if self._find_input_key(event):
                return True
            return super().eventFilter(obj, event)

        # Clicking an in-document anchor (footnote marker or its ↩ backlink) jumps
        # to it.  Mouse events land on the editor's viewport, not the editor.
        if self.editor is not None and obj is self.editor.viewport():
            if self._editor_anchor_click(event):
                return True
            return super().eventFilter(obj, event)

        if obj is not self.editor:
            return super().eventFilter(obj, event)

        # JAWS-style bare-Ctrl tap toggles speech (never consumes the event).
        self._ctrl_tap_track(event)

        try:
            from PyQt6.QtCore import QEvent  # noqa: F401

            kp = QEvent.Type.KeyPress
            Key = Qt.Key
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            kp = QEvent.KeyPress  # type: ignore
            Key = Qt  # type: ignore

        if event.type() != kp:
            return super().eventFilter(obj, event)

        key = event.key()

        try:
            k_tab = Key.Key_Tab
            k_up = Key.Key_Up
            k_dn = Key.Key_Down
            k_esc = Key.Key_Escape
            k_ret = Key.Key_Return
            k_ent = Key.Key_Enter
        except AttributeError:  # PyQt5 uses Qt.Key_Tab etc. directly
            k_tab = Qt.Key_Tab  # type: ignore
            k_up = Qt.Key_Up  # type: ignore
            k_dn = Qt.Key_Down  # type: ignore
            k_esc = Qt.Key_Escape  # type: ignore
            k_ret = Qt.Key_Return  # type: ignore
            k_ent = Qt.Key_Enter  # type: ignore

        if key == k_tab:
            if self._qt_sc_mode:
                self._qt_sc_exit()
            else:
                self._qt_sc_enter()
            return True  # consume; don't let Tab move focus

        if not self._qt_sc_mode:
            return super().eventFilter(obj, event)

        if key in (k_esc,):
            self._qt_sc_exit()
            return True
        if key in (k_ret, k_ent):
            self._qt_sc_exit(start_reading=True)
            return True
        if key == k_up:
            self._qt_sc_move(-1)
            return True
        if key == k_dn:
            self._qt_sc_move(+1)
            return True

        return super().eventFilter(obj, event)

    def _editor_anchor_click(self, event: Any) -> bool:
        """Jump to an in-document anchor when its link is clicked.

        Footnote markers link to ``#fn-<label>`` and their backlinks to
        ``#fnref-<label>``; ``scrollToAnchor`` matches the ``<a name=…>`` targets
        the renderer emits.  Returns True only when an anchor was actually clicked
        (so ordinary clicks still place the caret)."""
        try:
            from PyQt6.QtCore import QEvent

            rel = QEvent.Type.MouseButtonRelease
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            rel = QEvent.MouseButtonRelease  # type: ignore
        if event.type() != rel:
            return False
        try:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            anchor = self.editor.anchorAt(pos)
        except Exception:
            return False
        if not anchor:
            return False
        name = anchor[1:] if anchor.startswith("#") else anchor
        try:
            self.editor.scrollToAnchor(name)
        except Exception:
            return False
        return True

    def _qt_sc_enter(self) -> None:
        """Enter Qt Speech Cursor mode.

        Stops any running TTS, positions the reading cursor at the
        visible text-cursor position, and builds the persistent
        _SCReader engine so the first line has no startup lag.
        """
        self.tts_manager.stop()
        self.editor.setExtraSelections([])
        # Position SC cursor at the block under the text cursor.
        tc = self.editor.textCursor()
        self._qt_sc_block = tc.blockNumber()
        # Build the persistent reader so the first keystroke has no
        # SAPI5 engine-creation delay and stop() is always effective.
        if _PYTTSX3 and isinstance(self.tts_manager._backend, Pyttsx3Backend):
            self._qt_sc_reader = _SCReader(
                rate=int(self.settings["tts_rate"]),
                volume=float(self.settings["tts_volume"]),
            )
            self._qt_sc_reader.start()
        else:
            self._qt_sc_reader = None
        self._qt_sc_mode = True
        self._qt_sc_highlight()
        self.setWindowTitle(f"● SC CURSOR — {APP_TITLE}")
        self.statusBar().showMessage(
            "Speech Cursor ON  ↑↓:line  Enter:read-on  Esc/Tab:exit"
        )

    def _qt_sc_exit(self, start_reading: bool = False) -> None:
        """Exit Qt Speech Cursor mode.  Speech is always stopped first."""
        self._qt_sc_mode = False
        # Stop the persistent reader before stopping the main manager
        # so the SAPI5 engine is always reachable.
        if self._qt_sc_reader is not None:
            self._qt_sc_reader.close()
            self._qt_sc_reader = None
        self.tts_manager.stop()
        self.editor.setExtraSelections([])
        self.setWindowTitle(APP_TITLE)
        if start_reading:
            # Start continuous reading from the SC cursor position.
            doc_obj = self.editor.document()
            block = doc_obj.findBlockByNumber(self._qt_sc_block)
            if block.isValid():
                char_pos = block.position()
                wm = getattr(self.doc, "word_map", [])
                if wm:
                    qwm = self._qt_word_map
                    wi = 0
                    for i, off in enumerate(qwm):
                        if off >= char_pos:
                            wi = i
                            break
                    self._tts_play_from_word(wi)
                    self.statusBar().showMessage(
                        f"Reading from line {self._qt_sc_block + 1}"
                    )
                    return
            self._tts_play()
        else:
            self.statusBar().showMessage("Speech Cursor OFF")

    def _qt_sc_move(self, delta: int) -> None:
        """Move the SC cursor by *delta* blocks and read the new block."""
        doc_obj = self.editor.document()
        n_blocks = doc_obj.blockCount()
        if n_blocks == 0:
            return
        self._qt_sc_block = max(0, min(self._qt_sc_block + delta, n_blocks - 1))
        self._qt_sc_highlight()
        self._qt_sc_read_block()

    def _qt_sc_highlight(self) -> None:
        """Highlight the current SC cursor block with a bar selection."""
        doc_obj = self.editor.document()
        block = doc_obj.findBlockByNumber(self._qt_sc_block)
        if not block.isValid():
            return
        tc = QTextCursor(block)
        self.editor.setTextCursor(tc)
        self.editor.ensureCursorVisible()
        tc2 = QTextCursor(block)
        tc2.select(
            QTextCursor.SelectionType.BlockUnderCursor
            if hasattr(QTextCursor, "SelectionType")
            else QTextCursor.BlockUnderCursor  # type: ignore
        )
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#313244"))
        sel = QTextEdit.ExtraSelection()
        sel.cursor = tc2
        sel.format = fmt
        self.editor.setExtraSelections([sel])

    def _qt_sc_read_block(self) -> None:
        """Speak the plain text of the current SC cursor block.

        Uses the persistent _SCReader when the pyttsx3 backend is
        active so that stop() is always effective and there is no
        200–500 ms SAPI5 engine-construction window between navigation
        keystrokes.  Falls back to direct backend.speak() for eSpeak
        and other subprocess-based backends where termination is
        trivially reliable.
        """
        doc_obj = self.editor.document()
        block = doc_obj.findBlockByNumber(self._qt_sc_block)
        text = block.text().strip() if block.isValid() else ""
        # Stop the main TTS manager (clears timer, highlight, etc.) then
        # drive speech through the SC reader or backend directly.
        self.tts_manager.stop()
        if not text:
            if self._qt_sc_reader is not None:
                self._qt_sc_reader.speak("blank")
            else:
                self.tts_manager._backend.speak("blank")
            self.statusBar().showMessage(
                f"SC  —  line {self._qt_sc_block + 1}: (blank)"
            )
            return
        text = _preprocess_tts_text(text, self.settings)
        if self._qt_sc_reader is not None:
            self._qt_sc_reader.speak(text)
        else:
            self.tts_manager._backend.speak(text)
        self.statusBar().showMessage(
            f"SC  —  line {self._qt_sc_block + 1}: {text[:80]}"
        )

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

    # ─ document editing ───────────────────────────────────────────────

    def _qt_edit_mode_toggle(self) -> None:
        """Toggle between read mode and edit mode (Ctrl+E).

        In *read mode* the editor displays rendered HTML and is
        read-only.  In *edit mode* the raw Markdown source is shown
        as plain text so the user can make changes with any standard
        text-editing shortcut (Ctrl+Z/Y, Ctrl+X/C/V, arrow keys,
        Delete, Home, End, …).  Ctrl+S saves; Ctrl+E exits without
        saving.
        """
        if not self._qt_edit_mode:
            self._qt_enter_edit_mode()
        else:
            self._qt_exit_edit_mode(save=False)

    def _qt_enter_edit_mode(self) -> None:
        """Switch the editor to editable Markdown source view."""
        if not self.doc:
            self.statusBar().showMessage("No document to edit")
            return
        self.tts_manager.stop()
        self.editor.setReadOnly(False)
        self.editor.setCursorWidth(2)  # visible text cursor
        # Show raw Markdown so the user edits the source, not HTML.
        self.editor.setPlainText(self.doc.markdown or "")
        self.editor.document().setModified(False)
        self._qt_edit_mode = True
        self._qt_edit_dirty = False
        self.editor.document().contentsChanged.connect(
            self._qt_on_edit_contents_changed
        )
        # Attach the red-squiggle spell highlighter while editing (only when
        # pyspellchecker and a Qt QSyntaxHighlighter are both available).
        if _SPELL and SpellHighlighter is not None:
            try:
                self._spell_highlighter = SpellHighlighter(self.editor.document())
            except Exception:  # noqa: BLE001
                self._spell_highlighter = None
        # If the live-preview preference is on, show the preview pane now
        # and render the current source into it.
        if self.settings.get("qt_edit_preview", False):
            self._preview.setVisible(True)
            self._qt_render_preview()
            self.statusBar().showMessage(
                "✏  EDIT MODE — Markdown source + live preview  ·  "
                "Ctrl+S: save  ·  Ctrl+E: discard & exit"
            )
        else:
            self.statusBar().showMessage(
                "✏  EDIT MODE — Markdown source  ·  "
                "Ctrl+S: save  ·  Ctrl+E: discard & exit  ·  "
                "Ctrl+Shift+L: live preview"
            )

    def _qt_on_edit_contents_changed(self) -> None:
        """Mark the document dirty when the user types in edit mode and,
        when the live preview is visible, schedule a debounced re-render."""
        if not self._qt_edit_dirty:
            self._qt_edit_dirty = True
            title = self.doc.title if self.doc else "document"
            self.statusBar().showMessage(
                f"✏  EDIT MODE  ·  {title}  [modified — Ctrl+S to save]"
            )
        if self._qt_edit_mode and self._preview.isVisible():
            # Re-render ~300 ms after the last keystroke (keeps typing snappy).
            self._preview_timer.start(300)

    def _qt_exit_edit_mode(self, save: bool = False) -> None:
        """Leave edit mode, optionally saving first."""
        if not self._qt_edit_mode:
            return
        if save:
            self._qt_save()
        # Disconnect the dirty listener.
        try:
            self.editor.document().contentsChanged.disconnect(
                self._qt_on_edit_contents_changed
            )
        except (RuntimeError, TypeError):
            pass
        # Detach the spell highlighter so it stops re-checking the read-only view.
        if self._spell_highlighter is not None:
            try:
                self._spell_highlighter.setDocument(None)
            except Exception:  # noqa: BLE001
                pass
            self._spell_highlighter = None
        self._qt_edit_mode = False
        self._qt_edit_dirty = False
        # The preview pane is only meaningful while editing; hide it.
        self._preview.setVisible(False)
        # Re-render the (possibly updated) Markdown.
        md = self.doc.markdown if self.doc else ""
        self.editor.setReadOnly(True)
        self._apply_caret_mode()
        self.editor.setHtml(self._md_to_html(md))
        self._apply_block_spacing()
        self._qt_apply_user_highlights()
        self.statusBar().showMessage("Read mode")

    def _qt_check_spelling(self) -> None:
        """Count and report misspelled words in the current text (F7).

        Works whether or not the live red-squiggle highlighter is running:
        it checks the editable source in edit mode, otherwise the loaded
        document's plain text.
        """
        if not self._qt_require_optional_feature("spellcheck", tr("Spell check")):
            return
        if self._qt_edit_mode:
            text = self.editor.toPlainText()
        elif self.doc:
            text = self.doc.plain_text or ""
        else:
            self.statusBar().showMessage("Open a document to check spelling")
            return
        bad = sorted(misspelled_words(text))
        if not bad:
            QMessageBox.information(
                self, "Spell check", "No misspelled words found."
            )
            return
        preview = ", ".join(bad[:25])
        if len(bad) > 25:
            preview += ", …"
        QMessageBox.information(
            self,
            "Spell check",
            f"{len(bad)} misspelled word(s) found:\n\n{preview}",
        )

    # ─ live HTML preview (edit mode) ──────────────────────────────────

    def _qt_render_preview(self) -> None:
        """Render the current editor source into the live preview pane."""
        if not self._preview.isVisible():
            return
        md = (
            self.editor.toPlainText()
            if self._qt_edit_mode
            else (self.doc.markdown if self.doc else "")
        )
        # Preserve the reader's scroll position across re-renders.
        bar = self._preview.verticalScrollBar()
        pos = bar.value() if bar else 0
        self._preview.setHtml(self._md_to_html(md))
        if bar:
            bar.setValue(min(pos, bar.maximum()))

    def _qt_toggle_preview(self) -> None:
        """Toggle the live HTML preview pane (Ctrl+Shift+L).

        The preview is meaningful only while editing the Markdown source,
        so turning it on outside edit mode enters edit mode first.
        """
        new = not bool(self.settings.get("qt_edit_preview", False))
        self.settings["qt_edit_preview"] = new
        if hasattr(self, "_preview_act"):
            self._preview_act.setChecked(new)
        if new:
            if not self._qt_edit_mode:
                if not self.doc:
                    self.statusBar().showMessage("Open a document to preview")
                    return
                # Entering edit mode shows the preview itself.
                self._qt_enter_edit_mode()
            else:
                self._preview.setVisible(True)
                self._qt_render_preview()
            self.statusBar().showMessage("Live HTML preview: ON")
        else:
            self._preview.setVisible(False)
            self.statusBar().showMessage("Live HTML preview: OFF")

    # ─ reading statistics & library ───────────

    def _qt_save(self) -> None:
        """Save the current document.

        In *edit mode*: the edited Markdown is written back to the
        original file (for .md / .markdown / .txt / .rst / .org);
        for any other format a Save-As dialog is shown.  The document
        is then re-rendered and the TTS word maps are rebuilt.

        In *read mode*: falls through to the Markdown export dialog
        (same as File → Export → Export as Markdown…).
        """
        if not self._qt_edit_mode:
            # Not editing — offer markdown export.
            self._qt_export_markdown()
            return

        if not self.doc:
            return

        # Capture the edited source from the plain-text editor.
        new_md = self.editor.toPlainText()

        # --- persist to disk -------------------------------------------
        orig = Path(self.doc.path) if self.doc.path else None
        text_exts = {
            ".md",
            ".markdown",
            ".txt",
            ".rst",
            ".org",
            ".adoc",
            ".asc",
            ".asciidoc",
        }
        if orig and orig.suffix.lower() in text_exts:
            try:
                orig.write_text(new_md, encoding="utf-8")
                saved_path = str(orig)
            except OSError as exc:
                self.statusBar().showMessage(f"Save error: {exc}")
                return
        else:
            # Binary or non-text format — prompt for a .md path.
            stem = orig.stem if orig else "document"
            parent = str(orig.parent) if orig else ""
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Save As Markdown",
                str(Path(parent) / (stem + ".md")),
                "Markdown (*.md *.markdown)",
            )
            if not dest:
                return
            try:
                Path(dest).write_text(new_md, encoding="utf-8")
                saved_path = dest
            except OSError as exc:
                self.statusBar().showMessage(f"Save error: {exc}")
                return

        # --- update in-memory document ---------------------------------
        self.doc.markdown = new_md
        self.doc.plain_text = _strip_markdown_for_tts(
            new_md,
            skip_code=bool(self.settings.get("tts_skip_code", True)),
            table_mode=str(self.settings.get("table_reading_mode", "structured")),
        )
        self._qt_edit_dirty = False

        # --- exit edit mode and re-render ------------------------------
        try:
            self.editor.document().contentsChanged.disconnect(
                self._qt_on_edit_contents_changed
            )
        except (RuntimeError, TypeError):
            pass
        self._qt_edit_mode = False
        self.editor.setReadOnly(True)
        self._apply_caret_mode()
        self.editor.setHtml(self._md_to_html(new_md))
        self._apply_block_spacing()
        self._qt_apply_user_highlights()
        self._qt_build_toc()
        self._qt_build_annotations()

        # Rebuild word maps asynchronously (same flow as _on_doc_loaded_impl)
        qt_plain = self.editor.document().toPlainText()
        doc_ref = self.doc

        def _rebuild() -> None:
            try:
                flat = qt_plain.splitlines()
                doc_ref.word_map = _build_word_map(doc_ref.plain_text, flat)
                self.tts_manager.set_word_map(doc_ref.word_map)
                self._build_qt_word_map(doc_ref.plain_text, qt_plain)
            except Exception:
                pass

        import threading as _threading

        _threading.Thread(target=_rebuild, daemon=True).start()

        self.statusBar().showMessage(f"Saved → {saved_path}")

    # ── Reading position memory ──────────────────────────────────────

    def _qt_save_reading_position(self) -> None:
        """Persist the current reading offset for the open document.
        Identical logic to StarApp._save_reading_position."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return
        cur = self._qt_current_word_for_nav()
        wm = self.doc.word_map
        if cur < 0 or cur >= len(wm):
            return
        offset = wm[cur].tts_offset
        total_chars = len(self.doc.plain_text or "")
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
        # Mirror progress into the library-folder sidecar so it syncs across
        # machines (no-op when the document is not in a library folder).
        record_progress(
            self.settings,
            self.doc.path,
            {"offset": offset, "pct": pct, "ts": positions[self.doc.path]["ts"]},
        )

    def _qt_restore_reading_position(self) -> None:
        """Scroll to the saved position for the current document and
        optionally resume TTS.  Called on the GUI thread via
        _restore_signal after the word map has been built."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return
        if not self.settings.get("tts_auto_resume", True):
            return
        saved = self.settings.get("reading_positions", {}).get(self.doc.path)
        # A library-folder document may carry newer progress in its synced
        # sidecar (e.g. read further on another machine) — prefer whichever is
        # most recent by timestamp.
        side = progress_for(self.settings, self.doc.path)
        if side and (not saved or str(side.get("ts", "")) > str(saved.get("ts", ""))):
            saved = side
        if not saved:
            return
        target_offset = int(saved.get("offset", 0))
        pct = int(saved.get("pct", 0))
        ts = str(saved.get("ts", ""))[:10]
        # Find the word-map entry whose tts_offset is at or beyond the
        # saved offset.
        wm = self.doc.word_map
        best = len(wm) - 1
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        # Scroll the editor to that position and move the text cursor
        # there.  Moving the cursor is essential: _qt_current_word_for_nav
        # reads the cursor position when TTS is idle, so without this
        # a subsequent _qt_save_reading_position call (e.g. from
        # closeEvent before the user ever starts TTS) would see position 0
        # and overwrite the just-restored offset with the start of the doc.
        # Pagination: page to the saved word first so its offset is rendered.
        if getattr(self, "_paginator", None) is not None:
            self._page_ensure_word_visible(best)
        qwm = self._qt_word_map
        if best < len(qwm) and qwm[best] >= 0:
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(qwm[best])
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        self.statusBar().showMessage(f"Resumed at {pct}%  (saved {ts})", 5000)

