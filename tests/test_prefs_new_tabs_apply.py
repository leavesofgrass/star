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


@pytest.fixture
def dlg(window):
    """A Preferences dialog that is explicitly closed + scheduled for deletion
    on teardown — a leaked dialog lingers into the conftest drain phase and adds
    Qt-teardown-flake surface on the CI Linux legs."""
    from star.gui.preferences import PreferencesDialog

    d = PreferencesDialog(window)
    yield d
    d.close()
    d.deleteLater()


def test_consolidated_settings_round_trip_through_apply(dlg, window):
    """The 0.1.28 consolidation: settings that used to live only in menus
    (SSML, transcript timestamps, caret browsing, table reading mode, skip
    code, bionic reading, interface language) write + apply from Preferences."""
    dlg.caret_browsing.setChecked(False)
    dlg.table_mode.setCurrentIndex(dlg.table_mode.findText("flat"))
    dlg.skip_code.setChecked(False)
    dlg.aid_bionic.setChecked(True)
    dlg.transcript_ts.setChecked(True)
    dlg.ssml.setChecked(True)
    dlg._apply()
    s = window.settings
    assert s.get("qt_caret_browsing") is False
    assert s.get("table_reading_mode") == "flat"
    assert s.get("tts_skip_code") is False
    assert s.get("qt_bionic_reading") is True
    assert s.get("transcribe_timestamps") is True
    assert s.get("use_ssml") is True


def test_language_combo_stages_ui_language(dlg, window):
    """The General-tab language combo writes the language CODE (not the
    display name) into ui_language."""
    assert dlg._lang_codes, "no languages available"
    # Stage whatever is at index 0 (English in the shipped catalogs).
    dlg.lang_box.setCurrentIndex(0)
    dlg._write_settings()
    assert window.settings._data["ui_language"] == dlg._lang_codes[0]


def test_theme_combo_lists_community_palettes(dlg):
    """The Display-tab theme combo carries the full registry — including the
    0.1.28 community palettes and any custom CSS themes."""
    names = [dlg.theme_box.itemText(i) for i in range(dlg.theme_box.count())]
    for expected in ("galaxy", "dracula", "nord", "catppuccin-mocha"):
        assert expected in names


def test_reading_aids_and_fonts_round_trip_through_apply(dlg, window):
    """Both new tabs in one dialog/window (fewer teardowns): the Apply hook
    writes+applies the Reading-Aids toggles and the Fonts spacing without
    closing, and every value round-trips into the window settings."""
    dlg.aid_ruler.setChecked(True)
    dlg.aid_syllables.setChecked(True)
    dlg.aid_vocab.setChecked(True)
    dlg.aid_rsvp.setChecked(True)
    dlg.line_height.setValue(1.8)
    dlg.letter_spacing.setValue(2.5)
    dlg.word_spacing.setValue(4.0)
    dlg._apply()  # Apply button: writes + applies without closing
    s = window.settings
    assert s.get("qt_reading_ruler") is True
    assert s.get("qt_syllable_split") is True
    assert s.get("qt_vocab_highlight") is True
    assert s.get("qt_rsvp_mode") is True
    assert abs(float(s.get("qt_line_height")) - 1.8) < 1e-9
    assert abs(float(s.get("qt_letter_spacing")) - 2.5) < 1e-9
    assert abs(float(s.get("qt_word_spacing")) - 4.0) < 1e-9
