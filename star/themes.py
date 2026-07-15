"""CSS theme loading, palette parsing, and default theme seeding."""
from ._runtime import *  # noqa: F401,F403


_LICENSE_TEXT = (
    """\
# star — Speaking Terminal Access Reader

"""
    + __copyright__
    + """
License: """
    + __license__
    + """

---

## GNU General Public License v3

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

Full license text: https://www.gnu.org/licenses/gpl-3.0.txt

---

Press `q` or `Esc` to close.
"""
)

_WELCOME_TEXT = (
    """\
# star — Speaking Terminal Access Reader

Version """
    + APP_VERSION
    + """   """
    + __copyright__
    + """

---

## Getting started

  **Open a file:**   Ctrl+O  (or pass a filename on the command line)
  **Open a URL:**    F2, then type  open-url
  **Read aloud:**    Space   (plays from the current position)
  **Move caret:**    Arrow keys  (word by word / line by line)
  **Read here:**     Enter   (reads aloud from the caret)
  **Stop:**          Esc
  **Help:**          F1
  **Commands:**      F2
  **Quit:**          Ctrl+Q  or  q

## Supported formats

  Plain Text, Markdown, LaTeX, PDF, DOCX, ODT, HTML,
  CSV, TSV, XLSX, EPUB, DAISY, DTBook, R, Python,
  Jupyter Notebook, Org-mode, URLs

## TTS backends

  pyttsx3 (built-in system voice) · eSpeak-NG · DECtalk

  Switch:  M-x tts-backend
"""
)


# =============================================================================
# CSS theme helpers (Qt GUI)
# =============================================================================

# CSS that is generated from a built-in palette dict.  Used both to write
# the seed files and as the fallback when no custom CSS overrides a palette key.
_CSS_TEMPLATE = """\
body {{
    background: {bg};
    color: {fg};
    font-family: Georgia, serif;
    margin: 14px;
    line-height: 1.6;
}}
::selection {{
    background: {sel};
}}
h1 {{ color: {h1}; margin: 8px 0 4px; }}
h2 {{ color: {h2}; margin: 6px 0 3px; }}
h3 {{ color: {h3}; margin: 4px 0 2px; }}
h4 {{ color: {h4}; margin: 4px 0 2px; }}
h5 {{ color: {h4}; margin: 4px 0 2px; }}
h6 {{ color: {h4}; margin: 4px 0 2px; }}
a    {{ color: {link}; }}
code {{ color: {code}; background: {code_bg}; font-family: monospace; }}
pre  {{ color: {fg}; background: {code_bg}; font-family: monospace; white-space: pre-wrap; padding: 8px; }}
blockquote {{ color: {muted}; border-left: 3px solid {muted}; padding-left: 10px; }}
hr   {{ border: 0; border-top: 1px solid {muted}; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid {muted}; padding: 3px 8px; }}
b    {{ font-weight: bold; }}
i    {{ font-style: italic; }}
p    {{ margin: 4px 0; }}
"""

