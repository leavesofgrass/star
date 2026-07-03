"""reStructuredText (.rst / .rest) → Markdown heuristic converter."""
from .._runtime import *  # noqa: F401,F403
from ._regexes import (
    _RST_BOLD_RE,
    _RST_CODE_RE,
    _RST_DIRECTIVE_RE,
    _RST_HYPERLINK_RE,
    _RST_ITALIC_RE,
    _RST_NAMEDREF_RE,
)


def _rst_to_md(text: str) -> str:
    """Basic reStructuredText → Markdown heuristic converter.

    Handles section headings (underline ± overline style), bold, italic,
    inline/block code, external hyperlinks, bullet / numbered lists, and
    note / warning / tip admonitions.
    """
    ADORN_CHARS = set(r"=-~^\"'`#+*@!$%&,./:<>?[]{}()")
    level_chars: List[str] = []  # adornment chars in first-encounter order
    lines = text.splitlines()
    out: List[str] = []
    i = 0

    def _heading(char: str, title: str) -> str:
        if char not in level_chars:
            level_chars.append(char)
        return "#" * min(level_chars.index(char) + 1, 6) + " " + title

    def _is_adorn(s: str) -> bool:
        return (
            bool(s)
            and len(s) >= 3
            and all(c == s[0] for c in s)
            and s[0] in ADORN_CHARS
        )

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # Overline + title + underline  (=====  Title  =====)
        if _is_adorn(stripped) and i + 2 < len(lines):
            title = lines[i + 1].strip()
            under = lines[i + 2].strip()
            if title and _is_adorn(under) and under[0] == stripped[0]:
                out.append(_heading(stripped[0], title))
                i += 3
                continue

        # Title + underline
        if stripped and i + 1 < len(lines):
            under = lines[i + 1].strip()
            if _is_adorn(under) and len(under) >= len(stripped):
                out.append(_heading(under[0], stripped))
                i += 2
                continue

        # Bare adornment line (leftover overline or separator)
        if _is_adorn(stripped):
            i += 1
            continue

        # Directives: .. code-block::, .. note::, etc.
        dm = _RST_DIRECTIVE_RE.match(stripped)
        if dm:
            directive, arg = dm.group(1).lower(), dm.group(2).strip()
            if directive in ("code", "code-block", "sourcecode"):
                out.append(f"```{arg}")
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1  # blank line after directive
                while i < len(lines) and (
                    lines[i].startswith("   ")
                    or lines[i].startswith("\t")
                    or not lines[i].strip()
                ):
                    body = lines[i]
                    if body.startswith("   "):
                        body = body[3:]
                    elif body.startswith("\t"):
                        body = body[1:]
                    out.append(body)
                    i += 1
                out.append("```")
                continue
            if directive in (
                "note",
                "warning",
                "tip",
                "important",
                "caution",
                "danger",
            ):
                parts = [arg] if arg else []
                i += 1
                while i < len(lines) and (
                    lines[i].startswith("   ") or not lines[i].strip()
                ):
                    if lines[i].strip():
                        parts.append(lines[i].strip())
                    i += 1
                out.append(f"> **{directive.capitalize()}:** {' '.join(parts)}")
                out.append("")
                continue
            i += 1
            continue

        # Hyperlink target  .. _name: url  (skip — simplified)
        if stripped.startswith(".. _") and ":" in stripped:
            i += 1
            continue

        # Inline markup
        raw = _RST_CODE_RE.sub(r"`\1`", raw)  # inline code
        raw = _RST_BOLD_RE.sub(r"**\1**", raw)  # bold
        raw = _RST_ITALIC_RE.sub(r"*\1*", raw)  # italic
        raw = _RST_HYPERLINK_RE.sub(r"[\1](\2)", raw)  # hyperlink
        raw = _RST_NAMEDREF_RE.sub(r"\1", raw)  # named ref
        out.append(raw)
        i += 1

    return "\n".join(out)
