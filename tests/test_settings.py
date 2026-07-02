"""Tests for the persistent settings store (star/settings.py).

Focus: atomicity of ``Settings.save()`` (temp-file + os.replace, no scratch file
left behind, never a corrupt/partial settings.json, never raising) and loading a
pre-existing settings file (including nested-dict merge with defaults).
"""
from __future__ import annotations

import json

import pytest

import star.settings as settings_mod
from star.settings import DEFAULTS, Settings


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """Redirect SETTINGS_FILE to a throwaway path so save()/load() are sandboxed.

    (conftest.py already does this autouse for the whole suite, but binding the
    path here lets each test assert directly against the file it controls.)"""
    path = tmp_path / "cfg" / "settings.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", path)
    return path


def test_save_writes_valid_json(settings_file):
    s = Settings()
    s.set("theme", "contrast")
    assert settings_file.is_file()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["theme"] == "contrast"


def test_save_leaves_no_temp_file_behind(settings_file):
    s = Settings()
    s.save()
    # Only settings.json should exist in the config dir — no *.tmp scratch file.
    leftovers = [p.name for p in settings_file.parent.iterdir() if p.name != "settings.json"]
    assert leftovers == []


def test_save_is_atomic_never_truncates_existing(settings_file):
    """A second save fully replaces the file: it is always complete, parseable
    JSON — never a half-written middle from a torn write."""
    s = Settings()
    s.set("gui_width", 111)
    first = settings_file.read_text(encoding="utf-8")
    json.loads(first)  # parseable

    s.set("gui_width", 222)
    second = settings_file.read_text(encoding="utf-8")
    data = json.loads(second)  # still parseable after the replace
    assert data["gui_width"] == 222
    # No temp artifact from the second (or first) write.
    leftovers = [p.name for p in settings_file.parent.iterdir() if p.name != "settings.json"]
    assert leftovers == []


def test_save_never_raises_on_unwritable_target(tmp_path, monkeypatch, caplog):
    """If the destination cannot be written, save() logs and degrades to a no-op
    rather than raising — and leaves no temp file behind."""
    # Make the parent path a *file*, so mkdir(parents=True) fails inside save().
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "sub" / "settings.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", target)

    s = Settings.__new__(Settings)  # avoid _load touching the bad path
    s._data = dict(DEFAULTS)
    # Must not raise.
    s.save()
    assert not target.exists()


def test_load_reads_preexisting_file(settings_file):
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps({"theme": "solarized", "tts_rate": 300, "gui_width": 1234}),
        encoding="utf-8",
    )
    s = Settings()
    assert s.get("theme") == "solarized"
    assert s.get("tts_rate") == 300
    assert s.get("gui_width") == 1234
    # Unspecified keys fall back to defaults.
    assert s.get("tts_volume") == DEFAULTS["tts_volume"]


def test_load_merges_nested_dict_with_defaults(settings_file):
    """A pre-existing file that only overrides one nested-dict key keeps the
    other default nested keys (the merge behaviour save/load relies on)."""
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps({"speed_presets": {"skim": 999}}),
        encoding="utf-8",
    )
    s = Settings()
    presets = s.get("speed_presets")
    assert presets["skim"] == 999            # override applied
    assert presets["normal"] == DEFAULTS["speed_presets"]["normal"]  # default kept


def test_load_missing_file_uses_defaults(settings_file):
    assert not settings_file.exists()
    s = Settings()
    assert s.get("theme") == DEFAULTS["theme"]


def test_load_corrupt_file_falls_back_to_defaults(settings_file, caplog):
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text("{ this is not valid json ", encoding="utf-8")
    s = Settings()  # must not raise
    assert s.get("theme") == DEFAULTS["theme"]


def test_save_load_round_trip(settings_file):
    s = Settings()
    s.set("tts_rate", 275)
    s.set("recent_files", ["/a.md", "/b.pdf"])
    # A fresh Settings re-reads what the first one persisted.
    s2 = Settings()
    assert s2.get("tts_rate") == 275
    assert s2.get("recent_files") == ["/a.md", "/b.pdf"]