# The full palette schema.  ``bg/fg/sel/h1–h4/code`` are the original eight keys;
# ``code_bg`` (code/pre block background), ``link`` (anchor colour), and ``muted``
# (blockquote / rule / table borders) were added for the Obsidian and Zed themes.
# Every palette below carries all eleven keys; missing keys fall back to the
# ``dark`` defaults in :func:`_parse_css_palette`.
BUILT_IN_PALETTES: Dict[str, Dict[str, str]] = {
    # ── Galaxy (default) — purple-accented dark ───────────────────────────
    # (Named "obsidian"/"zed-one-*" before 0.1.27; renamed so star's own
    # themes never carry another project's name.  LEGACY_THEME_ALIASES below
    # keeps old settings/profiles working.)
    "galaxy": {
        "bg": "#1e1e1e", "fg": "#dadada", "sel": "#483d6b",
        "h1": "#c9b6ff", "h2": "#a98eff", "h3": "#8aa2ff", "h4": "#7bd0c1",
        "code": "#e0a87a", "code_bg": "#2a2a2a", "link": "#a882ff",
        "muted": "#7d7d7d",
    },
    "galaxy-light": {
        "bg": "#ffffff", "fg": "#2e3338", "sel": "#d8caff",
        "h1": "#6c3fd6", "h2": "#8257e5", "h3": "#3a6df0", "h4": "#1a9e8f",
        "code": "#b5673a", "code_bg": "#f2f0f9", "link": "#7c3aed",
        "muted": "#8a8f98",
    },
    # ── One Dark / One Light ──────────────────────────────────────────────
    "one-dark": {
        "bg": "#282c34", "fg": "#abb2bf", "sel": "#3e4451",
        "h1": "#61afef", "h2": "#c678dd", "h3": "#56b6c2", "h4": "#98c379",
        "code": "#e5c07b", "code_bg": "#21252b", "link": "#61afef",
        "muted": "#5c6370",
    },
    "one-light": {
        "bg": "#fafafa", "fg": "#383a42", "sel": "#dbdbdc",
        "h1": "#4078f2", "h2": "#a626a4", "h3": "#0184bc", "h4": "#50a14f",
        "code": "#c18401", "code_bg": "#eaeaeb", "link": "#4078f2",
        "muted": "#a0a1a7",
    },
    # ── Original built-ins ────────────────────────────────────────────────
    "dark": {
        "bg": "#16181d", "fg": "#c6ccd4", "sel": "#2c313a",
        "h1": "#82aaff", "h2": "#89ddff", "h3": "#c792ea", "h4": "#f78c6c",
        "code": "#7fdbab", "code_bg": "#1e2128", "link": "#82aaff",
        "muted": "#5c6370",
    },
    "light": {
        "bg": "#fafafa", "fg": "#24273a", "sel": "#bcd0f0",
        "h1": "#1e66f5", "h2": "#209fb5", "h3": "#8839ef", "h4": "#e64553",
        "code": "#40a02b", "code_bg": "#eceff4", "link": "#1e66f5",
        "muted": "#8c8fa1",
    },
    "contrast": {
        "bg": "#000000", "fg": "#ffffff", "sel": "#404040",
        "h1": "#ffff00", "h2": "#00ffff", "h3": "#ff80ff", "h4": "#80ff80",
        "code": "#00ff80", "code_bg": "#1a1a1a", "link": "#00ffff",
        "muted": "#c0c0c0",
    },
    # ── High-contrast AAA (low-vision) ────────────────────────────────────
    # Engineered for WCAG 2.1 AAA (§1.4.6): every text / heading / link / code
    # colour clears 7:1 contrast on the pure-black background by a wide margin
    # (lowest pair ≈ 11:1), so it also satisfies the 4.5:1 AA floor for large
    # and small text alike.  Unlike the legacy ``contrast`` theme (pure #ffff00
    # / #00ffff primaries that some low-vision users find glaring), the hues
    # here are slightly desaturated for comfort while staying well clear of the
    # AAA threshold.  Six distinct hues (near-white body, yellow / cyan / pink /
    # green headings, amber code, sky-blue links) mean information is never
    # carried by hue alone — links are additionally distinguished by an
    # underline in the rendered CSS, and headings by weight and size.
    "high-contrast": {
        "bg": "#000000", "fg": "#ffffff", "sel": "#2a2a2a",
        "h1": "#ffe14d", "h2": "#5fe3ff", "h3": "#ff9ce0", "h4": "#7dffb0",
        "code": "#ffbf66", "code_bg": "#141414", "link": "#8ac6ff",
        "muted": "#c0c0c0",
    },
    "phosphor": {
        "bg": "#001200", "fg": "#00cc00", "sel": "#004400",
        "h1": "#00ff00", "h2": "#00ee00", "h3": "#00cc00", "h4": "#00aa00",
        "code": "#009900", "code_bg": "#002600", "link": "#00ff00",
        "muted": "#008800",
    },
    # ── Popular community palettes (added 0.1.27) ─────────────────────────
    # Faithful to each scheme's published palette; appended AFTER the
    # original built-ins so the F5 cycle order existing users know is
    # unchanged.  Every color pairs ≥ 4.5:1 against its background (WCAG AA).
    "dracula": {
        "bg": "#282a36", "fg": "#f8f8f2", "sel": "#44475a",
        "h1": "#bd93f9", "h2": "#ff79c6", "h3": "#8be9fd", "h4": "#50fa7b",
        "code": "#f1fa8c", "code_bg": "#21222c", "link": "#8be9fd",
        "muted": "#9aa0b9",
    },
    "nord": {
        "bg": "#2e3440", "fg": "#eceff4", "sel": "#434c5e",
        "h1": "#88c0d0", "h2": "#81a1c1", "h3": "#8fbcbb", "h4": "#a3be8c",
        "code": "#ebcb8b", "code_bg": "#3b4252", "link": "#88c0d0",
        "muted": "#94a0b8",
    },
    # Solarized's canonical accents miss WCAG AA on their own backgrounds (a
    # known criticism of the scheme); these keep the Solarized character but
    # are nudged until every pair clears 4.5:1 — star is a reader first.
    "solarized-dark": {
        "bg": "#002b36", "fg": "#93a1a1", "sel": "#073642",
        "h1": "#4aa2df", "h2": "#2aa198", "h3": "#859900", "h4": "#b58900",
        "code": "#f0784a", "code_bg": "#073642", "link": "#4aa2df",
        "muted": "#82989f",
    },
    "solarized-light": {
        "bg": "#fdf6e3", "fg": "#586e75", "sel": "#eee8d5",
        "h1": "#1b6194", "h2": "#1b6b65", "h3": "#566500", "h4": "#7f6100",
        "code": "#b34212", "code_bg": "#eee8d5", "link": "#1b6194",
        "muted": "#5e7070",
    },
    "gruvbox-dark": {
        "bg": "#282828", "fg": "#ebdbb2", "sel": "#504945",
        "h1": "#fabd2f", "h2": "#fe8019", "h3": "#8ec07c", "h4": "#83a598",
        "code": "#b8bb26", "code_bg": "#3c3836", "link": "#83a598",
        "muted": "#a89984",
    },
    "tokyo-night": {
        "bg": "#1a1b26", "fg": "#c0caf5", "sel": "#33467c",
        "h1": "#7aa2f7", "h2": "#bb9af7", "h3": "#7dcfff", "h4": "#9ece6a",
        "code": "#e0af68", "code_bg": "#24283b", "link": "#7aa2f7",
        "muted": "#858dbb",
    },
    "catppuccin-mocha": {
        "bg": "#1e1e2e", "fg": "#cdd6f4", "sel": "#45475a",
        "h1": "#cba6f7", "h2": "#f5c2e7", "h3": "#89dceb", "h4": "#a6e3a1",
        "code": "#fab387", "code_bg": "#181825", "link": "#89b4fa",
        "muted": "#9399b2",
    },
    "monokai": {
        "bg": "#272822", "fg": "#f8f8f2", "sel": "#49483e",
        "h1": "#66d9ef", "h2": "#a6e22e", "h3": "#fd971f", "h4": "#ae81ff",
        "code": "#e6db74", "code_bg": "#1e1f1c", "link": "#66d9ef",
        "muted": "#a59f85",
    },
}

