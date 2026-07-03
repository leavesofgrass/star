"""Wiki Creole (.creole) → Markdown converter."""
from .._runtime import *  # noqa: F401,F403
from ._regexes import (
    _CR_HEADING_RE,
    _CR_HR_RE,
    _CR_IMG_ALT_RE,
    _CR_IMG_RE,
    _CR_ITALIC_RE,
    _CR_LINK_PIPE_RE,
    _CR_LINK_RE,
    _CR_NOWIKI_RE,
    _CR_NUM_RE,
    _CR_TABLE_HDR_RE,
)


def _creole_to_md(text: str) -> str:
    """Basic Wiki Creole 1.0 → Markdown converter.

    Creole is a deliberately simple and regular wiki syntax; the full spec
    is small enough to implement here without external libraries.
    """
    out_lines = []
    in_nowiki_block = False
    for line in text.splitlines():
        # Nowiki blocks  {{{ / }}}
        if line.strip() == "{{{":
            in_nowiki_block = True
            out_lines.append("```")
            continue
        if line.strip() == "}}}":
            in_nowiki_block = False
            out_lines.append("```")
            continue
        if in_nowiki_block:
            out_lines.append(line)
            continue

        # Headings  == h2 ==  up to ====== h6 ======
        hm = _CR_HEADING_RE.match(line)
        if hm:
            out_lines.append("#" * len(hm.group(1)) + " " + hm.group(2))
            continue

        # Horizontal rule  ----
        if _CR_HR_RE.match(line.strip()):
            out_lines.append("---")
            continue

        # Inline nowiki  {{{text}}}
        line = _CR_NOWIKI_RE.sub(r"`\1`", line)
        # Bold  **text**  → already Markdown
        # Italic  //text//
        line = _CR_ITALIC_RE.sub(r"*\1*", line)
        # Links  [[url|text]]  [[url]]
        line = _CR_LINK_PIPE_RE.sub(r"[\2](\1)", line)
        line = _CR_LINK_RE.sub(r"[\1](\1)", line)
        # Images  {{url|alt}}  {{url}}
        line = _CR_IMG_ALT_RE.sub(r"![\2](\1)", line)
        line = _CR_IMG_RE.sub(r"![](\1)", line)
        # Bullet lists  * item  (already Markdown-compatible)
        # Numbered lists  # item  → 1. item
        line = _CR_NUM_RE.sub(lambda m: "1. " * len(m.group(1)), line)
        # Table rows  |cell|cell|
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            # Header row has = in first cell convention; keep as-is
            cells = [_CR_TABLE_HDR_RE.sub(r"**\1**", c) for c in cells]
            line = "| " + " | ".join(cells) + " |"
        out_lines.append(line)
    return "\n".join(out_lines)
