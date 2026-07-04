"""Color roles, the THEMES table, and curses color-pair setup for the TUI."""
from .._runtime import *  # noqa: F401,F403


# =============================================================================
# Color / theme system
# =============================================================================

# Color-pair role names → CP_* numbers
_ROLES = [
    "normal",
    "h1",
    "h2",
    "h3",
    "h4",
    "bold",
    "italic",
    "bolditalic",
    "code",
    "code_normal",
    "codeblock",
    "keyword",
    "string",
    "comment",
    "number",
    "link",
    "image",
    "quote",
    "bullet",
    "ordinal",
    "table",
    "hr",
    "current_word",  # TTS word highlight
    "search_match",  # non-current search hit
    "search_current",  # current search hit
    "status",  # status bar
    "status_hi",  # emphasized item in status bar
    "minibuf",  # minibuffer normal
    "error",  # error message
    "dim",  # hints / secondary text
    "progress",  # loading indicator
    "title_bar",  # top title bar
]
CP: Dict[str, int] = {r: i + 1 for i, r in enumerate(_ROLES)}

# curses color constants — NEVER raw ints in the theme tables.  ncurses uses
# RGB bit-order (COLOR_BLUE == 4) but windows-curses/PDCurses uses BGR
# (COLOR_BLUE == 1, COLOR_RED == 4), so a raw 4 renders blue on Linux and RED
# on Windows.  That single mismatch painted the whole Windows TUI chrome red
# for releases — always go through the named constants, which are correct on
# both platforms.
_BLACK = curses.COLOR_BLACK
_GREEN = curses.COLOR_GREEN
_BLUE = curses.COLOR_BLUE
_MAGENTA = curses.COLOR_MAGENTA
_CYAN = curses.COLOR_CYAN
_WHITE = curses.COLOR_WHITE
_DEF = -1  # terminal default (use_default_colors)

# Orange sentinel for theme tables, resolved by _resolve_color at init_pair
# time: xterm-256 DarkOrange (#ff8700, index 208) on a 256-color terminal,
# else the nearest base-8 color (yellow).  The base-8 palette has no orange.
ORANGE = -2
_ORANGE_256 = 208

# (fg, bg, bold, italic, underline, dim)
_N = (_WHITE, _DEF, False, False, False, False)


def _t(**kw: tuple) -> Dict[str, tuple]:
    d: Dict[str, tuple] = {r: _N for r in _ROLES}
    d.update(kw)
    return d


