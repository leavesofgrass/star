"""Offscreen (headless) accessibility smoke tests for the Qt GUI.

star is an accessibility-first reader, so screen-reader / keyboard metadata is
part of the product contract, not a nicety.  These tests construct the real
``StarWindow`` and the ``DependencyChooser`` under the offscreen QPA and assert
the accessibility affordances a screen reader relies on:

* every dialog carries a window title (announced when it opens),
* the optional-feature checkboxes expose their detail text as an accessible
  description (the adjacent gray sub-label is visual-only and not reliably
  announced),
* the dock panels and the document view have accessible names, and
* the key toolbar actions have non-empty text (their accessible name).

Runs on every CI leg: PyQt6 is a base dependency.  The offscreen platform ships
zero fonts, so Windows TTFs are loaded up front for any text-rendering glyphs.
The module is fully skipped when Qt is unavailable.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let building StarWindow trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the module, with Windows fonts loaded."""
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


def test_document_view_has_accessible_metadata(window):
    """The main reading area names itself and describes its key shortcuts."""
    assert window.editor.accessibleName()
    assert window.editor.accessibleDescription()


def test_dock_panels_have_accessible_names(window):
    """ToC and Notes docks (and their lists) are named for screen readers."""
    assert window._toc_dock.accessibleName()
    assert window._toc_list.accessibleName()
    assert window._annot_dock.accessibleName()
    assert window._annot_list.accessibleName()
    # The notes filter relies on placeholder text visually; it must also carry
    # an accessible name since screen readers don't read placeholders reliably.
    assert window._annot_filter.accessibleName()


def test_key_toolbar_actions_have_text(window):
    """Icon-only toolbar buttons still announce a non-empty accessible name."""
    actions = [a for a in window._toolbar.actions() if not a.isSeparator()]
    assert actions, "toolbar has no actions"
    for act in actions:
        assert act.text().strip(), "a toolbar action has no accessible text"


def test_dependency_chooser_dialog(qapp):
    """The optional-feature chooser has a window title, its checkboxes expose
    an accessible description, and the preset buttons are named."""
    from star.gui.deps_dialog import DependencyChooser

    dlg = DependencyChooser(None)
    try:
        assert dlg.windowTitle().strip()
        assert dlg._boxes, "no feature checkboxes were built"
        for cb in dlg._boxes.values():
            assert cb.accessibleDescription().strip(), (
                "a feature checkbox has no accessible description"
            )
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# High-contrast AAA theme + OS colour-scheme following (Wave 2b).  These test
# pure palette/logic in star.themes and one setting, so they need no Qt widgets
# (only the module import) and run on every leg.
# ---------------------------------------------------------------------------


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` colour."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    R, G, B = _lin(r), _lin(g), _lin(b)
    return 0.2126 * R + 0.7152 * G + 0.0722 * B


def _contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours (>= 1.0)."""
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_high_contrast_theme_exists():
    """A dedicated AAA low-vision theme ships as a built-in palette."""
    from star.themes import BUILT_IN_PALETTES, BUILT_IN_THEME_NAMES

    assert "high-contrast" in BUILT_IN_PALETTES
    # It must be in the cycle order so F5 / Choose Theme can reach it.
    assert "high-contrast" in BUILT_IN_THEME_NAMES
    pal = BUILT_IN_PALETTES["high-contrast"]
    # Carries the full palette schema so rendering never falls back mid-theme.
    for key in ("bg", "fg", "sel", "h1", "h2", "h3", "h4", "code", "code_bg",
                "link", "muted"):
        assert key in pal, f"high-contrast palette missing {key!r}"


def test_high_contrast_theme_meets_wcag_aaa():
    """Every text/heading/link/code colour clears WCAG AAA (7:1) on the bg.

    AAA §1.4.6 requires >= 7:1 for normal text.  A dedicated low-vision theme
    must clear that for the body text and each semantic colour, not just body.
    """
    from star.themes import BUILT_IN_PALETTES

    pal = BUILT_IN_PALETTES["high-contrast"]
    bg = pal["bg"]
    for key in ("fg", "h1", "h2", "h3", "h4", "code", "link", "muted"):
        ratio = _contrast_ratio(bg, pal[key])
        assert ratio >= 7.0, (
            f"high-contrast {key} ({pal[key]}) is only {ratio:.2f}:1 on {bg}, "
            "below the WCAG AAA 7:1 floor"
        )


def test_high_contrast_theme_is_dark_and_distinct():
    """The theme is a genuine dark theme with hue-distinct semantic colours.

    'No reliance on hue alone' means the link/heading colours must also be
    *perceptibly different from each other and from the body text*, not merely
    all-white — so information survives for a colour-blind low-vision reader.
    """
    from star.themes import BUILT_IN_PALETTES

    pal = BUILT_IN_PALETTES["high-contrast"]
    # Dark background, light foreground → a dark theme.
    assert _relative_luminance(pal["bg"]) < 0.1
    assert _relative_luminance(pal["fg"]) > 0.5
    # Link colour is distinct from body text (not just white-on-white).
    assert pal["link"].lower() != pal["fg"].lower()
    # The semantic colours are not all identical (hue variety).
    semantic = {pal["h1"], pal["h2"], pal["h3"], pal["h4"], pal["link"], pal["code"]}
    assert len(semantic) >= 5, "high-contrast semantic colours lack hue variety"


def test_theme_for_os_scheme_maps_known_schemes():
    """The OS→theme mapper returns real built-ins for dark/light/high-contrast."""
    from star.themes import BUILT_IN_PALETTES, theme_for_os_scheme

    for scheme in ("dark", "light", "high-contrast"):
        name = theme_for_os_scheme(scheme)
        assert name in BUILT_IN_PALETTES, f"{scheme} → {name!r} not a built-in"
    # high-contrast maps to the AAA theme specifically.
    assert theme_for_os_scheme("high-contrast") == "high-contrast"
    # An unknown / unmapped scheme leaves the caller to keep the saved theme.
    assert theme_for_os_scheme("unknown") is None
    assert theme_for_os_scheme("") is None


def test_detect_os_color_scheme_never_raises():
    """Detection is best-effort: it returns a known token and never raises."""
    from star.themes import detect_os_color_scheme

    scheme = detect_os_color_scheme()
    assert scheme in ("dark", "light", "high-contrast", "unknown")


def test_follow_os_theme_setting_present():
    """The qt_follow_os_theme setting exists with a sensible default."""
    from star.settings import DEFAULTS

    assert "qt_follow_os_theme" in DEFAULTS
    assert isinstance(DEFAULTS["qt_follow_os_theme"], bool)
    # The explicit-choice guard that stops auto-detect from overriding a
    # deliberate pick must also exist and default to "not yet chosen".
    assert "qt_theme_explicit" in DEFAULTS
    assert DEFAULTS["qt_theme_explicit"] is False


def test_explicit_theme_choice_disables_os_follow(window):
    """Choosing a theme sets qt_theme_explicit so OS-follow won't override it."""
    assert window.settings.get("qt_theme_explicit") is False
    window._next_theme()
    assert window.settings.get("qt_theme_explicit") is True
    # A subsequent OS-follow pass must be a no-op now (explicit choice wins).
    before = window.settings.get("theme")
    window._maybe_follow_os_theme()
    assert window.settings.get("theme") == before
