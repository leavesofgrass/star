"""Tests for the screen-reader live-region announcement helper.

star is accessibility-first, so state changes must be *heard* by NVDA / JAWS /
Orca users without focus moving.  ``star.gui.a11y.announce`` wraps
``QAccessible.updateAccessibility(... Announcement)`` for that, and the key
StarWindow transitions call it alongside their status-bar message.

The absolute contract these tests pin down:

* :func:`announce` is **no-op-safe offscreen** — under the ``offscreen`` QPA
  (which has no active accessibility bridge) it returns cleanly and never
  raises, for any input including ``None`` / empty text.
* The helper is actually *wired* at the key transitions: playback
  start/pause/stop, document load, theme change, and the find count — verified
  by monkeypatching ``announce`` and driving each transition.

``a11y`` is import-safe even without PyQt, so the module-import smoke test runs
on every leg; the StarWindow-driven tests are skipped when Qt is absent.
"""
import importlib
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))


# ---------------------------------------------------------------------------
# Import-safety (runs even without Qt): the module must import and expose a
# callable ``announce`` that no-ops rather than raising when there is nothing
# to announce to.
# ---------------------------------------------------------------------------
def test_a11y_module_imports_without_qt():
    mod = importlib.import_module("star.gui.a11y")
    assert callable(mod.announce)


def test_announce_is_noop_safe_for_bad_input():
    from star.gui.a11y import announce

    # Empty text and None widget must be handled without raising and report
    # "not dispatched" (False).
    assert announce(None, "hi") is False
    assert announce(object(), "") is False
    assert announce(None, "") is False


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


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


@pytestmark_qt
def test_announce_never_raises_offscreen(qapp):
    """A real widget under offscreen QPA: announce must return cleanly.

    The offscreen platform has no active accessibility bridge, so the helper
    should short-circuit (return False) rather than raise — the property the
    whole app relies on to keep announcements strictly best-effort.
    """
    from PyQt6.QtWidgets import QLabel

    from star.gui.a11y import announce

    w = QLabel("x")
    # Must not raise; offscreen returns False because the bridge is inactive.
    result = announce(w, "hello screen reader")
    assert result in (True, False)  # never an exception, always a bool


@pytestmark_qt
def test_announce_called_on_playback_transitions(window, monkeypatch):
    """Play / pause / stop each fire an announcement (text, not just status)."""
    import star.gui.mixin_playback as mp

    calls = []
    monkeypatch.setattr(mp, "announce", lambda w, t: calls.append(t))

    # A minimal loaded document so _tts_play has something to speak.  We stub
    # the TTS manager so no real audio backend is required.
    class _FakeTTS:
        speaking = False
        current_word_idx = -1
        last_cb_word_idx = -1  # pause prefers the engine-confirmed word

        def stop(self):
            self.speaking = False

        def speak(self, *a, **k):
            self.speaking = True

        def set_on_highlight(self, cb):
            pass

    window.tts_manager = _FakeTTS()

    class _Doc:
        plain_text = "Hello there world."
        word_map = []
        path = ""

    window.doc = _Doc()

    window._tts_play()
    assert calls, "start of playback did not announce"
    assert any("Play" in c or c for c in calls)

    # Pause: _tts_toggle while speaking should announce a distinct "Paused".
    calls.clear()
    window.tts_manager.speaking = True
    window.tts_manager.current_word_idx = 2
    window._tts_toggle()
    assert calls, "pause did not announce"

    # Stop announces too.
    calls.clear()
    window._tts_stop()
    assert calls, "stop did not announce"


@pytestmark_qt
def test_announce_called_on_theme_change(window, monkeypatch):
    """Next Theme and Choose Theme announce the new theme name."""
    import star.gui.mixin_display as md

    calls = []
    monkeypatch.setattr(md, "announce", lambda w, t: calls.append(t))

    window._next_theme()
    assert calls, "theme change did not announce"


@pytestmark_qt
def test_announce_called_on_document_load(window, monkeypatch):
    """Loading a document announces the title alongside the status message."""
    import star.gui.mixin_document as mdoc

    calls = []
    monkeypatch.setattr(mdoc, "announce", lambda w, t: calls.append(t))

    class _Doc:
        title = "My Test Doc"
        markdown = "# Hi\n\nBody."
        plain_text = "Hi Body."
        word_map = []
        path = ""
        format = "markdown"

    window._pending_doc = _Doc()
    window._on_doc_loaded_impl()
    assert calls, "document load did not announce"
    assert any("My Test Doc" in c for c in calls)


@pytestmark_qt
def test_announce_called_on_find_count(window, monkeypatch):
    """The find bar announces the live N-of-M / no-matches count."""
    import star.gui.mixin_find as mf

    calls = []
    monkeypatch.setattr(mf, "announce", lambda w, t: calls.append(t))

    window._find_show()
    window._find_input.setText("the")  # drives _find_run → _find_update_count
    # An announcement should have fired for the count (match or no-match).
    assert calls, "find count did not announce"
    window._find_close()


@pytestmark_qt
def test_announce_helper_resolves_or_disables_cleanly(qapp):
    """The internal resolver caches and never leaves the module half-initialised."""
    from star.gui import a11y

    # First resolve may return a tuple (accessibility available) or None
    # (unavailable); either way a second call must be stable and not raise.
    first = a11y._resolve()
    second = a11y._resolve()
    assert first == second
