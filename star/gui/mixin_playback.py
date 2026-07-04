"""PlaybackMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(PlaybackMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from ._qtcompat import _FULL_WIDTH_SEL, _KEEP_ANCHOR
from .a11y import announce


class PlaybackMixin:
    # ── TTS controls ──────────────────────────────────────────────────

    def _refresh_hl_callback(self) -> None:
        """Re-register the TTS highlight callback, capturing the current
        session number.

        Every new speech invocation must call this *after* incrementing
        self._hl_session so that the closed-over ``_s`` value matches the
        session that _apply_word_highlight expects.  Any emission still in
        the Qt event queue from a prior session carries the old ``_s`` and
        is therefore silently dropped by _apply_word_highlight.
        """
        _s = self._hl_session
        self.tts_manager.set_on_highlight(
            lambda idx, __s=_s: self._word_signal.emit(idx, __s)
        )

    def _tts_play(self) -> None:
        """Start speech from the beginning (word 0)."""
        if not self.doc:
            return
        self._hl_session += 1  # new session — must come first
        self._refresh_hl_callback()  # re-wire before any stop/speak
        self.editor.setExtraSelections([])  # clear stale highlight
        self.tts_manager.stop()
        self._tts_paused_at_word = -1
        wm = getattr(self.doc, "word_map", [])
        text_offset = wm[0].tts_offset if wm else 0
        text_slice = self.doc.plain_text[text_offset:]
        self.tts_manager.speak(
            text_slice, start_word_idx=0, text_offset=text_offset
        )
        self.statusBar().showMessage(
            f"Reading at {self.settings['tts_rate']} wpm …"
        )
        # Announce to assistive tech without moving focus (pairs with status).
        announce(self.editor, tr("Playing"))

    def _tts_play_from_word(self, word_idx: int) -> None:
        """Resume or start speech from a specific word-map index."""
        if not self.doc:
            return
        self._hl_session += 1  # new session — must come first
        self._refresh_hl_callback()  # re-wire before any stop/speak
        self.editor.setExtraSelections([])
        self.tts_manager.stop()
        self._tts_paused_at_word = -1
        wm = getattr(self.doc, "word_map", [])
        if wm and word_idx < len(wm):
            text_offset = wm[word_idx].tts_offset
        else:
            text_offset = 0
            word_idx = 0
        text_slice = self.doc.plain_text[text_offset:]
        self.tts_manager.speak(
            text_slice, start_word_idx=word_idx, text_offset=text_offset
        )
        self.statusBar().showMessage(
            f"Resuming at {self.settings['tts_rate']} wpm …"
        )
        announce(self.editor, tr("Playing"))

    def _qt_play_from_cursor(self) -> None:
        """Start speech from the current text-cursor or selection position.

        If text is selected (e.g. the user click-dragged or used
        Shift+arrow), speech begins at the *start* of the selection so
        the user hears the passage they highlighted.  If there is no
        selection, speech begins at the plain cursor position (the
        word whose character offset is closest to or just after the
        cursor).

        Shortcut: Ctrl+Space (pairs with caret browsing — move the caret with the
        arrow keys, then Ctrl+Space to read from there).

        """
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        cursor = self.editor.textCursor()
        # Use selection start so clicking and highlighting a passage
        # then pressing Ctrl+Space reads from the top of the highlight.
        char_pos = (
            cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        )
        word_idx = self._qt_char_to_word(char_pos)
        self._tts_play_from_word(word_idx)

    def _tts_toggle(self) -> None:
        """Pause/resume speech (Space bar).

        * While speaking → pause, saving the current word so the next
          press resumes from exactly that word.
        * While paused   → resume from the saved word index.
        * While stopped  → start from the beginning.
        """
        if self.tts_manager.speaking:
            saved = self.tts_manager.current_word_idx
            # Suppress the stop announcement here — this is a *pause*, and we
            # announce that explicitly below so a screen reader says "Paused"
            # rather than "Stopped".
            self._tts_stop(announce_state=False)  # clears _tts_paused_at_word
            if saved >= 0:
                self._tts_paused_at_word = saved
            announce(self.editor, tr("Paused"))
            self.statusBar().showMessage(tr("Paused"))
        elif self._tts_paused_at_word >= 0:
            w = self._tts_paused_at_word
            self._tts_paused_at_word = -1
            self._tts_play_from_word(w)
        else:
            self._tts_play()

    def _tts_stop(self, announce_state: bool = True) -> None:
        """Full stop — saves position, clears speech.

        *announce_state* is False when called as the internal half of a pause
        (see :meth:`_tts_toggle`) so the caller can announce "Paused" instead of
        the "Stopped" message this method would otherwise speak.
        """
        self._qt_save_reading_position()
        self.tts_manager.stop()
        self.editor.setExtraSelections([])  # clear highlight immediately
        self._tts_paused_at_word = -1
        if announce_state:
            self.statusBar().showMessage("Stopped.")
            announce(self.editor, tr("Stopped"))

    # ── Word highlight (called on GUI thread via _word_signal) ─────────

    def _scroll_read_word_into_view(self, char_pos: int) -> None:
        """Keep the spoken word in a comfortable reading band as playback moves.

        Scrolls only when the word drifts out of the middle of the viewport,
        then brings it to ~40% down so there is already-read context above and
        upcoming text below — steadier than ensureCursorVisible's edge nudge,
        which lets the read line pin to the bottom where it's easy to lose.
        """
        ed = self.editor
        vh = ed.viewport().height()
        if vh <= 0:
            return
        cur = QTextCursor(ed.document())
        cur.setPosition(max(0, char_pos))
        r = ed.cursorRect(cur)
        if r.top() < vh * 0.15 or r.bottom() > vh * 0.85:
            vbar = ed.verticalScrollBar()
            vbar.setValue(vbar.value() + int(r.center().y() - vh * 0.40))

    def _apply_word_highlight(self, word_idx: int, session: int) -> None:
        """Paint the currently spoken word using QTextEdit.setExtraSelections().

        setExtraSelections() is non-destructive: it does not modify the
        document, does not touch the undo stack, and is cleared simply
        by passing an empty list.  User highlights are merged so they
        are not erased on each TTS word advance.

        The *session* parameter is compared against self._hl_session to
        reject stale deliveries.  Qt's QueuedConnection buffers signal
        emissions; when _tts_play_from_word() starts a new utterance, a
        signal from the *old* timer that was already in the queue can
        fire AFTER the viewport has scrolled to the ToC target and
        immediately scroll it back.  Dropping any delivery whose session
        doesn't match the current one eliminates that race entirely.
        """
        # Discard stale deliveries from superseded speech sessions.
        if session != self._hl_session:
            return

        # Pagination: if the spoken word has crossed out of the rendered window,
        # advance the window (a GUI-thread re-render) so its offset exists before
        # we paint.  No-op when pagination is off.  This is how reading continues
        # smoothly across a page boundary.
        if getattr(self, "_paginator", None) is not None and word_idx >= 0:
            self._page_ensure_word_visible(word_idx)

        # Build base list from persistent user highlights so they are
        # never erased by TTS word advances.
        selections = self._get_user_highlight_selections()

        if word_idx < 0 or not self._qt_word_map:
            self.editor.setExtraSelections(selections)
            return

        # Under pagination a word can still be out of window (e.g. the highlight
        # lead pushed vis_idx past the edge, or the re-render lagged); skip the
        # paint rather than dereference a sentinel offset.
        if self._qt_word_map[min(word_idx, len(self._qt_word_map) - 1)] < 0:
            self.editor.setExtraSelections(selections)
            return

        # Lead/lag tuning: shift the *visual* highlight ahead of (or
        # behind) the spoken word so the cursor can be made to anticipate
        # the audio for users who track best slightly ahead.
        try:
            lead = int(self.settings.get("highlight_lead_words", 0))
        except (TypeError, ValueError):
            lead = 0
        vis_idx = word_idx + lead
        vis_idx = max(0, min(vis_idx, len(self._qt_word_map) - 1))

        char_pos = self._qt_word_map[vis_idx]
        # Under pagination the lead-shifted vis_idx may fall just outside the
        # rendered window (sentinel -1); anchor the visual highlight on the
        # spoken word itself instead of painting at a bogus offset.
        if char_pos < 0:
            char_pos = self._qt_word_map[word_idx] if word_idx < len(
                self._qt_word_map
            ) else -1
            if char_pos < 0:
                self.editor.setExtraSelections(selections)
                return
            vis_idx = word_idx

        # Word length from the word map built in _build_qt_word_map.
        word_len = 1
        if self.doc and vis_idx < len(self.doc.word_map):
            word_len = max(1, self.doc.word_map[vis_idx].tts_len)

        # Clamp to actual document length.
        doc_obj = self.editor.document()
        doc_len = doc_obj.characterCount()
        if char_pos >= doc_len:
            return
        word_len = min(word_len, doc_len - char_pos - 1)
        if word_len <= 0:
            return

        # Build the selection cursor that spans exactly this word.
        cursor = QTextCursor(doc_obj)
        cursor.setPosition(char_pos)
        cursor.setPosition(char_pos + word_len, _KEEP_ANCHOR)

        # Optional current-line band: a full-width tint behind the line
        # being read, drawn *under* the word highlight (a reading aid).
        if self.settings.get("qt_current_line_highlight", False):
            pal = self._effective_palette(self.settings.get("theme", "dark"))
            band = QColor(str(pal.get("sel", "#2c313a")))
            line_fmt = QTextCharFormat()
            line_fmt.setBackground(band)
            # Property id is an int; PyQt6 enums expose it via .value.
            _fw = getattr(_FULL_WIDTH_SEL, "value", _FULL_WIDTH_SEL)
            line_fmt.setProperty(int(_fw), True)
            line_cur = QTextCursor(doc_obj)
            line_cur.setPosition(char_pos)
            line_sel = QTextEdit.ExtraSelection()
            line_sel.format = line_fmt
            line_sel.cursor = line_cur
            selections = selections + [line_sel]

        # Sentence-level highlight.  Resolve the character
        # span of the sentence containing this word.  In "sentence" mode
        # the whole sentence carries the highlight format; in "both" mode
        # the sentence gets a softer band and the word is marked on top.
        gran = str(self.settings.get("highlight_granularity", "word"))
        sent_cursor = None
        if gran in ("sentence", "both") and self._qt_sentence_starts:
            ss = self._qt_sentence_starts
            si = self._qt_find_sentence_idx(vis_idx)
            s_word = ss[si] if si < len(ss) else vis_idx
            e_word = (
                ss[si + 1] - 1 if si + 1 < len(ss) else len(self._qt_word_map) - 1
            )
            s_word = max(0, min(s_word, len(self._qt_word_map) - 1))
            e_word = max(s_word, min(e_word, len(self._qt_word_map) - 1))
            s_char = self._qt_word_map[s_word]
            e_char = self._qt_word_map[e_word]
            e_len = 1
            if self.doc and e_word < len(self.doc.word_map):
                e_len = max(1, self.doc.word_map[e_word].tts_len)
            e_char = min(e_char + e_len, doc_len - 1)
            # Under pagination the sentence may straddle the window edge (one end
            # a sentinel -1); fall back to the word-level mark rather than paint a
            # bogus span.
            if s_char >= 0 and e_char > s_char:
                sent_cursor = QTextCursor(doc_obj)
                sent_cursor.setPosition(s_char)
                sent_cursor.setPosition(e_char, _KEEP_ANCHOR)

        if gran == "sentence" and sent_cursor is not None:
            # Highlight the entire sentence; no separate per-word mark.
            sel = QTextEdit.ExtraSelection()
            sel.format = self._hl_fmt
            sel.cursor = sent_cursor
            self.editor.setExtraSelections(selections + [sel])
        elif gran == "both" and sent_cursor is not None:
            # Softer band over the sentence + the word marked on top.
            pal = self._effective_palette(self.settings.get("theme", "dark"))
            band_fmt = QTextCharFormat()
            _sent_col = str(self.settings.get("sentence_highlight_color", "") or "").strip()
            if _sent_col and QColor(_sent_col).isValid():
                band_fmt.setBackground(QColor(_sent_col))
            else:
                band_fmt.setBackground(QColor(str(pal.get("sel", "#2c313a"))))
            band_sel = QTextEdit.ExtraSelection()
            band_sel.format = band_fmt
            band_sel.cursor = sent_cursor
            word_sel = QTextEdit.ExtraSelection()
            word_sel.format = self._hl_fmt
            word_sel.cursor = cursor
            self.editor.setExtraSelections(selections + [band_sel, word_sel])
        else:
            # Word-level (default).  Wrap format + cursor in an
            # ExtraSelection and apply, prepending the persistent user
            # highlights (and line band).
            sel = QTextEdit.ExtraSelection()
            sel.format = self._hl_fmt
            sel.cursor = cursor
            self.editor.setExtraSelections(selections + [sel])

        # Move the (caret-invisible) text cursor to the spoken word so the
        # reading ruler and the resume point track it, then keep the word in a
        # steady reading band.  ensureCursorVisible only nudges the word to the
        # nearest edge — which lets the read line drift down to the bottom and is
        # easy to lose track of — so scroll it into the middle instead (honours
        # the qt_autoscroll preference).
        self.editor.setTextCursor(cursor)
        if self.settings.get("qt_autoscroll", True):
            self._scroll_read_word_into_view(char_pos)

        # Status bar: word text + reading progress.
        if self.doc and word_idx < len(self.doc.word_map):
            word_text = self.doc.word_map[word_idx].word
            pct = int(100 * word_idx / max(1, len(self.doc.word_map)))
            self.statusBar().showMessage(
                f'▶  “{word_text}”  —  {pct}%  —  {self.settings["tts_rate"]} wpm'  # noqa: RUF001
            )

        # ── RSVP overlay update ─────────────────────────────────────
        if (
            self._rsvp_overlay is not None
            and self._rsvp_overlay.isVisible()
            and self.doc
            and word_idx < len(self.doc.word_map)
        ):
            wm = self.doc.word_map
            vis_idx = min(
                max(0, word_idx + int(self.settings.get('highlight_lead_words', 0))),
                len(wm) - 1,
            )
            prev_word = wm[vis_idx - 1].word if vis_idx > 0 else ''
            curr_word = wm[vis_idx].word
            next_word = wm[vis_idx + 1].word if vis_idx + 1 < len(wm) else ''
            self._rsvp_overlay.update_word(prev_word, curr_word, next_word)

