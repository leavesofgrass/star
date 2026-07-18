"""Offscreen tests for the theme/display surface (star.gui.mixin_display).

Covers the observable state of theme switching — the F5 cycle (``_next_theme``),
the pick-by-name dialog (``_qt_pick_theme``), the stylesheet ``_apply_qt_theme``
hands the editor, and the OS-scheme follow logic (``_maybe_follow_os_theme`` +
``star.themes.theme_for_os_scheme``).  Assertions stay at the state level
(settings values, status-bar text, stylesheet strings) — never rendered pixels.

Determinism note: ``_all_theme_names`` appends every ``*.css`` file found in the
user's THEMES_DIR, which on a dev machine holds the seeded built-ins plus any
hand-made themes.  Each test pins ``window._css_themes`` explicitly so the cycle
order under test is exactly the built-in palette order (plus its own custom
entry where that is the point).
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test run trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def test_next_theme_cycles_and_returns_to_start(window):
    """F5 walks every theme in declaration order and a full cycle lands back on
    the starting theme, updating the setting + status bar at each step."""
    from star.themes import BUILT_IN_PALETTES

    window._css_themes = {}  # built-ins only — see module docstring
    names = window._all_theme_names
    assert names == list(BUILT_IN_PALETTES)  # cycle order = declaration order

    window.settings["theme"] = names[0]
    for expected in names[1:] + [names[0]]:
        window._next_theme()
        assert window.settings.get("theme") == expected
        assert window.statusBar().currentMessage() == f"Theme: {expected}"
        assert window.editor.styleSheet(), f"no stylesheet after {expected!r}"
    # Cycling is a deliberate pick — it must stop OS-follow.
    assert window.settings.get("qt_theme_explicit") is True


def test_next_theme_with_unknown_current_restarts_the_cycle(window):
    """A stale/unknown saved theme (e.g. a deleted custom CSS file) must not
    break cycling: it is treated as the first slot and F5 advances from there."""
    window._css_themes = {}
    names = window._all_theme_names
    window.settings["theme"] = "no-such-theme"
    window._next_theme()
    assert window.settings.get("theme") == names[1]


def test_pick_theme_dialog_applies_named_theme(window, monkeypatch):
    """Choosing a theme by name persists it, marks the pick explicit, and
    restyles the editor with that palette; Cancel changes nothing."""
    import star.gui.mixin_display as mixin_display
    from star.themes import BUILT_IN_PALETTES

    window._css_themes = {}
    monkeypatch.setattr(
        mixin_display.QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("nord", True)),
    )
    window._qt_pick_theme()
    assert window.settings.get("theme") == "nord"
    assert window.settings.get("qt_theme_explicit") is True
    sheet = window.editor.styleSheet()
    assert BUILT_IN_PALETTES["nord"]["bg"] in sheet
    assert BUILT_IN_PALETTES["nord"]["fg"] in sheet
    assert window.statusBar().currentMessage() == "Theme: nord"

    monkeypatch.setattr(
        mixin_display.QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("", False)),
    )
    window._qt_pick_theme()
    assert window.settings.get("theme") == "nord"  # cancel keeps the theme


def test_apply_qt_theme_stylesheet_carries_palette_and_font_size(window):
    """The editor stylesheet embeds the theme's bg/fg/sel colors and the
    configured font size (the _set_font ↔ theme-cycle coherence contract)."""
    from star.themes import BUILT_IN_PALETTES

    window._css_themes = {}
    window.settings["font_size"] = 18
    window._apply_qt_theme("high-contrast")
    sheet = window.editor.styleSheet()
    pal = BUILT_IN_PALETTES["high-contrast"]
    for key in ("bg", "fg", "sel"):
        assert pal[key] in sheet, f"palette {key!r} missing from stylesheet"
    assert "font-size: 18pt" in sheet


def test_custom_css_theme_joins_cycle_and_applies(window):
    """A THEMES_DIR *.css theme is appended after the built-ins, is reachable
    by cycling, styles the editor from its parsed palette, and the cycle wraps
    back to the first built-in after it."""
    from star.themes import BUILT_IN_PALETTES

    pal = dict(BUILT_IN_PALETTES["dark"])
    pal["bg"] = "#123456"
    pal["_css"] = "body { background: #123456; }"
    window._css_themes = {"zzz-custom": pal}

    names = window._all_theme_names
    assert names[-1] == "zzz-custom"  # customs come after every built-in

    window.settings["theme"] = names[-2]  # last built-in
    window._next_theme()
    assert window.settings.get("theme") == "zzz-custom"
    assert "#123456" in window.editor.styleSheet()
    window._next_theme()
    assert window.settings.get("theme") == names[0]  # wrapped around


def test_theme_for_os_scheme_mapping():
    """The OS-scheme → theme map: dark/light land on the Galaxy pair,
    high-contrast on the AAA theme, anything unknown on None (keep saved)."""
    from star.themes import theme_for_os_scheme

    assert theme_for_os_scheme("dark") == "galaxy"
    assert theme_for_os_scheme("light") == "galaxy-light"
    assert theme_for_os_scheme("high-contrast") == "high-contrast"
    assert theme_for_os_scheme("unknown") is None
    assert theme_for_os_scheme("") is None
    assert theme_for_os_scheme(" Dark ") == "galaxy"  # tolerant of case/space


def test_follow_os_theme_respects_toggle_and_explicit_choice(window, monkeypatch):
    """_maybe_follow_os_theme adopts the detected scheme's theme only when
    follow is on and the user never picked one deliberately — and the adoption
    itself is never marked explicit, so it keeps tracking the OS."""
    import star.gui.mixin_display as mixin_display

    monkeypatch.setattr(mixin_display, "detect_os_color_scheme", lambda: "light")

    # Follow on, no explicit pick → adopt the mapped theme.
    window.settings["qt_follow_os_theme"] = True
    window.settings["qt_theme_explicit"] = False
    window.settings["theme"] = "galaxy"
    window._maybe_follow_os_theme()
    assert window.settings.get("theme") == "galaxy-light"
    assert bool(window.settings.get("qt_theme_explicit", False)) is False

    # An explicit user pick wins over the OS.
    window.settings["theme"] = "nord"
    window._mark_theme_explicit()
    window._maybe_follow_os_theme()
    assert window.settings.get("theme") == "nord"

    # Follow toggled off → the theme is never touched.
    window.settings["qt_theme_explicit"] = False
    window.settings["qt_follow_os_theme"] = False
    window.settings["theme"] = "galaxy"
    window._maybe_follow_os_theme()
    assert window.settings.get("theme") == "galaxy"

    # Unknown scheme (older Qt / no hint) → saved theme left in place.
    window.settings["qt_follow_os_theme"] = True
    monkeypatch.setattr(mixin_display, "detect_os_color_scheme", lambda: "unknown")
    window._maybe_follow_os_theme()
    assert window.settings.get("theme") == "galaxy"
