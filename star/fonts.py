"""On-demand fetch & cache of dyslexia / low-vision reading fonts (all OFL).

star does not bundle font binaries; instead the files are downloaded from their
upstream GitHub repositories into star's cache dir the first time the reader
picks a reading font (Preferences ▸ Display ▸ Reading font). This keeps them
*optional* assets — fetched only when wanted, never shipped in the wheel/pyz.

Three families are supported, each an openly-licensed typeface tuned for
legibility:

* **OpenDyslexic** — purpose-built for dyslexic readers (weighted bottoms,
  distinct letterforms).  SIL OFL 1.1.
* **Atkinson Hyperlegible** — Braille Institute; maximizes character distinction
  for low-vision readers.  SIL OFL 1.1.
* **Lexend** — variable-friendly family shown to improve reading proficiency.
  SIL OFL 1.1.

Everything here is best-effort and offline-safe: any network or IO error is
logged and swallowed, so callers always get a (possibly empty) list of paths and
never see an exception. If a fetch fails (offline), star falls back to any
system-installed family, or the user's chosen font.

The OpenDyslexic module-level API (:data:`FONT_URLS`, :func:`family_name`,
:func:`is_fetched`, :func:`fetch`, …) is preserved unchanged for backward
compatibility; the generic :func:`fetch_font` / :func:`is_font_fetched` /
:func:`font_family` operate on any registered family by key.
"""
from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import NamedTuple

from ._runtime import CACHE_DIR

_log = logging.getLogger("star.fonts")


class FontSpec(NamedTuple):
    """A fetchable reading-font family.

    ``key``       stable identifier used by settings + the chooser.
    ``family``    the QFont family name the files register under.
    ``urls``      raw file URLs (pinned to immutable refs).
    ``probe``     the basename whose presence in the cache means "fetched".
    """

    key: str
    family: str
    urls: list[str]
    probe: str


# ── OpenDyslexic (SIL OFL 1.1) ───────────────────────────────────────────────
# Pinned to an immutable commit SHA rather than a branch (upstream renamed its
# default branch and has no tagged releases). Files live under compiled/ on
# antijingoist/opendyslexic.
_FONT_REF = "1824da5c0e41dc3e13ffc7f3a636dcaf695d61b7"
_FONT_BASE = f"https://raw.githubusercontent.com/antijingoist/opendyslexic/{_FONT_REF}/compiled"
FONT_URLS: list[str] = [
    f"{_FONT_BASE}/OpenDyslexic-Regular.otf",
    f"{_FONT_BASE}/OpenDyslexic-Bold.otf",
    f"{_FONT_BASE}/OpenDyslexic-Italic.otf",
    f"{_FONT_BASE}/OpenDyslexic-BoldItalic.otf",
]

# ── Atkinson Hyperlegible (Braille Institute, SIL OFL 1.1) ───────────────────
# Pinned to an immutable commit of googlefonts/atkinson-hyperlegible.
_ATKINSON_REF = "c14451f32cd7d15b8fae441338f41c3bcebc74c4"
_ATKINSON_BASE = (
    "https://raw.githubusercontent.com/googlefonts/atkinson-hyperlegible/"
    f"{_ATKINSON_REF}/fonts/ttf"
)
ATKINSON_URLS: list[str] = [
    f"{_ATKINSON_BASE}/AtkinsonHyperlegible-Regular.ttf",
    f"{_ATKINSON_BASE}/AtkinsonHyperlegible-Bold.ttf",
    f"{_ATKINSON_BASE}/AtkinsonHyperlegible-Italic.ttf",
    f"{_ATKINSON_BASE}/AtkinsonHyperlegible-BoldItalic.ttf",
]

