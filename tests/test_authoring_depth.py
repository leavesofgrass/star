"""Authoring-depth arc (0.1.26): find & replace, tables, image insertion,
autosave / crash recovery, and export-from-the-editor.

Each surface gets a focused GUI test (the per-surface discipline the recent
authoring releases established), plus pure-logic tests for the autosave
snapshot helpers that run without a QApplication.
"""
import json

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from star.gui import mixin_autosave as A  # noqa: E402
from star.settings import Settings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow

    win = StarWindow(Settings())
    yield win
    win.close()


def _enter_edit_with(window, text: str) -> None:
    """Load *text* as a new doc and enter edit mode."""
    window._qt_new_document()  # blank doc → edit mode
    window.editor.setPlainText(text)


# ── Find & Replace ───────────────────────────────────────────────────────────


def test_replace_one_replaces_current_match(window):
    _enter_edit_with(window, "alpha beta alpha gamma alpha")
    window._replace_show()  # opens the bar with the replace row (edit mode)
    window._find_input.setText("alpha")
    window._find_run("alpha")
    window._replace_input.setText("X")
    window._find_replace_one()
    # Exactly one 'alpha' became 'X'.
    assert window.editor.toPlainText().count("alpha") == 2
    assert "X" in window.editor.toPlainText()


def test_replace_all_replaces_every_match_one_undo(window):
    _enter_edit_with(window, "cat cat cat dog cat")
    window._replace_show()
    window._find_input.setText("cat")
    window._find_run("cat")
    window._replace_input.setText("fish")
    window._find_replace_all()
    txt = window.editor.toPlainText()
    assert "cat" not in txt
    assert txt.count("fish") == 4
    # Replace All is a single undo step.
    window.editor.undo()
    assert window.editor.toPlainText().count("cat") == 4


def test_replace_is_noop_outside_edit_mode(window):
    # Read mode: replace must not mutate the read-only rendered view.
    before = window.editor.toPlainText()
    window._find_replace_all()
    assert window.editor.toPlainText() == before


# ── Tables ───────────────────────────────────────────────────────────────────


def test_table_skeleton_shape():
    from star.gui.main_window import StarWindow

    sk = StarWindow._md_table_skeleton(2, 3)
    lines = sk.strip().splitlines()
    assert lines[0].count("|") == 4  # 3 columns → 4 pipes
    assert set(lines[1].replace("|", "").replace(" ", "")) == {"-"}
    assert len(lines) == 4  # header + separator + 2 body rows


def test_insert_table_writes_markdown(window, monkeypatch):
    _enter_edit_with(window, "")
    from star.gui import mixin_authoring as MA

    # Answer the two size prompts (columns=2, rows=2) without a real dialog.
    calls = iter([(2, True), (2, True)])
    monkeypatch.setattr(
        MA, "QInputDialog",
        type("D", (), {"getInt": staticmethod(lambda *a, **k: next(calls))}),
    )
    window._qt_md_insert_table()
    txt = window.editor.toPlainText()
    assert "| Column 1 | Column 2 |" in txt
    assert "| --- | --- |" in txt


def test_add_table_row_matches_columns(window):
    _enter_edit_with(window, "| a | b | c |\n| --- | --- | --- |\n| 1 | 2 | 3 |")
    # Put the cursor on the last table line.
    cur = window.editor.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    window.editor.setTextCursor(cur)
    window._qt_md_table_add_row()
    lines = window.editor.toPlainText().splitlines()
    assert lines[-1].count("|") == 4  # a fresh 3-column row


# ── Image insertion ──────────────────────────────────────────────────────────


def test_insert_image_uses_relative_path_when_saved(window, monkeypatch, tmp_path):
    from star.documents import Document
    from star.gui import mixin_authoring as MA

    doc_path = tmp_path / "note.md"
    doc_path.write_text("hi", encoding="utf-8")
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n")
    window._pending_doc = Document(path=str(doc_path), title="note", markdown="",
                                   plain_text="", format="markdown")
    window._on_doc_loaded()
    window._qt_enter_edit_mode()
    monkeypatch.setattr(
        MA.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(img), "")),
    )
    window._qt_md_insert_image()
    assert "![pic](pic.png)" in window.editor.toPlainText()


