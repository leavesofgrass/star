"""Tests for large-document pagination.

Two layers:

* Pure paging arithmetic in :mod:`star.pagination` — no Qt, always runs.
* GUI-level windowed rendering in ``StarWindow`` under the offscreen QPA —
  runs only when PyQt is installed; verifies the size gate keeps normal
  documents on the unchanged whole-document path, and that highlight / caret
  navigation / Define-Word / restore-position stay correct across a page
  boundary when pagination is engaged.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

from star.pagination import (  # noqa: E402
    DEFAULT_WORDS_PER_PAGE,
    Page,
    Paginator,
    paginate,
)

_HAS_QT = bool(
    importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5")
)


# ─────────────────────────────────────────────────────────────────────────
# Pure paging arithmetic (star/pagination.py)
# ─────────────────────────────────────────────────────────────────────────
def _block_starts(n_words: int, block_size: int) -> list:
    """Block boundaries every *block_size* words (a paragraph model)."""
    return list(range(0, n_words, block_size))


def test_paginate_tiles_document_without_gaps_or_overlaps():
    n = 10_000
    pages = paginate(n, _block_starts(n, 40), words_per_page=1200)
    assert pages[0].start == 0
    assert pages[-1].end == n
    # Contiguous: each page begins exactly where the previous ended.
    for a, b in zip(pages, pages[1:]):
        assert a.end == b.start
    # Every page (except perhaps the last) is at least the target size.
    for pg in pages[:-1]:
        assert pg.end - pg.start >= 1200


def test_paginate_boundaries_fall_on_block_starts():
    n = 5000
    block = 50
    starts = set(_block_starts(n, block))
    pages = paginate(n, sorted(starts), words_per_page=1000)
    for pg in pages:
        assert pg.start == 0 or pg.start in starts


def test_paginate_tiny_and_empty_documents():
    assert paginate(0, [0]) == [Page(0, 0)]
    assert paginate(1, [0]) == [Page(0, 1)]
    # A document smaller than one page is a single page.
    pages = paginate(10, [0, 5], words_per_page=1200)
    assert pages == [Page(0, 10)]


def test_paginate_all_words_reachable_exactly_once():
    n = 3333
    pages = paginate(n, _block_starts(n, 37), words_per_page=500)
    covered = []
    for pg in pages:
        covered.extend(range(pg.start, pg.end))
    assert covered == list(range(n))


def test_paginator_covers_and_recentres_across_pages():
    n = 12_000
    pages = paginate(n, _block_starts(n, 40), words_per_page=1000)
    pg = Paginator(pages, window_pages=1)
    # Window starts at the top of the document.
    assert pg.covers_word(0)
    assert pg.word_start == 0
    # A word far past the window is not covered until we recentre.
    far = n - 100
    assert not pg.covers_word(far)
    changed = pg.window_for_word(far)
    assert changed is True
    assert pg.covers_word(far)
    # Re-asking for a word already covered does not move the window.
    assert pg.window_for_word(far) is False


def test_paginator_page_of_word_is_monotonic_and_clamped():
    n = 6000
    pages = paginate(n, _block_starts(n, 30), words_per_page=800)
    pgn = Paginator(pages)
    assert pgn.page_of_word(-5) == 0
    assert pgn.page_of_word(0) == 0
    assert pgn.page_of_word(n + 999) == pgn.n_pages - 1
    # Monotonic non-decreasing across the whole index space.
    prev = 0
    for w in range(0, n, 137):
        cur = pgn.page_of_word(w)
        assert cur >= prev
        prev = cur


def test_paginator_whole_document_when_few_pages():
    n = 500
    pages = paginate(n, [0], words_per_page=DEFAULT_WORDS_PER_PAGE)
    pgn = Paginator(pages, window_pages=2)
    assert pgn.n_pages == 1
    assert pgn.is_whole_document() is True


# ─────────────────────────────────────────────────────────────────────────
# GUI-level windowed rendering (StarWindow) — offscreen, PyQt only
# ─────────────────────────────────────────────────────────────────────────
pytestmark_qt = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    for ttf in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ttf):
            QFontDatabase.addApplicationFont(ttf)
    return app


def _make_doc(nwords, path="/tmp/big.md"):
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
    """Let any in-flight async document load (e.g. the startup welcome page)
    settle so its background threads/queued signals can't race a later load."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if window.doc is not None and window._qt_word_map:
            break
        time.sleep(0.02)
    qapp.processEvents()


def _load_doc_sync(window, qapp, doc):
    """Drive the async doc-load path to completion for a prebuilt Document.

    The word-map build runs on a background thread and then, for a paginated
    document, hands the initial windowed render back to the GUI thread via a
    queued signal; wait for the document identity and the map to settle.
    """
    import time

    _drain_pending_load(window, qapp)  # settle the startup welcome load first
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


