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


def test_new_document_cancel_keeps_current_edits(window, monkeypatch):
    """New Document mid-edit offers Save / Discard / Cancel (like Ctrl+E and
    open-another-doc); Cancel keeps the current work and stays editing."""
    from PyQt6.QtWidgets import QMessageBox

    window._qt_enter_edit_mode()
    window._qt_edit_dirty = True
    window.editor.setPlainText("precious work")
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    window._qt_new_document()
    assert window.editor.toPlainText() == "precious work"
    assert window._qt_edit_mode is True


def test_new_document_discard_starts_blank(window, monkeypatch):
    """Discarding unsaved edits starts the blank Untitled document."""
    from PyQt6.QtWidgets import QMessageBox

    window._qt_enter_edit_mode()
    window._qt_edit_dirty = True
    window.editor.setPlainText("throwaway draft")
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard),
    )
    window._qt_new_document()
    assert window._qt_edit_mode is True
    assert window.doc.path == ""              # fresh in-memory Untitled doc
    assert window.editor.toPlainText() == ""  # blank canvas


def test_stale_background_load_does_not_clobber_new_document(window):
    """A slow startup file load must not overwrite a document created while it
    was still loading.

    This is the race behind the intermittent ``doc.path`` failures dismissed
    as flakes on two release days: the window's constructor kicks off an async
    welcome.md load; if the user creates a New document before it finishes, the
    late ``_doc_loaded`` signal used to apply the welcome doc over the blank
    one.  The load-generation guard drops the superseded result.  Replayed here
    deterministically (no thread-timing dependence)."""
    from star.documents import Document

    stale_gen = window._doc_load_gen  # the generation the "welcome load" holds

    window._qt_new_document()          # bumps the generation, applies blank
    assert window.doc.path == ""

    # The background welcome load now finishes and delivers its (stale) signal
    # — _on_doc_loaded_async is the slot the pyqtSignal is wired to, where the
    # freshness gate lives.
    window._pending_doc = Document(
        path="welcome.md", title="Welcome", markdown="# Welcome\n",
        plain_text="Welcome", format="markdown",
    )
    window._pending_doc_gen = stale_gen
    window._on_doc_loaded_async()

    # Dropped as superseded — the blank Untitled document survives.
    assert window.doc.path == ""
    assert window.editor.toPlainText() == ""

    # A *current* async delivery (matching generation) is still applied — the
    # gate drops only superseded results, never fresh ones.
    window._doc_load_gen += 1
    window._pending_doc = Document(
        path="real.md", title="Real", markdown="# Real\n",
        plain_text="Real", format="markdown",
    )
    window._pending_doc_gen = window._doc_load_gen
    window._on_doc_loaded_async()
    assert window.doc.path == "real.md"


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


def _action_for_shortcut(window, key):
    from PyQt6.QtGui import QAction, QKeySequence

    seq = QKeySequence(key)
    return [a for a in window.findChildren(QAction) if a.shortcut() == seq]


def test_bold_binding_ctrl_b_is_owned_by_format_not_bookmark(window):
    """True keyboard formatting: Ctrl+B triggers Bold (exactly one owner — the
    old Add Bookmark binding was moved to Ctrl+M)."""
    _edit(window, "word")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    cur.setPosition(4, _KA())
    window.editor.setTextCursor(cur)
    acts = _action_for_shortcut(window, "Ctrl+B")
    assert len(acts) == 1                       # unambiguous single owner
    acts[0].trigger()
    assert window.editor.toPlainText() == "**word**"


def test_italic_and_link_bindings_exist(window):
    assert len(_action_for_shortcut(window, "Ctrl+I")) == 1
    assert len(_action_for_shortcut(window, "Ctrl+K")) == 1
    # Bookmark relocated to Ctrl+M.
    assert len(_action_for_shortcut(window, "Ctrl+M")) == 1


