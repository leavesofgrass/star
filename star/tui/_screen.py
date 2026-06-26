"""Low-level curses draw primitives shared across the TUI mixins."""
from .._runtime import *  # noqa: F401,F403


# =============================================================================
# Helper functions
# =============================================================================


def _addstr(win: "curses.window", y: int, x: int, s: str, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w or not s:
        return
    s = s[: max(0, w - x)]
    if not s:
        return
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass


def _fillrow(win: "curses.window", y: int, attr: int = 0, ch: str = " ") -> None:
    h, w = win.getmaxyx()
    if y < 0 or y >= h:
        return
    try:
        win.addstr(y, 0, ch * (w - 1), attr)
    except curses.error:
        pass


def _fillrow_range(
    win: "curses.window", y: int, x: int, width: int, attr: int = 0
) -> None:
    """Fill a horizontal range [x, x+width) on row y with spaces."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    width = min(width, w - x)
    if width <= 0:
        return
    try:
        win.addstr(y, x, " " * width, attr)
    except curses.error:
        pass


# =============================================================================
# Canonical keyboard shortcuts  (GUI/TUI parity + cheat sheet)
# =============================================================================
