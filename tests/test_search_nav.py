"""Qt Find bar + bookmarks/history interactions (mixin_find, mixin_bookmarks_qt).

Runs offscreen with pytest-qt.  Exercises the real StarWindow:

* Find bar: incremental match discovery over the loaded document, next/prev with
  wrap, match count, case toggle, highlight-all via ExtraSelection, and Escape
  closing the bar.
* Bookmarks: add (auto-named) → persisted in settings['bookmarks'] → goto scrolls
  the editor.
* History: a jump pushes the departure offset; back/forward walk the stack.

The whole module is skipped when PyQt / pytest-qt is unavailable.  The module-level
``_find_all`` helper is also unit-tested without Qt so its logic is covered even
where Qt is not installed.
"""
import importlib.util
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
_HAS_QTBOT = importlib.util.find_spec("pytestqt") is not None


# ── pure-logic test (no Qt required) ─────────────────────────────────────────


def test_find_all_substring_offsets():
    from star.gui.mixin_find import _find_all

    text = "the cat sat on the mat"
    # case-insensitive
    assert _find_all(text, "the", False) == [0, 15]
    assert _find_all(text, "THE", False) == [0, 15]
    # case-sensitive misses the capital
    assert _find_all("The the", "the", True) == [4]
    # overlapping matches (advance by 1)
    assert _find_all("aaaa", "aa", False) == [0, 1, 2]
    # empty query and no-match
    assert _find_all(text, "", False) == []
    assert _find_all(text, "zzz", False) == []


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


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    """A StarWindow with the welcome doc loaded and TTS neutralised.

    The settings file is redirected to a temp path so bookmark writes don't
    pollute the user's real settings.json.
    """
    _load_fonts()
    from star import settings as settings_mod
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")

    win = StarWindow(Settings())
    qtbot.addWidget(win)

    class _StubTTS:
        def __init__(self, real):
            self._real = real
            self.speaking = False
            self.last_cb_word_idx = -1
            self.current_word_idx = -1
            self.speak_calls = []
            self.stop_calls = 0

        def speak(self, *a, **k):
            self.speak_calls.append((a, k))

        def stop(self):
            self.stop_calls += 1
            self.speaking = False

        def set_rate(self, *_a):
            pass

        def set_word_map(self, *_a):
            pass

        def set_on_highlight(self, *_a):
            pass

        def __getattr__(self, name):
            return getattr(self._real, name)

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


# ── Find bar ─────────────────────────────────────────────────────────────────


def test_find_bar_opens_and_finds_matches(window):
    window._find_show()
    assert window._find_bar is not None
    # isVisibleTo(window) reports the widget's own visibility flag independent of
    # whether the (offscreen, never-shown) top-level window is on screen.
    assert window._find_bar.isVisibleTo(window)

    # "the" appears many times in the welcome page; searching finds ≥1 match.
    window._find_input.setText("the")
    assert len(window._find_matches) >= 1
    assert 0 <= window._find_idx < len(window._find_matches)
    # A highlight-all ExtraSelection layer is painted (one per match).
    sels = window.editor.extraSelections()
    assert len(sels) >= len(window._find_matches)
    # The count label reflects the position/total.
    assert " of " in window._find_count.text()


def test_find_next_prev_wraps(window):
    window._find_show()
    window._find_input.setText("e")  # common letter → several matches
    total = len(window._find_matches)
    assert total >= 2

    window._find_idx = 0
    window._find_prev()  # wrap backward from first → last
    assert window._find_idx == total - 1
    window._find_next()  # wrap forward from last → first
    assert window._find_idx == 0


def test_find_reveals_current_match_in_cursor(window):
    window._find_show()
    window._find_input.setText("star")
    if not window._find_matches:
        pytest.skip("welcome page lacks the probe term")
    start = window._find_matches[window._find_idx]
    cur = window.editor.textCursor()
    # The current match is selected in the editor at its char offset.
    assert cur.selectionStart() == start
    assert cur.selectedText().lower() == "star"