# ── Lexend (SIL OFL 1.1) ─────────────────────────────────────────────────────
# The static Regular/Bold instances of the variable family, pinned to an
# immutable commit of the googlefonts/lexend repository.
_LEXEND_REF = "cd26b9c2538d758138c20c3d2f10362ed613854b"
_LEXEND_BASE = (
    "https://raw.githubusercontent.com/googlefonts/lexend/"
    f"{_LEXEND_REF}/fonts/lexend/ttf"
)
LEXEND_URLS: list[str] = [
    f"{_LEXEND_BASE}/Lexend-Regular.ttf",
    f"{_LEXEND_BASE}/Lexend-Bold.ttf",
]

# Registry of every fetchable family, keyed by the stable identifier persisted in
# settings (``qt_reading_font``).  "default" is intentionally absent — it means
# "no override" and never triggers a fetch.
FONTS: dict[str, FontSpec] = {
    "opendyslexic": FontSpec(
        "opendyslexic", "OpenDyslexic", FONT_URLS, "OpenDyslexic-Regular.otf"
    ),
    "atkinson": FontSpec(
        "atkinson",
        "Atkinson Hyperlegible",
        ATKINSON_URLS,
        "AtkinsonHyperlegible-Regular.ttf",
    ),
    "lexend": FontSpec("lexend", "Lexend", LEXEND_URLS, "Lexend-Regular.ttf"),
}


def family_name() -> str:
    """The font family name registered by the OpenDyslexic files.

    Retained for backward compatibility; new code should prefer
    :func:`font_family` with a key.
    """
    return "OpenDyslexic"


def font_family(key: str) -> str:
    """The QFont family name for a registered font *key* ("" if unknown)."""
    spec = FONTS.get(key)
    return spec.family if spec else ""


def font_dir() -> Path:
    """Return (and create) the directory where fetched fonts are cached."""
    path = CACHE_DIR / "fonts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetched_paths() -> list[Path]:
    """Every fetched font file in :func:`font_dir` (``*.otf`` and ``*.ttf``)."""
    try:
        return sorted(
            p for ext in ("*.otf", "*.ttf") for p in font_dir().glob(ext)
        )
    except OSError:
        return []


def is_fetched() -> bool:
    """True if the OpenDyslexic Regular file is present (back-compat helper)."""
    return is_font_fetched("opendyslexic")


def is_font_fetched(key: str) -> bool:
    """True if the probe file for font *key* is present in the cache."""
    spec = FONTS.get(key)
    if spec is None:
        return False
    try:
        return (font_dir() / spec.probe).exists()
    except OSError:
        return False


def _fetch_urls(urls: list[str], timeout: int, force: bool) -> None:
    """Download any missing files from *urls* into the cache (best-effort)."""
    directory = font_dir()
    for url in urls:
        target = directory / Path(url).name
        if target.exists() and not force:
            continue
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
                data = response.read()
            target.write_bytes(data)
        except Exception:  # noqa: BLE001 — offline-safe: log and skip.
            _log.warning("failed to fetch font from %s", url, exc_info=True)
            continue


def fetch(timeout: int = 20, force: bool = False) -> list[Path]:
    """Fetch any missing OpenDyslexic files and return the cached fonts present.

    Back-compat wrapper around :func:`fetch_font` for ``"opendyslexic"``.  For
    each URL in :data:`FONT_URLS`, the target is ``font_dir()/basename``; it is
    downloaded when missing (or *force* is true). Any exception on a single URL
    is logged and skipped — this function never raises. Callers should treat an
    empty return as "unavailable (offline?)".
    """
    return fetch_font("opendyslexic", timeout=timeout, force=force)


def fetch_font(key: str, timeout: int = 20, force: bool = False) -> list[Path]:
    """Fetch any missing files for font *key* and return all cached font paths.

    Mirrors :func:`fetch` but works for any registered family.  Offline-safe and
    idempotent; an unknown *key* is a no-op.  Returns :func:`fetched_paths` so
    callers can register whatever is present.
    """
    spec = FONTS.get(key)
    if spec is not None:
        _fetch_urls(spec.urls, timeout, force)
    return fetched_paths()
