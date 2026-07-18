"""Offscreen tests for the GUI document open/import flow (star.gui.mixin_document).

``_open_path`` is the single entry point every open goes through — the Open
dialog, Open URL, recents, drag-and-drop, and the CLI path all funnel into it —
yet until now only the welcome-page startup load exercised it.  Covered here:

* a real file load end-to-end: background ``load_document`` thread →
  ``_doc_loaded_signal`` → render + word-map build;
* a directory routes to the Library browser (``_qt_open_folder_as_library``)
  instead of claiming a document load;
* a load whose loader raises yields the error document (``format == "error"``)
  rather than a silent dead thread / frozen UI — the loaders themselves swallow
  plain missing-file OSErrors into inline "# Error" markdown (verified across
  .md/.pdf/.epub/.docx/.xlsx/.txt), so the GUI branch is the safety net for a
  loader that raises and must be driven with one;
* the load-generation freshness gate: a second open supersedes the first, so a
  slow earlier load can never clobber the newer document (the same guard
  test_authoring.py::test_stale_background_load_does_not_clobber_new_document
  replays for New Document).

Follows tests/test_gui_smoke.py: offscreen QPA set at import time, a
module-scoped QApplication, a per-test StarWindow closed on teardown (the
conftest autouse drain handles deletion), and bounded event-pump loops — no
bare sleeps, nothing external.
"""
import importlib.util
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test run trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def _pump_until(qapp, cond, tries=50):
    """Pump the event loop until *cond()* is true (bounded — max ~5s).

    Same shape as test_gui_smoke.py::test_welcome_loads_as_document: the
    document load and word-map build run on background threads and land via
    queued signals, so the loop processes events between checks.
    """
    for _ in range(tries):
        if cond():
            return True
        qapp.processEvents()
        time.sleep(0.1)
    return cond()


def test_open_md_file_loads_document(qapp, window, tmp_path):
    """A real .md file opened via _open_path becomes the current document:
    loaded in the background, rendered into the editor, word map built."""
    md_file = tmp_path / "note.md"
    md_file.write_text("# Alpha\n\nhello import flow\n", encoding="utf-8")

    window._open_path(str(md_file))
    assert _pump_until(
        qapp,
        lambda: (
            window.doc is not None
            and window.doc.path == str(md_file)
            and bool(getattr(window.doc, "word_map", None))
        ),
    ), "opened document never loaded"

    assert window.doc.format == "markdown"
    assert "hello import flow" in window.doc.markdown
    assert window._is_welcome(window.doc) is False
    # The document actually rendered into the reading view.
    assert "hello import flow" in window.editor.toPlainText()


def test_open_directory_routes_to_library_not_load(window, tmp_path, monkeypatch):
    """A directory is a library source, not a document: _open_path hands it to
    _qt_open_folder_as_library and never claims a load generation."""
    called = {}
    monkeypatch.setattr(
        window,
        "_qt_open_folder_as_library",
        lambda p: called.__setitem__("path", p),
    )
    gen_before = window._doc_load_gen
    window._open_path(str(tmp_path))
    assert called["path"] == str(tmp_path)
    # No background load was started for the folder (the generation counter is
    # bumped by every real document load, before the worker spawns).
    assert window._doc_load_gen == gen_before


def test_failed_load_becomes_error_document(qapp, window, tmp_path, monkeypatch):
    """A load whose loader raises must surface as the error document — the
    background worker never dies silently and leaves the UI frozen.

    ``load_document`` itself never raises for a merely-missing file (every
    loader folds the OSError into inline "# Error" markdown), so the raise is
    simulated at the star boundary the GUI worker actually calls — the
    documented remaining causes are a locked file or a loader bug."""
    import star.gui.mixin_document as mixin_document

    missing = tmp_path / "missing.md"
    assert not missing.exists()

    def _boom(path, settings):
        raise OSError(f"simulated unreadable file: {path}")

    monkeypatch.setattr(mixin_document, "load_document", _boom)
    window._open_path(str(missing))
    assert _pump_until(
        qapp,
        lambda: window.doc is not None and window.doc.format == "error",
    ), "error document never arrived"

    assert window.doc.path == str(missing)
    assert window.doc.title.startswith("Error")
    assert "missing.md" in window.doc.title
    assert "Could not open" in window.doc.markdown
    # A failed load must not read as a success ("Opened: …").
    assert window.statusBar().currentMessage().startswith("Could not open")


def test_second_open_supersedes_first(qapp, window, tmp_path):
    """Two back-to-back opens: the second one wins, whatever order the two
    background loads finish in — and a replayed stale delivery of the first
    load's generation is dropped by the freshness gate (the established
    pattern from test_authoring.py)."""
    from star.documents import Document

    first = tmp_path / "first.md"
    first.write_text("# First\n\nalpha content\n", encoding="utf-8")
    second = tmp_path / "second.md"
    second.write_text("# Second\n\nbeta content\n", encoding="utf-8")

    window._open_path(str(first))
    stale_gen = window._doc_load_gen   # the generation the first load holds
    window._open_path(str(second))    # bumps the counter — supersedes first
    assert window._doc_load_gen > stale_gen

    assert _pump_until(
        qapp,
        lambda: window.doc is not None and window.doc.path == str(second),
    ), "second document never loaded"
    assert "beta content" in window.editor.toPlainText()

    # Replay the first load finishing late — _on_doc_loaded_async is the slot
    # the pyqtSignal is wired to, where the freshness gate lives.  Deterministic
    # (no thread-timing dependence), like the test_authoring.py replay.
    window._pending_doc = Document(
        path=str(first), title="First", markdown="# First\n\nalpha content\n",
        plain_text="alpha content", format="markdown",
    )
    window._pending_doc_gen = stale_gen
    window._on_doc_loaded_async()

    # Dropped as superseded — the second document survives untouched.
    assert window.doc.path == str(second)
    assert "beta content" in window.editor.toPlainText()

    # And after the loop quiesces (any real late worker included), still second.
    for _ in range(5):
        qapp.processEvents()
        time.sleep(0.05)
    assert window.doc.path == str(second)
