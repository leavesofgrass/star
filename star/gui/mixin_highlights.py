"""HighlightsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(HighlightsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..vocab import _WORDFREQ, find_difficult_words
from ._qtcompat import _KEEP_ANCHOR


class HighlightsMixin:
    # ── User highlights ────────────────────────────────────────────────

    def _qt_highlight(self, color: str = "#ffff00") -> None:
        """Highlight the current selection in the given color and persist it.

        If no text is selected, shows a hint in the status bar.
        Default color is yellow; the Highlight menu exposes five presets.
        Shortcut: Ctrl+H (applies yellow highlight).
        """
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self.statusBar().showMessage(
                "Select text first, then press Ctrl+H or choose Highlight menu"
            )
            return
        if not self.doc:
            return
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        path_key = self.doc.path or "__no_path__"
        hl_store: dict = self.settings._data.setdefault("user_highlights", {})
        hl_list: list = hl_store.setdefault(path_key, [])
        hl_list.append({"start": start, "end": end, "color": color})
        self.settings.save()
        self._qt_apply_user_highlights()
        self.statusBar().showMessage(f"Highlight added ({color})")

    def _qt_highlight_clear(self) -> None:
        """Remove all user highlights for the current document."""
        if not self.doc:
            return
        path_key = self.doc.path or "__no_path__"
        hl_store: dict = self.settings._data.get("user_highlights", {})
        if path_key in hl_store:
            hl_store[path_key] = []
        self.settings.save()
        self.editor.setExtraSelections([])
        self.statusBar().showMessage("Highlights cleared")

    def _qt_apply_user_highlights(self) -> None:
        """Re-apply all persisted user highlights for the current document
        as extra selections (non-destructive, does not modify the document)."""
        self.editor.setExtraSelections(self._get_user_highlight_selections())

    def _get_user_highlight_selections(self) -> list:
        """Return a list of ExtraSelection objects for all saved user highlights.
        Called both by _qt_apply_user_highlights and _apply_word_highlight
        so TTS word highlights are always merged on top."""
        if not self.doc:
            return []
        path_key = self.doc.path or "__no_path__"
        highlights = self.settings._data.get("user_highlights", {}).get(
            path_key, []
        )
        doc_obj = self.editor.document()
        doc_len = doc_obj.characterCount()
        selections = []
        for hl in highlights:
            start = hl.get("start", 0)
            end = hl.get("end", 0)
            if start >= end or end > doc_len:
                continue
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(hl.get("color", "#ffff00")))
            cur = QTextCursor(doc_obj)
            cur.setPosition(start)
            cur.setPosition(end, _KEEP_ANCHOR)
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = cur
            selections.append(sel)
        # Difficult-word overlay paints *under* user highlights (so a user
        # highlight always wins where they overlap) and under the TTS word
        # highlight, which _apply_word_highlight appends on top of all of
        # these.
        return self._vocab_selections + selections

    def _compute_vocab_selections(self) -> None:
        """Rebuild the difficult-word overlay's extra-selection cache.

        Scans the rendered document once, flags words whose English Zipf
        frequency is below the threshold, and stores one ExtraSelection per
        occurrence so _get_user_highlight_selections can merge them in
        cheaply on every repaint (including each TTS word step).
        """
        self._vocab_selections = []
        if not (_WORDFREQ and self.doc):
            return
        plain = self.editor.document().toPlainText()
        if not plain:
            return
        difficult = find_difficult_words(plain)
        if not difficult:
            return
        doc_obj = self.editor.document()
        doc_len = doc_obj.characterCount()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#fffacd"))  # lemon chiffon (light yellow)
        selections: List[Any] = []
        for m in re.finditer(r"[A-Za-z]+", plain):
            if m.group(0).lower() not in difficult:
                continue
            start, end = m.start(), m.end()
            if end > doc_len:
                break
            cur = QTextCursor(doc_obj)
            cur.setPosition(start)
            cur.setPosition(end, _KEEP_ANCHOR)
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = cur
            selections.append(sel)
            if len(selections) >= 5000:
                # Soft cap: a pathologically long document can't flood the
                # overlay with selections (and slow every repaint).
                break
        self._vocab_selections = selections

    def _qt_refresh_vocab_highlight(self) -> None:
        """Recompute the overlay (when on) and repaint all extra-selections."""
        if self.settings.get("qt_vocab_highlight", False):
            self._compute_vocab_selections()
        else:
            self._vocab_selections = []
        self._qt_apply_user_highlights()

    def _qt_toggle_vocab_highlight(self) -> None:
        """Toggle the difficult-word overlay on the current document."""
        if not _WORDFREQ:
            QMessageBox.information(
                self,
                "Vocabulary overlay unavailable",
                "Highlighting difficult words requires wordfreq:\n\n"
                "    pip install wordfreq",
            )
            if hasattr(self, "_vocab_act"):
                self._vocab_act.setChecked(False)
            return
        new = not bool(self.settings.get("qt_vocab_highlight", False))
        self.settings["qt_vocab_highlight"] = new
        if hasattr(self, "_vocab_act"):
            self._vocab_act.setChecked(new)
        self._qt_refresh_vocab_highlight()
        self.statusBar().showMessage(
            "Highlight difficult words: " + ("ON" if new else "OFF")
        )

