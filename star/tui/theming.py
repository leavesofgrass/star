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

# (fg, bg, bold, italic, underline, dim)
_N = (7, -1, False, False, False, False)


def _t(**kw: tuple) -> Dict[str, tuple]:
    d: Dict[str, tuple] = {r: _N for r in _ROLES}
    d.update(kw)
    return d


# Dark modern theme (default) — colorblind-friendly (no red/green adjacency)
# Accent palette: cyan, blue, magenta, white.  No yellow, no green/red pairing.
THEMES: Dict[str, Dict] = {
    "dark": _t(
        normal=(7, -1, False, False, False, False),
        h1=(6, -1, True, False, False, False),  # cyan bold
        h2=(4, -1, True, False, False, False),  # blue bold
        h3=(5, -1, True, False, False, False),  # magenta bold
        h4=(7, -1, True, False, True, False),  # white bold underline
        bold=(7, -1, True, False, False, False),
        italic=(7, -1, False, True, False, False),
        bolditalic=(7, -1, True, True, False, False),
        code=(6, -1, False, False, False, False),  # cyan
        code_normal=(6, -1, False, False, False, False),
        codeblock=(6, -1, False, False, False, True),  # dim cyan
        keyword=(5, -1, True, False, False, False),  # magenta bold
        string=(6, -1, False, False, False, False),  # cyan
        comment=(4, -1, False, True, False, True),  # blue italic dim
        number=(5, -1, False, False, False, False),  # magenta
        link=(6, -1, False, False, True, False),  # cyan underline
        image=(5, -1, False, False, True, False),
        quote=(5, -1, False, True, False, False),  # magenta italic
        bullet=(6, -1, True, False, False, False),  # cyan bold
        ordinal=(6, -1, False, False, False, False),
        table=(6, -1, False, False, False, False),
        hr=(4, -1, False, False, False, True),  # blue dim
        current_word=(0, 6, True, False, False, False),  # black on cyan
        search_match=(0, 4, False, False, False, False),  # black on blue
        search_current=(0, 5, True, False, False, False),  # black on magenta
        status=(7, 4, True, False, False, False),  # white on blue
        status_hi=(6, 4, True, False, False, False),  # cyan on blue
        minibuf=(7, -1, False, False, False, False),
        error=(5, -1, True, False, False, False),  # magenta bold (no red)
        dim=(7, -1, False, False, False, True),
        progress=(6, 4, True, False, False, False),
        title_bar=(7, 4, True, False, False, False),
    ),
    "light": _t(
        normal=(0, 7, False, False, False, False),
        h1=(4, 7, True, False, False, False),  # blue bold
        h2=(5, 7, True, False, False, False),  # magenta bold
        h3=(4, 7, False, False, False, False),  # blue
        h4=(0, 7, True, False, True, False),
        bold=(0, 7, True, False, False, False),
        italic=(0, 7, False, True, False, False),
        bolditalic=(0, 7, True, True, False, False),
        code=(4, 7, False, False, False, False),
        code_normal=(4, 7, False, False, False, False),
        codeblock=(4, 7, False, False, False, True),
        keyword=(5, 7, True, False, False, False),
        string=(4, 7, False, False, False, False),
        comment=(5, 7, False, True, False, True),
        number=(5, 7, False, False, False, False),
        link=(4, 7, False, False, True, False),
        image=(5, 7, False, False, True, False),
        quote=(5, 7, False, True, False, False),
        bullet=(4, 7, True, False, False, False),
        ordinal=(4, 7, False, False, False, False),
        table=(4, 7, False, False, False, False),
        hr=(5, 7, False, False, False, True),
        current_word=(7, 4, True, False, False, False),  # white on blue
        search_match=(7, 5, False, False, False, False),  # white on magenta
        search_current=(7, 4, True, False, False, False),
        status=(7, 4, True, False, False, False),
        status_hi=(7, 5, True, False, False, False),
        minibuf=(0, 7, False, False, False, False),
        error=(5, 7, True, False, False, False),
        dim=(0, 7, False, False, False, True),
        progress=(7, 4, False, False, False, False),
        title_bar=(7, 4, True, False, False, False),
    ),
    "contrast": _t(
        # High contrast: bold white on black, cyan & magenta accents
        normal=(7, 0, False, False, False, False),
        h1=(6, 0, True, False, False, False),
        h2=(7, 0, True, False, False, False),
        h3=(5, 0, True, False, False, False),
        h4=(7, 0, True, False, True, False),
        bold=(7, 0, True, False, False, False),
        italic=(7, 0, False, True, False, False),
        bolditalic=(7, 0, True, True, False, False),
        code=(6, 0, True, False, False, False),
        code_normal=(6, 0, True, False, False, False),
        codeblock=(6, 0, False, False, False, False),
        keyword=(5, 0, True, False, False, False),
        string=(6, 0, False, False, False, False),
        comment=(7, 0, False, False, False, False),
        number=(5, 0, False, False, False, False),
        link=(6, 0, False, False, True, False),
        image=(5, 0, False, False, True, False),
        quote=(7, 0, False, False, False, False),
        bullet=(6, 0, True, False, False, False),
        ordinal=(6, 0, False, False, False, False),
        table=(7, 0, False, False, False, False),
        hr=(7, 0, False, False, False, False),
        current_word=(0, 6, True, False, False, False),
        search_match=(0, 7, False, False, False, False),
        search_current=(0, 5, True, False, False, False),
        status=(0, 7, True, False, False, False),
        status_hi=(0, 6, True, False, False, False),
        minibuf=(7, 0, True, False, False, False),
        error=(5, 0, True, False, False, False),
        dim=(7, 0, False, False, False, False),
        progress=(0, 6, False, False, False, False),
        title_bar=(0, 7, True, False, False, False),
    ),
    "phosphor": _t(
        # Classic green phosphor monochrome
        normal=(2, -1, False, False, False, False),
        h1=(2, -1, True, False, False, False),
        h2=(2, -1, True, False, True, False),
        h3=(2, -1, False, False, True, False),
        h4=(2, -1, True, False, False, False),
        bold=(2, -1, True, False, False, False),
        italic=(2, -1, False, True, False, False),
        bolditalic=(2, -1, True, True, False, False),
        code=(2, -1, True, False, False, False),
        code_normal=(2, -1, False, False, False, False),
        codeblock=(2, -1, False, False, False, True),
        keyword=(2, -1, True, False, False, False),
        string=(2, -1, False, False, False, False),
        comment=(2, -1, False, True, False, True),
        number=(2, -1, False, False, False, False),
        link=(2, -1, False, False, True, False),
        image=(2, -1, False, False, True, False),
        quote=(2, -1, False, True, False, False),
        bullet=(2, -1, True, False, False, False),
        ordinal=(2, -1, False, False, False, False),
        table=(2, -1, False, False, False, False),
        hr=(2, -1, False, False, False, True),
        current_word=(0, 2, True, False, False, False),
        search_match=(0, 2, False, False, False, False),
        search_current=(2, 0, True, False, False, False),
        status=(0, 2, True, False, False, False),
        status_hi=(0, 2, False, False, False, False),
        minibuf=(2, -1, False, False, False, False),
        error=(2, -1, True, False, False, False),
        dim=(2, -1, False, False, False, True),
        progress=(0, 2, False, False, False, False),
        title_bar=(0, 2, True, False, False, False),
    ),
}

THEME_NAMES = list(THEMES.keys())

# Roles that mark a heading line in the rendered output.
_HEADING_ROLES = frozenset({"h1", "h2", "h3", "h4"})

# Roles that mark a table line in the rendered output.
_TABLE_ROLES = frozenset({"table"})


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
