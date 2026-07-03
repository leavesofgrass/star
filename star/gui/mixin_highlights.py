"""HighlightsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(HighlightsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
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
        paged_note = ""
        # A highlight is stored as an *absolute* rendered-char offset into the
        # whole-document render.  Under pagination only a window is rendered, so
        # the selection above is *window-relative* — storing it would corrupt the
        # highlight (BUG 1).  Translate the window selection to whole-document
        # word indices, then suspend pagination (render whole) and re-derive the
        # absolute char offsets from the whole-document word→char map.  This
        # mirrors the "Find suspends pagination" degradation.
        if getattr(self, "_paginator", None) is not None:
            w_start = self._page_word_at_offset(start)
            w_end = self._page_word_at_offset(max(start, end - 1))
            self._page_disable_and_render_whole()
            qwm = getattr(self, "_qt_word_map", []) or []
            if (
                w_start is not None
                and w_end is not None
                and 0 <= w_start < len(qwm)
                and 0 <= w_end < len(qwm)
                and qwm[w_start] >= 0
                and qwm[w_end] >= 0
            ):
                abs_start = qwm[w_start]
                # Extend the end to cover the whole last word so the stored span
                # matches what the reader selected, not just its first char.
                abs_end = qwm[w_end]
                word = self.doc.word_map[w_end].word if self.doc.word_map else ""
                start, end = min(abs_start, abs_end), max(abs_start, abs_end) + len(word)
                paged_note = "  (pagination turned off — highlights use the whole document)"
            else:
                # Could not translate the selection reliably; do not store a
                # possibly-wrong offset.  Pagination is now off, so the reader can
                # re-select and highlight against the whole document.
                self.statusBar().showMessage(
                    "Pagination turned off for highlighting — reselect the text "
                    "and press Ctrl+H again."
                )
                return
        path_key = self.doc.path or "__no_path__"
        hl_store: dict = self.settings._data.setdefault("user_highlights", {})
        hl_list: list = hl_store.setdefault(path_key, [])
        hl_list.append({"start": start, "end": end, "color": color})
        self.settings.save()
        self._qt_apply_user_highlights()
        self.statusBar().showMessage(f"Highlight added ({color}){paged_note}")

    def _page_word_at_offset(self, offset: int) -> "Optional[int]":
        """Return the word-map index whose rendered-char offset is at/nearest
        *offset* in the current (possibly windowed) render, or None.

        Walks ``self._qt_word_map`` (full-document length; -1 for words not in the
        current window) and picks the in-window word whose char offset is the
        greatest one ``<= offset`` (falling back to the closest in-window word).
        Used to translate a window-relative selection into whole-document word
        indices before pagination is suspended for highlighting.
        """
        qwm = getattr(self, "_qt_word_map", []) or []
        best_idx: "Optional[int]" = None
        best_off = -1
        closest_idx: "Optional[int]" = None
        closest_dist = None
        for i, off in enumerate(qwm):
            if off is None or off < 0:
                continue
            dist = abs(off - offset)
            if closest_dist is None or dist < closest_dist:
                closest_dist, closest_idx = dist, i
            if off <= offset and off > best_off:
                best_off, best_idx = off, i
        return best_idx if best_idx is not None else closest_idx

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
            # The vocab overlay scans and paints the *whole* rendered text at
            # absolute char offsets.  If the document is currently paginated only
            # a window is rendered, so the overlay would be computed against — and
            # paint onto — the wrong slice (BUG 2).  Suspend pagination and render
            # the whole document first, then compute the overlay against it.
            if getattr(self, "_paginator", None) is not None:
                self._page_disable_and_render_whole()
            self._compute_vocab_selections()
        else:
            self._vocab_selections = []
        self._qt_apply_user_highlights()

    def _qt_toggle_vocab_highlight(self) -> None:
        """Toggle the difficult-word overlay on the current document."""
        if not self._qt_require_optional_feature("vocab", tr("Difficult-word highlighting")):
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

