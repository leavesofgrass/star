"""Profile export/import — the shareable-JSON envelope (0.1.28).

Pure-logic tests: profiles are exported with a format marker + app version
and imported with cross-version hygiene (unknown keys dropped, legacy theme
names resolved, same-name overwrite).
"""
import pytest

from star.settings import Settings
from star.stats import (
    PROFILE_EXPORT_FORMAT,
    _export_profiles,
    _import_profiles,
    _save_profile,
)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    import star.settings as settings_mod

    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    return Settings()


def _make_two_profiles(s: Settings) -> None:
    s._data["tts_rate"] = 300
    s._data["theme"] = "dracula"
    _save_profile(s, "fast-dracula")
    s._data["tts_rate"] = 180
    s._data["theme"] = "galaxy-light"
    _save_profile(s, "slow-light")


def test_export_all_round_trips_through_import(settings, tmp_path, monkeypatch):
    import json

    import star.settings as settings_mod

    _make_two_profiles(settings)
    payload = _export_profiles(settings)
    assert payload["star_profiles"] == PROFILE_EXPORT_FORMAT
    assert payload["app_version"]
    assert set(payload["profiles"]) == {"fast-dracula", "slow-light"}

    # A JSON round trip into a FRESH settings store (another machine).
    text = json.dumps(payload)
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "other.json")
    fresh = Settings()
    imported, dropped = _import_profiles(fresh, json.loads(text))
    assert sorted(imported) == ["fast-dracula", "slow-light"]
    assert dropped == []
    assert fresh.get("profiles")["fast-dracula"]["tts_rate"] == 300
    assert fresh.get("profiles")["slow-light"]["theme"] == "galaxy-light"


def test_export_single_profile(settings):
    _make_two_profiles(settings)
    payload = _export_profiles(settings, ["slow-light"])
    assert list(payload["profiles"]) == ["slow-light"]


def test_import_drops_unknown_keys_and_reports_them(settings):
    payload = {
        "star_profiles": 1,
        "app_version": "9.9.9",
        "profiles": {
            "future": {
                "tts_rate": 250,
                "hologram_mode": True,       # a key from a future star
                "qt_neural_lace": "on",      # another
            }
        },
    }
    imported, dropped = _import_profiles(settings, payload)
    assert imported == ["future"]
    assert dropped == ["hologram_mode", "qt_neural_lace"]
    prof = settings.get("profiles")["future"]
    assert prof == {"tts_rate": 250}


def test_import_resolves_legacy_theme_names(settings):
    payload = {
        "star_profiles": 1,
        "profiles": {"old": {"theme": "zed-one-dark", "tts_rate": 200}},
    }
    imported, _ = _import_profiles(settings, payload)
    assert imported == ["old"]
    assert settings.get("profiles")["old"]["theme"] == "one-dark"


def test_import_overwrites_same_name(settings):
    _make_two_profiles(settings)
    payload = {
        "star_profiles": 1,
        "profiles": {"fast-dracula": {"tts_rate": 111}},
    }
    _import_profiles(settings, payload)
    assert settings.get("profiles")["fast-dracula"]["tts_rate"] == 111
    # The untouched profile survives.
    assert settings.get("profiles")["slow-light"]["tts_rate"] == 180


@pytest.mark.parametrize("bad", [
    None,
    [],
    "text",
    {},                                  # no profiles object
    {"profiles": {}},                    # no format marker
    {"star_profiles": 1, "profiles": []},  # profiles not an object
])
def test_import_rejects_non_exports(settings, bad):
    with pytest.raises(ValueError):
        _import_profiles(settings, bad)


def test_import_skips_malformed_entries_quietly(settings):
    payload = {
        "star_profiles": 1,
        "profiles": {
            "good": {"tts_rate": 222},
            "": {"tts_rate": 1},          # unnamed
            "not-a-dict": "nope",         # malformed body
        },
    }
    imported, _ = _import_profiles(settings, payload)
    assert imported == ["good"]
