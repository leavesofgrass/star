"""Textile (.textile) → Markdown heuristic converter."""
from .._runtime import *  # noqa: F401,F403
from ._regexes import (
    _TX_BOLD1_RE,
    _TX_BOLD2_RE,
    _TX_BULLET_RE,
    _TX_CODE_RE,
    _TX_HEADING_RE,
    _TX_ITALIC1_RE,
    _TX_ITALIC2_RE,
    _TX_LINK_RE,
    _TX_NUM_RE,
)


def _textile_to_md(text: str) -> str:
    """Basic Textile → Markdown heuristic converter."""
    out_lines = []
    for line in text.splitlines():
        # Block tags  h1. h2. …  p.  bq.
        hm = _TX_HEADING_RE.match(line)
        if hm:
            out_lines.append("#" * int(hm.group(1)) + " " + hm.group(2))
            continue
        if line.startswith("bq. "):
            out_lines.append("> " + line[4:])
            continue
        if line.startswith("p. "):
            line = line[3:]
        if line.startswith("pre. "):
            out_lines.append("```")
            out_lines.append(line[5:])
            out_lines.append("```")
            continue

        # Inline
        line = _TX_BOLD2_RE.sub(r"**\1**", line)  # bold
        line = _TX_BOLD1_RE.sub(r"**\1**", line)  # Textile *bold*
        line = _TX_ITALIC2_RE.sub(r"*\1*", line)  # italic
        line = _TX_ITALIC1_RE.sub(r"*\1*", line)  # Textile _italic_
        line = _TX_CODE_RE.sub(r"`\1`", line)  # code
        line = _TX_LINK_RE.sub(r"[\1](\2)", line)  # link
        line = _TX_BULLET_RE.sub("* ", line)  # bullets (Textile allows */**)
        line = _TX_NUM_RE.sub("1. ", line)  # numbered
        out_lines.append(line)
    return "\n".join(out_lines)
