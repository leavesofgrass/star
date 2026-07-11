"""Offscreen test for the toolbar microphone (Voice Typing) button.

The mic toolbar action is a *checkable* QAction (ChromeMixin._build_edit_toolbar
in star/gui/mixin_chrome.py): it stays highlighted while dictation is listening.
``_qt_vt_sync_action`` (star/gui/mixin_transcription.py) reflects the on/off
state into the button's ``isChecked()`` so visual users can see it recording.

Follows tests/test_authoring.py: a real StarWindow under the offscreen QPA,
driving the transcription state directly (no microphone / no audio backend).
"""
import importlib.util

import pytest

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def _mic_action(window):
    """The checkable Voice Typing toolbar action, keyed on its stable label."""
    return window._toolbar_actions.get("Voice Typing")


def test_mic_toolbar_action_exists_checkable_and_tracks_state(window):
    """One window (fewer teardowns = less Qt-teardown-flake surface): the mic
    action exists, is checkable, starts idle, and its checked state mirrors
    ``_qt_vt_active`` via ``_qt_vt_sync_action``."""
    act = _mic_action(window)
    assert act is not None, "Voice Typing toolbar action missing"
    assert act.isCheckable() is True
    assert act.isChecked() is False  # idle at startup

    window._qt_vt_active = True
    window._qt_vt_sync_action()
    assert act.isChecked() is True   # highlighted while listening

    window._qt_vt_active = False
    window._qt_vt_sync_action()
    assert act.isChecked() is False  # cleared when idle
