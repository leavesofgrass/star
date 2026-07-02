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
