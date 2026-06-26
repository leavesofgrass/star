"""Import-smoke tests for the lazily-imported UI packages.

The Qt GUI is imported only inside ``star.gui.runner._run_qt_gui()``, and no
other test imports ``star.gui.main_window`` — so a module-level import error in
any GUI mixin escapes the rest of the suite entirely.  That blind spot let a
stale import (``from ..tui import _shortcuts_text``, left by the 0.1.14 tui →
``star/tui/`` package refactor) ship and crash the Qt GUI on launch with
``ImportError`` — invisible to CI for the whole 0.1.14 cycle.

These tests close the gap: they import **every** submodule of ``star.gui`` (and
``star.tui`` for symmetry) so any import-time breakage fails CI immediately, and
they assert ``StarWindow`` still composes from its mixins.  PyQt6 and curses are
base dependencies, so this runs on every CI leg.  The tests deliberately do not
instantiate ``StarWindow`` (that needs a live QApplication and is left to manual
/ integration use); resolving the module imports is what guards the regression
class we actually hit.
"""
import importlib
import importlib.util
import pkgutil

import pytest

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))


def _submodules(package_name: str):
    """All importable submodule names of *package_name* (``[]`` if it won't import)."""
    try:
        pkg = importlib.import_module(package_name)
    except Exception:
        return []
    return sorted(f"{package_name}.{m.name}" for m in pkgutil.iter_modules(pkg.__path__))


@pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")
@pytest.mark.parametrize("modname", _submodules("star.gui") or ["star.gui"])
def test_gui_submodule_imports_clean(modname):
    """Every star.gui submodule (main_window, runner, every mixin) imports."""
    importlib.import_module(modname)


@pytest.mark.parametrize("modname", _submodules("star.tui") or ["star.tui"])
def test_tui_submodule_imports_clean(modname):
    """Every star.tui submodule imports (app + every mixin + helpers)."""
    importlib.import_module(modname)


@pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")
def test_star_window_composes_from_mixins():
    """StarWindow is built; methods from several mixins resolve via the MRO."""
    mw = importlib.import_module("star.gui.main_window")
    StarWindow = mw.StarWindow
    assert isinstance(StarWindow, type)
    # One method drawn from a few different mixins — confirms the composition is
    # intact (and guards Define Word / the mixin imports specifically).
    for method in (
        "_qt_define_word",        # navigation mixin (the 0.1.15 feature)
        "_qt_translate",          # navigation mixin
        "_qt_toggle_vocab_highlight",  # highlights mixin
        "_qt_export_audio",       # export mixin
    ):
        assert callable(getattr(StarWindow, method, None)), f"missing StarWindow.{method}"


def test_star_app_composes_from_mixins():
    """StarApp (TUI) is built and exposes a representative method per the MRO."""
    StarApp = importlib.import_module("star.tui").StarApp
    assert isinstance(StarApp, type)
    for method in ("_define_cmd", "execute_command", "run", "draw"):
        assert callable(getattr(StarApp, method, None)), f"missing StarApp.{method}"
