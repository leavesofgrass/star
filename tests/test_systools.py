"""Tests for the native (non-pip) system-tools harness and its GUI status list.

``star.diagnostics.system_tools()`` reports the native engines star can drive
but pip cannot install (OCR, markup, audio/video, graph layout, TTS engines).
``star.gui.deps_dialog.DependencyChooser`` renders those as read-only status
rows *below* the pip-feature checklist — they must never become checkboxes, so
the one-checkbox-per-``FEATURE_INFO`` contract is preserved.
"""
import importlib.util
import os

import pytest

from star import diagnostics

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))


# ── diagnostics.system_tools() ───────────────────────────────────────────
def test_system_tools_shape():
    tools = diagnostics.system_tools()
    assert tools, "system_tools() must not be empty"
    keys = [t["key"] for t in tools]
    assert len(keys) == len(set(keys)), "duplicate system-tool keys"
    required = {"key", "label", "available", "vendored", "binary", "enables", "install"}
    for t in tools:
        assert required <= t.keys(), f"{t.get('key')} missing fields: {required - t.keys()}"
        assert isinstance(t["available"], bool)
        assert isinstance(t["vendored"], bool)
        assert t["binary"] is None or isinstance(t["binary"], str)
        assert isinstance(t["label"], str) and t["label"]
        assert isinstance(t["enables"], str)
        assert isinstance(t["install"], str)


def test_system_tools_cover_key_engines():
    keys = {t["key"] for t in diagnostics.system_tools()}
    # The task's named native engines must all be represented.
    for expected in ("pandoc", "ffmpeg", "tesseract", "dot", "piper"):
        assert expected in keys, f"missing native engine: {expected}"


def test_system_tools_availability_consistent_with_detection():
    """`available` is True iff the tool is vendored or its binary is on PATH."""
    import shutil

    for t in diagnostics.system_tools():
        on_path = bool(t["binary"] and shutil.which(t["binary"]))
        # vendored OR on PATH is sufficient; binary_alt names may also satisfy
        # it, so only assert the forward implication we can verify cheaply.
        if t["vendored"] or on_path:
            assert t["available"] is True


def test_system_tools_do_not_duplicate_registry_data():
    """Derived rows reuse OPTIONAL_DEPENDENCIES copy rather than restating it."""
    by_key = {d["key"]: d for d in diagnostics.OPTIONAL_DEPENDENCIES}
    tools = {t["key"]: t for t in diagnostics.system_tools()}
    # pandoc derives from the pandoc_bin registry entry.
    assert tools["pandoc"]["enables"] == by_key["pandoc_bin"]["enables"]
    assert tools["pandoc"]["install"] == by_key["pandoc_bin"]["install"]


# ── DependencyChooser (offscreen) ────────────────────────────────────────
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
def chooser(qapp):
    from star.gui.deps_dialog import DependencyChooser
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    dlg = DependencyChooser(win)
    yield dlg, win
    dlg.close()
    win.close()


def test_checkbox_count_unchanged(chooser):
    """System tools must NOT add checkboxes — still one per FEATURE_INFO."""
    from star import autodeps

    dlg, _win = chooser
    assert set(dlg._boxes) == set(autodeps.FEATURE_INFO)
    assert len(dlg._boxes) == len(autodeps.FEATURE_INFO)


def test_system_tool_rows_rendered(chooser):
    """Every native tool gets a read-only status row (a QLabel, not a box)."""
    from PyQt6.QtWidgets import QCheckBox, QLabel

    dlg, _win = chooser
    sys_keys = {t["key"] for t in diagnostics.system_tools()}
    assert set(dlg._sys_rows) == sys_keys
    assert dlg._sys_rows, "no system-tool rows rendered"
    for key, row in dlg._sys_rows.items():
        assert isinstance(row, QLabel), f"{key} row is not a QLabel"
        assert not isinstance(row, QCheckBox)
        # Accessibility: state announced up front, description present.
        assert row.accessibleName(), f"{key} row lacks an accessible name"
        assert row.accessibleDescription(), f"{key} row lacks a description"
