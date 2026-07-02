"""Offscreen (headless) smoke tests for the Qt GUI.

The GUI is imported only inside ``star.gui.runner._run_qt_gui()`` and never
instantiated by the rest of the suite — a blind spot that let a stale import
crash launch through the whole 0.1.14 cycle (see tests/test_import_smoke.py).
These tests go one step further and actually *construct* ``StarWindow`` under
the offscreen QPA, exercising the toolbar, the hand-drawn vector icons, and the
welcome-as-document startup path.

Runs on every CI leg: PyQt6 is a base dependency.  The offscreen platform ships
zero fonts, so Windows TTFs are loaded up front for any text-rendering glyphs.
The module is fully skipped when Qt is unavailable.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a smoke run trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the module, with Windows fonts loaded.

    The offscreen QPA has no fonts of its own; loading a couple of Windows TTFs
    keeps any QPainter text glyphs (the ``font``/``help`` icons) from rendering
    blank.  Loading is best-effort — absent fonts (non-Windows CI) are fine.
    """
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


def test_starwindow_constructs_with_toolbar(window):
    """StarWindow builds offscreen and its toolbar has actions."""
    tb = window._toolbar
    assert tb is not None
    assert len(tb.actions()) > 0


def test_make_icon_every_glyph(qapp):
    """make_icon() returns a non-null QIcon with a non-empty pixmap for every
    known glyph key, plus the unknown-name fallback."""
    from PyQt6.QtCore import QSize

    from star.gui import icons

    size = QSize(icons._SIZE, icons._SIZE)
    for name in icons._GLYPHS:
        icon = icons.make_icon(name)
        assert not icon.isNull(), f"icon {name!r} is null"
        pm = icon.pixmap(size)
        assert not pm.isNull() and pm.width() > 0, f"icon {name!r} has empty pixmap"

    # Unknown names must still yield a usable fallback icon (the neutral dot).
    fallback = icons.make_icon("this_glyph_does_not_exist")
    assert not fallback.isNull()
    assert not fallback.pixmap(size).isNull()


def test_welcome_loads_as_document(qapp, window):
    """With no initial path, StarWindow loads welcome.md as a real Document via
    a background thread; pump the event loop until it lands."""
    import time

    for _ in range(50):
        if window.doc is not None and getattr(window.doc, "word_map", None):
            break
        qapp.processEvents()
        time.sleep(0.1)

    assert window.doc is not None, "welcome document never loaded"
    assert window.doc.word_map, "welcome document has an empty word_map"
    assert window._is_welcome(window.doc) is True

    readme = window._bundled_path("README.md")
    assert readme is not None and readme.is_file()


def test_dyslexia_font_reaches_the_document_even_for_css_themes(window):
    """The dyslexia font must override a CSS/palette theme's own font-family.

    Regression: the Obsidian (default) theme injects its CSS verbatim with a
    hard-coded ``font-family: Georgia`` — which used to win in the reading pane,
    so OpenDyslexic changed only the chrome and 'nothing happened' in the
    document.  The renderer now appends an override the cascade resolves last.
    """
    # Avoid any network: pretend the family is available.
    window._find_dyslexia_font = lambda: "OpenDyslexic"
    window.settings["qt_dyslexia_font"] = True

    # The default theme is CSS-based (has a `_css`), which is the failing case.
    assert window._effective_palette(window.settings.get("theme")).get("_css")

    html = window._md_to_html("# Heading\n\nHello world.")
    # An OpenDyslexic font-family override is present…
    assert "OpenDyslexic" in html
    # …and it comes *after* the theme's own font-family so it wins the cascade.
    assert html.rfind("OpenDyslexic") > html.find("font-family")
    # Code stays monospace.
    assert "monospace" in html


def test_dyslexia_font_toggles_off_and_reverts_chrome(window, qapp):
    """Toggling the dyslexia font off must restore the original app font.

    Regression: app.setFont(QFont()) (a default-constructed font, no resolve
    mask) failed to revert already-styled widgets (menus, ToC), so they stayed
    OpenDyslexic. The real default font is now captured and restored.
    """
    original = qapp.font().family()
    window._find_dyslexia_font = lambda: "OpenDyslexic"
    window._apply_dyslexia_font(True, fetch=False)
    assert qapp.font().family() == "OpenDyslexic"
    window._apply_dyslexia_font(False)
    assert qapp.font().family() == original


def test_footnote_anchor_click_jumps(window):
    """Clicking a footnote marker (or its backlink) scrolls to the anchor;
    an ordinary click is not consumed so it still places the caret."""
    from PyQt6.QtCore import QEvent, QPoint

    md = "Body text.[^1]\n\n[^1]: The footnote."
    html = window._md_to_html(md)
    assert 'name="fn-1"' in html and 'href="#fn-1"' in html
    window.editor.setHtml(html)

    called = {}
    window.editor.anchorAt = lambda _p: "#fn-1"
    window.editor.scrollToAnchor = lambda n: called.__setitem__("n", n)

    class _Evt:
        def type(self):
            return QEvent.Type.MouseButtonRelease

        def pos(self):
            return QPoint(1, 1)

    assert window._editor_anchor_click(_Evt()) is True
    assert called["n"] == "fn-1"

    window.editor.anchorAt = lambda _p: ""   # not over an anchor
    assert window._editor_anchor_click(_Evt()) is False


def test_rsvp_overlay_toggles_and_feeds(window):
    """RSVP mode creates + shows the floating one-word overlay and accepts word
    updates. Regression: mixin_aiddialogs referenced _RSVPOverlay without
    importing it, so toggling RSVP on raised NameError."""
    window.settings["qt_rsvp_mode"] = True   # a stale setting must not block turning it on
    window._qt_toggle_rsvp()
    ov = window._rsvp_overlay
    # isHidden() is ancestor-independent (the test window is never shown), so it
    # reflects the explicit show/hide the toggle performs.
    assert ov is not None and not ov.isHidden()
    ov.update_word("a", "b", "c")            # the playback feed path
    assert ov._word_lbl.text() == "b"
    window._qt_toggle_rsvp()
    assert ov.isHidden()