def test_underline_wraps_selection_in_html(window):
    """Markdown has no native underline, so Ctrl+U wraps in <u></u> (inline
    HTML, which Markdown renderers pass through)."""
    _edit(window, "word")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    cur.setPosition(4, _KA())
    window.editor.setTextCursor(cur)
    acts = _action_for_shortcut(window, "Ctrl+U")
    assert len(acts) == 1
    acts[0].trigger()
    assert window.editor.toPlainText() == "<u>word</u>"
    assert "Underline" in window._edit_toolbar_actions


def test_menu_bar_padding_is_tightened(window):
    """star has ~11 top-level menus; the bar carries a QMenuBar::item padding
    override so they all fit on a 1080p display instead of overflowing into a
    chevron."""
    ss = window.menuBar().styleSheet()
    assert "QMenuBar::item" in ss and "padding" in ss
    # The 0.1.27 simplification: exactly these eleven menus, in this order
    # (Highlight+Notes+Bookmarks merged into Annotate; Citations into Study;
    # Profiles into Edit) — a menu creeping back in should be a conscious act.
    menus = [a.menu().title().replace("&", "")
             for a in window.menuBar().actions() if a.menu()]
    assert menus == [
        "File", "Edit", "View", "Annotate", "Speech", "Navigate",
        "Format", "Study", "Graph", "Tools", "Help",
    ]


def test_formatting_is_a_no_op_outside_edit_mode(window):
    # Read mode: the editor holds rendered HTML; formatting must not touch it.
    assert window._qt_edit_mode is False
    before = window.editor.toPlainText()
    window._qt_md_wrap("**", "**", "x")
    window._qt_md_line_prefix("# ")
    assert window.editor.toPlainText() == before
    assert "format" in window.statusBar().currentMessage().lower()


# ── Live-edit workflow (save-stays-in-edit-mode + preview refresh + finish) ───


def test_save_keeps_the_user_in_edit_mode(window, tmp_path):
    """Ctrl+S writes the file but stays in edit mode so the user keeps the
    live-edit loop instead of being dropped back to read mode."""
    src = tmp_path / "note.md"
    src.write_text("# Old\n", encoding="utf-8")
    window.doc.path = str(src)
    window._qt_enter_edit_mode()
    window.editor.setPlainText("# New heading\n\nBody.\n")
    window._qt_save()
    assert src.read_text(encoding="utf-8") == "# New heading\n\nBody.\n"
    assert window._qt_edit_mode is True                 # still editing
    assert not window.editor.isReadOnly()
    assert window._qt_edit_dirty is False               # clean after save
    assert window.editor.toPlainText() == "# New heading\n\nBody.\n"  # raw source


def test_formatting_refreshes_preview_immediately(window, monkeypatch):
    """A discrete formatting action re-renders the live preview at once rather
    than waiting for the typing debounce."""
    _edit(window, "para")
    # Offscreen never truly shows a widget, so force the preview's visibility
    # for this check and spy on the render call.
    monkeypatch.setattr(window._preview, "isVisible", lambda: True)
    calls = []
    monkeypatch.setattr(window, "_qt_render_preview", lambda: calls.append(1))
    window._qt_md_line_prefix("# ")
    assert calls, "formatting should refresh the live preview immediately"


def test_formatting_preview_refresh_is_a_no_op_when_hidden(window, monkeypatch):
    """With the preview hidden, formatting must not touch it (no render)."""
    _edit(window, "para")
    monkeypatch.setattr(window._preview, "isVisible", lambda: False)
    calls = []
    monkeypatch.setattr(window, "_qt_render_preview", lambda: calls.append(1))
    window._qt_md_wrap("**", "**", "bold")
    assert not calls


def _qmb():
    from PyQt6.QtWidgets import QMessageBox
    return QMessageBox


def test_finish_editing_cancel_keeps_editing(window, monkeypatch):
    """Ctrl+E with unsaved changes → Cancel leaves the user editing, unsaved."""
    QMessageBox = _qmb()
    window._qt_enter_edit_mode()
    window.editor.setPlainText("unsaved work")
    window._qt_edit_dirty = True
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    window._qt_edit_mode_toggle()   # Ctrl+E
    assert window._qt_edit_mode is True
    assert window.editor.toPlainText() == "unsaved work"


