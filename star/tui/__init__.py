"""The curses terminal UI, split out of the former monolithic star/tui.py.

This package replaces the single star/tui.py module.  It keeps the public
surface unchanged: `from star.tui import StarApp` (used by star/app.py and the
tests) plus `THEMES` / `THEME_NAMES` (used by star/app.py) still resolve via
this re-export shim.  Submodules:

  * app.py       - StarApp + its core run loop; composes the mixin_*.py classes.
  * theming.py   - color roles, THEMES table, and curses color-pair setup.
  * _screen.py   - low-level curses draw primitives.
  * text.py      - static command/help text (M-x table, shortcuts, help pager).
  * mixin_*.py   - StarApp's methods, grouped by responsibility.
"""
from .app import StarApp
from .theming import THEMES, THEME_NAMES

__all__ = ["StarApp", "THEMES", "THEME_NAMES"]
