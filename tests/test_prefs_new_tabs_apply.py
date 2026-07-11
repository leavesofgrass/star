"""Complementary round-trip tests for the 0.1.24 Reading Aids + Fonts tabs.

tests/test_preferences.py already covers these tabs via the OK path
(``_on_ok``).  This module mirrors that style but drives the *Apply* hook
(``_apply``) instead — the live-effect path a user hits with the Apply button —
so a regression that only breaks apply-without-closing is still caught.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def _dialog(window):
    from star.gui.preferences import PreferencesDialog

    return PreferencesDialog(window)


def test_reading_aids_toggles_round_trip_through_apply(window):
    dlg = _dialog(window)
    dlg.aid_ruler.setChecked(True)
    dlg.aid_syllables.setChecked(True)
    dlg.aid_vocab.setChecked(True)
    dlg.aid_rsvp.setChecked(True)
    dlg._apply()  # Apply button: writes + applies without closing
    s = window.settings
    assert s.get("qt_reading_ruler") is True
    assert s.get("qt_syllable_split") is True
    assert s.get("qt_vocab_highlight") is True
    assert s.get("qt_rsvp_mode") is True


def test_fonts_spacing_round_trips_through_apply(window):
    dlg = _dialog(window)
    dlg.line_height.setValue(1.8)
    dlg.letter_spacing.setValue(2.5)
    dlg.word_spacing.setValue(4.0)
    dlg._apply()
    s = window.settings
    assert abs(float(s.get("qt_line_height")) - 1.8) < 1e-9
    assert abs(float(s.get("qt_letter_spacing")) - 2.5) < 1e-9
    assert abs(float(s.get("qt_word_spacing")) - 4.0) < 1e-9
