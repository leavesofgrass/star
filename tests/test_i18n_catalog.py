"""Guard the i18n catalogs against silent drift.

star ships four UI-chrome translation catalogs (``star/locale/{es,fr,de,pt}.json``).
``tr()`` falls back to the English source for any missing key, so a lagging
catalog degrades quietly rather than crashing — which is exactly why drift is
easy to miss.  These tests fail CI the moment the four catalogs stop agreeing
on their key set, or when a known toolbar / optional-features string is dropped
from one language.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

_STAR_DIR = Path(__file__).resolve().parent.parent / "star"
_LOCALE_DIR = _STAR_DIR / "locale"
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
    # first-run language picker (deps_dialog.py)
    "Interface language:",
    "Interface language",
    "Choose the language for menus, toolbar, and messages.",
    # TUI chrome (status line + prompts) — the i18n audit's TUI wrap
    "No document",
    "Line",
    "Search: ",
    "Go to line: ",
    "Terminal too small (need 20×8 minimum)",
)

# Source strings that are intentionally left English-only in the catalogs.
# Encoded as an explicit allowlist so future additions here are a conscious act,
# not accidental drift.  (Currently empty: every tr()-wrapped UI-chrome string
# with a *static* literal is translated in all four catalogs.)  Add a key here
# only when a source-only string is deliberate — the reason belongs in a comment.
_UNTRANSLATED_ALLOWLIST: frozenset[str] = frozenset()


def _load(lang: str) -> dict:
    raw = json.loads((_LOCALE_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{lang}.json is not a JSON object"
    return raw


def _keys(lang: str) -> set[str]:
    # "@meta" is bookkeeping, not a translatable key (see i18n._load_catalog).
    return {k for k in _load(lang) if k != "@meta"}


def _static_str(node: ast.AST) -> str | None:
    """Return the fully-static string value of *node*, else ``None``.

    Handles a bare string constant and ``+``-concatenation of string constants
    (Python already folds *adjacent* literals into one Constant, so this only
    needs to cover the explicit ``a + b`` form the codebase uses for long
    tooltips).  Anything with an f-string, a variable, or a ``.format(...)`` is
    treated as non-static and skipped — those keys, when present, are guarded
    instead by the parity/required-key tests.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_str(node.left)
        right = _static_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _code_tr_keys() -> dict[str, str]:
    """Every static ``tr("literal")`` key across ``star/`` → first source file.

    Only the *first positional argument* of a call to a function named ``tr``
    is considered a key (matching both ``tr(...)`` and ``x.tr(...)``).  Keys
    reached via a variable (menu-spec tuples, ``tr(label)`` loops) are invisible
    to this static scan by design — they are covered by the parity guard.
    """
    keys: dict[str, str] = {}
    for py in sorted(_STAR_DIR.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            fn = node.func
            name = (
                fn.id if isinstance(fn, ast.Name)
                else fn.attr if isinstance(fn, ast.Attribute)
                else None
            )
            if name != "tr":
                continue
            val = _static_str(node.args[0])
            if val:  # skip empty string and non-static args
                keys.setdefault(val, str(py.relative_to(_STAR_DIR)))
    return keys


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


def test_every_static_code_key_is_translated() -> None:
    """Every static ``tr("literal")`` in star/ must exist in all four catalogs.

    This is the guard the i18n audit adds: when a developer wraps a new UI
    string in ``tr()`` but forgets to add its translation, this test names the
    key and the file it came from so the catalogs never silently drift behind
    the code.  Intentional source-only strings go in ``_UNTRANSLATED_ALLOWLIST``.
    """
    code_keys = _code_tr_keys()
    per_lang = {lang: _keys(lang) for lang in _LANGS}
    problems = []
    for key, src in sorted(code_keys.items()):
        if key in _UNTRANSLATED_ALLOWLIST:
            continue
        absent = [lang for lang in _LANGS if key not in per_lang[lang]]
        if absent:
            problems.append(f"{key!r} (from {src}) missing from: {', '.join(absent)}")
    assert not problems, (
        "code strings wrapped in tr() but not translated in every catalog "
        "(add the translation, or allowlist an intentional source-only key):\n  "
        + "\n  ".join(problems)
    )


def test_code_key_extractor_finds_known_keys() -> None:
    """Sanity-check the extractor itself so a broken scan can't pass vacuously."""
    code_keys = _code_tr_keys()
    assert len(code_keys) >= 50, f"extractor found only {len(code_keys)} keys"
    # A couple of strings we know are statically wrapped somewhere in star/.
    assert "star — Optional Features" in code_keys
    assert "Install selected" in code_keys


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
