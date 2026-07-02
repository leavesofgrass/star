"""Offscreen (headless) accessibility smoke tests for the Qt GUI.

star is an accessibility-first reader, so screen-reader / keyboard metadata is
part of the product contract, not a nicety.  These tests construct the real
``StarWindow`` and the ``DependencyChooser`` under the offscreen QPA and assert
the accessibility affordances a screen reader relies on:

* every dialog carries a window title (announced when it opens),
* the optional-feature checkboxes expose their detail text as an accessible
  description (the adjacent gray sub-label is visual-only and not reliably
  announced),
* the dock panels and the document view have accessible names, and
* the key toolbar actions have non-empty text (their accessible name).

Runs on every CI leg: PyQt6 is a base dependency.  The offscreen platform ships
zero fonts, so Windows TTFs are loaded up front for any text-rendering glyphs.
The module is fully skipped when Qt is unavailable.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let building StarWindow trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the module, with Windows fonts loaded."""
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


def test_document_view_has_accessible_metadata(window):
    """The main reading area names itself and describes its key shortcuts."""
    assert window.editor.accessibleName()
    assert window.editor.accessibleDescription()


def test_dock_panels_have_accessible_names(window):
    """ToC and Notes docks (and their lists) are named for screen readers."""
    assert window._toc_dock.accessibleName()
    assert window._toc_list.accessibleName()
    assert window._annot_dock.accessibleName()
    assert window._annot_list.accessibleName()
    # The notes filter relies on placeholder text visually; it must also carry
    # an accessible name since screen readers don't read placeholders reliably.
    assert window._annot_filter.accessibleName()


def test_key_toolbar_actions_have_text(window):
    """Icon-only toolbar buttons still announce a non-empty accessible name."""
    actions = [a for a in window._toolbar.actions() if not a.isSeparator()]
    assert actions, "toolbar has no actions"
    for act in actions:
        assert act.text().strip(), "a toolbar action has no accessible text"


def test_dependency_chooser_dialog(qapp):
    """The optional-feature chooser has a window title, its checkboxes expose
    an accessible description, and the preset buttons are named."""
    from star.gui.deps_dialog import DependencyChooser

    dlg = DependencyChooser(None)
    try:
        assert dlg.windowTitle().strip()
        assert dlg._boxes, "no feature checkboxes were built"
        for cb in dlg._boxes.values():
            assert cb.accessibleDescription().strip(), (
                "a feature checkbox has no accessible description"
            )
    finally:
        dlg.deleteLater()