# ── Export from the editor ───────────────────────────────────────────────────


def test_live_markdown_reflects_unsaved_edits(window):
    _enter_edit_with(window, "# Draft heading\n\nlive body")
    assert window._qt_live_markdown() == "# Draft heading\n\nlive body"
    # A copy doc carries the live buffer without mutating self.doc.
    live = window._qt_live_doc()
    assert "live body" in live.markdown
    assert window.doc.markdown != "# Draft heading\n\nlive body"  # self.doc untouched


def test_export_markdown_writes_editor_buffer(window, monkeypatch, tmp_path):
    from star.gui import mixin_export as ME

    _enter_edit_with(window, "edited but unsaved")
    dest = tmp_path / "out.md"
    monkeypatch.setattr(
        ME.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(dest), "")),
    )
    window._qt_export_markdown()
    assert dest.read_text(encoding="utf-8") == "edited but unsaved"


# ── Autosave / crash recovery (pure helpers) ─────────────────────────────────


def test_snapshot_key_stable_for_path():
    k1 = A._snapshot_key("/tmp/a.md", "id1")
    k2 = A._snapshot_key("/tmp/a.md", "id2")
    assert k1 == k2 and k1.startswith("doc-")
    # Untitled keys off the per-window id instead.
    assert A._snapshot_key("", "id1") != A._snapshot_key("", "id2")


def test_write_and_scan_snapshot(tmp_path):
    d = tmp_path / "recovery"
    payload = {"path": "", "title": "Untitled", "markdown": "unsaved text",
               "ts": "2026-07-11T00:00:00"}
    assert A._write_snapshot(d / "untitled-abc.json", payload)
    found = A._scan_snapshots(d)
    assert len(found) == 1
    assert found[0]["markdown"] == "unsaved text"


def test_scan_skips_already_saved(tmp_path):
    d = tmp_path / "recovery"
    saved = tmp_path / "saved.md"
    saved.write_text("same text", encoding="utf-8")
    A._write_snapshot(
        d / "doc-xyz.json",
        {"path": str(saved), "title": "saved", "markdown": "same text", "ts": "x"},
    )
    # On-disk content matches the snapshot → stale → skipped and removed.
    assert A._scan_snapshots(d) == []
    assert not (d / "doc-xyz.json").exists()


def test_autosave_tick_writes_only_when_dirty(window, monkeypatch, tmp_path):
    monkeypatch.setattr(A, "_CFG_ROOT", tmp_path)
    _enter_edit_with(window, "typing…")
    window._qt_edit_dirty = True
    window._autosave_tick()
    snap = window._autosave_snapshot_path()
    assert snap.exists()
    data = json.loads(snap.read_text(encoding="utf-8"))
    assert data["markdown"] == "typing…"
    # A clean (non-dirty) buffer writes nothing new.
    snap.unlink()
    window._qt_edit_dirty = False
    window._autosave_tick()
    assert not snap.exists()


def test_autosave_opt_out_setting_disables_snapshots(window, monkeypatch, tmp_path):
    monkeypatch.setattr(A, "_CFG_ROOT", tmp_path)
    window.settings["autosave_recovery"] = False
    _enter_edit_with(window, "should not be snapshotted")
    window._qt_edit_dirty = True
    window._autosave_tick()
    assert not window._autosave_snapshot_path().exists()


def test_startup_recovery_offer_loads_the_snapshot(window, monkeypatch, tmp_path):
    """Accepting the recovery prompt opens the snapshot as an editable doc."""
    monkeypatch.setattr(A, "_CFG_ROOT", tmp_path)
    # Seed a recovery snapshot as if a prior session crashed mid-edit.
    A._write_snapshot(
        tmp_path / "recovery" / "untitled-crashed.json",
        {"path": "", "title": "Draft", "markdown": "recovered body",
         "ts": "2026-07-11T09:00:00"},
    )
    # Auto-answer the prompt "Yes".
    from star.gui import mixin_autosave as MA

    monkeypatch.setattr(
        MA.QMessageBox, "question",
        staticmethod(lambda *a, **k: MA.QMessageBox.StandardButton.Yes),
    )
    window._autosave_check_on_startup()
    assert window._qt_edit_mode is True
    assert window._qt_edit_dirty is True
    assert window.editor.toPlainText() == "recovered body"
    # The consumed snapshot is removed so it isn't offered again.
    assert not (tmp_path / "recovery" / "untitled-crashed.json").exists()