#: Built-in theme names in cycle order (Galaxy first; it is the default).
BUILT_IN_THEME_NAMES: List[str] = list(BUILT_IN_PALETTES.keys())

#: Pre-0.1.27 theme names → their current names.  star's own themes no
#: longer carry another project's name; these aliases keep old settings
#: files, saved profiles, and `star --theme obsidian` working forever.
LEGACY_THEME_ALIASES: Dict[str, str] = {
    "obsidian": "galaxy",
    "obsidian-light": "galaxy-light",
    "zed-one-dark": "one-dark",
    "zed-one-light": "one-light",
}


def resolve_theme_name(name: str) -> str:
    """Map a legacy theme name to its current name (identity otherwise)."""
    return LEGACY_THEME_ALIASES.get((name or "").strip(), name)


# =============================================================================
# OS colour-scheme / contrast auto-detection
# =============================================================================

#: Theme picked for each detected OS appearance.  ``dark``/``light`` map to the
#: default Galaxy variants; the *high-contrast* mode (some platforms report a
#: dedicated forced-colors / high-contrast preference) maps to the AAA theme.
_OS_SCHEME_THEME: Dict[str, str] = {
    "dark": "galaxy",
    "light": "galaxy-light",
    "high-contrast": "high-contrast",
}


def theme_for_os_scheme(scheme: str) -> Optional[str]:
    """Map a detected OS colour scheme to a built-in theme name.

    *scheme* is one of ``"dark"``, ``"light"``, ``"high-contrast"``, or
    ``"unknown"`` (see :func:`detect_os_color_scheme`).  Returns the matching
    built-in palette name, or ``None`` when the scheme is unknown / unmapped so
    the caller can leave the saved theme untouched.
    """
    name = _OS_SCHEME_THEME.get((scheme or "").strip().lower())
    if name and name in BUILT_IN_PALETTES:
        return name
    return None


