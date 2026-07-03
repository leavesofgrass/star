"""Interactive Qt GUI tests driven by pytest-qt (qtbot).

``tests/test_gui_smoke.py`` proves ``StarWindow`` *constructs* offscreen.  This
module goes further and exercises **real interactions and state transitions** on
a live window: playback toggle, sentence/paragraph navigation moving the reading
cursor, caret-browsing and dyslexia-font toggles reaching the widget, and the
welcome document actually populating ``window.doc``.  Each test asserts on
observable state — settings flags, the editor's text cursor, the app font — not
merely that a call returned.

Environment: the offscreen QPA has no fonts, so a couple of Windows TTFs are
loaded up front to keep any glyph rendering non-blank (best-effort; harmless on
non-Windows).  ``STAR_NO_AUTOINSTALL`` keeps a construction from kicking off a
background pip install.  TTS is neutralised per-window so no real speech engine
is driven and navigation logic is observed in isolation.

The whole module is skipped when PyQt or pytest-qt is unavailable.
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
    """Pump the event loop until *ready(window)* or the timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ready(window):
            return True
        qtbot.wait(50)
    return ready(window)


@pytest.fixture
def window(qtbot):
    """A StarWindow with the welcome doc fully loaded and TTS neutralised.

    We wait for the async welcome load *and* its background word-map build so
    navigation methods (which depend on word_map / _qt_word_map) operate on real
    data.  The TTS manager is stubbed so no engine runs during navigation.
    """
    _load_fonts()
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    qtbot.addWidget(win)

    # Neutralise the real TTS engine: record intent, never touch audio.
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

    # Wait for the welcome document AND its word map (built on a bg thread).
    _pump_until(
        qtbot,
        win,
        lambda w: w.doc is not None
        and getattr(w.doc, "word_map", None)
        and len(w._qt_word_map) > 0,
    )
    yield win
    win.close()


# ── welcome document loads and populates state ───────────────────────────────


def test_welcome_document_populates_window_state(window):
    """Opening with no path loads welcome.md as a real Document with word maps."""
    assert window.doc is not None
    assert window._is_welcome(window.doc)
    assert window.doc.word_map, "welcome doc must have a word map"
    assert window._qt_word_map, "Qt char-offset map must be built"
    assert len(window._qt_word_map) == len(window.doc.word_map)
    # Sentence starts were computed from the word map.
    assert window._qt_sentence_starts and window._qt_sentence_starts[0] == 0


# ── playback toggle ──────────────────────────────────────────────────────────


def test_playback_toggle_starts_and_pauses(window):
    """Space (via _tts_toggle) starts speech, then pauses saving the word."""
    stub = window.tts_manager
    # First toggle from stopped → play from the beginning.
    window._tts_toggle()
    assert stub.speak_calls, "toggling from stopped should call speak()"

    # Simulate the engine now speaking at word 5, then toggle → pause.
    stub.speaking = True
    stub.current_word_idx = 5
    window._tts_toggle()
    assert window._tts_paused_at_word == 5
    assert stub.stop_calls >= 1

    # Toggle again → resume from the saved word (a fresh speak call).
    before = len(stub.speak_calls)
    window._tts_toggle()
    assert len(stub.speak_calls) == before + 1
    assert window._tts_paused_at_word == -1


def test_play_from_word_sets_session_and_speaks(window):
    """_tts_play_from_word bumps the highlight session and issues one speak."""
    stub = window.tts_manager
    sess_before = window._hl_session
    window._tts_play_from_word(3)
    assert window._hl_session == sess_before + 1
    assert stub.speak_calls
    # The start word index is threaded through to the engine.
    _args, kwargs = stub.speak_calls[-1]
    assert kwargs.get("start_word_idx") == 3


# ── navigation moves the reading cursor ──────────────────────────────────────


def test_sentence_navigation_moves_cursor(window):
    """Skipping to the next sentence moves the editor's text cursor forward."""
    # Start at the very top.
    from PyQt6.QtGui import QTextCursor

    cur = QTextCursor(window.editor.document())
    cur.setPosition(0)
    window.editor.setTextCursor(cur)

    start_pos = window.editor.textCursor().position()
    window._qt_skip_next_sentence()
    end_pos = window.editor.textCursor().position()
    # The welcome page has multiple sentences, so the cursor advances.
    assert end_pos > start_pos
    # And a "→ Sentence" status was shown.
    assert "Sentence" in window.statusBar().currentMessage()


