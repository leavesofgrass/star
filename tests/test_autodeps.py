"""Tests for star.autodeps — the optional-dependency install engine.

Never runs real pip: the install function and marker directory are injected.
"""
import pytest

from star import autodeps


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """autodeps with a temp marker dir, a fake install fn, and clean session state."""
    calls = []
    monkeypatch.setattr(autodeps, "_MARKER_DIR", str(tmp_path))
    monkeypatch.setattr(autodeps, "_INSTALL_FN", lambda pip, **kw: calls.append(pip) or True)
    monkeypatch.setattr(autodeps, "_attempted_session", set())
    monkeypatch.setattr(autodeps, "_enabled_override", None)
    monkeypatch.delenv("STAR_NO_AUTOINSTALL", raising=False)
    return calls


# ── registry / presets ───────────────────────────────────────────────────────

def test_every_feature_has_info_and_vice_versa():
    assert set(autodeps.FEATURES) == set(autodeps.FEATURE_INFO)


def test_presets_reference_real_features():
    for name, keys in autodeps.PRESETS.items():
        for key in keys:
            assert key in autodeps.FEATURES, f"{name} references unknown {key}"


def test_all_preset_excludes_the_heavy_packs():
    all_keys = set(autodeps.preset("all"))
    assert "transcribe" not in all_keys
    assert "ner" not in all_keys
    # …but they still exist as pickable features.
    assert "transcribe" in autodeps.FEATURES
    assert "ner" in autodeps.FEATURES


def test_thin_is_a_subset_of_features_and_lighter_than_all():
    assert set(autodeps.preset("thin")).issubset(set(autodeps.FEATURES))
    assert len(autodeps.preset("thin")) <= len(autodeps.preset("all"))


def test_unknown_preset_is_empty():
    assert autodeps.preset("nope") == []


def test_all_packages_dedupes_shared_deps():
    pkgs = autodeps.all_packages()
    pips = [p for p, _m in pkgs]
    assert len(pips) == len(set(pips))          # nltk is in both dictionary and ner
    assert ("nltk", "nltk") in pkgs


# ── installed / missing / feature_installed ──────────────────────────────────

def test_installed_true_for_stdlib_false_for_fake():
    assert autodeps.installed("json") is True
    assert autodeps.installed("definitely_not_a_real_module_xyz") is False


def test_missing_filters_present_packages():
    pkgs = [("json", "json"), ("nope-pkg", "definitely_not_a_real_module_xyz")]
    assert autodeps.missing(pkgs) == [("nope-pkg", "definitely_not_a_real_module_xyz")]


def test_feature_installed_reflects_module_presence(monkeypatch):
    monkeypatch.setitem(autodeps.FEATURES, "_probe_ok", [("x", "json")])
    monkeypatch.setitem(autodeps.FEATURES, "_probe_bad", [("y", "no_such_mod_zzz")])
    assert autodeps.feature_installed("_probe_ok") is True
    assert autodeps.feature_installed("_probe_bad") is False


# ── ensure(): once-per-machine, force, disabled ──────────────────────────────

def test_ensure_installs_missing_foreground(sandbox):
    todo = autodeps.ensure([("fakepkg", "no_such_mod_aaa")], background=False)
    assert todo == ["fakepkg"]
    assert sandbox == ["fakepkg"]


def test_ensure_skips_already_installed(sandbox):
    todo = autodeps.ensure([("json", "json")], background=False)
    assert todo == []
    assert sandbox == []


def test_ensure_is_attempted_only_once(sandbox):
    first = autodeps.ensure([("fakepkg", "no_such_mod_bbb")], background=False)
    second = autodeps.ensure([("fakepkg", "no_such_mod_bbb")], background=False)
    assert first == ["fakepkg"]
    assert second == []                          # marker blocks the retry
    assert sandbox == ["fakepkg"]                # installed exactly once


def test_force_ignores_the_marker(sandbox):
    autodeps.ensure([("fakepkg", "no_such_mod_ccc")], background=False)
    forced = autodeps.ensure([("fakepkg", "no_such_mod_ccc")], background=False, force=True)
    assert forced == ["fakepkg"]
    assert sandbox == ["fakepkg", "fakepkg"]


def test_disabled_via_setting_returns_nothing(sandbox):
    autodeps.set_enabled(False)
    assert autodeps.ensure([("fakepkg", "no_such_mod_ddd")], background=False) == []
    assert sandbox == []


def test_disabled_via_env(sandbox, monkeypatch):
    monkeypatch.setenv("STAR_NO_AUTOINSTALL", "1")
    assert autodeps.enabled() is False
    assert autodeps.ensure([("fakepkg", "no_such_mod_eee")], background=False) == []


def test_ensure_feature_uses_the_registry(sandbox, monkeypatch):
    monkeypatch.setitem(autodeps.FEATURES, "_feat", [("fakepkg", "no_such_mod_fff")])
    assert autodeps.ensure_feature("_feat", background=False) == ["fakepkg"]
    assert sandbox == ["fakepkg"]


def test_marker_file_written(sandbox, tmp_path):
    autodeps.ensure([("markerpkg", "no_such_mod_ggg")], background=False)
    assert (tmp_path / "markerpkg.attempted").exists()