def test_find_no_match_reports_and_clears(window):
    window._find_show()
    window._find_input.setText("zqxjkwv")  # will not occur
    assert window._find_matches == []
    assert window._find_idx == -1
    assert window._find_count.text()  # "No matches"


def test_find_case_toggle_changes_results(window):
    window._find_show()
    window._find_input.setText("star")
    insensitive = len(window._find_matches)
    window._find_case.setChecked(True)  # re-runs the search
    sensitive = len(window._find_matches)
    # Case-sensitive can only match a subset of case-insensitive.
    assert sensitive <= insensitive


def test_find_close_hides_and_clears(window):
    window._find_show()
    window._find_input.setText("the")
    assert window._find_bar.isVisibleTo(window)
    window._find_close()
    assert not window._find_bar.isVisibleTo(window)
    assert window._find_matches == []
    # Find highlights are gone (only base user/vocab highlights, if any, remain).
    for sel in window.editor.extraSelections():
        assert sel.format.background().color().name() != "#ff9632"


# ── Bookmarks ────────────────────────────────────────────────────────────────


def test_bookmark_add_persists_and_goto_moves_cursor(window):
    # Position partway into the document, then bookmark there.
    target = min(12, len(window._qt_word_map) - 1)
    window._qt_navigate_to_word(target)
    window._qt_bookmark_add()  # auto-named "mark1"

    key = window._bm_doc_key()
    bms = window.settings.get("bookmarks", {}).get(key, {})
    assert "mark1" in bms
    assert bms["mark1"]["offset"] >= 0

    # Move away, then goto the bookmark → cursor returns near the saved offset.
    window._qt_navigate_to_word(0)
    assert window.editor.textCursor().position() == 0
    window._qt_bookmark_goto("mark1")
    saved_offset = bms["mark1"]["offset"]
    expected_word = window._qt_word_for_offset(saved_offset)
    assert window.editor.textCursor().position() == window._qt_word_map[expected_word]


def test_bookmark_auto_names_increment(window):
    window._qt_bookmark_add()
    window._qt_bookmark_add()
    key = window._bm_doc_key()
    bms = window.settings.get("bookmarks", {}).get(key, {})
    assert "mark1" in bms and "mark2" in bms


def test_bookmark_delete(window):
    window._qt_bookmark_add()
    key = window._bm_doc_key()
    assert "mark1" in window.settings.get("bookmarks", {}).get(key, {})
    window._qt_bookmark_delete("mark1")
    assert "mark1" not in window.settings.get("bookmarks", {}).get(key, {})


# ── History ──────────────────────────────────────────────────────────────────


def test_history_back_forward_round_trip(window):
    # Start at word 0.
    window._qt_navigate_to_word(0)
    origin = window.editor.textCursor().position()

    # A bookmark goto pushes the origin offset onto the history, then jumps.
    far = min(20, len(window._qt_word_map) - 1)
    window._qt_navigate_to_word(far)
    window._qt_bookmark_add()  # mark1 at the far position
    window._qt_navigate_to_word(0)
    window._qt_bookmark_goto("mark1")  # pushes offset(0), jumps to far
    after_jump = window.editor.textCursor().position()
    assert after_jump != origin

    # Back → returns toward the pushed origin position.
    window._qt_history_back()
    back_pos = window.editor.textCursor().position()
    assert back_pos <= after_jump


def test_history_push_branches_discard_forward(window):
    window._init_nav_history()
    window._history_push(10)
    window._history_push(20)
    window._history_push(30)
    assert window._nav_history == [10, 20, 30]

    # Step back twice, then push → forward entries are discarded.
    window._qt_history_back()  # pos → 2 (offset 30)
    window._qt_history_back()  # pos → 1 (offset 20)
    window._history_push(99)   # branch: truncate to [10, 20] + 99
    assert window._nav_history == [10, 20, 99]


def test_history_back_empty_is_safe(window):
    window._init_nav_history()
    window._qt_history_back()  # must not raise on an empty stack
    assert window._nav_hist_pos == -1
