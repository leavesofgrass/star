"""Offscreen tests for the centralized Preferences dialog.

Constructs a real ``StarWindow`` under the offscreen QPA (like
``tests/test_gui_interactive.py``), builds a ``PreferencesDialog`` on it, and
verifies (a) it assembles with the four tabs and (b) the OK/Apply path writes
the changed widget values back into ``win.settings`` and persists them.

``QDialog.exec`` is monkeypatched so opening the dialog never blocks the suite.
The whole module is skipped when PyQt is unavailable.
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
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def _dialog(window):
    from star.gui.preferences import PreferencesDialog

    return PreferencesDialog(window)


def test_dialog_builds_with_four_tabs(window):
    dlg = _dialog(window)
    assert dlg.tabs.count() == 4
    titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert titles == ["Reading", "Voice", "Display", "General"]


def test_ok_writes_changed_settings(window, monkeypatch):
    """Changing a few widgets and driving the OK path writes them to settings."""
    from PyQt6.QtWidgets import QDialog

    # Never block on a modal exec during the test.
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)

    dlg = _dialog(window)

    # Change one widget per tab.
    dlg.style_box.setCurrentText("underline")
    dlg.rate_spin.setValue(180)
    dlg.volume_spin.setValue(50)
    dlg.theme_box.setCurrentIndex(
        1 if dlg.theme_box.count() > 1 else 0
    )
    picked_theme = dlg.theme_box.currentText()
    dlg.auto_updates.setChecked(True)

    # Drive the OK path (writes + applies + saves, then accepts).
    dlg._on_ok()

    s = window.settings
    assert s.get("highlight_style") == "underline"
    assert s.get("tts_rate") == 180
    assert abs(float(s.get("tts_volume")) - 0.5) < 1e-9  # 0–100% stored as 0.0–1.0
    assert s.get("theme") == picked_theme
    assert s.get("auto_check_updates") is True


def test_apply_button_writes_without_closing(window):
    """The Apply hook writes settings without needing OK/accept."""
    dlg = _dialog(window)
    dlg.lead_spin.setValue(3)
    dlg.paginate.setChecked(True)
    dlg._apply()

    s = window.settings
    assert s.get("highlight_lead_words") == 3
    assert s.get("qt_paginate_large_docs") is True


def test_none_engine_stored_as_silent(window):
    """The Voice combo's 'none' choice is normalised to the 'silent' backend."""
    dlg = _dialog(window)
    dlg.engine_box.setCurrentText("none")
    dlg._write_settings()
    assert window.settings.get("tts_backend") == "silent"


def test_palette_only_dialogs_construct(window, monkeypatch):
    """The three tuning dialogs demoted from the menu bar still build.

    They are reachable only from the Command Palette now, so nothing else in
    CI would touch them — a rename/regression would otherwise ship silently
    (the 0.1.15 'nothing imports it' failure class)."""
    from PyQt6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    window._qt_karaoke_dialog()
    window._qt_reading_ruler_dialog()
    window._qt_rsvp_position_dialog()


def test_preferences_opener_runs(window, monkeypatch):
    """Edit ▸ Preferences… (Ctrl+,) opens via the lazy _qt_preferences hook."""
    from PyQt6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    window._qt_preferences()


def test_palette_registers_tuning_dialogs(window):
    """The Command Palette lists all three tuners by their stable names."""
    labels = [label for label, _fn in window._qt_command_registry()]
    for want in (
        "Tune Karaoke Highlight…",
        "Tune Reading Ruler…",
        "Tune RSVP Position…",
    ):
        assert want in labels, f"palette lost {want!r}"


def test_theme_change_marks_explicit(window):
    """Deliberately changing the theme sets qt_theme_explicit so OS-follow
    won't silently override it on the next launch (mirrors the menu pickers)."""
    window.settings._data["qt_theme_explicit"] = False
    dlg = _dialog(window)
    other = next(
        dlg.theme_box.itemText(i)
        for i in range(dlg.theme_box.count())
        if dlg.theme_box.itemText(i) != dlg._orig_theme
    )
    dlg.theme_box.setCurrentText(other)
    dlg._apply()
    assert window.settings.get("qt_theme_explicit") is True


def test_reenabling_follow_os_rearms_auto_detect(window):
    """Ticking 'Follow OS theme' without changing the theme clears the explicit
    flag so OS auto-detection resumes on the next launch."""
    window.settings._data["qt_theme_explicit"] = True
    window.settings._data["qt_follow_os_theme"] = False
    dlg = _dialog(window)
    assert dlg._orig_follow_os is False
    dlg.follow_os.setChecked(True)  # re-enable; theme left unchanged
    dlg._apply()
    assert window.settings.get("qt_theme_explicit") is False
