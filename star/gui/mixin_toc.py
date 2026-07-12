"""TocMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(TocMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ._qtcompat import _USER_ROLE


class TocMixin:
    # ── Table of Contents panel ───────────────────────────────────────────

    def _qt_build_toc(self) -> None:
        """Populate the Contents dock from the current document headings.

        Each item stores two roles:
          _USER_ROLE     – the raw heading title (used for display).
          _USER_ROLE + 1 – the pre-computed character offset of that
                           heading inside the rendered QTextDocument.

        The character offset is found with a *rolling forward search* so
        that repeated section titles (e.g. "Introduction" in multiple
        chapters) each resolve to their own occurrence rather than always
        the first.  -1 is stored when the title cannot be located.
        """
        self._toc_list.clear()
        if not self.doc:
            return
        search_from = 0  # advance past each match to avoid re-matching
        for line in (self.doc.markdown or "").splitlines():
            m = re.match(r"^(#{1,6})\s+(.*)", line)
            if not m:
                continue
            level = len(m.group(1))
            title = m.group(2).strip()
            if not title:
                continue
            indent = "\u2002" * (level - 1) * 2  # en-spaces for visual indent
            item = QListWidgetItem(indent + title)
            item.setData(_USER_ROLE, title)
            # Locate this heading in the rendered document using a
            # rolling cursor so identical heading titles in different
            # chapters resolve to their own paragraph, not always the
            # first occurrence (which is the bug that made ToC always
            # start speech from word 0).
            c = self.editor.document().find(title, search_from)
            if not c.isNull():
                char_pos: int = c.selectionStart()
                search_from = c.selectionEnd() + 1
            else:
                char_pos = -1
            item.setData(_USER_ROLE + 1, char_pos)
            self._toc_list.addItem(item)

    def _qt_char_to_word(self, char_pos: int) -> int:
        """Return the word-map index of the first TTS word at or after
        *char_pos* (a character offset in the rendered QTextDocument).

        Handles three edge cases robustly:
          • *char_pos* is before the first word  → returns 0.
          • *char_pos* is past the last word     → returns the last index.
          • _qt_word_map is still empty (async build in progress)
            → falls back to a proportional estimate using doc.word_map
              length so at least the correct region of the document is
              reached rather than always word 0.
        """
        wm = self._qt_word_map
        if wm:
            for i, off in enumerate(wm):
                if off >= char_pos:
                    return i
            # char_pos is past every mapped word — start from the last.
            return len(wm) - 1

        # Fallback: word map not yet built by the background thread.
        # Estimate position proportionally so the user lands in roughly
        # the right place instead of always restarting from word 0.
        if self.doc and self.doc.word_map:
            doc_len = self.editor.document().characterCount()
            if doc_len > 1:
                pct = char_pos / doc_len
                return max(
                    0,
                    min(
                        int(pct * len(self.doc.word_map)),
                        len(self.doc.word_map) - 1,
                    ),
                )
        return 0

    def _qt_toc_navigate(self, item: QListWidgetItem) -> None:
        """Single-click / Enter: scroll the viewport to the heading.

        Intentionally does *not* stop or redirect speech — the user
        may be browsing the ToC while the book reads.  To jump speech
        to a heading, double-click instead.
        """
        char_pos_data = item.data(_USER_ROLE + 1)
        char_pos: int = char_pos_data if char_pos_data is not None else -1
        if char_pos < 0:
            # Heading wasn't found at build time — try a live search.
            title = item.data(_USER_ROLE) or ""
            c = self.editor.document().find(title)
            if c.isNull():
                return
            char_pos = c.selectionStart()
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(char_pos)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()
        title = item.data(_USER_ROLE) or ""
        self.statusBar().showMessage(
            f"Navigated to: {title}  \u00b7  double-click to start reading here"
        )

    def _qt_toc_play(self, item: QListWidgetItem) -> None:
        """Double-click: stop current speech and start reading from the heading.

        Word-index resolution uses a direct search of *doc.plain_text* —
        the same text the speech engine will speak — rather than the
        Qt-char-offset → _qt_word_map indirection.  The indirection fails
        silently in several common situations:

          • _qt_word_map is still being built asynchronously.
          • Char positions become stale after a theme re-render.
          • document().find() matches the title in body text that
            precedes the actual heading, giving char_pos ≈ 0.

        Duplicate heading titles are handled by counting the number of
        items before this one in the ToC list that carry the same title
        and picking the corresponding occurrence in plain_text.
        """
        if not self.doc:
            return
        title = item.data(_USER_ROLE) or ""
        if not title:
            return

        # ── Scroll the viewport to the heading ───────────────────────
        char_pos_data = item.data(_USER_ROLE + 1)
        char_pos: int = char_pos_data if char_pos_data is not None else -1
        if char_pos < 0:
            c = self.editor.document().find(title)
            if not c.isNull():
                char_pos = c.selectionStart()
        if char_pos >= 0:
            scroll_cur = QTextCursor(self.editor.document())
            scroll_cur.setPosition(char_pos)
            self.editor.setTextCursor(scroll_cur)
            self.editor.ensureCursorVisible()

        # ── Determine which occurrence of this title we want ─────────
        # Some documents have identical headings in multiple chapters
        # (e.g. “Introduction” repeated).  Count prior ToC rows with the
        # same title to pick the correct occurrence in plain_text.
        row = self._toc_list.row(item)
        occurrence = sum(
            1
            for r in range(row)
            if (
                (self._toc_list.item(r) or QListWidgetItem()).data(_USER_ROLE)
                == title
            )
        )

        # ── Search doc.plain_text for the heading ────────────────────
        plain = self.doc.plain_text or ""
        plain_lower = plain.lower()
        title_lower = title.lower()
        search_pos = 0
        tts_pos = -1
        for _ in range(occurrence + 1):
            idx = plain_lower.find(title_lower, search_pos)
            if idx < 0:
                break
            tts_pos = idx
            search_pos = idx + max(1, len(title_lower))

        # ── Map plain-text position → word index ────────────────────
        wm = getattr(self.doc, "word_map", [])
        if tts_pos >= 0 and wm:
            word_idx = len(wm) - 1  # default: last word
            for i, wp in enumerate(wm):
                if wp.tts_offset >= tts_pos:
                    word_idx = i
                    break
        else:
            # word_map not ready yet (rare) — fall back to Qt mapping
            word_idx = self._qt_char_to_word(char_pos) if char_pos >= 0 else 0

        # ── Start speech from the heading ────────────────────────────
        self._tts_play_from_word(word_idx)
        self.statusBar().showMessage(f"▶  Reading from: {title}")

    def _qt_auto_toc_visibility(self) -> None:
        """Show the Contents dock only when the document has headings.

        Called after every ToC rebuild (document load, and on finishing an
        edit) so the pane appears automatically for a document with headings
        and stays out of the way for a heading-free document (a new/blank
        document, plain notes) — the reading space is never taken by an empty
        Contents pane.  An explicit toggle (``_qt_toggle_toc``) overrides this
        until the next rebuild."""
        dock = getattr(self, "_toc_dock", None)
        if dock is None:
            return
        dock.setVisible(self._toc_list.count() > 0)

    def _qt_toggle_toc(self) -> None:
        """Toggle the visibility of the Contents dock panel (Ctrl+\\).

        A transient, per-view action: the next ToC rebuild re-derives the
        pane's visibility from whether the document has headings
        (_qt_auto_toc_visibility), so toggling an empty pane on never makes it
        stick open across documents."""
        # isHidden() (not isVisible()) so the toggle is correct even before the
        # window is shown (isVisible() is False for a child of a hidden window).
        self._toc_dock.setVisible(self._toc_dock.isHidden())

