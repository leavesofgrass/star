"""FindMixin — an in-document Find bar for StarWindow (Ctrl+F).

A slim search bar docked at the bottom of the window, over the document
``self.editor``.  It provides incremental substring matching as the user types,
next/previous navigation (F3 / Shift+F3 or Enter / Shift+Enter), a live match
counter, a case-sensitivity toggle, wrap-around, and highlight-all via
``QTextEdit.ExtraSelection`` with the current match emphasised and revealed.
Escape closes the bar and clears the highlights.

Match discovery reuses the plain-text substring semantics of
:class:`star.search.SearchEngine` (case-insensitive ``str.find`` scanning), run
directly over the editor's ``toPlainText`` so the character offsets map straight
onto ``QTextCursor`` selections.

IMPORT SAFETY: references Qt at module scope — imported lazily by main_window.py
(itself imported after the _QT guard), like the other mixin_*.py modules.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from .a11y import announce


class FindMixin:
    # Selection colours for the find highlights.  Distinct so the current match
    # stands out from the other (all-matches) highlights even at a glance.
    _FIND_ALL_BG = "#664e00"      # dim amber for every match
    _FIND_CURRENT_BG = "#ff9632"  # bright orange for the active match

    # ── construction ───────────────────────────────────────────────────
    def _ensure_find_bar(self) -> None:
        """Create the find-bar widget the first time it is needed (lazy)."""
        if getattr(self, "_find_bar", None) is not None:
            return

        # State: absolute character offsets of every match, plus the active one.
        self._find_matches: List[int] = []
        self._find_query: str = ""
        self._find_idx: int = -1

        bar = QWidget(self)
        bar.setObjectName("find_bar")
        # A vertical container holds the find row and (in edit mode) the replace
        # row beneath it, so one bar serves both Find and Find & Replace.
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(6, 3, 6, 3)
        outer.setSpacing(3)
        find_row = QWidget(bar)
        layout = QHBoxLayout(find_row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        outer.addWidget(find_row)

        lbl = QLabel(tr("Find:"))
        layout.addWidget(lbl)

        self._find_input = QLineEdit()
        self._find_input.setObjectName("find_input")
        self._find_input.setAccessibleName(tr("Find in document"))
        self._find_input.setAccessibleDescription(
            tr("Type to search the document. Enter for next, Shift+Enter for "
               "previous, Escape to close.")
        )
        self._find_input.setClearButtonEnabled(True)
        self._find_input.textChanged.connect(self._find_on_text_changed)
        self._find_input.returnPressed.connect(self._find_next)
        layout.addWidget(self._find_input, 1)

        self._find_count = QLabel("")
        self._find_count.setObjectName("find_count")
        self._find_count.setAccessibleName(tr("Match count"))
        self._find_count.setMinimumWidth(80)
        layout.addWidget(self._find_count)

        prev_btn = QPushButton(tr("Previous"))
        prev_btn.setAccessibleDescription(tr("Go to the previous match"))
        prev_btn.clicked.connect(self._find_prev)
        layout.addWidget(prev_btn)

        next_btn = QPushButton(tr("Next"))
        next_btn.setAccessibleDescription(tr("Go to the next match"))
        next_btn.clicked.connect(self._find_next)
        layout.addWidget(next_btn)

        self._find_case = QCheckBox(tr("Match case"))
        self._find_case.setAccessibleDescription(
            tr("Toggle case-sensitive matching")
        )
        self._find_case.toggled.connect(lambda _c: self._find_run(self._find_query))
        layout.addWidget(self._find_case)

        # Toggle that reveals the replace row (only useful while editing).
        self._replace_toggle = QPushButton(tr("Replace ▾"))
        self._replace_toggle.setCheckable(True)
        self._replace_toggle.setAccessibleDescription(
            tr("Show the replace field (edit mode only)")
        )
        self._replace_toggle.toggled.connect(self._find_set_replace_visible)
        layout.addWidget(self._replace_toggle)

        close_btn = QPushButton(tr("×"))
        close_btn.setAccessibleName(tr("Close find bar"))
        close_btn.setAccessibleDescription(tr("Close the find bar (Escape)"))
        close_btn.setMaximumWidth(28)
        close_btn.clicked.connect(self._find_close)
        layout.addWidget(close_btn)

        # ── replace row (hidden until Find & Replace or the toggle) ──────────
        self._replace_row = QWidget(bar)
        rlayout = QHBoxLayout(self._replace_row)
        rlayout.setContentsMargins(0, 0, 0, 0)
        rlayout.setSpacing(6)
        rlayout.addWidget(QLabel(tr("Replace:")))
        self._replace_input = QLineEdit()
        self._replace_input.setObjectName("replace_input")
        self._replace_input.setAccessibleName(tr("Replace with"))
        self._replace_input.setAccessibleDescription(
            tr("Type the replacement text. Enter replaces the current match.")
        )
        self._replace_input.setClearButtonEnabled(True)
        self._replace_input.returnPressed.connect(self._find_replace_one)
        rlayout.addWidget(self._replace_input, 1)
        rep_btn = QPushButton(tr("Replace"))
        rep_btn.setAccessibleDescription(tr("Replace the current match"))
        rep_btn.clicked.connect(self._find_replace_one)
        rlayout.addWidget(rep_btn)
        rep_all_btn = QPushButton(tr("Replace All"))
        rep_all_btn.setAccessibleDescription(tr("Replace every match"))
        rep_all_btn.clicked.connect(self._find_replace_all)
        rlayout.addWidget(rep_all_btn)
        outer.addWidget(self._replace_row)
        self._replace_row.setVisible(False)
        self._replace_input.installEventFilter(self)

        # An event filter on the input lets Escape close and F3/Shift+F3 and
        # Shift+Enter navigate even while the line edit has focus.
        self._find_input.installEventFilter(self)

        # Slot the bar into the central layout beneath the editor splitter.
        # The central widget is the QSplitter created in _setup_ui; wrap both in
        # a vertical container so the find bar sits under the document view.
        central = self.centralWidget()
        container = QWidget(self)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        if central is not None:
            vbox.addWidget(central)
        vbox.addWidget(bar)
        self.setCentralWidget(container)

        bar.setVisible(False)
        self._find_bar = bar

    # ── open / close ───────────────────────────────────────────────────
    def _find_show(self) -> None:
        """Show the find bar and focus the input (Ctrl+F)."""
        # Find must see the *whole* document: its match offsets and highlight-all
        # span the entire text, not just a rendered page window.  When a large
        # document is paginated, suspend paging and render it whole so search is
        # fully correct (the documented safe degradation — see docs/PERFORMANCE.md).
        if getattr(self, "_paginator", None) is not None:
            self._page_disable_and_render_whole()
        self._ensure_find_bar()
        self._find_bar.setVisible(True)
        # Seed the query from the current selection, if any, for a fast workflow.
        try:
            sel = self.editor.textCursor().selectedText()
        except Exception:  # noqa: BLE001
            sel = ""
        if sel and " " not in sel:  # single-line selection only
            self._find_input.setText(sel)
        self._find_input.setFocus()
        self._find_input.selectAll()
        # Re-run in case a previous query is still in the box.
        self._find_run(self._find_input.text())

    def _find_close(self) -> None:
        """Hide the find bar and clear its highlights (Escape)."""
        if getattr(self, "_find_bar", None) is None:
            return
        self._find_bar.setVisible(False)
        # Collapse the replace row too so the next plain Find opens compact.
        if getattr(self, "_replace_toggle", None) is not None:
            self._replace_toggle.setChecked(False)
        self._find_matches = []
        self._find_idx = -1
        # Repaint without the find highlights (keeps user/TTS highlights).
        self._find_repaint()
        try:
            self.editor.setFocus()
        except Exception:  # noqa: BLE001
            pass

    def _find_toggle(self) -> None:
        """Toggle the find bar (menu/command entry point)."""
        if getattr(self, "_find_bar", None) is not None and self._find_bar.isVisible():
            self._find_close()
        else:
            self._find_show()

    # ── replace ────────────────────────────────────────────────────────
    def _find_set_replace_visible(self, show: bool) -> None:
        """Show/hide the replace row (driven by the Replace ▾ toggle)."""
        self._ensure_find_bar()
        self._replace_row.setVisible(bool(show))
        if getattr(self, "_replace_toggle", None) is not None:
            # Keep the toggle in sync when called programmatically.
            if self._replace_toggle.isChecked() != bool(show):
                self._replace_toggle.setChecked(bool(show))
        if show:
            self._replace_input.setFocus()

    def _replace_show(self) -> None:
        """Open Find & Replace (Edit ▸ Find & Replace…).

        Replace edits the source, so it only makes sense while editing — outside
        edit mode we show Find and hint how to enable replacing."""
        self._find_show()
        if not getattr(self, "_qt_edit_mode", False):
            self.statusBar().showMessage(
                tr("Turn on Edit Mode (Ctrl+E) to replace text")
            )
            return
        self._find_set_replace_visible(True)
        # Focus the *find* field first so the user types what to search for;
        # _find_set_replace_visible parks focus on the replace box, which is the
        # right default only when a query is already in the bar.
        if not self._find_input.text():
            self._find_input.setFocus()

    def _find_replace_one(self) -> None:
        """Replace the current match with the replacement, then advance.

        A no-op outside edit mode (the document is read-only) or with no active
        match.  Recomputes matches afterwards since offsets shift."""
        if not getattr(self, "_qt_edit_mode", False):
            self.statusBar().showMessage(
                tr("Turn on Edit Mode (Ctrl+E) to replace text")
            )
            return
        if not (0 <= self._find_idx < len(self._find_matches)):
            return
        replacement = self._replace_input.text() if getattr(
            self, "_replace_input", None) else ""
        start = self._find_matches[self._find_idx]
        n = len(self._find_query)
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start)
        try:
            _keep = QTextCursor.MoveMode.KeepAnchor
        except AttributeError:  # PyQt5
            _keep = QTextCursor.KeepAnchor  # type: ignore[attr-defined]
        cursor.setPosition(start + n, _keep)
        cursor.insertText(replacement)
        # Offsets shifted by (len(replacement) - n); recompute from the point
        # just past the inserted text so the next match is found forward.
        self.editor.setTextCursor(cursor)
        self._find_run(self._find_query)
        self.statusBar().showMessage(tr("Replaced 1 match"))

    def _find_replace_all(self) -> None:
        """Replace every match in one undo step; report the count."""
        if not getattr(self, "_qt_edit_mode", False):
            self.statusBar().showMessage(
                tr("Turn on Edit Mode (Ctrl+E) to replace text")
            )
            return
        if not self._find_matches:
            self.statusBar().showMessage(tr("No matches"))
            return
        replacement = self._replace_input.text() if getattr(
            self, "_replace_input", None) else ""
        n = len(self._find_query)
        doc = self.editor.document()
        try:
            _keep = QTextCursor.MoveMode.KeepAnchor
        except AttributeError:  # PyQt5
            _keep = QTextCursor.KeepAnchor  # type: ignore[attr-defined]
        count = len(self._find_matches)
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        # Replace back-to-front so earlier offsets stay valid as text shifts.
        for start in reversed(self._find_matches):
            cursor.setPosition(start)
            cursor.setPosition(start + n, _keep)
            cursor.insertText(replacement)
        cursor.endEditBlock()
        self._find_run(self._find_query)
        msg = tr("Replaced {n} matches").format(n=count)
        self.statusBar().showMessage(msg)
        announce(self._find_input if getattr(self, "_find_input", None) else self.editor, msg)

    # ── keyboard handling on the find input ────────────────────────────
    def _find_input_key(self, event: Any) -> bool:
        """Handle key presses on the find input.  Returns True if consumed.

        Escape closes the bar; F3 / Enter go to the next match; Shift+F3 /
        Shift+Enter go to the previous match.  ``returnPressed`` already wires
        plain Enter → next, so here we only need the Shift+Enter variant plus
        F3 and Escape."""
        try:
            from PyQt6.QtCore import QEvent

            kp = QEvent.Type.KeyPress
            Key = Qt.Key
            shift_mod = Qt.KeyboardModifier.ShiftModifier
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            kp = QEvent.KeyPress  # type: ignore[attr-defined]
            Key = Qt  # type: ignore
            shift_mod = Qt.ShiftModifier  # type: ignore[attr-defined]

        if event.type() != kp:
            return False
        key = event.key()
        try:
            mods = event.modifiers()
            has_shift = bool(mods & shift_mod)
        except Exception:  # noqa: BLE001
            has_shift = False

        try:
            k_esc = Key.Key_Escape
            k_f3 = Key.Key_F3
            k_ret = Key.Key_Return
            k_ent = Key.Key_Enter
        except AttributeError:  # PyQt5
            k_esc = Qt.Key_Escape  # type: ignore[attr-defined]
            k_f3 = Qt.Key_F3  # type: ignore[attr-defined]
            k_ret = Qt.Key_Return  # type: ignore[attr-defined]
            k_ent = Qt.Key_Enter  # type: ignore[attr-defined]

        if key == k_esc:
            self._find_close()
            return True
        if key == k_f3:
            self._find_prev() if has_shift else self._find_next()
            return True
        if key in (k_ret, k_ent) and has_shift:
            self._find_prev()
            return True
        return False

    # ── search ─────────────────────────────────────────────────────────
    def _find_on_text_changed(self, text: str) -> None:
        self._find_run(text)

    def _find_run(self, query: str) -> None:
        """Recompute all matches for *query* and reveal the first at/after the
        current cursor (incremental search)."""
        self._find_query = query or ""
        text = self.editor.toPlainText()
        case = bool(self._find_case.isChecked()) if getattr(self, "_find_case", None) else False
        self._find_matches = _find_all(text, self._find_query, case)
        if not self._find_matches:
            self._find_idx = -1
            self._find_update_count()
            self._find_repaint()
            return
        # Choose the first match at or after the current cursor position so the
        # search feels anchored where the reader is looking.
        cursor_pos = self.editor.textCursor().position()
        self._find_idx = 0
        for i, off in enumerate(self._find_matches):
            if off >= cursor_pos:
                self._find_idx = i
                break
        self._find_update_count()
        self._find_reveal_current()
        self._find_repaint()

    def _find_next(self) -> None:
        """Advance to the next match (wraps around)."""
        if not self._find_matches:
            return
        self._find_idx = (self._find_idx + 1) % len(self._find_matches)
        self._find_update_count()
        self._find_reveal_current()
        self._find_repaint()

    def _find_prev(self) -> None:
        """Go to the previous match (wraps around)."""
        if not self._find_matches:
            return
        self._find_idx = (self._find_idx - 1) % len(self._find_matches)
        self._find_update_count()
        self._find_reveal_current()
        self._find_repaint()

    # ── rendering ──────────────────────────────────────────────────────
    def _find_reveal_current(self) -> None:
        """Move the editor's text cursor onto the active match and scroll to it."""
        if not (0 <= self._find_idx < len(self._find_matches)):
            return
        start = self._find_matches[self._find_idx]
        n = len(self._find_query)
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start)
        try:
            _keep = QTextCursor.MoveMode.KeepAnchor
        except AttributeError:  # PyQt5
            _keep = QTextCursor.KeepAnchor  # type: ignore[attr-defined]
        cursor.setPosition(start + n, _keep)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def _find_selections(self) -> List[Any]:
        """Build the ExtraSelection list for all matches (current emphasised)."""
        sels: List[Any] = []
        if not self._find_matches or not self._find_query:
            return sels
        n = len(self._find_query)
        doc = self.editor.document()
        try:
            _keep = QTextCursor.MoveMode.KeepAnchor
        except AttributeError:  # PyQt5
            _keep = QTextCursor.KeepAnchor  # type: ignore[attr-defined]
        all_fmt = QTextCharFormat()
        all_fmt.setBackground(QColor(self._FIND_ALL_BG))
        cur_fmt = QTextCharFormat()
        cur_fmt.setBackground(QColor(self._FIND_CURRENT_BG))
        for i, start in enumerate(self._find_matches):
            c = QTextCursor(doc)
            c.setPosition(start)
            c.setPosition(start + n, _keep)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = c
            sel.format = cur_fmt if i == self._find_idx else all_fmt
            sels.append(sel)
        return sels

    def _find_repaint(self) -> None:
        """Repaint the editor's extra selections, merging find highlights on top
        of any user/vocab highlights so neither wipes the other.

        Uses ``_get_user_highlight_selections`` (the same merged base that TTS
        word-highlighting paints over — user highlights + the difficult-word
        overlay) as the foundation and appends the find selections last so the
        current match wins the cascade."""
        find_sels = self._find_selections()
        base_fn = getattr(self, "_get_user_highlight_selections", None)
        if callable(base_fn):
            try:
                base = list(base_fn())
            except Exception:  # noqa: BLE001
                base = []
        else:
            base = []
        self.editor.setExtraSelections(base + find_sels)

    def _find_update_count(self) -> None:
        """Update the "N of M" counter label."""
        total = len(self._find_matches)
        if total == 0:
            self._find_count.setText(tr("No matches") if self._find_query else "")
        else:
            self._find_count.setText(
                tr("{i} of {n}").format(i=self._find_idx + 1, n=total)
            )
        # Also surface it in the status bar for screen-reader users.
        if self._find_query:
            self.statusBar().showMessage(
                tr("Find “{q}” — {c}").format(
                    q=self._find_query, c=self._find_count.text()
                )
            )
            # Announce the live result count ("3 of 12" / "No matches") so a
            # screen-reader user hears their search progress without leaving the
            # find input.  Announce against the find input (which holds focus)
            # so the utterance is associated with the control being used.
            widget = getattr(self, "_find_input", None) or self.editor
            spoken = (
                tr("No matches")
                if total == 0
                else tr("{i} of {n}").format(i=self._find_idx + 1, n=total)
            )
            announce(widget, spoken)


def _find_all(text: str, query: str, case_sensitive: bool) -> List[int]:
    """Return the start offsets of every occurrence of *query* in *text*.

    Mirrors :meth:`star.search.SearchEngine.search`'s substring semantics — a
    forward ``str.find`` scan advancing one character past each hit so
    overlapping matches are found — but operates on a single flat string so the
    offsets map directly onto ``QTextCursor`` positions."""
    if not query:
        return []
    hay = text if case_sensitive else text.lower()
    needle = query if case_sensitive else query.lower()
    out: List[int] = []
    col = 0
    while True:
        pos = hay.find(needle, col)
        if pos < 0:
            break
        out.append(pos)
        col = pos + 1
    return out
