"""Offscreen tests for the first-run optional-feature chooser.

``star.gui.deps_dialog.DependencyChooser`` builds one checkbox per feature in
``star.autodeps.FEATURE_INFO`` and drives them from the ``thin`` / ``all``
presets, disabling (and forcing checked) any feature already installed.  These
tests pin that contract without touching the network or invoking any install.

Runs on every CI leg (PyQt6 is a base dependency); skipped when Qt is absent.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

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


@pytest.fixture
def chooser(qapp):
    from star.gui.deps_dialog import DependencyChooser
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    dlg = DependencyChooser(win)
    yield dlg, win
    dlg.close()
    win.close()


def _checked(dlg):
    return {k for k, cb in dlg._boxes.items() if cb.isChecked()}


def _enabled(dlg):
    return {k for k, cb in dlg._boxes.items() if cb.isEnabled()}


def test_one_checkbox_per_feature(chooser):
    from star import autodeps

    dlg, _win = chooser
    assert set(dlg._boxes) == set(autodeps.FEATURE_INFO)
    assert len(dlg._boxes) == len(autodeps.FEATURE_INFO)


def test_default_checked_is_all_preset(chooser):
    """The dialog defaults to the 'all' preset (now literally every feature)."""
    from star import autodeps

    dlg, _win = chooser
    assert _checked(dlg) == set(autodeps.preset("all"))


def test_apply_thin_preset(chooser):
    from star import autodeps

    dlg, _win = chooser
    dlg._apply_preset("thin")
    # A preset only touches enabled boxes; already-installed features stay
    # checked regardless, so intersect the preset with the enabled set.
    expected = set(autodeps.preset("thin")) & _enabled(dlg)
    assert _checked(dlg) & _enabled(dlg) == expected


def test_installed_features_checked_and_disabled(chooser):
    from star import autodeps

    dlg, _win = chooser
    for key, cb in dlg._boxes.items():
        if autodeps.feature_installed(key):
            assert cb.isChecked(), f"installed feature {key!r} not checked"
            assert not cb.isEnabled(), f"installed feature {key!r} not disabled"


def test_system_tools_live_inside_the_scroll_area(chooser):
    """The native-tools status list must be inside the scrollable region (not
    below it), or it pushes the Install/Not-now buttons off a 1080p screen.
    Guard: the scroll area's inner widget contains the system-tool rows."""
    dlg, _win = chooser
    assert dlg._sys_rows, "no system-tool rows built"
    # Every system-tool row's ancestry must pass through a QScrollArea.
    from PyQt6.QtWidgets import QScrollArea

    for key, row in dlg._sys_rows.items():
        w = row.parent()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parent()
        assert w is not None, f"system-tool row {key!r} is not inside a scroll area"


def test_dialog_is_capped_to_the_screen_height(chooser):
    """The dialog never opens taller than the available screen (1080p-safe)."""
    from PyQt6.QtWidgets import QApplication

    dlg, _win = chooser
    scr = QApplication.primaryScreen()
    if scr is not None:
        assert dlg.height() <= scr.availableGeometry().height()
        assert dlg.maximumHeight() <= scr.availableGeometry().height()
