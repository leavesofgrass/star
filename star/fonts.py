"""On-demand fetch & cache of the OpenDyslexic font (SIL OFL 1.1).

OpenDyslexic is a free, openly-licensed typeface designed to ease reading for
people with dyslexia. star does not bundle the binaries; instead the font files
are downloaded from the upstream GitHub repository into star's cache dir the
first time the reader enables the dyslexia-friendly font (View ▸ Reading Aids ▸
Dyslexia-Friendly Font). This keeps it an *optional* asset — fetched only when
wanted, never shipped in the wheel/pyz.

Everything here is best-effort and offline-safe: any network or IO error is
logged and swallowed, so callers always get a (possibly empty) list of paths and
never see an exception. If the fetch fails (offline), star falls back to any
system-installed dyslexia-friendly family, or the user's chosen font.
"""
from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

from ._runtime import CACHE_DIR

_log = logging.getLogger("star.fonts")

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


def family_name() -> str:
    """The font family name registered by these files."""
    return "OpenDyslexic"


def font_dir() -> Path:
    """Return (and create) the directory where fetched fonts are cached."""
    path = CACHE_DIR / "fonts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetched_paths() -> list[Path]:
    """The existing ``*.otf`` files in :func:`font_dir`, sorted."""
    try:
        return sorted(font_dir().glob("*.otf"))
    except OSError:
        return []


def is_fetched() -> bool:
    """True if the Regular ``.otf`` is present in the cache."""
    try:
        return (font_dir() / "OpenDyslexic-Regular.otf").exists()
    except OSError:
        return False


def fetch(timeout: int = 20, force: bool = False) -> list[Path]:
    """Fetch any missing font files and return the cached fonts present.

    For each URL in :data:`FONT_URLS`, the target is ``font_dir()/basename``;
    it is downloaded when missing (or *force* is true). Any exception on a single
    URL is logged and skipped — this function never raises. Callers should treat
    an empty return as "unavailable (offline?)".
    """
    directory = font_dir()
    for url in FONT_URLS:
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
    return fetched_paths()
