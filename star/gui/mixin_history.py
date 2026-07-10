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

_HISTORY_CAP = 500  # keep the log bounded; a session rarely needs more


class HistoryMixin:

    # ── Undo / redo (editor) ───────────────────────────────────────────────

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
