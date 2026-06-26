"""Shared pytest fixtures.

`Settings.set()` / `Settings[...] = ...` auto-persist to the user's real
settings.json (see star/settings.py).  Without isolation, any test that mutates
a Settings object would clobber the developer's actual configuration and leak
state into later tests.  This autouse fixture redirects the settings file to a
per-test temp path so construction and saves stay sandboxed.
"""
import pytest

import star.settings as _settings_mod


@pytest.fixture(autouse=True)
def _isolate_settings_file(monkeypatch, tmp_path):
    monkeypatch.setattr(_settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