@pytestmark_qt
def test_normal_document_is_not_paginated(qapp):
    """A normal-sized document keeps the unchanged whole-document path:
    pagination never engages and no Paginator is created."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True  # even opted-in…
    win = StarWindow(settings)
    try:
        doc = _make_doc(3000, path="/tmp/small.md")  # well under the gate
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is None, "small doc must not paginate"
        # The whole document is rendered: the last word is mapped.
        assert len(win._qt_word_map) == len(doc.word_map)
        assert win._qt_word_map[-1] > 0
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_pagination_disabled_by_default_setting(qapp):
    """With the setting off (its default), even a huge document loads whole —
    behavior is byte-for-byte the legacy path."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    assert settings.get("qt_paginate_large_docs") is False  # default
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is None, "pagination is opt-in and off by default"
        assert len(win._qt_word_map) == len(doc.word_map)
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_large_document_paginates_when_enabled(qapp):
    """Opted-in + over the word gate → a Paginator is created and only a window
    of the document is rendered (the editor holds far fewer chars than whole)."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None, "large doc + opt-in should paginate"
        assert win._paginator.n_pages > 1
        # Only a window is rendered, so the editor's plain text is much shorter
        # than the full document text.
        rendered_chars = win.editor.document().characterCount()
        assert rendered_chars < len(doc.plain_text)
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_caret_navigation_across_page_boundary_is_correct(qapp):
    """Navigating (Define-Word / caret) to a word beyond the rendered window
    advances the window and lands the caret on the right word."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None
        target = 70_000  # far outside the initial window
        assert not win._paginator.covers_word(target)
        win._qt_navigate_to_word(target)
        qapp.processEvents()
        # After navigation the window covers the target and the caret sits on it.
        assert win._paginator.covers_word(target)
        off = win._qt_word_map[target]
        assert off >= 0
        # The word under the caret's mapped offset is the expected token.
        cur_pos = win.editor.textCursor().position()
        assert abs(cur_pos - off) <= 1
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_highlight_across_page_boundary_does_not_crash(qapp):
    """Applying a TTS word highlight for a word outside the window advances the
    window and paints without desync or exception."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None
        # Highlight a word far past the initial window (session must match).
        target = 60_000
        win._apply_word_highlight(target, win._hl_session)
        qapp.processEvents()
        assert win._paginator.covers_word(target)
        # The highlighted word's char offset is valid within the rendered doc.
        off = win._qt_word_map[target]
        assert 0 <= off < win.editor.document().characterCount()
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_find_disables_pagination_and_renders_whole_document(qapp):
    """Opening Find on a paginated document suspends paging and renders the whole
    document so search offsets/highlight-all span the entire text (the documented
    safe degradation)."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None
        win._find_show()
        qapp.processEvents()
        # Paging is suspended and the whole document is now rendered.
        assert win._paginator is None
        assert win.editor.document().characterCount() > len(doc.plain_text) * 0.5
        # A word near the end now has a real (non-sentinel) offset — full-doc find
        # can reach it.
        assert win._qt_word_map[85_000] >= 0
        win._find_close()
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_reading_ruler_tracks_caret_with_pagination_on(qapp):
    """The Area-3 reading ruler still follows the caret across a paginated
    window re-render (its follow_caret is invoked after each windowed render)."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    settings._data["qt_reading_ruler"] = True
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert win._paginator is not None
        assert win._reading_ruler is not None
        # Navigate across a boundary — the ruler must not raise and should end up
        # visible/tracking near the caret line.
        win._qt_navigate_to_word(70_000)
        qapp.processEvents()
        assert win._paginator.covers_word(70_000)
        # follow_caret() ran during the re-render; calling it again is safe.
        win._reading_ruler.follow_caret()
    finally:
        win.close()
        qapp.processEvents()


@pytestmark_qt
def test_word_map_length_matches_full_document_under_pagination(qapp):
    """The word→char map is always full-document length; out-of-window words
    carry the sentinel so index math never drifts."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_paginate_large_docs"] = True
    settings._data["qt_paginate_threshold_words"] = 20_000
    win = StarWindow(settings)
    try:
        doc = _make_doc(90_000)
        _load_doc_sync(win, qapp, doc)
        assert len(win._qt_word_map) == len(doc.word_map)
        # Words inside the initial window are mapped; words far outside are the
        # sentinel (-1) until the window advances to them.
        assert win._qt_word_map[0] >= 0
        assert win._qt_word_map[80_000] == -1
    finally:
        win.close()
        qapp.processEvents()
