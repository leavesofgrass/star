"""UI internationalization (i18n) for star's own chrome (menus, toolbar, docks).

A deliberately small, gettext-style layer: each language is a JSON catalog of
``{english_source: translation}`` pairs stored in ``star/locale/<code>.json``.
``tr(text)`` returns the active language's translation, or the English source
unchanged when no translation exists — so any string that is not yet translated
simply appears in English instead of breaking the UI.

Design goals:

* **No build tooling.**  Unlike Qt's native ``.ts``/``.qm`` workflow (which needs
  ``pylupdate``/``lrelease`` and ships compiled binaries), catalogs are plain
  JSON loaded at runtime.  A contributor adds a language by dropping one file in
  ``star/locale/`` and appending it to :data:`LANGUAGES` — nothing to compile.
* **Graceful degradation.**  English is the *source* language: its msgids are the
  English strings themselves, so it needs no catalog and ``tr()`` is a no-op when
  English is active.  Missing keys in any other catalog fall back to English.
* **Reusable.**  The Qt GUI uses it today; the TUI can adopt the same ``tr()``
  later with no change to this module.

This mirrors star's existing optional-feature philosophy: the feature is always
present, and absent translation data degrades quietly rather than failing.
"""
from ._runtime import *  # noqa: F401,F403

# -----------------------------------------------------------------------------
# Available UI languages
# -----------------------------------------------------------------------------
# (Native display name shown in the picker, ISO-639-1 code = catalog filename
# stem).  English is the source language and intentionally has no catalog file.
# The set starts small and high-quality; community catalogs extend it by adding
# a JSON file here and a row below.
LANGUAGES: List[Tuple[str, str]] = [
    ("English", "en"),
    ("Español", "es"),
    ("Français", "fr"),
    ("Deutsch", "de"),
    ("Português", "pt"),
    ("العربية", "ar"),
]

# Right-to-left scripts.  When one of these is the active UI language the whole
# app is mirrored (Qt.LayoutDirection.RightToLeft) and the reading pane's HTML is
# rendered with ``dir="rtl"``.  ISO-639-1 codes: Arabic, Hebrew, Persian/Farsi,
# Urdu — the four RTL languages a catalog is most likely to target.  Keeping this
# a set (rather than tying it to the shipped catalogs) means direction is correct
# the moment a community catalog for any of these is dropped in.
_RTL_CODES: frozenset = frozenset({"ar", "he", "fa", "ur"})

_LOCALE_DIR = Path(__file__).resolve().parent / "locale"

# Module-level active state.  A single active language is the norm for a desktop
# app; callers switch it with set_language() and read it back with get_language().
_active_code: str = "en"
_active_catalog: Dict[str, str] = {}
_cache: Dict[str, Dict[str, str]] = {}


def available_languages() -> List[Tuple[str, str]]:
    """Return ``[(display_name, code), …]`` for the language picker."""
    return list(LANGUAGES)


def language_codes() -> List[str]:
    """Return just the known ISO codes."""
    return [code for _name, code in LANGUAGES]


def _load_catalog(code: str) -> Dict[str, str]:
    """Load (and cache) the JSON catalog for *code*; ``{}`` on any problem."""
    if code in _cache:
        return _cache[code]
    catalog: Dict[str, str] = {}
    if code and code != "en":
        path = _LOCALE_DIR / f"{code}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # Keep only non-empty string translations; ignore the optional
                # leading "@meta" bookkeeping key contributors may include.
                catalog = {
                    str(k): str(v)
                    for k, v in raw.items()
                    if k != "@meta" and isinstance(v, str) and v
                }
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            catalog = {}
    _cache[code] = catalog
    return catalog


def set_language(code: str) -> str:
    """Activate UI language *code*; unknown codes fall back to ``"en"``.

    Returns the code that was actually applied (so callers can persist the
    normalized value).
    """
    global _active_code, _active_catalog
    code = (code or "en").strip()
    if code not in language_codes():
        code = "en"
    _active_code = code
    _active_catalog = _load_catalog(code)
    return code


def get_language() -> str:
    """Return the active language code."""
    return _active_code


def is_rtl(code: Optional[str] = None) -> bool:
    """Return ``True`` when *code* (default: the active language) is right-to-left.

    RTL scripts (Arabic, Hebrew, Persian, Urdu — see :data:`_RTL_CODES`) require
    the whole UI to be mirrored.  Callers use this to flip Qt's layout direction
    and to set ``dir="rtl"`` on the rendered document; an unknown or LTR code
    (including ``"en"``) returns ``False`` so left-to-right locales are untouched.
    """
    lang = (code if code is not None else _active_code) or ""
    return lang.strip().lower() in _RTL_CODES


def tr(text: str) -> str:
    """Translate *text* into the active UI language (English source fallback).

    ``text`` is the English source string, which doubles as the catalog key.
    When English is active, or the key is missing, the source is returned
    unchanged.
    """
    if not text or _active_code == "en":
        return text
    return _active_catalog.get(text, text)
