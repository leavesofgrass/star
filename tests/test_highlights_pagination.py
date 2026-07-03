"""Regression tests for the pagination × per-char-highlight interaction.

Three adversarially-confirmed bugs are pinned here (all offscreen, PyQt only):

* BUG 1 — a document that has stored user highlights (or the vocab overlay on)
  must NOT paginate, because highlights/vocab store & paint *absolute* rendered
  char offsets that a windowed render would misplace; and creating a highlight
  while paginated must suspend pagination and store an *absolute* offset that
  maps to the intended text (never a window-relative one).
* BUG 2 — turning the vocab overlay on while a document is paginated must
  suspend pagination and render the whole document so the overlay scans/paints
  the full text.
* BUG 3 — a corrupt (non-dict) synced progress value must never crash the
  position-restore consumer.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(
    importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5")
)
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    for ttf in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ttf):
            QFontDatabase.addApplicationFont(ttf)
    return app


def _make_doc(nwords, path="/tmp/big_hl.md"):
    """A synthetic Document whose markdown is many short paragraphs."""
    from star.documents import Document, _build_word_map

    words = [f"w{i:06d}" for i in range(nwords)]
    paras = []
    for i in range(0, nwords, 40):
        paras.append(" ".join(words[i:i + 40]))
    md = "\n\n".join(paras)
    plain = " ".join(words)
    doc = Document(
        path=path, title="Big", markdown=md, plain_text=plain, format="markdown"
    )
    doc.word_map = _build_word_map(plain, md.splitlines())
    return doc


def _drain_pending_load(window, qapp, timeout=4.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if window.doc is not None and window._qt_word_map:
            break
        time.sleep(0.02)
    qapp.processEvents()


def _load_doc_sync(window, qapp, doc):
    import time

    _drain_pending_load(window, qapp)
    window._qt_word_map = []
    window._pending_doc = doc
    window._on_doc_loaded()
    deadline = time.time() + 6.0
    while time.time() < deadline:
        qapp.processEvents()
        if (
            window.doc is doc
            and window._qt_word_map
            and len(window._qt_word_map) == len(doc.word_map)
        ):
            break
        time.sleep(0.02)
    qapp.processEvents()


# ─────────────────────────────────────────────────────────────────────────
# BUG 1 — highlights force whole-document render
# ─────────────────────────────────────────────────────────────────────────
def test_document_with_stored_highlights_is_not_paginated(qapp):
    """A >threshold doc with the paginate setting on but a stored user highlight
    must render whole (no Paginator), so the highlight's absolute offset is
    valid."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    path = "/tmp/has_highlight.md"
    # Pre-seed a stored highlight for this document's path.
    settings._data["user_highlights"] = {path: [{"start": 5, "end": 12, "color": "#ffff00"}]}
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000, path=path)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is None, "a doc with stored highlights must not paginate"
        # Whole document is rendered → the last word has a real char offset.
        assert win._qt_word_map[-1] > 0
    finally:
        win.close()
        qapp.processEvents()


def test_creating_highlight_while_paginated_disables_pagination_and_stores_absolute(qapp):
    """Creating a highlight while paginated must suspend pagination (render whole)
    and store an *absolute* offset that maps to the selected word — never a
    window-relative offset (BUG 1's corruption case)."""
    from PyQt6.QtGui import QTextCursor

    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    settings._data["user_highlights"] = {}  # start with none so it paginates
    win = StarWindow(settings)
    try:
        path = "/tmp/mk_highlight.md"
        doc = _make_doc(90_000, path=path)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None, "should paginate before any highlight exists"

        # Navigate to a word deep in the document so the rendered window is NOT
        # the leading one — this is exactly where window-relative offsets diverge
        # from absolute offsets and the old code corrupted the stored highlight.
        target_word = 50_000
        win._qt_navigate_to_word(target_word)
        qapp.processEvents()
        assert win._paginator.covers_word(target_word)

        # Select that word in the (windowed) editor and highlight it.
        win_off = win._qt_word_map[target_word]
        assert win_off >= 0
        expected = doc.word_map[target_word].word
        cur = QTextCursor(win.editor.document())
        cur.setPosition(win_off)
        cur.setPosition(win_off + len(expected), QTextCursor.MoveMode.KeepAnchor)
        win.editor.setTextCursor(cur)

        win._qt_highlight("#ffff00")
        qapp.processEvents()

        # Pagination is now off (whole document rendered).
        assert win._paginator is None, "creating a highlight must suspend pagination"

        # The stored offset is absolute: reading the whole-document render at the
        # stored [start,end) yields the word that was selected.
        stored = settings._data["user_highlights"][path]
        assert len(stored) == 1
        hl = stored[0]
        full_text = win.editor.document().toPlainText()
        got = full_text[hl["start"]:hl["end"]]
        assert expected in got, (
            f"stored highlight must map to the selected word: "
            f"expected {expected!r} inside {got!r}"
        )
    finally:
        win.close()
        qapp.processEvents()


# ─────────────────────────────────────────────────────────────────────────
# BUG 2 — enabling the vocab overlay while paginated renders whole
# ─────────────────────────────────────────────────────────────────────────
def test_enabling_vocab_overlay_while_paginated_renders_whole(qapp):
    """Turning the difficult-word overlay ON while a doc is paginated must
    suspend pagination (paginator becomes None) so the overlay scans/paints the
    whole text."""
    pytest.importorskip("wordfreq")  # the overlay only computes when wordfreq is present
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    settings._data["qt_vocab_highlight"] = False  # off at load so it paginates
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000, path="/tmp/vocab_toggle.md")
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None, "should paginate before the overlay is on"

        # Simulate the user toggling the overlay on, then refreshing.
        settings._data["qt_vocab_highlight"] = True
        win._qt_refresh_vocab_highlight()
        qapp.processEvents()

        assert win._paginator is None, (
            "enabling the vocab overlay must suspend pagination and render whole"
        )
    finally:
        win.close()
        qapp.processEvents()


# ─────────────────────────────────────────────────────────────────────────
# BUG 3 — a corrupt (list-valued) sidecar progress must not crash resume
# ─────────────────────────────────────────────────────────────────────────
def test_list_valued_sidecar_progress_does_not_crash_restore(qapp, monkeypatch):
    """A corrupt synced sidecar value (a list where a progress dict belongs) must
    not crash the position-restore consumer (`side.get(...)` would raise)."""
    from star.gui import mixin_navigation
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["tts_auto_resume"] = True
    win = StarWindow(settings)
    try:
        doc = _make_doc(3000, path="/tmp/resume_corrupt.md")
        _load_doc_sync(win, qapp, doc)
        # Make the synced-sidecar lookup hand back a corrupt (non-dict) value.
        monkeypatch.setattr(
            mixin_navigation._position, "progress_for", lambda *a, **k: ["garbage"]
        )
        # Must not raise AttributeError; falls back to the locally-saved position.
        win._qt_restore_reading_position()
        qapp.processEvents()
    finally:
        win.close()
        qapp.processEvents()
