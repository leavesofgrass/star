"""Tests for the document-authoring features: New Document + the Markdown
formatting toolbar (star.gui.mixin_authoring + ChromeMixin._build_edit_toolbar).

Offscreen Qt, following tests/test_translate_dictate.py: a real StarWindow with
a fake document, driving the authoring methods directly.
"""
import importlib.util

import pytest

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")


def _KA():
    """The KeepAnchor cursor move-mode (binding-agnostic), imported lazily."""
    from star.gui._qtcompat import _KEEP_ANCHOR

    return _KEEP_ANCHOR


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


# ── New Document ─────────────────────────────────────────────────────────────


def test_new_document_opens_blank_in_edit_mode(window):
    window._qt_new_document()
    assert window._qt_edit_mode is True
    assert window.doc.path == ""            # in-memory until first save
    assert window.doc.format == "markdown"
    assert window.editor.toPlainText() == ""  # blank canvas, editable


def test_new_document_confirms_before_discarding_edits(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    window._qt_enter_edit_mode()
    window._qt_edit_dirty = True
    window.editor.setPlainText("precious work")
    # User answers "No" → keep the current document.
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    window._qt_new_document()
    assert window.editor.toPlainText() == "precious work"


# ── Formatting toolbar visibility ────────────────────────────────────────────


def test_formatting_toolbar_exists_and_follows_edit_mode(window):
    tb = window._edit_toolbar
    assert tb is not None
    # Offscreen: the top-level window isn't shown, so isVisible() is always
    # False; isHidden() reflects the explicit setVisible() state we drive.
    assert tb.isHidden()                             # hidden in read mode
    window._qt_enter_edit_mode()
    assert not tb.isHidden()                         # shown while editing
    window._qt_exit_edit_mode(save=False)
    assert tb.isHidden()                             # hidden again
    # The core authoring actions are all present.
    for label in ("Bold", "Italic", "Heading", "Bullet List", "Numbered List",
                  "Quote", "Inline Code", "Link", "Horizontal Rule"):
        assert label in window._edit_toolbar_actions


# ── Formatting actions ───────────────────────────────────────────────────────


def _edit(window, text):
    window._qt_enter_edit_mode()
    window.editor.setPlainText(text)


def test_bold_wraps_the_selection(window):
    _edit(window, "make me bold")
    cur = window.editor.textCursor()
    cur.setPosition(8)
    cur.setPosition(12, _KA())
    window.editor.setTextCursor(cur)
    window._qt_md_wrap("**", "**", "bold text")
    assert window.editor.toPlainText() == "make me **bold**"


def test_wrap_with_no_selection_inserts_a_placeholder(window):
    _edit(window, "")
    window._qt_md_wrap("*", "*", "italic text")
    assert window.editor.toPlainText() == "*italic text*"
    # The placeholder is selected so the user types over it.
    assert window.editor.textCursor().selectedText() == "italic text"


def test_heading_prefixes_the_current_line(window):
    _edit(window, "Title\nbody")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    window.editor.setTextCursor(cur)
    window._qt_md_line_prefix("# ")
    assert window.editor.toPlainText() == "# Title\nbody"


def test_numbered_list_renumbers_selected_lines(window):
    _edit(window, "one\ntwo\nthree")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    cur.setPosition(len("one\ntwo\nthree"),
                    _KA())
    window.editor.setTextCursor(cur)
    window._qt_md_line_prefix("", numbered=True)
    assert window.editor.toPlainText() == "1. one\n2. two\n3. three"


def test_bullet_list_prefixes_each_selected_line(window):
    _edit(window, "a\nb")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    cur.setPosition(3, _KA())
    window.editor.setTextCursor(cur)
    window._qt_md_line_prefix("- ")
    assert window.editor.toPlainText() == "- a\n- b"


def test_link_wraps_selection_as_link_text(window):
    _edit(window, "click here")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    cur.setPosition(10, _KA())
    window.editor.setTextCursor(cur)
    window._qt_md_link()
    assert window.editor.toPlainText() == "[click here](https://)"


def test_horizontal_rule_inserts_a_rule(window):
    _edit(window, "above")
    cur = window.editor.textCursor()
    cur.setPosition(5)
    window.editor.setTextCursor(cur)
    window._qt_md_insert_rule()
    assert window.editor.toPlainText() == "above\n---\n"


def test_formatting_is_a_no_op_outside_edit_mode(window):
    # Read mode: the editor holds rendered HTML; formatting must not touch it.
    assert window._qt_edit_mode is False
    before = window.editor.toPlainText()
    window._qt_md_wrap("**", "**", "x")
    window._qt_md_line_prefix("# ")
    assert window.editor.toPlainText() == before
    assert "format" in window.statusBar().currentMessage().lower()
