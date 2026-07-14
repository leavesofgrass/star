"""Theme registry invariants — palette schema, contrast, and GUI/TUI parity.

The community palettes (0.1.28) reproduce well-known color schemes; because
star is a reader for people who need reading to work, every text color must
clear WCAG AA (4.5:1) on its background even where the upstream scheme does
not (Solarized's canonical accents famously miss it — ours are nudged).
"""
import re

import pytest

from star.themes import BUILT_IN_PALETTES, BUILT_IN_THEME_NAMES

_PALETTE_KEYS = (
    "bg", "fg", "sel", "h1", "h2", "h3", "h4",
    "code", "code_bg", "link", "muted",
)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_COMMUNITY = [
    "dracula", "nord", "solarized-dark", "solarized-light",
    "gruvbox-dark", "tokyo-night", "catppuccin-mocha", "monokai",
]

# Text-carrying keys checked for contrast against bg (sel/code_bg are
# backgrounds themselves; muted borders/quotes still carry quote text).
_TEXT_KEYS = ("fg", "h1", "h2", "h3", "h4", "code", "link", "muted")


def _luminance(hexstr: str) -> float:
    r, g, b = (int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("name", list(BUILT_IN_PALETTES))
def test_palette_schema_complete(name):
    """Every built-in palette carries all 11 keys as #rrggbb values."""
    pal = BUILT_IN_PALETTES[name]
    for key in _PALETTE_KEYS:
        assert key in pal, f"{name} missing {key!r}"
        assert _HEX.match(pal[key]), f"{name}[{key}] = {pal[key]!r} not #rrggbb"


@pytest.mark.parametrize("name", _COMMUNITY)
def test_community_theme_registered(name):
    assert name in BUILT_IN_THEME_NAMES


def test_cycle_order_preserved():
    """The 0.1.28 additions are appended — the first nine names (the F5
    cycle order existing users know) are unchanged."""
    assert BUILT_IN_THEME_NAMES[:9] == [
        "obsidian", "obsidian-light", "zed-one-dark", "zed-one-light",
        "dark", "light", "contrast", "high-contrast", "phosphor",
    ]


@pytest.mark.parametrize("name", _COMMUNITY)
def test_community_theme_meets_wcag_aa(name):
    """Every text color clears 4.5:1 on the theme background."""
    pal = BUILT_IN_PALETTES[name]
    for key in _TEXT_KEYS:
        ratio = _contrast(pal["bg"], pal[key])
        assert ratio >= 4.5, (
            f"{name} {key} ({pal[key]}) is only {ratio:.2f}:1 on {pal['bg']}"
        )


@pytest.mark.parametrize("name", _COMMUNITY)
def test_community_theme_code_readable_on_code_bg(name):
    """Inline code paints on code_bg, not bg — it must clear AA there too."""
    pal = BUILT_IN_PALETTES[name]
    ratio = _contrast(pal["code_bg"], pal["code"])
    assert ratio >= 4.5, (
        f"{name} code ({pal['code']}) is only {ratio:.2f}:1 on "
        f"code_bg {pal['code_bg']}"
    )


def test_gui_and_tui_share_community_names():
    """A profile's theme name carries across both UIs: every community
    palette exists in the TUI THEMES table under the same name."""
    from star.tui.theming import THEMES as TUI_THEMES

    for name in _COMMUNITY:
        assert name in TUI_THEMES, f"TUI lacks {name!r}"


def test_seeded_css_round_trips(tmp_path, monkeypatch):
    """_seed_default_css_themes writes every palette; _parse_css_palette
    recovers the same colors from the generated CSS."""
    import star.themes as themes_mod

    monkeypatch.setattr(themes_mod, "THEMES_DIR", tmp_path)
    themes_mod._seed_default_css_themes()
    for name, pal in BUILT_IN_PALETTES.items():
        css_path = tmp_path / f"{name}.css"
        assert css_path.exists(), f"seed missing for {name}"
        parsed = themes_mod._parse_css_palette(
            css_path.read_text(encoding="utf-8")
        )
        for key in ("bg", "fg", "h1", "code", "link"):
            assert parsed[key].lower() == pal[key].lower(), (
                f"{name}[{key}] did not round-trip: "
                f"{pal[key]} -> {parsed[key]}"
            )