def test_finish_editing_discard_exits_without_saving(window, monkeypatch, tmp_path):
    """Ctrl+E → Discard leaves edit mode and does NOT write the file."""
    QMessageBox = _qmb()
    src = tmp_path / "note.md"
    src.write_text("original\n", encoding="utf-8")
    window.doc.path = str(src)
    window.doc.markdown = "original\n"
    window._qt_enter_edit_mode()
    window.editor.setPlainText("throwaway")
    window._qt_edit_dirty = True
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard),
    )
    window._qt_edit_mode_toggle()   # Ctrl+E
    assert window._qt_edit_mode is False
    assert src.read_text(encoding="utf-8") == "original\n"   # not overwritten


def test_finish_editing_save_persists_then_exits(window, monkeypatch, tmp_path):
    """Ctrl+E → Save writes the file and then leaves edit mode."""
    QMessageBox = _qmb()
    src = tmp_path / "note.md"
    src.write_text("original\n", encoding="utf-8")
    window.doc.path = str(src)
    window.doc.markdown = "original\n"
    window._qt_enter_edit_mode()
    window.editor.setPlainText("kept edit\n")
    window._qt_edit_dirty = True
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save),
    )
    window._qt_edit_mode_toggle()   # Ctrl+E
    assert src.read_text(encoding="utf-8") == "kept edit\n"
    assert window._qt_edit_mode is False


def test_finish_editing_when_clean_just_exits(window):
    """Ctrl+E with no unsaved changes exits straight to read mode (no prompt)."""
    window._qt_enter_edit_mode()
    window._qt_edit_dirty = False
    window._qt_edit_mode_toggle()   # Ctrl+E
    assert window._qt_edit_mode is False
    assert window.editor.isReadOnly()


# ── Document-replacement teardown (regression: open mid-edit must not corrupt) ─


def test_confirm_leave_edit_cancel_aborts(window, monkeypatch):
    """Opening another document mid-edit → Cancel keeps the user editing."""
    QMessageBox = _qmb()
    window._qt_enter_edit_mode()
    window.editor.setPlainText("mid-edit")
    window._qt_edit_dirty = True
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    assert window._qt_confirm_leave_edit_for_replace() is False
    assert window._qt_edit_mode is True          # still editing, open aborted


def test_confirm_leave_edit_discard_tears_down(window, monkeypatch):
    """Discarding leaves edit mode cleanly so the next document loads read-only."""
    QMessageBox = _qmb()
    window._qt_enter_edit_mode()
    window.editor.setPlainText("mid-edit")
    window._qt_edit_dirty = True
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard),
    )
    assert window._qt_confirm_leave_edit_for_replace() is True
    assert window._qt_edit_mode is False
    assert window.editor.isReadOnly()


def test_loading_a_document_mid_edit_tears_edit_mode_down(window, tmp_path):
    """Regression (HIGH): with Ctrl+S now keeping the user in edit mode, loading
    another file must not leave the editor editable over the new document — a
    later save would otherwise overwrite that file with markdown-stripped text.
    The _on_doc_loaded safety net tears edit mode down before rendering."""
    from star.documents import Document

    fileB = tmp_path / "b.md"
    fileB.write_text("# B\n\n**bold** stays.\n", encoding="utf-8")
    window._qt_enter_edit_mode()
    window.editor.setPlainText("edits to the previous doc")
    window._qt_edit_dirty = True
    # Simulate the background load of fileB completing.
    window._pending_doc = Document(
        path=str(fileB), title="B",
        markdown="# B\n\n**bold** stays.\n", plain_text="B bold stays.",
    )
    window._on_doc_loaded()
    assert window._qt_edit_mode is False          # torn down by the safety net
    assert window.editor.isReadOnly()
    # fileB on disk is untouched — no accidental overwrite.
    assert fileB.read_text(encoding="utf-8") == "# B\n\n**bold** stays.\n"


