"""Guard the i18n catalogs against silent drift.

star ships four UI-chrome translation catalogs (``star/locale/{es,fr,de,pt}.json``).
``tr()`` falls back to the English source for any missing key, so a lagging
catalog degrades quietly rather than crashing — which is exactly why drift is
easy to miss.  These tests fail CI the moment the four catalogs stop agreeing
on their key set, or when a known toolbar / optional-features string is dropped
from one language.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_LOCALE_DIR = Path(__file__).resolve().parent.parent / "star" / "locale"
_LANGS = ("es", "fr", "de", "pt")

# The runtime value of the "Toggle Contents panel" tooltip contains two literal
# backslashes (the source writes ``Ctrl+\\\\`` which Python collapses to two).
_CONTENTS_TOGGLE = "Toggle Contents panel (Ctrl+\\\\)"

# A representative slice of the strings this catalog set must always translate:
# the new icon-toolbar accessible labels + tooltips and the optional-features
# chooser (star/gui/deps_dialog.py + the Tools "Install Optional Features…"
# entry).  If any of these is missing from any language, drift has crept in.
_REQUIRED_KEYS = (
    # optional-features chooser / deps dialog
    "star — Optional Features",
    "Install Optional Features…",
    "Install selected",
    "Not now",
    "Thin  (~40 MB)",
    "All  (~150 MB)   — recommended",
    "Selected optional features are already installed.",
    "Installing {n} optional package(s) in the background…",
    "Pick which optional capabilities to download (OCR, dictionary, graph, speech-to-text, …)",
    "installed",
    # icon-toolbar accessible labels
    "Open",
    "Play / Pause",
    "Slower",
    "Faster",
    "Previous Sentence",
    "Voice",
    "Speech Cursor",
    "Clear Highlights",
    "Edit Mode",
    "Contents",
    "Add Note",
    "Reading Level",
    # a few toolbar tooltips (with intact shortcut hints / placeholders)
    "Open a file (Ctrl+O)",
    "Play / pause speech (Space)",
    _CONTENTS_TOGGLE,
)

# Source strings that are intentionally left English-only in the catalogs.
# Encoded as an explicit allowlist so future additions here are a conscious act,
# not accidental drift.  (Currently empty: every tr()-wrapped UI-chrome string
# is translated in all four catalogs.)
_UNTRANSLATED_ALLOWLIST: frozenset[str] = frozenset()


def _load(lang: str) -> dict:
    raw = json.loads((_LOCALE_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{lang}.json is not a JSON object"
    return raw


def _keys(lang: str) -> set[str]:
    # "@meta" is bookkeeping, not a translatable key (see i18n._load_catalog).
    return {k for k in _load(lang) if k != "@meta"}


def test_all_catalogs_load_and_are_nonempty() -> None:
    for lang in _LANGS:
        assert _keys(lang), f"{lang}.json has no translatable keys"


def test_catalogs_are_at_key_parity() -> None:
    """All four catalogs must share an identical key set.

    Any key in one language but not another means that language silently
    falls back to English for that string — the drift this guard prevents.
    """
    per_lang = {lang: _keys(lang) for lang in _LANGS}
    union = set().union(*per_lang.values())
    problems = []
    for lang in _LANGS:
        missing = union - per_lang[lang] - _UNTRANSLATED_ALLOWLIST
        if missing:
            problems.append(f"{lang} is missing {len(missing)} key(s): {sorted(missing)}")
    assert not problems, "\n".join(problems)


def test_no_empty_translations() -> None:
    for lang in _LANGS:
        cat = _load(lang)
        empties = [k for k, v in cat.items() if k != "@meta" and (not isinstance(v, str) or not v.strip())]
        assert not empties, f"{lang}.json has empty translations: {empties}"


@pytest.mark.parametrize("lang", _LANGS)
def test_required_ui_keys_present(lang: str) -> None:
    """The toolbar + optional-features chrome must be translated everywhere."""
    have = _keys(lang)
    missing = [k for k in _REQUIRED_KEYS if k not in have]
    assert not missing, f"{lang}.json is missing required UI keys: {missing}"


@pytest.mark.parametrize("lang", _LANGS)
def test_placeholder_preserved(lang: str) -> None:
    """The ``{n}`` placeholder must survive translation intact."""
    key = "Installing {n} optional package(s) in the background…"
    val = _load(lang)[key]
    assert "{n}" in val, f"{lang}.json dropped the {{n}} placeholder: {val!r}"
