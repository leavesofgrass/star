"""Right-to-left (RTL) internationalization groundwork — Area 8.

star ships left-to-right by default.  These tests cover the RTL plumbing added
for Arabic/Hebrew/Persian/Urdu locales:

* :func:`star.i18n.is_rtl` correctly classifies codes.
* Selecting an RTL UI language flips the *whole application* to
  ``Qt.LayoutDirection.RightToLeft`` (and switching back restores LTR).
* The rendered document carries ``dir="rtl"`` under an RTL locale and is
  byte-for-byte free of it under an LTR locale (LTR stays visually identical).
* The i18n parity guard is still green under the chosen catalog option
  (Option B: a documented proof-catalog exemption; es/fr/de/pt strict).

The GUI is imported under the offscreen QPA, like tests/test_gui_smoke.py.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a test trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))


# ── is_rtl (pure logic — no Qt required) ──────────────────────────────────
def test_is_rtl_classifies_codes():
    from star.i18n import is_rtl

    for rtl in ("ar", "he", "fa", "ur", "AR", " ar ", "He"):
        assert is_rtl(rtl) is True, f"{rtl!r} should be RTL"
    # An explicit LTR (or unknown / empty) code is never RTL.  ``None`` is not
    # tested here: it means "use the active language" (see the next test).
    for ltr in ("en", "es", "fr", "de", "pt", "", "xx"):
        assert is_rtl(ltr) is False, f"{ltr!r} should be LTR"


def test_is_rtl_uses_active_language_by_default():
    from star import i18n

    prev = i18n.get_language()
    try:
        i18n.set_language("ar")
        assert i18n.is_rtl() is True
        i18n.set_language("en")
        assert i18n.is_rtl() is False
    finally:
        i18n.set_language(prev)


def test_arabic_is_a_selectable_language():
    """The RTL proof language appears in the Interface Language picker."""
    from star.i18n import available_languages

    codes = [code for _disp, code in available_languages()]
    assert "ar" in codes


# ── Qt layout direction (offscreen GUI) ───────────────────────────────────
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
def window(qapp):
    from star import i18n
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    prev_lang = i18n.get_language()
    win = StarWindow(Settings())
    yield win
    win.close()
    # Restore global i18n + app direction so one test can't leak into the next.
    i18n.set_language(prev_lang)
    try:
        from PyQt6.QtCore import Qt

        qapp.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    except Exception:
        pass


def _direction(qapp):
    from PyQt6.QtCore import Qt

    return qapp.layoutDirection(), Qt.LayoutDirection.RightToLeft, Qt.LayoutDirection.LeftToRight


def test_selecting_rtl_language_mirrors_the_app(window, qapp):
    """Switching to an RTL language sets the app to RightToLeft, and switching
    back to an LTR language restores LeftToRight."""
    cur, RTL, LTR = _direction(qapp)
    # Baseline: the default English UI is left-to-right.
    assert qapp.layoutDirection() == LTR

    window._set_ui_language("ar")
    assert qapp.layoutDirection() == RTL

    window._set_ui_language("en")
    assert qapp.layoutDirection() == LTR


def test_startup_applies_layout_direction(window, qapp):
    """_apply_layout_direction is idempotent and reads the active language."""
    from star import i18n

    _cur, RTL, LTR = _direction(qapp)
    i18n.set_language("ar")
    window._apply_layout_direction()
    assert qapp.layoutDirection() == RTL
    i18n.set_language("en")
    window._apply_layout_direction()
    assert qapp.layoutDirection() == LTR


def test_document_render_carries_dir_rtl_under_rtl_locale(window):
    """_md_to_html tags the document dir=rtl for an RTL locale, and omits it
    entirely for an LTR locale (so LTR HTML is unchanged)."""
    from star import i18n

    md = "# Heading\n\nHello world."
    i18n.set_language("en")
    ltr_html = window._md_to_html(md)
    assert 'dir="rtl"' not in ltr_html

    i18n.set_language("ar")
    rtl_html = window._md_to_html(md)
    assert 'dir="rtl"' in rtl_html
    # The mirroring is applied at the document root and body, not the content.
    assert "<body dir=\"rtl\">" in rtl_html

    i18n.set_language("en")


def test_ltr_render_is_identical_before_and_after_rtl_support(window):
    """An English-locale render is free of any dir attribute — RTL support must
    not perturb the LTR output that every existing test/user relies on."""
    from star import i18n

    i18n.set_language("en")
    html = window._md_to_html("Some **bold** text.")
    assert "dir=" not in html


# ── Parity guard is still green (Option B) ────────────────────────────────
def test_parity_guard_still_enforces_production_catalogs():
    """es/fr/de/pt remain at strict all-keys parity; ar (proof) is exempt but
    still validated for its core.  This re-runs the catalog guard's own checks
    so this file fails loudly if the exemption ever leaked into the strict set.
    """
    from tests import test_i18n_catalog as guard

    # Production catalogs: strictly parity-enforced, ar not among them.
    assert guard._LANGS == ("es", "fr", "de", "pt")
    assert "ar" not in guard._LANGS
    assert "ar" in guard._PROOF_CATALOGS

    # The strict checks pass over the production catalogs …
    guard.test_catalogs_are_at_key_parity()
    guard.test_every_static_code_key_is_translated()
    # … and the proof catalog satisfies its (looser) contract.
    guard.test_proof_catalog_translates_core("ar")
    guard.test_proof_catalog_keys_are_known_source_strings("ar")
