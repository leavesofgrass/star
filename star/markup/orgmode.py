"""Org-mode → Markdown heuristic converter."""
from .._runtime import *  # noqa: F401,F403
from ._regexes import (
    _ORG_BLOCK_BEGIN_RE,
    _ORG_BLOCK_END_RE,
    _ORG_BOLD_RE,
    _ORG_CODE_RE,
    _ORG_COMMENT_RE,
    _ORG_DIRECTIVE_RE,
    _ORG_DRAWER_RE,
    _ORG_FOOTNOTE_RE,
    _ORG_HEADLINE_RE,
    _ORG_ITALIC_RE,
    _ORG_LINK_BARE_RE,
    _ORG_LINK_DESC_RE,
    _ORG_LIST_RE,
    _ORG_OLIST_RE,
    _ORG_PRIORITY_RE,
    _ORG_STATS_RE,
    _ORG_STRIKE_RE,
    _ORG_TABLE_SEP_RE,
    _ORG_TAGS_RE,
    _ORG_TODO_RE,
    _ORG_VERBATIM_RE,
)


def _orgmode_to_md(text: str) -> str:  # noqa: C901
    """Convert Org-mode markup to Markdown.

    Covers: headlines with TODO/tag/priority stripping, all block types
    (src, example, verbatim, quote, verse, comment), PROPERTIES and
    LOGBOOK drawers, bullet/numbered lists, tables, and the full set of
    Org inline markup (bold, italic, underline, strike-through, code,
    verbatim, links, footnotes).
    """
    lines = text.splitlines()
    out: List[str] = []
    title_prefix: List[str] = []
    in_block: Optional[str] = (
        None  # 'src'|'example'|'verbatim'|'quote'|'verse'|'comment'
    )
    i = 0

    def _inline(ln: str) -> str:
        """Apply Org inline markup to a plain line."""
        ln = _ORG_BOLD_RE.sub(r"**\1**", ln)  # bold
        ln = _ORG_ITALIC_RE.sub(r"*\1*", ln)  # italic
        ln = _ORG_STRIKE_RE.sub(r"~~\1~~", ln)  # strike
        ln = _ORG_CODE_RE.sub(r"`\1`", ln)  # code
        ln = _ORG_VERBATIM_RE.sub(r"`\1`", ln)  # verbatim
        ln = _ORG_LINK_DESC_RE.sub(r"[\2](\1)", ln)  # link+desc
        ln = _ORG_LINK_BARE_RE.sub(r"[\1](\1)", ln)  # bare link
        ln = _ORG_FOOTNOTE_RE.sub(r"^[\1]^", ln)  # footnote
        return ln

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── Block begin ─────────────────────────────────────────────────
        bm = _ORG_BLOCK_BEGIN_RE.match(stripped)
        if bm:
            btype = bm.group(1).lower()
            barg = bm.group(2).strip()
            in_block = btype
            if btype == "src":
                lang = barg.split()[0] if barg else ""
                out.append(f"```{lang}")
            elif btype in ("example", "verbatim"):
                out.append("```")
            # quote / verse / comment: no open fence
            i += 1
            continue

        # ── Block end ────────────────────────────────────────────────────
        if _ORG_BLOCK_END_RE.match(stripped):
            if in_block in ("src", "example", "verbatim"):
                out.append("```")
            in_block = None
            i += 1
            continue

        # ── Inside a block ──────────────────────────────────────────────
        if in_block == "comment":
            i += 1
            continue
        if in_block in ("src", "example", "verbatim"):
            out.append(line)
            i += 1
            continue
        if in_block in ("quote", "verse"):
            out.append("> " + _inline(stripped) if stripped else ">")
            i += 1
            continue

        # ── File-level directives ───────────────────────────────────────
        if stripped.startswith("#"):
            dm = _ORG_DIRECTIVE_RE.match(stripped)
            if dm:
                key, val = dm.group(1).upper(), dm.group(2).strip()
                if key == "TITLE":
                    title_prefix[:] = [f"# {val}", ""]
                elif key == "SUBTITLE":
                    title_prefix.append(f"**{val}**")
                    title_prefix.append("")
                elif key == "AUTHOR":
                    title_prefix.append(f"*{val}*")
                elif key == "DATE":
                    title_prefix.append(f"*{val}*")
            i += 1
            continue

        # ── Drawers  :PROPERTIES: / :LOGBOOK: / arbitrary ──────────────
        if _ORG_DRAWER_RE.match(stripped) and stripped != ":END:":
            while i < len(lines) and lines[i].strip() != ":END:":
                i += 1
            i += 1  # skip :END:
            continue

        # ── Headlines ────────────────────────────────────────────────────
        hm = _ORG_HEADLINE_RE.match(line)
        if hm:
            body = hm.group(2)
            body = _ORG_TODO_RE.sub("", body)
            body = _ORG_COMMENT_RE.sub("", body)
            body = _ORG_PRIORITY_RE.sub("", body)  # priority
            body = _ORG_TAGS_RE.sub("", body)  # tags
            body = _ORG_STATS_RE.sub("", body)  # statistics
            out.append("#" * min(len(hm.group(1)), 6) + " " + body.strip())
            i += 1
            continue

        # ── Tables ──────────────────────────────────────────────────────
        if stripped.startswith("|"):
            # Separator row  |---+---|  → Markdown  | --- | --- |
            if _ORG_TABLE_SEP_RE.match(stripped.replace(" ", "")):
                # Count columns from previous row if available
                prev = out[-1] if out else ""
                ncols = prev.count("|") - 1 if "|" in prev else 1
                out.append("|" + "|".join([" --- "] * max(ncols, 1)) + "|")
            else:
                cells = [_inline(c.strip()) for c in stripped.strip("|").split("|")]
                out.append("| " + " | ".join(cells) + " |")
            i += 1
            continue

        # ── Lists ────────────────────────────────────────────────────────
        # Org unordered: - item  + item  (checkboxes: - [ ] item)
        lm = _ORG_LIST_RE.match(line)
        if lm:
            checkbox = lm.group(2) or ""
            check_md = "[x] " if "X" in checkbox else "[ ] " if "[" in checkbox else ""
            out.append(lm.group(1) + "* " + check_md + _inline(lm.group(3)))
            i += 1
            continue
        # Org ordered: 1. item  1) item
        lm2 = _ORG_OLIST_RE.match(line)
        if lm2:
            out.append(lm2.group(1) + "1. " + _inline(lm2.group(2)))
            i += 1
            continue

        # ── Plain text with inline markup ───────────────────────────────
        out.append(_inline(line))
        i += 1

    return "\n".join(title_prefix + out)
