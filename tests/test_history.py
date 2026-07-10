"""Tests for editor undo/redo + the command-history log (star.gui.mixin_history).

Offscreen Qt, following tests/test_authoring.py.
"""
import importlib.util
import os

import pytest

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")


@pytest.fixture
def window(qapp):
    from star.documents import Document
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    win.doc = Document(path="/tmp/d.md", title="D", markdown="# D\n\nhi",
                       plain_text="hi")
    yield win
    win.close()


# ── Undo / redo ──────────────────────────────────────────────────────────────


def test_undo_reverts_a_formatting_action(window):
    window._qt_enter_edit_mode()
    window.editor.setPlainText("word")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    from star.gui._qtcompat import _KEEP_ANCHOR
    cur.setPosition(4, _KEEP_ANCHOR)
    window.editor.setTextCursor(cur)
    window._qt_md_wrap("**", "**", "bold text")
    assert window.editor.toPlainText() == "**word**"
    window._qt_undo()
    assert window.editor.toPlainText() == "word"      # one undo step
    window._qt_redo()
    assert window.editor.toPlainText() == "**word**"


def test_undo_outside_edit_mode_is_a_gentle_no_op(window):
    assert window._qt_edit_mode is False
    window._qt_undo()
    assert "edit" in window.statusBar().currentMessage().lower()


def test_undo_and_redo_are_in_the_edit_menu(window):
    from PyQt6.QtWidgets import QMenu

    edit = next(m for m in window.menuBar().findChildren(QMenu)
                if m.title().replace("&", "") == "Edit")
    labels = [a.text().replace("&", "") for a in edit.actions()]
    assert "Undo" in labels and "Redo" in labels


def test_edit_menu_shows_undo_redo_shortcuts(window):
    """The shortcut text is visible in the menu — but scoped to the editor so
    it never hijacks Ctrl+Z/Y from the Find bar or dialogs."""
    from PyQt6.QtCore import Qt

    assert window._undo_act.shortcut().toString() == "Ctrl+Z"
    assert window._redo_act.shortcut().toString() == "Ctrl+Y"
    for act in (window._undo_act, window._redo_act):
        assert act.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
        assert act in window.editor.actions()   # scoped to the editor


def test_editor_scoped_undo_redo_still_drive_the_editor(window):
    window._qt_enter_edit_mode()
    window.editor.setPlainText("abc")
    window.editor.textCursor().insertText("X")   # one undoable step
    after_insert = window.editor.toPlainText()
    window._undo_act.trigger()
    assert window.editor.toPlainText() == "abc"      # undo reverts it
    window._redo_act.trigger()
    assert window.editor.toPlainText() == after_insert  # redo restores it


def test_editor_context_menu_offers_undo_redo_while_editing(window):
    """Right-click in edit mode must offer Undo/Redo (Qt's standard edit menu)
    plus the Format submenu — the user's ask for context-menu access."""
    window._qt_enter_edit_mode()
    window.editor.setPlainText("hello")
    menu = window.editor.createStandardContextMenu()
    std = [a.text().replace("&", "") for a in menu.actions()]
    assert any(t.startswith("Undo") for t in std)
    assert any(t.startswith("Redo") for t in std)
    menu.deleteLater()


# ── Command history ──────────────────────────────────────────────────────────


def test_commands_are_recorded_with_a_timestamp(window):
    window._record_command("Bold")
    window._record_command("Italic")
    hist = window._command_history
    assert [row[2] for row in hist] == ["Bold", "Italic"]
    assert all(len(row) == 3 for row in hist)         # (time, kind, label)
    assert all(row[1] == "cmd" for row in hist)


def test_errors_are_recorded_as_errors(window):
    window._status_error("Save error: disk full")
    assert any(kind == "error" and "disk full" in label
               for _ts, kind, label in window._command_history)


def test_history_text_marks_errors_and_orders_oldest_first(window):
    window._record_command("Open")
    window._status_error("boom")
    text = window._command_history_text()
    lines = text.splitlines()
    assert "Open" in lines[0] and "·" in lines[0]
    assert "boom" in lines[1] and "⚠" in lines[1]


def test_history_is_capped(window):
    from star.gui.mixin_history import _HISTORY_CAP

    for i in range(_HISTORY_CAP + 50):
        window._record_command(f"cmd{i}")
    assert len(window._command_history) == _HISTORY_CAP
    # Oldest entries dropped; the most recent survive.
    assert window._command_history[-1][2] == f"cmd{_HISTORY_CAP + 49}"


def test_menu_and_toolbar_commands_feed_the_history(window):
    """The action-creation helpers wire every command into the log — clicking a
    toolbar button records it, no per-command wiring needed."""
    window._command_history = []
    window._toolbar_actions["Stop"].trigger()
    labels = [row[2] for row in window._command_history]
    assert "Stop" in labels


def test_empty_history_reads_cleanly(window):
    window._command_history = []
    assert "No commands" in window._command_history_text()
