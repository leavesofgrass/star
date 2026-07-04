"""Locate bundled documents (welcome.md, README.md) wherever star runs.

Shared by the Qt GUI and the curses TUI — both load the bundled welcome page
as a real document at startup and gate it out of recents / the library /
reading positions, so the two UIs must agree byte-for-byte on what counts as
"the welcome page".  Anchored on the ``star/`` package directory, which is
the same regardless of which UI asks.

Deliberately dependency-free (stdlib only): imported by ``star/gui/`` and
``star/tui/`` before any heavy machinery is up.
"""
from pathlib import Path
from typing import Any, Optional

_PKG_ROOT = Path(__file__).resolve().parent  # star/


def bundled_path(name: str) -> Optional[Path]:
    """Resolve a bundled doc by filename, wherever star is installed.

    Searches the package root (wheel / pyz install — README.md, welcome.md
    ship there via package-data), then the repo root (running from source).
    """
    for cand in (_PKG_ROOT / name, _PKG_ROOT.parent / name):
        if cand.is_file():
            return cand
    return None


def welcome_path() -> Optional[Path]:
    return bundled_path("welcome.md")


def is_welcome_doc(doc: Any) -> bool:
    """True if *doc* is the bundled welcome page (kept out of recents, the
    library, and reading positions by both UIs)."""
    wp = welcome_path()
    path = getattr(doc, "path", "") or ""
    if not wp or not path:
        return False
    try:
        return Path(path).resolve() == wp.resolve()
    except OSError:
        return False
