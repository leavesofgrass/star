"""Tests for the UI internationalization (i18n) layer.

Pure-logic tests — no Qt required.  They exercise star.i18n directly and audit
the shipped JSON catalogs in star/locale/.
"""
import json
from pathlib import Path

import pytest

from star import i18n

LOCALE_DIR = Path(i18n.__file__).resolve().parent / "locale"

# Menu-bar titles that every shipped (non-English) catalog must translate — the
# most visible chrome.  A missing one would show an English word in an otherwise
# localized menu bar, so we treat it as a regression.
CORE_MENU_TITLES = [
    "File", "Edit", "View", "Highlight", "Notes", "Speech",
    "Navigate", "Citations", "Tools", "Help",
]


# =============================================================================
# set_language / get_language / tr
# =============================================================================


def setup_function(_fn):
    # Each test starts from a known state (English).
    i18n.set_language("en")


def test_default_language_is_english():
    assert i18n.get_language() == "en"


def test_tr_is_identity_in_english():
    assert i18n.tr("File") == "File"
    assert i18n.tr("Some untranslated string") == "Some untranslated string"


def test_tr_empty_string():
    assert i18n.tr("") == ""


def test_set_language_returns_applied_code():
    assert i18n.set_language("es") == "es"
    assert i18n.get_language() == "es"


def test_unknown_language_falls_back_to_english():
    assert i18n.set_language("xx") == "en"
    assert i18n.get_language() == "en"
    assert i18n.tr("File") == "File"


def test_none_language_falls_back_to_english():
    assert i18n.set_language(None) == "en"  # type: ignore[arg-type]


def test_spanish_translation():
    i18n.set_language("es")
    assert i18n.tr("File") == "Archivo"
    assert i18n.tr("Quit") == "Salir"
    assert i18n.tr("Reading Aids") == "Ayudas de lectura"


def test_missing_key_falls_back_to_source():
    i18n.set_language("es")
    # A string with no catalog entry returns the English source unchanged.
    assert i18n.tr("This string is intentionally untranslated") == (
        "This string is intentionally untranslated"
    )


def test_switching_language_changes_output():
    i18n.set_language("fr")
    assert i18n.tr("Tools") == "Outils"
    i18n.set_language("de")
    assert i18n.tr("Tools") == "Werkzeuge"
    i18n.set_language("pt")
    assert i18n.tr("Tools") == "Ferramentas"
    i18n.set_language("en")
    assert i18n.tr("Tools") == "Tools"


def test_language_codes_and_available_languages_agree():
    codes = i18n.language_codes()
    assert codes == [c for _name, c in i18n.available_languages()]
    assert "en" in codes
    # No duplicate codes.
    assert len(codes) == len(set(codes))


def test_english_has_no_catalog_file():
    # English is the source language; there must be no en.json.
    assert not (LOCALE_DIR / "en.json").exists()


# =============================================================================
# Catalog file audits
# =============================================================================


# Every non-English language declared in LANGUAGES must ship a catalog.
NON_EN_CODES = [c for _name, c in i18n.available_languages() if c != "en"]


@pytest.mark.parametrize("code", NON_EN_CODES)
def test_catalog_file_exists(code):
    assert (LOCALE_DIR / f"{code}.json").exists(), f"missing locale/{code}.json"


@pytest.mark.parametrize("code", NON_EN_CODES)
def test_catalog_is_flat_string_map(code):
    raw = json.loads((LOCALE_DIR / f"{code}.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    for k, v in raw.items():
        assert isinstance(k, str), f"non-string key in {code}.json: {k!r}"
        assert isinstance(v, str), f"non-string value in {code}.json for {k!r}"
        # No empty translations (they would just mask the English fallback).
        if k != "@meta":
            assert v.strip(), f"empty translation in {code}.json for {k!r}"


@pytest.mark.parametrize("code", NON_EN_CODES)
def test_catalog_covers_core_menu_titles(code):
    catalog = i18n._load_catalog(code)
    missing = [t for t in CORE_MENU_TITLES if t not in catalog]
    assert not missing, f"{code}.json missing core titles: {missing}"


@pytest.mark.parametrize("code", NON_EN_CODES)
def test_catalog_translations_differ_from_source_for_core(code):
    # Guard against a wholesale-copied catalog.  Some titles are legitimate
    # cognates ('Notes'/'Citations' in French), so only require that a clear
    # majority of the core titles actually differ from the English source.
    catalog = i18n._load_catalog(code)
    identical = [t for t in CORE_MENU_TITLES if catalog.get(t) == t]
    assert len(identical) <= len(CORE_MENU_TITLES) // 3, (
        f"{code}.json leaves too many core titles untranslated: {identical}"
    )


def test_meta_key_is_ignored_by_loader():
    # "@meta" is documentation only and must never leak into translations.
    for code in NON_EN_CODES:
        catalog = i18n._load_catalog(code)
        assert "@meta" not in catalog


# =============================================================================
# Settings integration
# =============================================================================


def test_settings_default_ui_language():
    from star.settings import DEFAULTS
    assert DEFAULTS["ui_language"] == "en"
