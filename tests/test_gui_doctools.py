"""Offscreen tests for the Tools surface (star/gui/mixin_doctools.py).

Summarize, Translate, and Define Word share one shape: the menu action
captures its input on the GUI thread, hands the slow part (LexRank, the
translation network call, WordNet's first corpus load) to a
``StarWindow._spawn_worker`` thread, and the result returns through a queued
pyqtSignal to a main-thread handler that shows a dialog or an error surface.
These tests drive that full worker→signal→handler round trip — invoke the
action, pump the event loop until the queued result lands, assert on the
surface — with every backend monkeypatched (no network, no sumy / WordNet /
translation deps), so they are deterministic on every CI leg.  The result
*handlers* called synchronously are already covered in
tests/test_translate_dictate.py; the background wiring is what this pins.
"""
import importlib.util
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    from star.documents import Document
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    # Supersede the constructor's async welcome.md load NOW (the same
    # generation bump closeEvent uses): these tests pump the event loop, and
    # a welcome doc landing mid-pump would replace the fixture document.
    win._doc_load_gen += 1
    win.doc = Document(
        path="/tmp/tools.md", title="Tools", markdown="# Tools\n\nalpha beta gamma",
        plain_text="alpha beta gamma", format="markdown",
    )
    yield win
    win.close()


def _pump_until(qapp, cond, seconds=5.0):
    """Pump the event loop (bounded) until cond() — how a queued signal
    emitted from a worker thread gets delivered to its main-thread slot."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if cond():
            return True
        qapp.processEvents()
        time.sleep(0.02)
    return cond()


def _capture_dialogs(monkeypatch):
    """Make QDialog.exec non-blocking, recording each dialog instead of
    showing it (offscreen has nobody to dismiss a real modal)."""
    from PyQt6.QtWidgets import QDialog

    opened = []
    monkeypatch.setattr(
        QDialog, "exec", lambda self: opened.append(self) or 0, raising=False
    )
    return opened


# ── Summarize ────────────────────────────────────────────────────────────────


def test_summarize_delivers_result_through_the_signal(window, qapp, monkeypatch):
    """Happy path: the worker's summary crosses the thread boundary and lands
    in the result dialog's text view, with the status bar reporting ready."""
    import star.gui.mixin_doctools as mod
    from PyQt6.QtWidgets import QTextEdit

    calls = {}

    def _fake_summarize(text, n):
        calls.update(text=text, n=n)
        return "THE-SUMMARY"

    monkeypatch.setattr(mod, "summarize_document", _fake_summarize)
    monkeypatch.setattr(window, "_qt_require_optional_feature", lambda *a: True)
    opened = _capture_dialogs(monkeypatch)

    window._qt_summarize()
    assert _pump_until(qapp, lambda: opened), "summary result never arrived"

    # The worker was fed the open document's text, not something stale.
    assert calls["text"] == "alpha beta gamma"
    dlg = opened[0]
    assert "Summary" in dlg.windowTitle()
    view = dlg.findChild(QTextEdit)
    assert view is not None and view.toPlainText() == "THE-SUMMARY"
    assert window.statusBar().currentMessage() == "Summary ready"


def test_summarize_empty_document_never_spawns_a_worker(window, monkeypatch):
    """An empty document short-circuits on the GUI thread — no thread, no
    signal, just the status-bar explanation."""
    from star.documents import Document

    monkeypatch.setattr(window, "_qt_require_optional_feature", lambda *a: True)
    spawned = []
    monkeypatch.setattr(window, "_spawn_worker", lambda *a, **k: spawned.append(a))

    window.doc = Document(path="/tmp/empty.md", title="Empty", markdown="",
                          plain_text="   ", format="markdown")
    window._qt_summarize()
    assert spawned == []
    assert window.statusBar().currentMessage() == "Nothing to summarize"


# ── Translate ────────────────────────────────────────────────────────────────


def test_translate_backend_error_surfaces_without_replacing_the_doc(
    window, qapp, monkeypatch
):
    """A raising backend must reach the user as an error via the signal — and
    the failed translation must not replace the live document."""
    import star.gui.mixin_doctools as mod

    def _boom(text, target_lang="en", progress=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(mod, "translate_text", _boom)
    seen = {}
    monkeypatch.setattr(window, "_status_error", lambda m: seen.setdefault("err", m))
    doc_before = window.doc

    window._qt_do_translate("fr", "French")
    assert _pump_until(qapp, lambda: "err" in seen), "translate error never arrived"

    assert "Translation failed" in seen["err"] and "network down" in seen["err"]
    assert window.doc is doc_before  # the original document survives


# ── Define Word ──────────────────────────────────────────────────────────────


def _patch_dictionary(monkeypatch, result):
    """Point the mixin's dictionary bindings at fixed fakes (no WordNet)."""
    import star.gui.mixin_doctools as mod

    monkeypatch.setattr(mod, "_dict_availability", lambda settings: (True, ""))
    monkeypatch.setattr(mod, "_dict_define", lambda word, settings: result)
    monkeypatch.setattr(
        mod, "_dict_markdown",
        lambda res: f"# {res['word']}\n\nA fortunate discovery.",
    )


def test_define_word_shows_the_selected_words_definition(window, qapp, monkeypatch):
    """Happy path: the selected word goes to the worker, the definition comes
    back through the signal and renders in the dialog's browser."""
    from PyQt6.QtWidgets import QTextBrowser

    from star.gui._qtcompat import _KEEP_ANCHOR

    _patch_dictionary(monkeypatch, {"word": "serendipity"})
    opened = _capture_dialogs(monkeypatch)

    window.editor.setPlainText("serendipity is luck")
    cur = window.editor.textCursor()
    cur.setPosition(0)
    cur.setPosition(len("serendipity"), _KEEP_ANCHOR)
    window.editor.setTextCursor(cur)

    window._qt_define_word()
    assert _pump_until(qapp, lambda: opened), "definition never arrived"

    dlg = opened[0]
    assert "serendipity" in dlg.windowTitle()
    view = dlg.findChild(QTextBrowser)
    assert view is not None and "fortunate discovery" in view.toPlainText()
    assert view.accessibleName() == "Definition of serendipity"
    assert window.statusBar().currentMessage() == "Definition ready"


def test_define_word_not_found_reports_instead_of_a_dialog(window, qapp, monkeypatch):
    """A None lookup result (word not in the dictionary) surfaces as the
    friendly not-found note, never a definition dialog."""
    from PyQt6.QtWidgets import QMessageBox

    _patch_dictionary(monkeypatch, None)
    opened = _capture_dialogs(monkeypatch)
    infos = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: infos.append(a)),
    )

    window.editor.setPlainText("xyzzy")  # caret at 0 → word under cursor
    window._qt_define_word()
    assert _pump_until(qapp, lambda: infos), "not-found result never arrived"

    assert "xyzzy" in infos[0][2]  # the message names the word
    assert opened == []            # no definition dialog was built
    assert window.statusBar().currentMessage() == "No definition found"