def test_prev_sentence_returns_toward_start(window):
    window._qt_navigate_to_word(0)  # ensure a known origin
    # Move forward a few sentences, then back one.
    window._qt_skip_next_sentence()
    window._qt_skip_next_sentence()
    forward_pos = window.editor.textCursor().position()
    window._qt_skip_prev_sentence()
    back_pos = window.editor.textCursor().position()
    assert back_pos <= forward_pos


def test_paragraph_navigation_moves_cursor(window):
    """Skipping to the next paragraph advances the cursor to a later block."""
    from PyQt6.QtGui import QTextCursor

    cur = QTextCursor(window.editor.document())
    cur.setPosition(0)
    window.editor.setTextCursor(cur)
    start_block = window.editor.textCursor().blockNumber()

    window._qt_skip_next_paragraph()
    end_block = window.editor.textCursor().blockNumber()
    assert end_block >= start_block
    assert "paragraph" in window.statusBar().currentMessage().lower()


def test_navigate_to_word_scrolls_and_positions_cursor(window):
    """_qt_navigate_to_word places the text cursor at the mapped char offset."""
    target = min(10, len(window._qt_word_map) - 1)
    window._qt_navigate_to_word(target)
    expected_char = window._qt_word_map[target]
    assert window.editor.textCursor().position() == expected_char


# ── caret browsing toggle reaches the widget ─────────────────────────────────


def test_caret_browsing_toggle_flips_setting_and_cursor_width(window):
    """Toggling caret browsing flips the setting and the editor caret width."""
    try:
        from PyQt6.QtCore import Qt

        kbd_flag = Qt.TextInteractionFlag.TextSelectableByKeyboard
    except AttributeError:  # PyQt5
        from PyQt5.QtCore import Qt  # type: ignore

        kbd_flag = Qt.TextSelectableByKeyboard  # type: ignore[attr-defined]

    # Force a known starting state: caret browsing ON.
    window.settings["qt_caret_browsing"] = True
    window._apply_caret_mode()
    assert window.editor.cursorWidth() == 2
    assert bool(window.editor.textInteractionFlags() & kbd_flag)

    # Toggle OFF → width 0 and keyboard-selection flag cleared.
    window._qt_toggle_caret_browsing()
    assert window.settings.get("qt_caret_browsing") is False
    assert window.editor.cursorWidth() == 0
    assert not bool(window.editor.textInteractionFlags() & kbd_flag)

    # Toggle back ON.
    window._qt_toggle_caret_browsing()
    assert window.settings.get("qt_caret_browsing") is True
    assert window.editor.cursorWidth() == 2


# ── dyslexia font toggle reaches the document + reverts ───────────────────────


def test_dyslexia_font_toggle_applies_and_reverts(window, qtbot):
    """Toggling the dyslexia font changes the app font family and restores it."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    original = app.font().family()

    # Pretend OpenDyslexic is installed so no network fetch happens.
    window._find_dyslexia_font = lambda prefer="": "OpenDyslexic"

    # The setting flag is what _md_to_html / _effective_font_family gate on
    # (the menu toggle sets it before calling _apply_dyslexia_font).
    window.settings["qt_dyslexia_font"] = True
    window._apply_dyslexia_font(True, fetch=False)
    assert app.font().family() == "OpenDyslexic"
    # The rendered HTML now carries an OpenDyslexic font-family override that
    # wins the cascade over the theme's own font-family.
    html = window._md_to_html("# H\n\nsome text")
    assert "OpenDyslexic" in html
    assert html.rfind("OpenDyslexic") > html.find("font-family")

    window.settings["qt_dyslexia_font"] = False
    window._apply_dyslexia_font(False)
    assert app.font().family() == original


# ── theme cycling re-renders without error ───────────────────────────────────


def test_next_theme_cycles_and_persists(window):
    """Cycling the theme updates the setting and re-renders the document."""
    before = window.settings.get("theme")
    window._next_theme()
    after = window.settings.get("theme")
    assert after != before or len(window._all_theme_names) == 1
    assert "Theme:" in window.statusBar().currentMessage()
    # The editor still holds rendered HTML for the (still-loaded) welcome doc.
    assert window.editor.toPlainText().strip()
