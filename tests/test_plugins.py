"""
Enforce plugin registry invariants for built-in star plugins.

Tests
-----
test_all_builtin_entry_points_registered
    Every name in PLUGIN_ENTRY_POINTS appears in the installed entry-points.

test_all_builtin_plugins_load
    Every registered built-in entry-point loads to a valid subclass.

test_singleton_identity
    PluginRegistry.get() returns the same object on repeated calls.

test_reset_creates_new_instance
    PluginRegistry.reset() causes get() to return a new object.

test_override_plugins_context_manager
    override_plugins() replaces and restores the singleton correctly.

Note
----
The ``star.exporters`` group is deferred to Phase 3 (see
wiki/plugin-architecture.md §3); its built-in classes do not exist yet, so it is
intentionally absent from PLUGIN_ENTRY_POINTS and from GROUP_BASE below.
"""
from __future__ import annotations

import pytest
from importlib.metadata import entry_points
from pathlib import Path

from star.diagnostics import PLUGIN_ENTRY_POINTS
from star.formats import FormatHandler
from star.plugins import PluginRegistry, override_plugins
from star.tts import TTSBackend, SilentBackend


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_registry():
    """Reset the singleton before and after every test."""
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()


# ── entry-point completeness ──────────────────────────────────────────────────

@pytest.mark.parametrize("group", PLUGIN_ENTRY_POINTS.keys())
def test_all_builtin_entry_points_registered(group):
    expected = set(PLUGIN_ENTRY_POINTS[group])
    installed = {ep.name for ep in entry_points(group=group)}
    missing = expected - installed
    assert not missing, (
        f"[{group}] Missing entry-points: {sorted(missing)}\n"
        "Run `pip install -e .` from the repo root to register them."
    )


# ── plugin loading ────────────────────────────────────────────────────────────

GROUP_BASE = {
    "star.backends": TTSBackend,
    "star.formats": FormatHandler,
}

@pytest.mark.parametrize("group,base", GROUP_BASE.items())
def test_all_builtin_plugins_load(group, base):
    for ep in entry_points(group=group):
        cls = ep.load()
        assert isinstance(cls, type), f"{ep.name}: entry-point did not return a class"
        assert issubclass(cls, base), f"{ep.name}: not a subclass of {base.__name__}"
        assert cls.name, f"{ep.name}: empty .name attribute"


# ── singleton behaviour ───────────────────────────────────────────────────────

def test_singleton_identity():
    r1 = PluginRegistry.get()
    r2 = PluginRegistry.get()
    assert r1 is r2


def test_reset_creates_new_instance():
    r1 = PluginRegistry.get()
    PluginRegistry.reset()
    r2 = PluginRegistry.get()
    assert r1 is not r2


# ── override_plugins ──────────────────────────────────────────────────────────

def test_override_backends():
    with override_plugins(backends=[SilentBackend]) as reg:
        assert reg.backends == [SilentBackend]
        assert PluginRegistry.get() is reg


def test_override_restores_on_exit():
    outer = PluginRegistry.get()
    with override_plugins(backends=[SilentBackend]):
        pass
    assert PluginRegistry.get() is outer


def test_override_restores_on_exception():
    outer = PluginRegistry.get()
    try:
        with override_plugins(backends=[SilentBackend]):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert PluginRegistry.get() is outer


# ── handler_for ───────────────────────────────────────────────────────────────

class _FakeTxtHandler(FormatHandler):
    name = "fake_txt"
    @classmethod
    def extensions(cls): return frozenset({".faketxt"})
    @classmethod
    def available(cls): return True
    def load(self, path, **kwargs): return None


def test_handler_for_returns_instance():
    with override_plugins(formats=[_FakeTxtHandler]):
        reg = PluginRegistry.get()
        h = reg.handler_for(Path("example.faketxt"))
        assert isinstance(h, _FakeTxtHandler)


def test_handler_for_returns_none_for_unknown_ext():
    with override_plugins(formats=[]):
        reg = PluginRegistry.get()
        assert reg.handler_for(Path("example.zzz")) is None
