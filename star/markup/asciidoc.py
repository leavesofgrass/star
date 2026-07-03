"""AsciiDoc (.adoc / .asciidoc / .asc) → Markdown heuristic converter."""
from .._runtime import *  # noqa: F401,F403
from ._regexes import (
    _AD_ADMONITION_RE,
    _AD_ATTR_RE,
    _AD_BLOCK_ATTR_RE,
    _AD_BLOCK_DELIM_RE,
    _AD_BOLD1_RE,
    _AD_BOLD2_RE,
    _AD_BOLDITALIC_RE,
    _AD_HEADING_RE,
    _AD_ITALIC_RE,
    _AD_LINK_RE,
    _AD_LIST_RE,
    _AD_MONO_RE,
    _AD_NUM_RE,
    _AD_SOURCE_RE,
    _AD_URL_RE,
    _AD_XREF_RE,
    _AD_XREF_TEXT_RE,
)


def _asciidoc_to_md(text: str) -> str:
    """Basic AsciiDoc → Markdown heuristic converter."""
    out_lines = []
    skip_next_block = False
    i = 0
    lines = text.splitlines()
    while i < len(lines):
        line = lines[i]
        # Block delimiter  ---- or ==== or ....  (listing / example blocks)
        if _AD_BLOCK_DELIM_RE.match(line.strip()):
            skip_next_block = not skip_next_block
            if skip_next_block:
                # Check if it is a source block by looking at [source] above
                prev = out_lines[-1].strip() if out_lines else ""
                lang_m = _AD_SOURCE_RE.match(prev)
                lang = lang_m.group(1) if lang_m and lang_m.group(1) else ""
                if lang_m:
                    out_lines.pop()  # remove [source,...] line
                out_lines.append(f"```{lang}")
            else:
                out_lines.append("```")
            i += 1
            continue

        stripped = line.strip()

        # Section title  = h1  == h2  === h3 …
        hm = _AD_HEADING_RE.match(stripped)
        if hm:
            out_lines.append("#" * len(hm.group(1)) + " " + hm.group(2))
            i += 1
            continue

        # Attribute entries  :name: value  (skip)
        if _AD_ATTR_RE.match(stripped):
            i += 1
            continue

        # Block title  .Title
        if stripped.startswith(".") and not stripped.startswith("..."):
            out_lines.append(f"**{stripped[1:]}**")
            i += 1
            continue

        # Admonitions  NOTE: / TIP: / WARNING: / IMPORTANT: / CAUTION:
        am = _AD_ADMONITION_RE.match(stripped)
        if am:
            out_lines.append(f"> **{am.group(1)}:** {am.group(2)}")
            i += 1
            continue

        # Inline markup
        line = _AD_MONO_RE.sub(r"`\1`", line)  # monospace
        line = _AD_BOLD2_RE.sub(r"**\1**", line)  # bold (unchanged)
        line = _AD_BOLD1_RE.sub(r"**\1**", line)  # AsciiDoc *bold*
        line = _AD_BOLDITALIC_RE.sub(r"***\1\2***", line)  # bold italic
        line = _AD_ITALIC_RE.sub(r"*\1*", line)  # italic
        line = _AD_LINK_RE.sub(r"[\2](\1)", line)  # link
        line = _AD_URL_RE.sub(
            lambda m: f"[{m.group(1)}]({m.group(0)[: m.group(0).index('[')]})",
            line,
        )  # URL[text]
        line = _AD_XREF_TEXT_RE.sub(r"\2", line)  # xref
        line = _AD_XREF_RE.sub(r"\1", line)  # bare xref
        line = _AD_LIST_RE.sub("* ", line)  # list continuity
        line = _AD_NUM_RE.sub("1. ", line)  # numbered list item
        line = _AD_BLOCK_ATTR_RE.sub("", line)  # block attribute lines
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)