# Dark modern theme (default) — colorblind-friendly (no red or green anywhere;
# deuteranopia/protanopia-safe).  Chrome + spoken-word accent: ORANGE (yellow
# on 8-color terminals); content accents: cyan, blue, magenta, white.
THEMES: Dict[str, Dict] = {
    "dark": _t(
        normal=(_WHITE, _DEF, False, False, False, False),
        h1=(_CYAN, _DEF, True, False, False, False),  # cyan bold
        h2=(_BLUE, _DEF, True, False, False, False),  # blue bold
        h3=(_MAGENTA, _DEF, True, False, False, False),  # magenta bold
        h4=(_WHITE, _DEF, True, False, True, False),  # white bold underline
        bold=(_WHITE, _DEF, True, False, False, False),
        italic=(_WHITE, _DEF, False, True, False, False),
        bolditalic=(_WHITE, _DEF, True, True, False, False),
        code=(_CYAN, _DEF, False, False, False, False),  # cyan
        code_normal=(_CYAN, _DEF, False, False, False, False),
        codeblock=(_CYAN, _DEF, False, False, False, True),  # dim cyan
        keyword=(_MAGENTA, _DEF, True, False, False, False),  # magenta bold
        string=(_CYAN, _DEF, False, False, False, False),  # cyan
        comment=(_BLUE, _DEF, False, True, False, True),  # blue italic dim
        number=(_MAGENTA, _DEF, False, False, False, False),  # magenta
        link=(_CYAN, _DEF, False, False, True, False),  # cyan underline
        image=(_MAGENTA, _DEF, False, False, True, False),
        quote=(_MAGENTA, _DEF, False, True, False, False),  # magenta italic
        bullet=(_CYAN, _DEF, True, False, False, False),  # cyan bold
        ordinal=(_CYAN, _DEF, False, False, False, False),
        table=(_CYAN, _DEF, False, False, False, False),
        hr=(_BLUE, _DEF, False, False, False, True),  # blue dim
        current_word=(_BLACK, ORANGE, True, False, False, False),  # black on orange
        search_match=(_BLACK, _BLUE, False, False, False, False),  # black on blue
        search_current=(_BLACK, _MAGENTA, True, False, False, False),
        status=(_BLACK, ORANGE, True, False, False, False),  # black on orange
        status_hi=(_BLACK, ORANGE, True, False, True, False),  # + underline
        minibuf=(_WHITE, _DEF, False, False, False, False),
        error=(_MAGENTA, _DEF, True, False, False, False),  # magenta bold (no red)
        dim=(_WHITE, _DEF, False, False, False, True),
        progress=(_BLACK, ORANGE, True, False, False, False),
        title_bar=(_BLACK, ORANGE, True, False, False, False),
    ),
    "light": _t(
        normal=(_BLACK, _WHITE, False, False, False, False),
        h1=(_BLUE, _WHITE, True, False, False, False),  # blue bold
        h2=(_MAGENTA, _WHITE, True, False, False, False),  # magenta bold
        h3=(_BLUE, _WHITE, False, False, False, False),  # blue
        h4=(_BLACK, _WHITE, True, False, True, False),
        bold=(_BLACK, _WHITE, True, False, False, False),
        italic=(_BLACK, _WHITE, False, True, False, False),
        bolditalic=(_BLACK, _WHITE, True, True, False, False),
        code=(_BLUE, _WHITE, False, False, False, False),
        code_normal=(_BLUE, _WHITE, False, False, False, False),
        codeblock=(_BLUE, _WHITE, False, False, False, True),
        keyword=(_MAGENTA, _WHITE, True, False, False, False),
        string=(_BLUE, _WHITE, False, False, False, False),
        comment=(_MAGENTA, _WHITE, False, True, False, True),
        number=(_MAGENTA, _WHITE, False, False, False, False),
        link=(_BLUE, _WHITE, False, False, True, False),
        image=(_MAGENTA, _WHITE, False, False, True, False),
        quote=(_MAGENTA, _WHITE, False, True, False, False),
        bullet=(_BLUE, _WHITE, True, False, False, False),
        ordinal=(_BLUE, _WHITE, False, False, False, False),
        table=(_BLUE, _WHITE, False, False, False, False),
        hr=(_MAGENTA, _WHITE, False, False, False, True),
        current_word=(_WHITE, _BLUE, True, False, False, False),  # white on blue
        search_match=(_WHITE, _MAGENTA, False, False, False, False),
        search_current=(_WHITE, _BLUE, True, False, False, False),
        status=(_WHITE, _BLUE, True, False, False, False),
        status_hi=(_WHITE, _MAGENTA, True, False, False, False),
        minibuf=(_BLACK, _WHITE, False, False, False, False),
        error=(_MAGENTA, _WHITE, True, False, False, False),
        dim=(_BLACK, _WHITE, False, False, False, True),
        progress=(_WHITE, _BLUE, False, False, False, False),
        title_bar=(_WHITE, _BLUE, True, False, False, False),
    ),
    "contrast": _t(
        # High contrast: bold white on black, cyan & magenta accents
        normal=(_WHITE, _BLACK, False, False, False, False),
        h1=(_CYAN, _BLACK, True, False, False, False),
        h2=(_WHITE, _BLACK, True, False, False, False),
        h3=(_MAGENTA, _BLACK, True, False, False, False),
        h4=(_WHITE, _BLACK, True, False, True, False),
        bold=(_WHITE, _BLACK, True, False, False, False),
        italic=(_WHITE, _BLACK, False, True, False, False),
        bolditalic=(_WHITE, _BLACK, True, True, False, False),
        code=(_CYAN, _BLACK, True, False, False, False),
        code_normal=(_CYAN, _BLACK, True, False, False, False),
        codeblock=(_CYAN, _BLACK, False, False, False, False),
        keyword=(_MAGENTA, _BLACK, True, False, False, False),
        string=(_CYAN, _BLACK, False, False, False, False),
        comment=(_WHITE, _BLACK, False, False, False, False),
        number=(_MAGENTA, _BLACK, False, False, False, False),
        link=(_CYAN, _BLACK, False, False, True, False),
        image=(_MAGENTA, _BLACK, False, False, True, False),
        quote=(_WHITE, _BLACK, False, False, False, False),
        bullet=(_CYAN, _BLACK, True, False, False, False),
        ordinal=(_CYAN, _BLACK, False, False, False, False),
        table=(_WHITE, _BLACK, False, False, False, False),
        hr=(_WHITE, _BLACK, False, False, False, False),
        current_word=(_BLACK, _CYAN, True, False, False, False),
        search_match=(_BLACK, _WHITE, False, False, False, False),
        search_current=(_BLACK, _MAGENTA, True, False, False, False),
        status=(_BLACK, _WHITE, True, False, False, False),
        status_hi=(_BLACK, _CYAN, True, False, False, False),
        minibuf=(_WHITE, _BLACK, True, False, False, False),
        error=(_MAGENTA, _BLACK, True, False, False, False),
        dim=(_WHITE, _BLACK, False, False, False, False),
        progress=(_BLACK, _CYAN, False, False, False, False),
        title_bar=(_BLACK, _WHITE, True, False, False, False),
    ),
    "phosphor": _t(
        # Classic green phosphor monochrome
        normal=(_GREEN, _DEF, False, False, False, False),
        h1=(_GREEN, _DEF, True, False, False, False),
        h2=(_GREEN, _DEF, True, False, True, False),
        h3=(_GREEN, _DEF, False, False, True, False),
        h4=(_GREEN, _DEF, True, False, False, False),
        bold=(_GREEN, _DEF, True, False, False, False),
        italic=(_GREEN, _DEF, False, True, False, False),
        bolditalic=(_GREEN, _DEF, True, True, False, False),
        code=(_GREEN, _DEF, True, False, False, False),
        code_normal=(_GREEN, _DEF, False, False, False, False),
        codeblock=(_GREEN, _DEF, False, False, False, True),
        keyword=(_GREEN, _DEF, True, False, False, False),
        string=(_GREEN, _DEF, False, False, False, False),
        comment=(_GREEN, _DEF, False, True, False, True),
        number=(_GREEN, _DEF, False, False, False, False),
        link=(_GREEN, _DEF, False, False, True, False),
        image=(_GREEN, _DEF, False, False, True, False),
        quote=(_GREEN, _DEF, False, True, False, False),
        bullet=(_GREEN, _DEF, True, False, False, False),
        ordinal=(_GREEN, _DEF, False, False, False, False),
        table=(_GREEN, _DEF, False, False, False, False),
        hr=(_GREEN, _DEF, False, False, False, True),
        current_word=(_BLACK, _GREEN, True, False, False, False),
        search_match=(_BLACK, _GREEN, False, False, False, False),
        search_current=(_GREEN, _BLACK, True, False, False, False),
        status=(_BLACK, _GREEN, True, False, False, False),
        status_hi=(_BLACK, _GREEN, False, False, False, False),
        minibuf=(_GREEN, _DEF, False, False, False, False),
        error=(_GREEN, _DEF, True, False, False, False),
        dim=(_GREEN, _DEF, False, False, False, True),
        progress=(_BLACK, _GREEN, False, False, False, False),
        title_bar=(_BLACK, _GREEN, True, False, False, False),
    ),
}

