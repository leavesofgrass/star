"""Accessibility guard for the Preferences dialog (0.1.27 audit).

Every interactive control a screen reader can focus must announce *which*
setting it is.  Checkboxes and buttons carry their own visible text; combo
boxes, spin boxes, and text fields show none, so they get an explicit
accessible name derived from their form-row label (see
``PreferencesDialog._ensure_accessible_names``).  This test walks the whole
dialog and fails if any control would be announced as a bare, unlabelled
widget — the regression guard for that audit.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture
def dlg(qapp):
    from star.gui.main_window import StarWindow
    from star.gui.preferences import PreferencesDialog
    from star.settings import Settings

    win = StarWindow(Settings())
    d = PreferencesDialog(win)
    yield d
    d.close()
    d.deleteLater()
    win.close()


def _widgets():
    try:  # PyQt6
        from PyQt6.QtWidgets import (
            QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit,
        )
    except ImportError:  # PyQt5
        from PyQt5.QtWidgets import (  # type: ignore[no-redef]
            QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit,
        )
    return QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit


def _announceable(w) -> bool:
    """A control is announceable if it has an accessible name or its own
    visible text (checkboxes / buttons)."""
    if w.accessibleName():
        return True
    text = getattr(w, "text", None)
    return bool(text()) if callable(text) else False


def test_every_preferences_control_is_announceable(dlg):
    QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit = _widgets()

    unlabelled = []
    for w in dlg.findChildren((QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit)):
        # Skip the line edit and buttons Qt embeds *inside* a spin box / editable
        # combo — those are internal parts, announced as part of their parent.
        parent = w.parent()
        if isinstance(w, QLineEdit) and isinstance(parent, (QAbstractSpinBox, QComboBox)):
            continue
        if isinstance(w, QAbstractButton) and isinstance(parent, (QAbstractSpinBox, QComboBox)):
            continue
        if not _announceable(w):
            unlabelled.append(f"{type(w).__name__} objectName={w.objectName()!r}")

    assert not unlabelled, (
        "Preferences controls with no accessible name and no visible text "
        "(a screen reader announces them as bare widgets):\n  "
        + "\n  ".join(unlabelled)
    )


def test_combo_boxes_carry_a_derived_name(dlg):
    """The core of the fix: combo boxes (which show no text of their own) must
    all get an accessible name from their form label."""
    _AB, _ASB, QComboBox, _LE = _widgets()
    nameless = [
        c.objectName() or "<combo>"
        for c in dlg.findChildren(QComboBox)
        if not c.accessibleName()
    ]
    assert not nameless, f"combo boxes with no accessible name: {nameless}"