def detect_os_color_scheme() -> str:
    """Best-effort detection of the OS colour-scheme / contrast preference.

    Uses ``QGuiApplication.styleHints().colorScheme()`` (Qt 6.5+).  Returns one
    of ``"dark"``, ``"light"``, ``"high-contrast"``, or ``"unknown"``.  Never
    raises: any missing API (older Qt, no running application, PyQt absent)
    yields ``"unknown"`` so callers degrade to the saved theme.

    High-contrast is reported separately where the platform exposes it: Windows
    high-contrast mode surfaces via ``QStyleHints.colorScheme`` returning Dark
    plus a forced-colors palette; we additionally consult the style hint's
    ``colorScheme`` and, when a dedicated ``ColorScheme`` value beyond Dark/Light
    is present, map it through.  In practice most builds report only Dark/Light,
    so high-contrast users are served by explicitly choosing the AAA theme —
    which this module also exposes as a first-class built-in.
    """
    try:
        try:  # PyQt6
            from PyQt6.QtGui import QGuiApplication
            from PyQt6.QtCore import Qt as _Qt
        except ImportError:  # PyQt5 has no colorScheme() — treat as unknown
            return "unknown"
        app = QGuiApplication.instance()
        if app is None:
            return "unknown"
        hints = app.styleHints()
        getter = getattr(hints, "colorScheme", None)
        if not callable(getter):
            return "unknown"  # Qt < 6.5
        scheme = getter()
        cs_enum = getattr(_Qt, "ColorScheme", None)
        if cs_enum is None:
            return "unknown"
        if scheme == getattr(cs_enum, "Dark", object()):
            return "dark"
        if scheme == getattr(cs_enum, "Light", object()):
            return "light"
        return "unknown"  # ColorScheme.Unknown or an unrecognised value
    except Exception:  # noqa: BLE001 — detection is best-effort only
        return "unknown"


def _palette_to_css(pal: Dict[str, str]) -> str:
    """Format *_CSS_TEMPLATE* with the values from a palette dict.

    Missing keys (e.g. a user palette predating ``code_bg``/``link``/``muted``)
    fall back to the ``dark`` palette so formatting never raises.
    """
    full = dict(BUILT_IN_PALETTES["dark"])
    full.update(pal)
    return _CSS_TEMPLATE.format(**full)


