"""Offscreen tests for the profile export/import dialog handlers
(star/gui/mixin_presets.py — the 0.1.27 profile-sharing surface).

The JSON envelope itself (format marker, cross-version key hygiene) is covered
by tests/test_profiles_export.py; what was untested is the QFileDialog /
QInputDialog glue in ``_qt_export_profiles`` and ``_qt_import_profiles``:
which file gets written, what a cancelled dialog does, and what the status bar
reports.  Every picker is monkeypatched — no dialog is ever shown — so these
tests drive the handlers exactly as the menu actions do and assert only their
file / settings / status-bar effects.
"""
import importlib.util
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test run trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the module.  No fonts are loaded (unlike the
    smoke module): nothing here renders glyphs — the dialogs are monkeypatched
    away and only the handlers' side effects are asserted."""
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def _never(*_a, **_k):
    """Stand-in for a dialog static method that must NOT be reached."""
    raise AssertionError("this dialog must not be shown on this path")


def _pick_first_item(monkeypatch):
    """QInputDialog.getItem accepts its first entry — in the export picker
    that is the 'All profiles (n)' aggregate.  Positional arg 3 is the items
    list (parent, title, label, items, current, editable)."""
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: (a[3][0], True))
    )


def _save_dialog_returns(monkeypatch, path):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(path), "JSON (*.json)")),
    )


def _open_dialog_returns(monkeypatch, path):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(path), "JSON (*.json)")),
    )


# ── Export ───────────────────────────────────────────────────────────────────


def test_export_all_writes_the_envelope_and_confirms(window, tmp_path, monkeypatch):
    """Exporting 'All profiles' writes the versioned JSON envelope to the
    picked path and confirms on the status bar."""
    from star.stats import PROFILE_EXPORT_FORMAT, _save_profile

    window.settings.set("tts_rate", 321)
    _save_profile(window.settings, "loud-and-fast")
    dest = tmp_path / "star-profiles.json"
    _pick_first_item(monkeypatch)
    _save_dialog_returns(monkeypatch, dest)

    window._qt_export_profiles()

    assert dest.is_file()
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert payload["star_profiles"] == PROFILE_EXPORT_FORMAT
    assert payload["app_version"]
    assert payload["profiles"]["loud-and-fast"]["tts_rate"] == 321
    assert window.statusBar().currentMessage() == (
        "Exported 1 profile(s) to star-profiles.json"
    )


def test_export_single_profile_writes_only_that_one(window, tmp_path, monkeypatch):
    """Picking a named profile (not the 'All' aggregate) exports just it."""
    from PyQt6.QtWidgets import QInputDialog

    from star.stats import _save_profile

    window.settings.set("tts_rate", 200)
    _save_profile(window.settings, "alpha")
    window.settings.set("tts_rate", 300)
    _save_profile(window.settings, "beta")
    dest = tmp_path / "star-profile-beta.json"
    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: ("beta", True))
    )
    _save_dialog_returns(monkeypatch, dest)

    window._qt_export_profiles()

    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert list(payload["profiles"]) == ["beta"]
    assert payload["profiles"]["beta"]["tts_rate"] == 300
    assert window.statusBar().currentMessage() == (
        "Exported 1 profile(s) to star-profile-beta.json"
    )


def test_export_cancel_at_profile_picker_is_a_noop(window, monkeypatch):
    """Escaping the which-profile chooser never opens the file dialog."""
    from PyQt6.QtWidgets import QFileDialog, QInputDialog

    from star.stats import _save_profile

    _save_profile(window.settings, "kept")
    monkeypatch.setattr(
        QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False))
    )
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(_never))
    window.statusBar().showMessage("sentinel")

    window._qt_export_profiles()

    assert window.statusBar().currentMessage() == "sentinel"


def test_export_cancel_at_file_dialog_is_a_noop(window, monkeypatch):
    """An empty path from getSaveFileName (user cancelled) writes nothing —
    the envelope is never even built."""
    import star.gui.mixin_presets as presets
    from PyQt6.QtWidgets import QFileDialog

    from star.stats import _save_profile

    _save_profile(window.settings, "kept")
    _pick_first_item(monkeypatch)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    monkeypatch.setattr(presets, "_export_profiles", _never)
    window.statusBar().showMessage("sentinel")

    window._qt_export_profiles()

    assert window.statusBar().currentMessage() == "sentinel"


def test_export_with_no_profiles_hints_instead_of_dialogs(window, monkeypatch):
    """With nothing to export the handler points at the save-profile menu and
    never opens a picker."""
    from PyQt6.QtWidgets import QFileDialog, QInputDialog

    assert not window.settings.get("profiles", {})
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(_never))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(_never))

    window._qt_export_profiles()

    assert window.statusBar().currentMessage().startswith("No profiles to export")


# ── Import ───────────────────────────────────────────────────────────────────


def test_import_round_trips_an_exported_file(window, tmp_path, monkeypatch):
    """The headline path: export → wipe → import restores the profile (the
    changed setting round-trips through the file) and the status bar confirms."""
    from star.stats import _save_profile

    window.settings.set("tts_rate", 321)
    _save_profile(window.settings, "roundtrip")
    dest = tmp_path / "star-profiles.json"
    _pick_first_item(monkeypatch)
    _save_dialog_returns(monkeypatch, dest)
    window._qt_export_profiles()
    assert dest.is_file()

    # Wipe + drift so the restoration is observable, then import the file.
    window.settings.set("profiles", {})
    window.settings.set("tts_rate", 180)
    _open_dialog_returns(monkeypatch, dest)

    window._qt_import_profiles()

    assert window.settings.get("profiles")["roundtrip"]["tts_rate"] == 321
    assert window.statusBar().currentMessage() == (
        "Imported 1 profile(s): roundtrip"
    )


def test_import_cancel_is_a_noop(window, monkeypatch):
    """An empty path from getOpenFileName (user cancelled) reads nothing and
    changes nothing."""
    import star.gui.mixin_presets as presets
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    monkeypatch.setattr(presets, "_import_profiles", _never)
    before = dict(window.settings.get("profiles", {}) or {})
    window.statusBar().showMessage("sentinel")

    window._qt_import_profiles()

    assert dict(window.settings.get("profiles", {}) or {}) == before
    assert window.statusBar().currentMessage() == "sentinel"


def test_import_malformed_file_reports_error_and_keeps_settings(
    window, tmp_path, monkeypatch
):
    """Broken JSON and valid-JSON-but-not-an-envelope both surface 'Import
    failed' (via _status_error) and leave profiles untouched."""
    for name, text in (
        ("broken.json", "{ this is not json"),
        ("not-an-export.json", json.dumps({"unrelated": True})),
    ):
        bad = tmp_path / name
        bad.write_text(text, encoding="utf-8")
        _open_dialog_returns(monkeypatch, bad)

        window._qt_import_profiles()

        assert window.statusBar().currentMessage().startswith("Import failed:")
        assert not (window.settings.get("profiles", {}) or {})