THEME_NAMES = list(THEMES.keys())

# Roles that mark a heading line in the rendered output.
_HEADING_ROLES = frozenset({"h1", "h2", "h3", "h4"})

# Roles that mark a table line in the rendered output.
_TABLE_ROLES = frozenset({"table"})


def _resolve_color(c: int, colors_available: int) -> int:
    """Map the ORANGE sentinel to a real terminal color.

    xterm-256 DarkOrange (208, #ff8700) when the terminal offers 256+ colors,
    else the nearest base-8 color (yellow — via the constant, since PDCurses
    and ncurses number it differently).  Every other value passes through."""
    if c == ORANGE:
        return _ORANGE_256 if colors_available >= 256 else curses.COLOR_YELLOW
    return c


def _setup_colors(theme_name: str) -> Dict[str, int]:
    """Initialize curses color pairs from a theme dict.
    Returns a mapping role → combined curses attribute integer."""
    if not curses.has_colors():
        return {r: curses.A_NORMAL for r in _ROLES}
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        pass
    # curses.COLORS is only meaningful after start_color(); default to the
    # base palette when absent so the ORANGE fallback stays safe.
    colors_available = getattr(curses, "COLORS", 8) or 8

    theme = THEMES.get(theme_name, THEMES["dark"])
    _ATTR = {
        "bold": curses.A_BOLD,
        "italic": getattr(curses, "A_ITALIC", 0),
        "underline": curses.A_UNDERLINE,
        "dim": curses.A_DIM,
    }
    result: Dict[str, int] = {}
    for role in _ROLES:
        fg, bg, b, it, ul, dim = theme[role]
        fg = _resolve_color(fg, colors_available)
        bg = _resolve_color(bg, colors_available)
        # Range-guard: an out-of-range color would hit the silent except
        # below and leave the pair uninitialized (default white-on-black).
        if fg >= colors_available:
            fg = curses.COLOR_WHITE
        if bg >= colors_available:
            bg = -1
        cp = CP[role]
        try:
            curses.init_pair(cp, fg, bg)
        except curses.error:
            pass
        attr = curses.color_pair(cp)
        if b:
            attr |= curses.A_BOLD
        if it:
            attr |= _ATTR["italic"]
        if ul:
            attr |= curses.A_UNDERLINE
        if dim:
            attr |= curses.A_DIM
        result[role] = attr
    return result


# =============================================================================
