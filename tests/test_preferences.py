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


def test_dialog_builds_with_six_tabs(window):
    dlg = _dialog(window)
    assert dlg.tabs.count() == 6
    titles = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert titles == ["Reading", "Reading Aids", "Voice", "Display",
                      "Fonts", "General"]


def test_reading_aids_tab_mirrors_stay_in_sync(window):
    """The Reading Aids tab duplicates a few Reading-tab toggles (accessibility:
    more than one way in); the copies must mirror each other both directions."""
    dlg = _dialog(window)
    dlg.hl_master.setChecked(False)
    assert dlg.aid_highlight.isChecked() is False       # Reading -> Aids
    dlg.aid_highlight.setChecked(True)
    assert dlg.hl_master.isChecked() is True            # Aids -> Reading
    dlg.autoscroll.setChecked(False)
    assert dlg.aid_autoscroll.isChecked() is False


def test_reading_aids_tab_writes_the_new_toggles(window, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    dlg = _dialog(window)
    dlg.aid_ruler.setChecked(True)
    dlg.aid_syllables.setChecked(True)
    dlg.aid_vocab.setChecked(True)
    dlg.aid_rsvp.setChecked(True)
    dlg._on_ok()
    s = window.settings
    assert s.get("qt_reading_ruler") is True
    assert s.get("qt_syllable_split") is True
    assert s.get("qt_vocab_highlight") is True
    assert s.get("qt_rsvp_mode") is True


def test_fonts_tab_writes_spacing_and_mirrors_reading_font(window, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    dlg = _dialog(window)
    # Reading-font combo mirrors the Display tab's.
    dlg.reading_font.setCurrentText("atkinson")
    assert dlg.font_reading.currentText() == "atkinson"
    dlg.font_reading.setCurrentText("opendyslexic")
    assert dlg.reading_font.currentText() == "opendyslexic"
    # Spacing controls write through.
    dlg.line_height.setValue(2.0)
    dlg.letter_spacing.setValue(5.0)
    dlg.word_spacing.setValue(3.0)
    dlg._on_ok()
    s = window.settings
    assert abs(float(s.get("qt_line_height")) - 2.0) < 1e-9
    assert abs(float(s.get("qt_letter_spacing")) - 5.0) < 1e-9
    assert abs(float(s.get("qt_word_spacing")) - 3.0) < 1e-9


def test_restore_defaults_resets_the_new_tabs(window):
    dlg = _dialog(window)
    dlg.aid_ruler.setChecked(True)
    dlg.line_height.setValue(2.5)
    dlg._restore_defaults()
    from star.settings import DEFAULTS
    assert dlg.aid_ruler.isChecked() is bool(DEFAULTS["qt_reading_ruler"])
    assert abs(dlg.line_height.value() - float(DEFAULTS["qt_line_height"])) < 1e-9


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


def test_whisper_model_combo_stages_and_writes(window):
    """The Voice tab's dictation-model combo reflects the saved setting and
    writes the picked size back through the OK/Apply path."""
    from star.gui.preferences import _WHISPER_MODELS

    window.settings._data["whisper_model"] = "small"
    dlg = _dialog(window)
    assert dlg.whisper_box.currentText() == "small"
    assert [dlg.whisper_box.itemText(i) for i in range(dlg.whisper_box.count())] \
        == _WHISPER_MODELS
    dlg.whisper_box.setCurrentText("large-v3-turbo")
    dlg._write_settings()
    assert window.settings.get("whisper_model") == "large-v3-turbo"


def test_whisper_model_combo_defaults_to_base_on_unknown(window):
    """A hand-edited settings.json with an unknown size falls back to base."""
    window.settings._data["whisper_model"] = "gigantic-v9"
    dlg = _dialog(window)
    assert dlg.whisper_box.currentText() == "base"


def test_whisper_model_restore_defaults(window):
    from star.settings import DEFAULTS

    dlg = _dialog(window)
    dlg.whisper_box.setCurrentText("medium")
    dlg._restore_defaults()
    assert dlg.whisper_box.currentText() == str(DEFAULTS["whisper_model"])


def test_restore_defaults_stages_shipped_values(window):
    """Restore Defaults re-stages every widget from DEFAULTS without saving."""
    from star.settings import DEFAULTS

    dlg = _dialog(window)
    before = dict(window.settings._data)
    dlg.rate_spin.setValue(390)
    dlg.style_box.setCurrentText("underline")
    dlg._hl_color["v"] = "#123456"
    dlg._restore_defaults()
    assert dlg.rate_spin.value() == DEFAULTS["tts_rate"]
    assert dlg.style_box.currentText() == DEFAULTS["highlight_style"]
    assert dlg._hl_color["v"] == DEFAULTS["highlight_color"]
    assert dlg.bitrate_box.currentText() == DEFAULTS["audiobook_bitrate"]
    assert dlg.paginate_threshold.value() == DEFAULTS["qt_paginate_threshold_words"]
    # Staging only: nothing was written or saved.
    assert window.settings._data == before


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


def test_highlight_master_toggle_writes_and_gates_rows(window):
    """The Reading tab's master switch writes highlight_current_word and
    grays out the dependent karaoke rows while unchecked."""
    dlg = _dialog(window)
    assert dlg.hl_master.isChecked() is True  # shipped default
    dlg.hl_master.setChecked(False)
    assert all(not dep.isEnabled() for dep in dlg._hl_dependents)
    dlg._write_settings()
    assert window.settings.get("highlight_current_word") is False
    dlg.hl_master.setChecked(True)
    assert all(dep.isEnabled() for dep in dlg._hl_dependents)


def test_apply_fires_live_hooks_with_picked_values(window):
    """_apply() must actually invoke every live-effect hook with the staged
    values — the hooks are try/except-guarded, so without these spies a hook
    that regresses to raising would leave the UI dead while CI stayed green."""
    from types import SimpleNamespace

    from PyQt6.QtGui import QColor

    calls = {}
    window._rebuild_hl_fmt = lambda: calls.setdefault("hl", True)
    window._apply_qt_theme = lambda name: calls.__setitem__("theme", name)
    window._set_font = lambda family, size: calls.__setitem__("font", (family, size))
    window._qt_refresh_vocab_highlight = lambda: calls.setdefault("vocab", True)
    window.tts_manager = SimpleNamespace(
        set_rate=lambda r: calls.__setitem__("rate", r),
        set_volume=lambda v: calls.__setitem__("volume", v),
        change_backend=lambda name: calls.__setitem__("backend", name),
        backend_name="pyttsx3",
        speaking=False,          # read by the window's close/teardown path
        stop=lambda: None,
    )
    ruler_calls = {}
    window._reading_ruler = SimpleNamespace(
        set_height=lambda h: ruler_calls.__setitem__("h", h),
        set_opacity=lambda o: ruler_calls.__setitem__("o", o),
        set_color=lambda c: ruler_calls.__setitem__("c", c.name()),
    )
    rsvp_calls = {}
    window._rsvp_overlay = SimpleNamespace(
        set_position=lambda k: rsvp_calls.__setitem__("pos", k),
        set_font_size=lambda s: rsvp_calls.__setitem__("size", s),
        set_show_context=lambda b: rsvp_calls.__setitem__("ctx", b),
    )

    dlg = _dialog(window)
    dlg.rate_spin.setValue(200)
    dlg.volume_spin.setValue(70)
    dlg.ruler_height.setValue(60)
    dlg.ruler_opacity.setValue(33)
    dlg._hl_color["v"] = "#ff8800"
    dlg._ruler_color["v"] = ""  # exercise the empty → highlight-color fallback
    dlg.rsvp_pos.setCurrentText("center")
    dlg.rsvp_font.setValue(72)
    dlg.rsvp_ctx.setChecked(False)
    dlg._apply()

    assert calls.get("hl") and calls.get("vocab")
    assert calls["rate"] == 200
    assert abs(calls["volume"] - 0.7) < 1e-9
    assert calls["theme"] == window.settings.get("theme")
    assert calls["font"] == (
        window.settings.get("qt_font_family"),
        window.settings.get("qt_font_size"),
    )
    assert ruler_calls == {"h": 60, "o": 33, "c": QColor("#ff8800").name()}
    assert rsvp_calls == {"pos": "center", "size": 72, "ctx": False}


def test_apply_changes_backend_once_and_skips_auto(window):
    """The engine hook fires exactly once for a real change — never for
    'auto', never when the manager already runs the chosen backend."""
    from types import SimpleNamespace

    calls = []
    window.tts_manager = SimpleNamespace(
        set_rate=lambda r: None,
        set_volume=lambda v: None,
        change_backend=lambda name: calls.append(name),
        backend_name="pyttsx3",
        speaking=False,          # read by the window's close/teardown path
        stop=lambda: None,
    )
    dlg = _dialog(window)

    dlg.engine_box.setCurrentText("auto")
    dlg._apply()
    assert calls == []  # auto never forces a backend

    target = next(
        dlg.engine_box.itemText(i)
        for i in range(dlg.engine_box.count())
        if dlg.engine_box.itemText(i) not in ("auto", "none", "pyttsx3")
    )
    dlg.engine_box.setCurrentText(target)
    dlg._apply()
    assert calls == [target]  # real change fires once

    window.tts_manager.backend_name = target
    dlg._apply()
    assert calls == [target]  # already active → no second call


def test_apply_survives_raising_hook_and_still_saves(window):
    """A hook that raises must not abort the rest of _apply() — later writes
    still land and settings.save() still runs (the guarded-hook contract)."""
    def _boom() -> None:
        raise RuntimeError("boom")

    window._rebuild_hl_fmt = _boom
    saved = {}
    window.settings.save = lambda: saved.setdefault("saved", True)
    dlg = _dialog(window)
    dlg.rate_spin.setValue(222)
    dlg._apply()  # must not raise
    assert saved.get("saved"), "settings.save() skipped after a raising hook"
    assert window.settings.get("tts_rate") == 222


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


def test_apply_announces_to_screen_readers(window, monkeypatch):
    """Apply must announce() — the status bar is invisible to screen readers."""
    import star.gui.preferences as prefs_mod

    spoken = []
    monkeypatch.setattr(prefs_mod, "announce", lambda _w, msg: spoken.append(msg))
    dlg = _dialog(window)
    dlg._apply()
    assert any("applied" in m.lower() for m in spoken), spoken
    # A deliberate theme change is announced by name, once.
    other = next(
        dlg.theme_box.itemText(i)
        for i in range(dlg.theme_box.count())
        if dlg.theme_box.itemText(i) != dlg._orig_theme
    )
    spoken.clear()
    dlg.theme_box.setCurrentText(other)
    dlg._apply()
    assert any(other in m for m in spoken), spoken
