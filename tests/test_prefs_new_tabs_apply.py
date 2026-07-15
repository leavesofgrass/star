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
    """The 0.1.27 consolidation: settings that used to live only in menus
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


def test_reading_aid_colors_round_trip_through_apply(dlg, window):
    """Every reading-aid visual element's color is settable from the Reading
    Aids tab: line tint, reading ruler, RSVP word + panel (word highlight is
    the same state as the Reading tab swatch)."""
    dlg._line_color["v"] = "#123456"
    dlg._ruler_color["v"] = "#654321"
    dlg._rsvp_text_color["v"] = "#abcdef"
    dlg._rsvp_bg_color["v"] = "#0d1117"
    dlg._apply()
    s = window.settings
    assert s.get("qt_current_line_color") == "#123456"
    assert s.get("qt_ruler_color") == "#654321"
    assert s.get("qt_rsvp_text_color") == "#abcdef"
    assert s.get("qt_rsvp_bg_color") == "#0d1117"


def test_rsvp_overlay_honors_color_settings(window):
    """The RSVP overlay paints the configured word/panel colors, live via
    set_colors(), and falls back to its defaults when the settings are empty."""
    from star.gui.main_window import _RSVPOverlay

    window.settings["qt_rsvp_text_color"] = "#ff8800"
    window.settings["qt_rsvp_bg_color"] = "#112233"
    ov = _RSVPOverlay(window.editor, window.settings)
    try:
        assert ov._text_color().name() == "#ff8800"
        bg = ov._bg_color()
        assert (bg.red(), bg.green(), bg.blue()) == (0x11, 0x22, 0x33)
        assert bg.alpha() == 230  # translucency preserved for any color
        assert "#ff8800" in ov._word_lbl.styleSheet()
        # Live re-apply picks up a change without rebuilding the overlay.
        window.settings["qt_rsvp_text_color"] = "#00ff77"
        ov.set_colors()
        assert "#00ff77" in ov._word_lbl.styleSheet()
        # Empty settings restore the built-in defaults.
        window.settings["qt_rsvp_text_color"] = ""
        window.settings["qt_rsvp_bg_color"] = ""
        ov.set_colors()
        assert ov._text_color().name() == "#e8e8e8"
        assert (ov._bg_color().red(), ov._bg_color().green(),
                ov._bg_color().blue()) == (24, 27, 34)
    finally:
        ov.deleteLater()


def test_rsvp_overlay_prev_next_independently_toggleable(window):
    """Each RSVP context word hides independently — and a hidden label leaves
    the layout entirely, so 'only the single large word' is truly only the
    word."""
    from star.gui.main_window import _RSVPOverlay

    window.settings["qt_rsvp_show_prev"] = False
    window.settings["qt_rsvp_show_next"] = True
    ov = _RSVPOverlay(window.editor, window.settings)
    try:
        ov.update_word("before", "WORD", "after")
        assert not ov._prev_lbl.isVisibleTo(ov)
        assert ov._next_lbl.isVisibleTo(ov)
        assert ov._next_lbl.text() == "after"
        # Live re-apply picks up a change without rebuilding the overlay.
        window.settings["qt_rsvp_show_next"] = False
        ov.set_display_options()
        assert not ov._next_lbl.isVisibleTo(ov)
        window.settings["qt_rsvp_show_prev"] = True
        ov.set_display_options()
        ov.update_word("before", "WORD", "after")
        assert ov._prev_lbl.isVisibleTo(ov)
        assert ov._prev_lbl.text() == "before"
    finally:
        ov.deleteLater()


def test_legacy_rsvp_context_setting_migrates():
    """A settings.json saved with the pre-0.1.27 combined qt_rsvp_context
    switch carries its value over to both new prev/next toggles."""
    import json
    import tempfile
    from pathlib import Path
    from unittest import mock

    import star.settings as settings_mod

    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "settings.json"
        f.write_text(json.dumps({"qt_rsvp_context": False}), encoding="utf-8")
        with mock.patch.object(settings_mod, "SETTINGS_FILE", f):
            s = settings_mod.Settings()
            assert s.get("qt_rsvp_show_prev") is False
            assert s.get("qt_rsvp_show_next") is False
            assert "qt_rsvp_context" not in s._data


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
    0.1.27 community palettes and any custom CSS themes."""
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
