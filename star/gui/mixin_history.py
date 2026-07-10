"""HistoryMixin — editor undo/redo + a command-history log for troubleshooting.

Now that star can author documents, users make mistakes and need to undo them,
and a running log of the commands they invoked (and errors that surfaced) makes
"what did I just do?" answerable — both for the user and for a bug report.

* ``_qt_undo`` / ``_qt_redo`` drive the editor's own undo stack (each formatting
  action is one step — see AuthoringMixin's beginEditBlock/endEditBlock).  They
  are exposed as toolbar buttons + Format-menu items rather than global
  Ctrl+Z/Y shortcuts, so the editor's (and every dialog field's) native undo
  keeps working untouched.
* ``_record_command`` is called from the action-creation helpers in ChromeMixin
  for every menu/toolbar command, and from ``_status_error`` for failures, so
  the history is captured centrally with no per-command wiring.
* ``_qt_show_command_history`` shows the log in a copyable dialog.

Mixed into StarWindow; operates on ``self.editor`` and ``self._command_history``.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from .a11y import announce

try:  # QKeySequence isn't re-exported by _runtime
    from PyQt6.QtGui import QKeySequence
except ImportError:  # PyQt5
    from PyQt5.QtGui import QKeySequence  # type: ignore

_HISTORY_CAP = 500  # keep the log bounded; a session rarely needs more


class HistoryMixin:

    # ── Undo / redo (editor) ───────────────────────────────────────────────

    def _make_editor_edit_action(self, label, std_key, fn, tip):
        """A QAction whose shortcut is scoped to the editor.

        Setting the shortcut makes menus display it, but the
        WidgetWithChildrenShortcut context + adding the action to self.editor
        means the key only fires while the editor has focus — so Ctrl+Z /
        Ctrl+Y never hijack undo in the Find bar, dialogs, or other fields."""
        a = QAction(tr(label), self)
        a.setShortcut(QKeySequence(std_key))
        try:
            a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        except AttributeError:  # PyQt5
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)  # type: ignore
        a.setToolTip(tr(tip))
        a.triggered.connect(fn)
        a.triggered.connect(lambda *_a, _L=label: self._record_command(_L))
        self.editor.addAction(a)
        return a

    def _qt_undo(self) -> None:
        if not getattr(self, "_qt_edit_mode", False):
            self.statusBar().showMessage(tr("Undo works while editing (Ctrl+E)"))
            return
        self.editor.undo()
        self.statusBar().showMessage(tr("Undo"))
        announce(self.editor, tr("Undo"))

    def _qt_redo(self) -> None:
        if not getattr(self, "_qt_edit_mode", False):
            self.statusBar().showMessage(tr("Redo works while editing (Ctrl+E)"))
            return
        self.editor.redo()
        self.statusBar().showMessage(tr("Redo"))
        announce(self.editor, tr("Redo"))

    def _qt_editor_context_menu(self, pos) -> None:
        """Right-click menu for the editor.

        Built on Qt's standard edit menu — Undo, Redo, Cut, Copy, Paste,
        Delete, Select All — which already carries the correct enabled state
        and native shortcuts, so Undo/Redo are always a right-click away while
        editing.  In edit mode a Format submenu is appended for the Markdown
        authoring actions."""
        menu = self.editor.createStandardContextMenu()
        if getattr(self, "_qt_edit_mode", False):
            menu.addSeparator()
            fmt = menu.addMenu(tr("Format"))
            fmt.addAction(tr("Bold"),
                          lambda: self._qt_md_wrap("**", "**", "bold text"))
            fmt.addAction(tr("Italic"),
                          lambda: self._qt_md_wrap("*", "*", "italic text"))
            fmt.addAction(tr("Underline"),
                          lambda: self._qt_md_wrap("<u>", "</u>", "underlined text"))
            fmt.addAction(tr("Inline Code"),
                          lambda: self._qt_md_wrap("`", "`", "code"))
            fmt.addSeparator()
            fmt.addAction(tr("Heading"), lambda: self._qt_md_line_prefix("# "))
            fmt.addAction(tr("Bullet List"), lambda: self._qt_md_line_prefix("- "))
            fmt.addAction(tr("Numbered List"),
                          lambda: self._qt_md_line_prefix("", True))
            fmt.addAction(tr("Block Quote"), lambda: self._qt_md_line_prefix("> "))
            fmt.addSeparator()
            fmt.addAction(tr("Insert Link"), self._qt_md_link)
            fmt.addAction(tr("Horizontal Rule"), self._qt_md_insert_rule)
        gpos = self.editor.mapToGlobal(pos)
        menu.exec(gpos) if _QT == "PyQt6" else menu.exec_(gpos)
        menu.deleteLater()

    # ── Command history ────────────────────────────────────────────────────

    def _record_command(self, label: str, kind: str = "cmd") -> None:
        """Append one entry to the in-session command log.

        *kind* is ``"cmd"`` (a command was run) or ``"error"`` (a failure was
        surfaced).  Best-effort — never let logging break a command."""
        try:
            hist = getattr(self, "_command_history", None)
            if hist is None:
                hist = self._command_history = []
            hist.append((time.strftime("%H:%M:%S"), kind, str(label)))
            if len(hist) > _HISTORY_CAP:
                del hist[: len(hist) - _HISTORY_CAP]
        except Exception:  # noqa: BLE001
            pass

    def _command_history_text(self) -> str:
        """The log rendered oldest→newest, one line per entry."""
        hist = getattr(self, "_command_history", None) or []
        if not hist:
            return tr("No commands recorded yet.")
        out = []
        for ts, kind, label in hist:
            mark = "⚠" if kind == "error" else "·"
            out.append(f"{ts}  {mark} {label}")
        return "\n".join(out)

    def _qt_show_command_history(self) -> None:
        """Show the command log in a copyable dialog (for troubleshooting)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Command History"))
        dlg.resize(520, 460)
        lay = QVBoxLayout(dlg)
        hint = QLabel(
            tr("What you've done this session, newest at the bottom. Use "
               "Copy to include it in a bug report."),
            dlg,
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)
        view = QTextEdit(dlg)
        view.setReadOnly(True)
        view.setPlainText(self._command_history_text())
        view.setAccessibleName(tr("Command history"))
        # Scroll to the most recent entry.
        try:
            view.moveCursor(QTextCursor.MoveOperation.End)
        except AttributeError:  # PyQt5
            view.moveCursor(QTextCursor.End)  # type: ignore[attr-defined]
        lay.addWidget(view)
        try:
            _copy = QDialogButtonBox.StandardButton.Close
        except AttributeError:  # PyQt5
            _copy = QDialogButtonBox.Close  # type: ignore[attr-defined]
        box = QDialogButtonBox(_copy)
        copy_btn = QPushButton(tr("Copy to clipboard"), dlg)

        def _do_copy() -> None:
            app = QApplication.instance()
            if app is not None:
                app.clipboard().setText(self._command_history_text())
                self.statusBar().showMessage(tr("Command history copied"))

        copy_btn.clicked.connect(_do_copy)
        box.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole
                      if hasattr(QDialogButtonBox, "ButtonRole")
                      else QDialogButtonBox.ActionRole)  # type: ignore[attr-defined]
        box.rejected.connect(dlg.reject)
        lay.addWidget(box)
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()
