"""End-to-end Qt GUI workflow tests over the full mixin chain.

Where ``test_gui_interactive.py`` isolates single interactions, this module
strings them into the multi-step scenarios a real reader performs, proving the
mixins cooperate:

  * **load → navigate → highlight → copy → export**: open the welcome doc, jump a
    heading, select a span, add a persisted user highlight, copy it to the Qt
    clipboard, then export the document to Markdown through a *mocked* file
    dialog — asserting the file lands on disk with the document's content.
  * **highlight persistence + clear** round-trips through ``settings``.
  * **edit → save round-trip** for a plain-text document rewrites the file and
    re-renders read-only.

File dialogs and message boxes are monkeypatched so nothing blocks; TTS is
stubbed so no engine runs.  Skipped without PyQt / pytest-qt.
"""
import importlib.util
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
_HAS_QTBOT = importlib.util.find_spec("pytestqt") is not None

pytestmark = pytest.mark.skipif(
    not (_HAS_QT and _HAS_QTBOT), reason="PyQt / pytest-qt not installed"
)


def _load_fonts():
    from PyQt6.QtGui import QFontDatabase

    for ttf in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ttf):
            QFontDatabase.addApplicationFont(ttf)


def _pump_until(qtbot, window, ready, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ready(window):
            return True
        qtbot.wait(50)
    return ready(window)


class _StubTTS:
    """Neutral TTS manager: records calls, drives no audio engine."""

    def __init__(self, real):
        self._real = real
        self.speaking = False
        self.last_cb_word_idx = -1
        self.current_word_idx = -1
        self.speak_calls = []

    def speak(self, *a, **k):
        self.speak_calls.append((a, k))

    def stop(self):
        self.speaking = False

    def set_rate(self, *_a):
        pass

    def set_word_map(self, *_a):
        pass

    def set_on_highlight(self, *_a):
        pass

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture
def window(qtbot):
    _load_fonts()
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    qtbot.addWidget(win)
    win.tts_manager = _StubTTS(win.tts_manager)
    _pump_until(
        qtbot,
        win,
        lambda w: w.doc is not None
        and getattr(w.doc, "word_map", None)
        and len(w._qt_word_map) > 0,
    )
    yield win
    win.close()


def _select_first_words(window, n_chars=12):
    """Select the first *n_chars* of real body text and return the string."""
    from PyQt6.QtGui import QTextCursor

    doc_obj = window.editor.document()
    # Find the first block with more than a few characters of content.
    block = doc_obj.firstBlock()
    while block.isValid() and len(block.text().strip()) < n_chars:
        block = block.next()
    assert block.isValid(), "no substantial text block found in the welcome doc"
    start = block.position()
    cur = QTextCursor(doc_obj)
    cur.setPosition(start)
    cur.setPosition(start + n_chars, QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cur)
    return cur.selectedText()


# ── full load → navigate → highlight → copy → export chain ───────────────────


def test_load_navigate_highlight_copy_export(window, qtbot, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QApplication

    # 1. LOAD — the welcome doc is already loaded by the fixture.
    assert window.doc is not None and window.doc.word_map

    # 2. NAVIGATE — jump to the next heading; the cursor should move.
    # (_qt_read_next_heading is the real surface: menu Ctrl+H / toolbar; the
    # silent _qt_skip_* pair was dead code and has been removed.)
    start_pos = window.editor.textCursor().position()
    window._qt_read_next_heading()
    # (welcome.md has headings, so this advances or reports movement)
    assert window.editor.textCursor().position() >= start_pos

    # 3. HIGHLIGHT — select a span and add a persisted user highlight.
    selected = _select_first_words(window, 12)
    assert selected.strip()
    window._qt_highlight("#ffff00")
    path_key = window.doc.path or "__no_path__"
    saved = window.settings._data.get("user_highlights", {}).get(path_key, [])
    assert saved, "the highlight must be persisted in settings"
    assert saved[-1]["color"] == "#ffff00"
    # It renders as an extra selection (non-destructive overlay).
    sels = window._get_user_highlight_selections()
    assert len(sels) >= 1

    # 4. COPY — re-select and copy to the Qt clipboard.
    _select_first_words(window, 12)
    window._qt_copy()
    clip = QApplication.clipboard().text()
    assert clip.strip(), "clipboard should hold the copied text"

    # 5. EXPORT — mock the save dialog to a temp path, then export Markdown.
    dest = tmp_path / "exported.md"
    monkeypatch.setattr(
        "star.gui.mixin_export.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(dest), "Markdown (*.md)"),
    )
    window._qt_export_markdown()
    assert dest.is_file(), "export must write the Markdown file"
    content = dest.read_text(encoding="utf-8")
    assert content == window.doc.markdown
    assert content.strip(), "exported Markdown should be non-empty"
    assert "Exported Markdown" in window.statusBar().currentMessage()


# ── highlight persistence + clear round-trip ─────────────────────────────────


def test_highlight_persist_then_clear(window):
    _select_first_words(window, 10)
    window._qt_highlight("#ff8800")
    path_key = window.doc.path or "__no_path__"
    store = window.settings._data.get("user_highlights", {})
    assert store.get(path_key), "highlight saved"

    window._qt_highlight_clear()
    assert store.get(path_key) == [], "clear empties this document's highlights"


def test_highlight_without_selection_is_a_no_op(window):
    from PyQt6.QtGui import QTextCursor

    # Collapse any selection.
    cur = QTextCursor(window.editor.document())
    cur.setPosition(0)
    window.editor.setTextCursor(cur)
    path_key = window.doc.path or "__no_path__"
    before = list(window.settings._data.get("user_highlights", {}).get(path_key, []))
    window._qt_highlight("#ffff00")
    after = list(window.settings._data.get("user_highlights", {}).get(path_key, []))
    assert after == before, "no selection → no highlight added"
    assert "Select text first" in window.statusBar().currentMessage()


# ── edit → save round-trip on a plain-text document ──────────────────────────


def test_edit_mode_save_round_trip(window, qtbot, tmp_path):
    """Enter edit mode, change the Markdown source, save it back to disk, and
    verify the file + in-memory document update while the user *stays in edit
    mode* (the live-edit loop) — then finishing (Ctrl+E) restores read mode."""
    # Open a real editable text file so _qt_save writes in place (no dialog).
    src = tmp_path / "note.md"
    src.write_text("# Title\n\nOriginal body text.\n", encoding="utf-8")
    window._open_path(str(src))
    _pump_until(
        qtbot,
        window,
        lambda w: w.doc is not None and (w.doc.path or "").endswith("note.md"),
    )

    window._qt_enter_edit_mode()
    assert window._qt_edit_mode is True
    assert not window.editor.isReadOnly()

    new_src = "# Title\n\nEdited body text now.\n"
    window.editor.setPlainText(new_src)
    window._qt_save()

    # File on disk and the in-memory document both reflect the edit.
    assert src.read_text(encoding="utf-8") == new_src
    assert window.doc.markdown == new_src
    # Ctrl+S keeps you editing: still in edit mode, still the raw source, clean.
    assert window._qt_edit_mode is True
    assert not window.editor.isReadOnly()
    assert window._qt_edit_dirty is False
    assert window.editor.toPlainText() == new_src   # raw Markdown, not rendered

    # A second edit + save writes in place again (no dialog) and stays editing.
    newer = "# Title\n\nEdited twice.\n"
    window.editor.setPlainText(newer)
    window._qt_save()
    assert src.read_text(encoding="utf-8") == newer
    assert window._qt_edit_mode is True

    # Finishing (Ctrl+E, nothing unsaved) restores read mode: read-only + rendered.
    window._qt_exit_edit_mode(save=False)
    assert window._qt_edit_mode is False
    assert window.editor.isReadOnly()
    assert "Edited twice." in window.editor.toPlainText()


# ── stray "<" in prose must not swallow document text ────────────────────────


def test_open_doc_with_bare_less_than_keeps_all_text(window, qtbot, tmp_path):
    """Opening a document whose prose contains a bare "<" keeps every word in
    the read view.

    Regression: Qt's rich-text parser treated "< 0.001)…" as a malformed tag
    and silently dropped everything from "p <" onward — the editor showed a
    hole that doc.plain_text (the TTS stream) never had, so speech read text
    the reader could not see."""
    line = (
        "Mean systolic pressure fell from 142.6 to 127.3 mmHg "
        "(95% CI, 124.1 to 130.5; p < 0.001)."
    )
    src = tmp_path / "stats.md"
    src.write_text(
        f"# Trial results\n\n{line}\n\nThe next paragraph survives too.\n",
        encoding="utf-8",
    )
    window._open_path(str(src))
    _pump_until(
        qtbot,
        window,
        lambda w: w.doc is not None and (w.doc.path or "").endswith("stats.md"),
    )

    shown = window.editor.document().toPlainText()
    assert "p < 0.001" in shown
    assert shown.count("The next paragraph survives too.") == 1
    # And the TTS plain text agrees with the view (no speak-what-you-can't-see).
    assert "p < 0.001" in (window.doc.plain_text or "")


# ── archive open (File ▸ Open Archive…) ──────────────────────────────────────


def test_open_archive_single_member_loads(window, qtbot, tmp_path, monkeypatch):
    """A one-member zip opens through _qt_open_archive.

    This path called a method that never existed (self._load_document) from
    ~0.1.12 until 0.1.22 — every archive open raised AttributeError.  Nothing
    in CI exercised it, so it shipped broken through ten releases."""
    import zipfile

    from PyQt6.QtWidgets import QFileDialog

    zip_path = tmp_path / "docs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("inner.md", "# Inside the archive\n\nHello from the zip.\n")

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(zip_path), "")),
    )
    window._qt_open_archive()
    assert _pump_until(
        qtbot,
        window,
        lambda w: w.doc is not None and "Inside the archive" in (w.doc.markdown or ""),
    ), "archive member did not load as the current document"