# ── Notes pane visibility (only when the doc has notes, or on toggle) ─────────


# Offscreen tests never .show() the window, so a child dock's isVisible() is
# always False; isHidden() tracks the explicit hide state we actually set.


def test_notes_pane_hidden_at_launch(window):
    """The welcome document has no notes, so the pane must not steal space."""
    assert window._annot_dock.isHidden() is True


def test_notes_pane_auto_shows_for_a_doc_with_notes(window):
    from star.documents import Document

    # A document that carries a saved note.
    window._pending_doc = Document(path="", title="HasNotes", markdown="body",
                                   plain_text="body", format="markdown")
    window._on_doc_loaded()
    key = window._annot_key()
    window.settings.set("annotations", {key: [
        {"char_pos": 0, "anchor": "body", "note": "a note", "tags": [],
         "cite": "", "ts": "t"}
    ]})
    window._qt_auto_notes_visibility()
    assert window._annot_dock.isHidden() is False
    # Re-loading a note-free document hides it again.
    window._pending_doc = Document(path="", title="NoNotes", markdown="x",
                                   plain_text="x", format="markdown")
    window._on_doc_loaded()
    assert window._annot_dock.isHidden() is True


def test_notes_pane_manual_toggle_is_transient(window):
    # Toggle the (empty) pane on…
    window._qt_toggle_annotations()
    assert window._annot_dock.isHidden() is False
    # …but loading a note-free document re-derives visibility and hides it.
    from star.documents import Document

    window._pending_doc = Document(path="", title="Fresh", markdown="y",
                                   plain_text="y", format="markdown")
    window._on_doc_loaded()
    assert window._annot_dock.isHidden() is True


# ── Contents (ToC) pane visibility (only when the doc has headings) ───────────


def test_toc_pane_visibility_matches_heading_presence_at_launch(window):
    """At launch the Contents pane is shown iff the loaded document has
    headings (the welcome page has headings; a heading-free doc would not)."""
    assert window._toc_dock.isHidden() is (window._toc_list.count() == 0)


def test_toc_pane_auto_shows_for_a_doc_with_headings(window):
    from star.documents import Document

    window._pending_doc = Document(path="", title="Doc", markdown="# Heading\n\nbody",
                                   plain_text="Heading body", format="markdown")
    window._on_doc_loaded()
    assert window._toc_list.count() > 0
    assert window._toc_dock.isHidden() is False
    # A heading-free document hides the pane again.
    window._pending_doc = Document(path="", title="Flat", markdown="just prose here",
                                   plain_text="just prose here", format="markdown")
    window._on_doc_loaded()
    assert window._toc_list.count() == 0
    assert window._toc_dock.isHidden() is True


def test_toc_pane_manual_toggle_is_transient(window):
    from star.documents import Document

    # Start on a heading-free doc → hidden.
    window._pending_doc = Document(path="", title="Flat", markdown="no headings",
                                   plain_text="no headings", format="markdown")
    window._on_doc_loaded()
    assert window._toc_dock.isHidden() is True
    # Toggle it on…
    window._qt_toggle_toc()
    assert window._toc_dock.isHidden() is False
    # …but loading another heading-free doc re-derives and hides it.
    window._pending_doc = Document(path="", title="Flat2", markdown="still none",
                                   plain_text="still none", format="markdown")
    window._on_doc_loaded()
    assert window._toc_dock.isHidden() is True


def test_startup_recovery_declined_drops_the_snapshot(window, monkeypatch, tmp_path):
    monkeypatch.setattr(A, "_CFG_ROOT", tmp_path)
    snap = tmp_path / "recovery" / "untitled-x.json"
    A._write_snapshot(
        snap, {"path": "", "title": "D", "markdown": "x", "ts": "t"}
    )
    from star.gui import mixin_autosave as MA

    monkeypatch.setattr(
        MA.QMessageBox, "question",
        staticmethod(lambda *a, **k: MA.QMessageBox.StandardButton.No),
    )
    window._autosave_check_on_startup()
    assert not snap.exists()  # declined → removed, never offered again
