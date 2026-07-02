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
