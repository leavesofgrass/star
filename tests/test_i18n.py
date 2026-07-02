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


# =============================================================================
# Locale-aware TTS voice fallback (star/tts/manager.py)
# =============================================================================
#
# The manager biases the *default* voice (when the user has not pinned one)
# toward a voice whose language matches the UI language, then English, then the
# engine default.  These tests drive that logic with a fake multilingual
# backend injected through the plugin registry — no real speech engine is
# constructed.

from star import tts  # noqa: E402
from star.plugins import override_plugins  # noqa: E402
from star.settings import Settings  # noqa: E402

# A small multilingual voice roster covering the shipped UI languages, with the
# several `lang`-tag spellings real engines use (bare code, locale, and one that
# only names the language in `name`/`id`, exercising the name→code sniffer).
_FAKE_VOICES = [
    {"id": "v-en", "name": "English (US)", "lang": "en-US"},
    {"id": "v-es", "name": "Spanish (Spain)", "lang": "es_ES"},
    {"id": "v-fr", "name": "Voix française", "lang": "fr"},
    {"id": "v-de", "name": "Deutsch Stimme", "lang": ""},  # lang only in name
]


def _voice_backend_cls():
    class _VoiceFake(tts.TTSBackend):
        name = "voicefake"
        priority = 20
        _avail = True

        def __init__(self, *args, **kwargs):
            self.voice_set = None

        def available(self):
            return True

        def speak(self, text, on_word=None, on_done=None):
            if on_done:
                on_done()

        def stop(self):
            pass

        def set_rate(self, wpm):
            pass

        def set_volume(self, vol):
            pass

        def set_voice(self, voice_id):
            self.voice_set = voice_id

        def list_voices(self):
            return list(_FAKE_VOICES)

    return _VoiceFake


def _voice_manager(ui_language="en", tts_voice="", prefer_voice=""):
    s = Settings()
    s["tts_backend"] = "voicefake"
    s["tts_voice"] = tts_voice
    s["tts_prefer_voice"] = prefer_voice
    s["ui_language"] = ui_language
    return tts.TTSManager(s)


def test_tts_picks_voice_matching_ui_language():
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="es")
        assert mgr._backend.voice_set == "v-es"
        assert mgr.preferred_language == "es"


def test_tts_matches_language_by_locale_tag():
    # "es_ES" must normalise to "es" and still match.
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="es")
        assert mgr._backend.voice_set == "v-es"


def test_tts_matches_language_by_voice_name_when_no_lang_tag():
    # The German voice carries no lang tag; the name→code sniffer must find it.
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="de")
        assert mgr._backend.voice_set == "v-de"


def test_tts_english_ui_leaves_default_voice_untouched():
    # English / no preference must not force a language voice (historical
    # behaviour): the default-voice resolver ran, but no language override.
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="en")
        assert mgr._backend.voice_set is None
        assert mgr.preferred_language == ""


def test_tts_no_matching_voice_keeps_default():
    # UI language with no matching voice must fall back (no override applied).
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="pt")  # no Portuguese voice in roster
        assert mgr._backend.voice_set is None


def test_tts_explicit_user_voice_always_wins():
    # A pinned tts_voice must never be overridden by the language preference.
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="es", tts_voice="my-custom-voice")
        assert mgr._backend.voice_set is None


def test_tts_set_language_reresolves_voice():
    with override_plugins(backends=[_voice_backend_cls()]):
        mgr = _voice_manager(ui_language="en")
        assert mgr._backend.voice_set is None
        mgr.set_language("fr")
        assert mgr.preferred_language == "fr"
        assert mgr._backend.voice_set == "v-fr"
        # Switching back to English clears the preference but leaves the last
        # applied voice in place (we only ever set a voice, never unset it).
        mgr.set_language("en")
        assert mgr.preferred_language == ""


def test_voice_lang_normalisation():
    vl = tts.TTSManager._voice_lang
    assert vl({"lang": "es_ES"}) == "es"
    assert vl({"lang": "fr-FR"}) == "fr"
    assert vl({"lang": "en"}) == "en"
    assert vl({"lang": "", "name": "Deutsch Stimme"}) == "de"
    # The name/id sniffer matches spelled-out language *words* only, not bare
    # ISO codes, so a code embedded in an id ("mbrola-en1") does NOT match —
    # this is deliberate: substring-matching "en" would over-match ("generic").
    assert vl({"lang": "", "name": "", "id": "english-us"}) == "en"
    assert vl({"lang": "", "name": "", "id": "mbrola-en1"}) == ""
    assert vl({"lang": "", "name": "Robot"}) == ""
