"""BookmarksQtMixin — named bookmarks + back/forward history for StarWindow.

Ports the terminal-UI logic in ``star/tui/mixin_bookmarks.py`` to the Qt GUI:

* **Named bookmarks**, one set per document, persisted in ``settings['bookmarks']``
  keyed by document path — identical schema to the TUI so a bookmark set in one
  UI is visible in the other.  Add (Ctrl+B, auto-named ``mark1``, ``mark2``, …),
  a bookmarks list dialog to jump/delete, and add-named via a prompt.
* **Navigation history** — a stack of TTS offsets with back (Alt+Left) and
  forward (Alt+Right).  Every jump (bookmark, list, back/forward target) pushes
  the departure point first, mirroring the TUI's branch-on-jump behaviour.

Jumps reuse :meth:`NavigationMixin._qt_navigate_to_word`, and the current reading
position comes from :meth:`_qt_current_word_for_nav`, so bookmark/history targets
scroll the editor and resume speech exactly like sentence/paragraph navigation.

IMPORT SAFETY: references Qt at module scope — imported lazily by main_window.py
(itself imported after the _QT guard), like the other mixin_*.py modules.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr


class BookmarksQtMixin:
    # ── init helper (called from __init__) ─────────────────────────────
    def _init_nav_history(self) -> None:
        """Initialise the in-memory navigation-history state.

        Mirrors StarApp: ``_nav_history`` is a list of TTS char-offsets;
        ``_nav_hist_pos`` is the cursor into it (-1 means "at the live
        position", i.e. no back-steps taken yet)."""
        self._nav_history: List[int] = []
        self._nav_hist_pos: int = -1

    # ── document key ───────────────────────────────────────────────────
    def _bm_doc_key(self) -> str:
        """The settings key under which this document's bookmarks live."""
        if not self.doc:
            return ""
        return self.doc.path or self.doc.title or ""

    # ── bookmarks ──────────────────────────────────────────────────────
    def _qt_bookmark_add(self, name: str = "") -> None:
        """Set a named bookmark at the current reading position (Ctrl+B).

        With no *name*, auto-generate ``mark1``, ``mark2``, … as the TUI does."""
        if not self.doc or not self.doc.word_map:
            self.statusBar().showMessage(tr("No document loaded."))
            return
        doc_path = self._bm_doc_key()
        bookmarks = dict(self.settings.get("bookmarks", {}))
        doc_bm = dict(bookmarks.get(doc_path, {}))
        name = (name or "").strip()
        if not name:
            n = 1
            while f"mark{n}" in doc_bm:
                n += 1
            name = f"mark{n}"
        cur = self._qt_current_word_for_nav()
        wm = self.doc.word_map
        if not (0 <= cur < len(wm)):
            cur = 0
        offset = wm[cur].tts_offset
        total_chars = len(self.doc.plain_text or "")
        pct = int(100 * offset / max(1, total_chars))
        doc_bm[name] = {
            "offset": offset,
            "pct": pct,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        bookmarks[doc_path] = doc_bm
        self.settings.set("bookmarks", bookmarks)
        self.statusBar().showMessage(
            tr("Bookmark set: {name}  ({pct}%)").format(name=name, pct=pct)
        )

    def _qt_bookmark_add_named(self) -> None:
        """Prompt for a name and set a bookmark there (Ctrl+Shift+B)."""
        if not self.doc or not self.doc.word_map:
            self.statusBar().showMessage(tr("No document loaded."))
            return
        name, ok = QInputDialog.getText(
            self, tr("Add Bookmark"), tr("Bookmark name (blank = auto):")
        )
        if not ok:
            return
        self._qt_bookmark_add(name.strip())

    def _qt_bookmark_goto(self, name: str) -> None:
        """Jump to a named bookmark in the current document."""
        if not self.doc or not self.doc.word_map:
            self.statusBar().showMessage(tr("No document loaded."))
            return
        doc_bm = self.settings.get("bookmarks", {}).get(self._bm_doc_key(), {})
        if name not in doc_bm:
            self.statusBar().showMessage(
                tr("Bookmark '{name}' not found.").format(name=name)
            )
            return
        target_offset = int(doc_bm[name].get("offset", 0))
        best = self._qt_word_for_offset(target_offset)
        self._history_push()
        self._qt_navigate_to_word(best)
        self.statusBar().showMessage(
            tr("Jumped to bookmark '{name}'").format(name=name)
        )

    def _qt_bookmark_delete(self, name: str) -> None:
        """Remove a named bookmark from the current document."""
        doc_path = self._bm_doc_key()
        bookmarks = dict(self.settings.get("bookmarks", {}))
        doc_bm = dict(bookmarks.get(doc_path, {}))
        if name not in doc_bm:
            return
        del doc_bm[name]
        bookmarks[doc_path] = doc_bm
        self.settings.set("bookmarks", bookmarks)
        self.statusBar().showMessage(
            tr("Bookmark '{name}' deleted.").format(name=name)
        )

    def _qt_bookmarks_dialog(self) -> None:
        """Show a list of this document's bookmarks; jump to or delete one."""
        if not self.doc:
            self.statusBar().showMessage(tr("No document loaded."))
            return
        doc_bm = self.settings.get("bookmarks", {}).get(self._bm_doc_key(), {})
        if not doc_bm:
            self.statusBar().showMessage(tr("No bookmarks for this document."))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Bookmarks"))
        dlg.resize(420, 360)
        layout = QVBoxLayout(dlg)
        lst = QListWidget()
        lst.setAccessibleName(tr("Bookmarks"))
        lst.setAccessibleDescription(
            tr("Bookmarks for this document. Enter jumps to one.")
        )
        # Order by saved percentage so the list reads top-to-bottom through the
        # document.
        ordered = sorted(
            doc_bm.items(), key=lambda kv: int(kv[1].get("pct", 0))
        )
        for _name, _v in ordered:
            item = QListWidgetItem(
                f"{_name}   —   {_v.get('pct', '?')}%   ({str(_v.get('ts', ''))[:10]})"
            )
            item.setData(_ITEM_ROLE, _name)
            lst.addItem(item)
        if lst.count():
            lst.setCurrentRow(0)
        layout.addWidget(lst)

        def _go() -> None:
            it = lst.currentItem()
            if it is not None:
                dlg.accept()
                self._qt_bookmark_goto(it.data(_ITEM_ROLE))

        def _del() -> None:
            it = lst.currentItem()
            if it is not None:
                self._qt_bookmark_delete(it.data(_ITEM_ROLE))
                row = lst.currentRow()
                lst.takeItem(row)
                if lst.count() == 0:
                    dlg.accept()

        lst.itemActivated.connect(lambda _i: _go())

        row = QHBoxLayout()
        go_btn = QPushButton(tr("Go"))
        go_btn.clicked.connect(_go)
        del_btn = QPushButton(tr("Delete"))
        del_btn.clicked.connect(_del)
        close_btn = QPushButton(tr("Close"))
        close_btn.clicked.connect(dlg.reject)
        row.addWidget(go_btn)
        row.addWidget(del_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        layout.addLayout(row)
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()

    # ── navigation history ─────────────────────────────────────────────
    def _history_push(self, offset: int = -1) -> None:
        """Record the current TTS offset before a jump (mirrors StarApp)."""
        if not self.doc or not self.doc.word_map:
            return
        if not hasattr(self, "_nav_history"):
            self._init_nav_history()
        if offset < 0:
            cur = self._qt_current_word_for_nav()
            wm = self.doc.word_map
            if 0 <= cur < len(wm):
                offset = wm[cur].tts_offset
            else:
                return
        # Branching off mid-history discards the forward entries.
        if self._nav_hist_pos >= 0:
            self._nav_history = self._nav_history[: self._nav_hist_pos + 1]
            self._nav_hist_pos = -1
        self._nav_history.append(offset)
        max_size = int(self.settings.get("nav_history_size", 50))
        if len(self._nav_history) > max_size:
            self._nav_history = self._nav_history[-max_size:]

    def _qt_history_back(self) -> None:
        """Navigate to the previous position in the history (Alt+Left)."""
        if not hasattr(self, "_nav_history"):
            self._init_nav_history()
        if not self._nav_history:
            self.statusBar().showMessage(tr("Navigation history is empty."))
            return
        total = len(self._nav_history)
        if self._nav_hist_pos == -1:
            new_pos = total - 1  # first back-step → most recently saved position
        elif self._nav_hist_pos > 0:
            new_pos = self._nav_hist_pos - 1
        else:
            self.statusBar().showMessage(tr("No earlier history."))
            return
        self._nav_hist_pos = new_pos
        self.statusBar().showMessage(
            tr("History: position {n}/{total}").format(n=new_pos + 1, total=total)
        )
        self._qt_jump_to_offset(self._nav_history[new_pos])

    def _qt_history_forward(self) -> None:
        """Navigate forward after going back in the history (Alt+Right)."""
        if not hasattr(self, "_nav_history"):
            self._init_nav_history()
        if self._nav_hist_pos < 0:
            self.statusBar().showMessage(tr("No forward history."))
            return
        total = len(self._nav_history)
        new_pos = self._nav_hist_pos + 1
        if new_pos >= total:
            self._nav_hist_pos = -1
            self.statusBar().showMessage(tr("History: at present position."))
            return
        self._nav_hist_pos = new_pos
        self.statusBar().showMessage(
            tr("History: position {n}/{total}").format(n=new_pos + 1, total=total)
        )
        self._qt_jump_to_offset(self._nav_history[new_pos])

    # ── shared jump helpers ────────────────────────────────────────────
    def _qt_word_for_offset(self, target_offset: int) -> int:
        """Return the word-map index whose ``tts_offset`` is at/after *target*."""
        wm = self.doc.word_map if self.doc else []
        best = len(wm) - 1 if wm else 0
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        return best

    def _qt_jump_to_offset(self, target_offset: int) -> None:
        """Scroll to the word closest to *target_offset* (history jumps).

        Unlike a bookmark/user jump this does **not** push history — the caller
        (back/forward) is already walking the recorded stack."""
        if not self.doc or not self.doc.word_map:
            return
        self._qt_navigate_to_word(self._qt_word_for_offset(target_offset))


# QListWidgetItem user-data role for stashing the bookmark name behind its label.
try:
    _ITEM_ROLE = Qt.ItemDataRole.UserRole  # PyQt6
except AttributeError:  # PyQt5
    _ITEM_ROLE = Qt.UserRole  # type: ignore[attr-defined]
