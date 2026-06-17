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
code {{ color: {code}; font-family: monospace; }}
pre  {{ color: {code}; font-family: monospace; white-space: pre-wrap; }}
b    {{ font-weight: bold; }}
i    {{ font-style: italic; }}
p    {{ margin: 4px 0; }}
"""


def _palette_to_css(pal: Dict[str, str]) -> str:
    """Format *_CSS_TEMPLATE* with the values from a palette dict."""
    return _CSS_TEMPLATE.format(**pal)


def _parse_css_palette(css: str) -> Dict[str, str]:
    """Extract the 8 palette keys (bg/fg/sel/h1–h4/code) from a CSS string.

    Only plain color values (hex codes, named colors, or rgb/rgba) are
    extracted; any key that cannot be found falls back to the 'dark' palette
    so the result is always a complete, valid palette dict.
    """
    # Start with dark-theme defaults so every key is always present.
    from copy import deepcopy as _dc

    _DARK = {
        "bg": "#16181d",
        "fg": "#c6ccd4",
        "sel": "#2c313a",
        "h1": "#82aaff",
        "h2": "#89ddff",
        "h3": "#c792ea",
        "h4": "#f78c6c",
        "code": "#7fdbab",
    }
    pal = _dc(_DARK)

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

    # code { color: X; }
    m = re.search(r"\bcode\b\s*\{([^}]*)\}", css, re.DOTALL | re.IGNORECASE)
    if m:
        c = re.search(r"(?<!background-)color\s*:\s*" + _val, m.group(1), re.I)
        if c:
            pal["code"] = c.group(1).strip().rstrip(";")

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
    """Write the four built-in palettes as CSS files in *THEMES_DIR*.

    Files are only written if they do not already exist, so hand-edited
    customizations are never overwritten.  Each generated file serves as a
    ready-made starting point for user customization — copy, rename, and
    edit to create a new theme.
    """
    # Import the built-in palettes lazily to avoid a forward-reference at
    # module level (StarWindow._PALETTES is defined inside _run_qt_gui).
    _BUILT_IN: Dict[str, Dict[str, str]] = {
        "dark": {
            "bg": "#16181d",
            "fg": "#c6ccd4",
            "sel": "#2c313a",
            "h1": "#82aaff",
            "h2": "#89ddff",
            "h3": "#c792ea",
            "h4": "#f78c6c",
            "code": "#7fdbab",
        },
        "light": {
            "bg": "#fafafa",
            "fg": "#24273a",
            "sel": "#bcd0f0",
            "h1": "#1e66f5",
            "h2": "#209fb5",
            "h3": "#8839ef",
            "h4": "#e64553",
            "code": "#40a02b",
        },
        "contrast": {
            "bg": "#000000",
            "fg": "#ffffff",
            "sel": "#404040",
            "h1": "#ffff00",
            "h2": "#00ffff",
            "h3": "#ff80ff",
            "h4": "#80ff80",
            "code": "#00ff80",
        },
        "phosphor": {
            "bg": "#001200",
            "fg": "#00cc00",
            "sel": "#004400",
            "h1": "#00ff00",
            "h2": "#00ee00",
            "h3": "#00cc00",
            "h4": "#00aa00",
            "code": "#009900",
        },
    }
    try:
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
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