def test_converted_doc_save_as_adopts_path_no_reprompt(window, monkeypatch, tmp_path):
    """Regression: a document whose source is a non-text file must adopt the
    chosen .md path on first Save-As, so the live-edit loop's next Ctrl+S writes
    in place instead of re-opening the Save-As dialog every time."""
    from PyQt6.QtWidgets import QFileDialog

    md = tmp_path / "report.md"
    window.doc.path = str(tmp_path / "report.pdf")   # non-text source format
    window.doc.markdown = "# R\n"
    window._qt_enter_edit_mode()
    window.editor.setPlainText("# Report\n\nEdited once.\n")

    calls = {"n": 0}

    def fake_save_as(*a, **k):
        calls["n"] += 1
        return (str(md), "")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fake_save_as))
    window._qt_save()
    assert md.read_text(encoding="utf-8") == "# Report\n\nEdited once.\n"
    assert window.doc.path == str(md)     # adopted the saved .md path
    assert calls["n"] == 1
    assert window._qt_edit_mode is True   # still editing (live-edit loop)

    # Second save writes in place — the dialog must NOT appear again.
    window.editor.setPlainText("# Report\n\nEdited twice.\n")
    window._qt_save()
    assert md.read_text(encoding="utf-8") == "# Report\n\nEdited twice.\n"
    assert calls["n"] == 1


# ── Word-map rebuild gate (Qt-teardown flake hardening) ──────────────────────


def test_word_map_rebuild_only_after_a_real_change(window, monkeypatch, tmp_path):
    """The read-view word/sentence-map rebuild runs on a background thread that
    races Qt teardown (the documented exit-139 flake). Gate it: it must fire only
    when an edit was actually saved — never on a plain enter/finish or discard —
    so the common no-change path spawns no daemon thread."""
    calls = {"n": 0}
    monkeypatch.setattr(
        window, "_qt_rebuild_word_maps_async",
        lambda: calls.__setitem__("n", calls["n"] + 1),
    )

    # (a) Enter edit mode and finish with NO change → no rebuild.
    window._qt_enter_edit_mode()
    window._qt_exit_edit_mode(save=False)
    assert calls["n"] == 0
    assert window._qt_maps_stale is False

    # (b) Enter, edit, save (stays editing) → flag set, but no rebuild yet …
    src = tmp_path / "n.md"
    src.write_text("# Old\n", encoding="utf-8")
    window.doc.path = str(src)
    window._qt_enter_edit_mode()
    window.editor.setPlainText("# New\n\nBody.\n")
    window._qt_save()
    assert calls["n"] == 0
    assert window._qt_maps_stale is True
    # … finishing rebuilds exactly once and clears the flag.
    window._qt_exit_edit_mode(save=False)
    assert calls["n"] == 1
    assert window._qt_maps_stale is False


def test_loading_a_document_clears_the_stale_maps_flag(window, tmp_path):
    """A fresh load builds its own maps, so a stale flag from a prior edit must
    not carry over (which would suppress the next legitimate rebuild)."""
    from star.documents import Document

    window._qt_maps_stale = True   # pretend a prior edit left it stale
    window._pending_doc = Document(
        path=str(tmp_path / "x.md"), title="X", markdown="# X\n", plain_text="X",
    )
    window._on_doc_loaded()
    assert window._qt_maps_stale is False


def test_word_map_worker_bails_when_window_is_closing(window):
    """The rebuild worker must skip its work when the window is closing rather
    than churn a daemon thread against a teardown-in-progress. With _closing set,
    calling the rebuild leaves the maps untouched."""
    # A valid word map is List[int] (char offsets); use ints so any incidental
    # highlight/caret event that touches it during the test can't type-error.
    sentinel = [0, 1, 2]
    window._qt_word_map = sentinel
    window._closing = True
    window._qt_rebuild_word_maps_async()   # spawns a thread that must early-return
    import time as _t
    _t.sleep(0.2)                           # give any (wrongly-spawned) work time
    assert window._qt_word_map is sentinel  # worker bailed, nothing rebuilt
