"""Visual LaTeX-math → readable Unicode rendering for the GUI document view.

This module renders a *subset* of inline/display LaTeX math to Unicode so the
Qt rich-text pane can show ``x²``, ``√2``, ``½``, ``α`` etc. instead of raw
``x^2``, ``\\sqrt{2}``, ``\\frac{1}{2}``, ``\\alpha``.

It is deliberately independent of the *speech* path: TTS still receives the
**raw** LaTeX and is normalized to spoken English by
``star.ttstext._normalize_math_inline``.  Nothing here touches that pipeline —
this only rewrites the display markdown that ``_md_body_to_html`` turns into
HTML.

Design constraints
------------------
* Pure string→string, no third-party deps, safe to import anywhere.
* Best-effort: anything it cannot map to Unicode is left as readable text
  (braces stripped, command backslashes dropped) rather than raising.
* The QTextEdit rich-text subset has *no* MathML and unreliable ``<sup>`` /
  ``<sub>`` sizing, so we prefer real Unicode super/subscript codepoints and
  fall back to ``<sup>``/``<sub>`` tags only for characters that lack them.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Unicode super/subscript maps
# ---------------------------------------------------------------------------
# Superscript forms exist in Unicode for digits, +, -, =, (, ), n, i and a
# handful of letters.  Subscript forms exist for digits, +, -, =, (, ) and a
# small set of lowercase letters.  Anything outside these falls back to a tag.

_SUP_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
    "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "j": "ʲ", "k": "ᵏ",
    "l": "ˡ", "m": "ᵐ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ",
    "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ",
    "x": "ˣ", "y": "ʸ", "z": "ᶻ",
    "A": "ᴬ", "B": "ᴮ", "D": "ᴰ", "E": "ᴱ", "G": "ᴳ",
    "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ",
    "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "R": "ᴿ",
    "T": "ᵀ", "U": "ᵁ", "W": "ᵂ",
}

_SUB_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
    "v": "ᵥ", "x": "ₓ",
}

# ---------------------------------------------------------------------------
# Greek letters and common symbols
# ---------------------------------------------------------------------------

_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "ϕ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "omicron": "ο",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

# Backslash command → Unicode symbol.  Longest-name-first ordering is enforced
# at substitution time so e.g. ``\leftrightarrow`` wins over ``\left``.
_SYMBOLS = {
    "times": "×", "div": "÷", "cdot": "⋅", "ast": "∗",
    "star": "⋆", "circ": "∘", "bullet": "∙",
    "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "neq": "≠", "ne": "≠", "equiv": "≡", "approx": "≈",
    "sim": "∼", "simeq": "≃", "cong": "≅", "propto": "∝",
    "ll": "≪", "gg": "≫",
    "infty": "∞", "partial": "∂", "nabla": "∇",
    "sum": "∑", "prod": "∏", "int": "∫", "oint": "∮",
    "sqrt": "√", "surd": "√",
    "rightarrow": "→", "to": "→", "Rightarrow": "⇒",
    "leftarrow": "←", "gets": "←", "Leftarrow": "⇐",
    "leftrightarrow": "↔", "Leftrightarrow": "⇔",
    "mapsto": "↦", "uparrow": "↑", "downarrow": "↓",
    "forall": "∀", "exists": "∃", "nexists": "∄",
    "in": "∈", "notin": "∉", "ni": "∋",
    "subset": "⊂", "supset": "⊃", "subseteq": "⊆",
    "supseteq": "⊇", "cup": "∪", "cap": "∩",
    "emptyset": "∅", "varnothing": "∅",
    "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨",
    "neg": "¬", "lnot": "¬",
    "angle": "∠", "perp": "⟂", "parallel": "∥",
    "deg": "°", "prime": "′",
    "cdots": "⋯", "ldots": "…", "dots": "…", "vdots": "⋮",
    "aleph": "ℵ", "hbar": "ℏ", "ell": "ℓ", "Re": "ℜ",
    "Im": "ℑ", "wp": "℘",
    "leftharpoonup": "↼", "rightharpoonup": "⇀",
    "langle": "⟨", "rangle": "⟩",
    "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "otimes": "⊗", "oplus": "⊕", "odot": "⊙",
    "setminus": "∖", "backslash": "∖",
    "top": "⊤", "bot": "⊥", "vdash": "⊢", "models": "⊨",
    "therefore": "∴", "because": "∵",
    "quad": " ", "qquad": "  ", "space": " ",
}

# Common ``\frac{a}{b}`` numerator/denominator pairs that have a dedicated
# Unicode vulgar-fraction glyph.  Anything else becomes ``a⁄b`` (fraction
# slash) which still reads clearly.
_VULGAR = {
    ("1", "2"): "½", ("1", "3"): "⅓", ("2", "3"): "⅔",
    ("1", "4"): "¼", ("3", "4"): "¾", ("1", "5"): "⅕",
    ("2", "5"): "⅖", ("3", "5"): "⅗", ("4", "5"): "⅘",
    ("1", "6"): "⅙", ("5", "6"): "⅚", ("1", "7"): "⅐",
    ("1", "8"): "⅛", ("3", "8"): "⅜", ("5", "8"): "⅝",
    ("7", "8"): "⅞", ("1", "9"): "⅑", ("1", "10"): "⅒",
}

# Accent commands → combining Unicode mark appended after the base char.
_ACCENTS = {
    "hat": "̂", "widehat": "̂", "bar": "̄", "overline": "̄",
    "vec": "⃗", "dot": "̇", "ddot": "̈", "tilde": "̃",
    "widetilde": "̃", "acute": "́", "grave": "̀",
    "check": "̌", "breve": "̆",
}

# Font-style wrappers that carry no visual math meaning for us — unwrap to the
# inner text (``\mathbf{x}`` → ``x``, ``\text{if}`` → ``if``).
_FONT_CMDS = (
    "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb",
    "mathfrak", "boldsymbol", "text", "textrm", "textbf", "textit", "operatorname",
)

_GREEK_RE = re.compile(
    r"\\(" + "|".join(sorted(_GREEK, key=len, reverse=True)) + r")\b"
)
_SYMBOL_RE = re.compile(
    r"\\(" + "|".join(re.escape(k) for k in sorted(_SYMBOLS, key=len, reverse=True)) + r")"
    r"(?![a-zA-Z])"
)
_FONT_RE = re.compile(r"\\(?:" + "|".join(_FONT_CMDS) + r")\s*\{([^{}]*)\}")
_ACCENT_RE = re.compile(
    r"\\(" + "|".join(sorted(_ACCENTS, key=len, reverse=True)) + r")\s*"
    r"(?:\{([^{}]*)\}|(\w))"
)
_FRAC_RE = re.compile(r"\\(?:d|t)?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT_RE = re.compile(r"\\sqrt\s*(?:\[([^\]]*)\])?\s*\{([^{}]*)\}")
_SUP_RE = re.compile(r"\^\s*(?:\{([^{}]*)\}|(\\?[A-Za-z0-9]))")
_SUB_RE = re.compile(r"_\s*(?:\{([^{}]*)\}|(\\?[A-Za-z0-9]))")

# Inline math delimiters, longest first so ``$$`` / ``\[`` win over ``$`` / ``\(``.
_DISPLAY_DOLLAR_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_DISPLAY_BRACKET_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_INLINE_DOLLAR_RE = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$", re.DOTALL)
_INLINE_PAREN_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)


def _to_super(s: str) -> str:
    """Map *s* to Unicode superscript, or fall back to a ``<sup>`` tag when any
    character has no superscript codepoint."""
    if s and all(c in _SUP_MAP for c in s):
        return "".join(_SUP_MAP[c] for c in s)
    return f"<sup>{s}</sup>"


def _to_sub(s: str) -> str:
    """Map *s* to Unicode subscript, or fall back to a ``<sub>`` tag."""
    if s and all(c in _SUB_MAP for c in s):
        return "".join(_SUB_MAP[c] for c in s)
    return f"<sub>{s}</sub>"


def _render_expr(expr: str) -> str:
    """Render one LaTeX math *expr* body (delimiters already stripped) to a
    readable Unicode/HTML string.

    The transformations run inside-out where nesting matters (fonts and accents
    first so their inner text is exposed, then fractions/roots, then scripts,
    then bare symbols)."""
    s = expr

    # Font/style wrappers → inner text (repeat to unwrap simple nesting).
    for _ in range(3):
        new = _FONT_RE.sub(lambda m: m.group(1), s)
        if new == s:
            break
        s = new

    # Accents: base char + combining mark.
    def _accent(m: "re.Match") -> str:
        mark = _ACCENTS[m.group(1)]
        base = m.group(2) if m.group(2) is not None else (m.group(3) or "")
        base = _render_expr(base) if len(base) > 1 else base
        return base + mark

    s = _ACCENT_RE.sub(_accent, s)

    # Fractions.
    def _frac(m: "re.Match") -> str:
        num, den = m.group(1).strip(), m.group(2).strip()
        vulgar = _VULGAR.get((num, den))
        if vulgar:
            return vulgar
        return f"{_render_expr(num)}⁄{_render_expr(den)}"

    s = _FRAC_RE.sub(_frac, s)

    # Roots: √{x} and n-th roots.
    def _sqrt(m: "re.Match") -> str:
        index, body = m.group(1), _render_expr(m.group(2).strip())
        if index:
            return f"{_to_super(index.strip())}√{body}"
        return f"√{body}"

    s = _SQRT_RE.sub(_sqrt, s)

    # Superscripts / subscripts (braced group or single token).
    def _sup(m: "re.Match") -> str:
        body = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        return _to_super(_render_expr(body).lstrip("\\"))

    def _sub(m: "re.Match") -> str:
        body = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        return _to_sub(_render_expr(body).lstrip("\\"))

    s = _SUP_RE.sub(_sup, s)
    s = _SUB_RE.sub(_sub, s)

    # LaTeX spacing commands (\, \; \: \! \ ) — collapse to a space (or nothing
    # for the negative thin space) before the general symbol pass, which uses a
    # letter lookahead that would otherwise skip a punctuation-named command
    # immediately followed by a letter (e.g. ``\,dx``).
    s = re.sub(r"\\[,;:]", " ", s)
    s = s.replace("\\!", "").replace("\\ ", " ")

    # Greek letters and standalone symbols.
    s = _GREEK_RE.sub(lambda m: _GREEK[m.group(1)], s)
    s = _SYMBOL_RE.sub(lambda m: _SYMBOLS[m.group(1)], s)

    # \left( \right) sizing hints carry no meaning here.
    s = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg)\b", "", s)

    # Any residual command: drop the backslash, keep the name (e.g. \max → max).
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)
    # Drop leftover braces and the LaTeX alignment/escape characters.
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    s = s.replace("&", " ")
    # Collapse the double spaces a stripped command can leave behind.
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def render_math_to_unicode(text: str) -> str:
    """Rewrite inline/display LaTeX math in *text* to Unicode for display.

    Recognizes ``$…$``, ``$$…$$``, ``\\(…\\)`` and ``\\[…\\]`` delimiters and
    replaces each with a rendered Unicode string.  Text outside math is
    untouched.  The raw LaTeX is *not* preserved in the output — callers that
    need the original (e.g. the TTS path) must work from the pre-render source.

    Display math (``$$`` / ``\\[``) is wrapped so the caller can center it; here
    it is emitted plain and the block wrapper is added by the HTML builder.
    """
    if not text or ("$" not in text and "\\(" not in text and "\\[" not in text):
        return text

    text = _DISPLAY_DOLLAR_RE.sub(lambda m: _render_expr(m.group(1).strip()), text)
    text = _DISPLAY_BRACKET_RE.sub(lambda m: _render_expr(m.group(1).strip()), text)
    text = _INLINE_PAREN_RE.sub(lambda m: _render_expr(m.group(1).strip()), text)
    text = _INLINE_DOLLAR_RE.sub(lambda m: _render_expr(m.group(1).strip()), text)
    return text


def has_math(text: str) -> bool:
    """Cheap pre-check: does *text* look like it contains LaTeX math?"""
    return bool(text) and (
        "$" in text or "\\(" in text or "\\[" in text or "\\frac" in text
    )