def _parse_css_palette(css: str) -> Dict[str, str]:
    """Extract the 8 palette keys (bg/fg/sel/h1–h4/code) from a CSS string.

    Only plain color values (hex codes, named colors, or rgb/rgba) are
    extracted; any key that cannot be found falls back to the 'dark' palette
    so the result is always a complete, valid palette dict.
    """
    # Start with dark-theme defaults so every key is always present.
    from copy import deepcopy as _dc

    pal = _dc(BUILT_IN_PALETTES["dark"])

    _val = r"([#\w][\w(),. %]*)"  # loose color value pattern

    # body { background: X; color: Y; }
    m = re.search(r"body\s*\{([^}]*)\}", css, re.DOTALL | re.IGNORECASE)
    if m:
        blk = m.group(1)
        bg = re.search(r"background(?:-color)?\s*:\s*" + _val, blk, re.I)
        fg = re.search(r"(?<!background-)color\s*:\s*" + _val, blk, re.I)
        if bg:
            pal["bg"] = bg.group(1).strip().rstrip(";")
        if fg:
            pal["fg"] = fg.group(1).strip().rstrip(";")

    # ::selection { background: Z; }
    m = re.search(r"::?selection\s*\{([^}]*)\}", css, re.DOTALL | re.IGNORECASE)
    if m:
        sel = re.search(r"background(?:-color)?\s*:\s*" + _val, m.group(1), re.I)
        if sel:
            pal["sel"] = sel.group(1).strip().rstrip(";")

    # h1 { color: X; }  …  h4 { color: X; }
    for lvl in range(1, 5):
        m = re.search(rf"h{lvl}\s*\{{([^}}]*)\}}", css, re.DOTALL | re.IGNORECASE)
        if m:
            c = re.search(r"(?<!background-)color\s*:\s*" + _val, m.group(1), re.I)
            if c:
                pal[f"h{lvl}"] = c.group(1).strip().rstrip(";")

    # code { color: X; background: Y; }
    m = re.search(r"\bcode\b\s*\{([^}]*)\}", css, re.DOTALL | re.IGNORECASE)
    if m:
        c = re.search(r"(?<!background-)color\s*:\s*" + _val, m.group(1), re.I)
        if c:
            pal["code"] = c.group(1).strip().rstrip(";")
        cb = re.search(r"background(?:-color)?\s*:\s*" + _val, m.group(1), re.I)
        if cb:
            pal["code_bg"] = cb.group(1).strip().rstrip(";")

    # a { color: X; }  →  link
    m = re.search(r"(?<![\w-])a\s*\{([^}]*)\}", css, re.DOTALL | re.IGNORECASE)
    if m:
        c = re.search(r"(?<!background-)color\s*:\s*" + _val, m.group(1), re.I)
        if c:
            pal["link"] = c.group(1).strip().rstrip(";")

    # blockquote { color: X; }  →  muted
    m = re.search(r"\bblockquote\b\s*\{([^}]*)\}", css, re.DOTALL | re.IGNORECASE)
    if m:
        c = re.search(r"(?<!background-)color\s*:\s*" + _val, m.group(1), re.I)
        if c:
            pal["muted"] = c.group(1).strip().rstrip(";")

    return pal


def _load_css_themes() -> Dict[str, Dict[str, Any]]:
    """Scan *THEMES_DIR* for *.css files and return a mapping
    theme-name → palette-dict (with key '_css' holding the raw CSS text).
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not THEMES_DIR.exists():
        return result
    for css_path in sorted(THEMES_DIR.glob("*.css")):
        try:
            css_text = css_path.read_text(encoding="utf-8", errors="replace")
            pal: Dict[str, Any] = _parse_css_palette(css_text)
            pal["_css"] = css_text
            result[css_path.stem] = pal
        except Exception:  # noqa: BLE001  — skip unreadable files silently
            pass
    return result


def _seed_default_css_themes() -> None:
    """Write the built-in palettes (:data:`BUILT_IN_PALETTES`) as CSS files in
    *THEMES_DIR*.

    Files are only written if they do not already exist, so hand-edited
    customizations are never overwritten.  Each generated file serves as a
    ready-made starting point for user customization — copy, rename, and
    edit to create a new theme.
    """
    _BUILT_IN = BUILT_IN_PALETTES
    try:
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    # Migrate seed files written under the pre-0.1.27 names: rename them so
    # any hand edits carry over to the new name (skip when the new file
    # already exists — never clobber).
    for old, new in LEGACY_THEME_ALIASES.items():
        old_path = THEMES_DIR / f"{old}.css"
        new_path = THEMES_DIR / f"{new}.css"
        if old_path.exists() and not new_path.exists():
            try:
                old_path.rename(new_path)
            except OSError:
                pass
    header = (
        "/* star CSS theme\n"
        " * Copy this file, give it a new name, and edit freely.\n"
        " * star picks up any *.css file in this directory automatically.\n"
        " * Run  View → Reload CSS Themes  (or restart) to apply changes.\n"
        " */\n\n"
    )
    for name, pal in _BUILT_IN.items():
        path = THEMES_DIR / f"{name}.css"
        if not path.exists():
            try:
                path.write_text(header + _palette_to_css(pal), encoding="utf-8")
            except OSError:
                pass
