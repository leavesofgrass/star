"""Lightweight markup -> Markdown converters (RST, Org, MediaWiki,
AsciiDoc, Textile, Creole, LaTeX) and the Pandoc bridge."""
from ._runtime import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Precompiled regexes for the per-line conversion loops.
# ---------------------------------------------------------------------------
# These patterns previously lived as literal ``re.sub``/``re.match`` calls
# inside ``for line in ...`` loops, so CPython re-looked-up (and, on a cold
# cache, re-compiled) each one on every source line.  They are constant, so
# hoisting them to module scope removes that per-line overhead with byte-for-
# byte identical results.  (The single-pass ``_latex_to_md`` applies each of
# its patterns once per document, so it is intentionally left inline.)

# Org-mode inline markup (applied per line by _orgmode_to_md._inline).
_ORG_BOLD_RE = re.compile(r"\*([^*\s][^*]*[^*\s]|[^*\s])\*")
_ORG_ITALIC_RE = re.compile(r"/([^/\s][^/]*[^/\s]|[^/\s])/")
_ORG_STRIKE_RE = re.compile(r"\+([^+\s][^+]*[^+\s]|[^+\s])\+")
_ORG_CODE_RE = re.compile(r"~([^~]+)~")
_ORG_VERBATIM_RE = re.compile(r"=([^=]+)=")
_ORG_LINK_DESC_RE = re.compile(r"\[\[([^\]]+)\]\[([^\]]+)\]\]")
_ORG_LINK_BARE_RE = re.compile(r"\[\[([^\]]+)\]\]")
_ORG_FOOTNOTE_RE = re.compile(r"\[fn:(\w+)\]")

# MediaWiki (per line by _mediawiki_to_md).
_MW_HEADING_RE = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
_MW_TEMPLATE_RE = re.compile(r"\{\{[^}]+\}\}")
_MW_FILE_RE = re.compile(r"\[\[(?:File|Image|Media):[^\]]*\]\]", re.I)
_MW_WIKILINK_PIPE_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_MW_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_MW_EXTLINK_TEXT_RE = re.compile(r"\[https?://\S+\s+([^\]]+)\]")
_MW_EXTLINK_BARE_RE = re.compile(r"\[https?://\S+\]")
_MW_BOLD_RE = re.compile(r"'''(.+?)'''")
_MW_ITALIC_RE = re.compile(r"''(.+?)''")
_MW_HEADER_CELL_RE = re.compile(r"^!\s*")
_MW_CELL_SEP_RE = re.compile(r"^\|\|")
_MW_ROW_SEP_RE = re.compile(r"^\|-")

# AsciiDoc (per line by _asciidoc_to_md).
_AD_BLOCK_DELIM_RE = re.compile(r"^[-=.+*_]{4,}$")
_AD_SOURCE_RE = re.compile(r"\[source(?:,\s*(\w+))?")
_AD_HEADING_RE = re.compile(r"^(={1,6})\s+(.+)$")
_AD_ATTR_RE = re.compile(r"^:[\w-]+:")
_AD_ADMONITION_RE = re.compile(r"^(NOTE|TIP|WARNING|IMPORTANT|CAUTION):\s*(.*)$")
_AD_MONO_RE = re.compile(r"`(.+?)`")
_AD_BOLD2_RE = re.compile(r"\*\*(.+?)\*\*")
_AD_BOLD1_RE = re.compile(r"\*(?!\*)(.+?)\*")
_AD_BOLDITALIC_RE = re.compile(r"_\*(.+?)\*_|\*_(.+?)_\*")
_AD_ITALIC_RE = re.compile(r"_(?!_)(.+?)_(?!_)")
_AD_LINK_RE = re.compile(r"link:([^\[]+)\[([^\]]*)\]")
_AD_URL_RE = re.compile(r"https?://\S+\[([^\]]+)\]")
_AD_XREF_TEXT_RE = re.compile(r"<<([^,>]+),([^>]+)>>")
_AD_XREF_RE = re.compile(r"<<([^>]+)>>")
_AD_LIST_RE = re.compile(r"^\*\s+")
_AD_NUM_RE = re.compile(r"^\. ")
_AD_BLOCK_ATTR_RE = re.compile(r"^\[.*?\]\s*$")

# Textile (per line by _textile_to_md).
_TX_HEADING_RE = re.compile(r"^h([1-6])\. (.+)$")
_TX_BOLD2_RE = re.compile(r"\*\*(.+?)\*\*")
_TX_BOLD1_RE = re.compile(r"\*(?!\*)(.+?)\*")
_TX_ITALIC2_RE = re.compile(r"__(.+?)__")
_TX_ITALIC1_RE = re.compile(r"_(?!_)(.+?)_")
_TX_CODE_RE = re.compile(r"@(.+?)@")
_TX_LINK_RE = re.compile(r'"([^"]+)":(https?://\S+)')
_TX_BULLET_RE = re.compile(r"^\*{1,3} ")
_TX_NUM_RE = re.compile(r"^#{1,3} ")

# Creole (per line by _creole_to_md).
_CR_HEADING_RE = re.compile(r"^(={1,6})\s*(.+?)\s*=*\s*$")
_CR_HR_RE = re.compile(r"^-{4,}$")
_CR_NOWIKI_RE = re.compile(r"\{\{\{(.+?)\}\}\}")
_CR_ITALIC_RE = re.compile(r"//(.+?)//")
_CR_LINK_PIPE_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_CR_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_CR_IMG_ALT_RE = re.compile(r"\{\{([^|\}]+)\|([^\}]+)\}\}")
_CR_IMG_RE = re.compile(r"\{\{([^\}]+)\}\}")
_CR_NUM_RE = re.compile(r"^(#+) ")

# reStructuredText inline markup (per line by _rst_to_md).
_RST_DIRECTIVE_RE = re.compile(r"\.\.\s+(\w[\w-]*)::(.*)$")
_RST_CODE_RE = re.compile(r"``(.+?)``")
_RST_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_RST_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
_RST_HYPERLINK_RE = re.compile(r"`([^`]+)\s+<([^>]+)>`_+")
_RST_NAMEDREF_RE = re.compile(r"`([^`]+)`_\b")

# Org-mode block-structure patterns (per line by _orgmode_to_md's main loop).
_ORG_BLOCK_BEGIN_RE = re.compile(r"^\s*#\+BEGIN_(\w+)(.*)", re.I)
_ORG_BLOCK_END_RE = re.compile(r"^\s*#\+END_", re.I)
_ORG_DIRECTIVE_RE = re.compile(r"#\+(\w+):\s*(.*)", re.I)
_ORG_DRAWER_RE = re.compile(r"^:[\w-]+:\s*$")
_ORG_HEADLINE_RE = re.compile(r"^(\*+)\s+(.*)")
_ORG_TODO_RE = re.compile(r"^(TODO|DONE|NEXT|WAITING|CANCELED|HOLD)\s+")
_ORG_COMMENT_RE = re.compile(r"^COMMENT\s+")
_ORG_PRIORITY_RE = re.compile(r"\[#[A-Z]\]\s*")
_ORG_TAGS_RE = re.compile(r"\s+:[:\w@#%]+:\s*$")
_ORG_STATS_RE = re.compile(r"\s*\[\d*/?\d*%?\]\s*")
_ORG_TABLE_SEP_RE = re.compile(r"^\|[-+]+\|?$")
_ORG_LIST_RE = re.compile(r"^(\s*)[-+]\s+(\[[ X-]\]\s+)?(.*)")
_ORG_OLIST_RE = re.compile(r"^(\s*)\d+[.)]]\s+(.*)")

# Creole table header cell (per cell inside _creole_to_md's table branch).
_CR_TABLE_HDR_RE = re.compile(r"^=(.+?)=$")


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


# =============================================================================
# Wiki format loaders  (RST · MediaWiki · AsciiDoc · Textile · Creole)
# =============================================================================
#
# Each loader follows the same three-tier strategy:
#   1. Pandoc with an explicit --from flag  —  highest quality when available
#   2. A dedicated Python library            —  no external binary required
#   3. A built-in regex converter            —  always works, covers ~80% of
#      real-world documents well enough for TTS
# =============================================================================


def _pandoc_convert(path: str, from_fmt: str) -> Optional[str]:
    """Run Pandoc with an explicit input format flag.  Returns Markdown or None."""
    if _PYPANDOC:
        try:
            return _pypandoc.convert_file(path, "markdown", format=from_fmt)
        except Exception:
            pass
    if _PANDOC_BIN:
        try:
            r = subprocess.run(
                [_PANDOC_BIN, "--from", from_fmt, "--to", "markdown", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout
        except Exception:
            pass
    return None


# ── reStructuredText (.rst / .rest) ──────────────────────────────────────────────


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


# ── MediaWiki (.wiki / .mediawiki) ───────────────────────────────────────────


def _mediawiki_to_md(text: str) -> str:
    """Basic MediaWiki markup → Markdown heuristic converter."""
    out_lines = []
    for line in text.splitlines():
        # Headings  == Title ==  /  === Title ===  etc.
        hm = _MW_HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1)) - 1  # == is h2 in wiki, treat as ##
            out_lines.append("#" * max(1, level) + " " + hm.group(2))
            continue

        # Template calls  {{...}}  — strip silently
        line = _MW_TEMPLATE_RE.sub("", line)
        # File / Image links  [[File:...]]  [[Image:...]]
        line = _MW_FILE_RE.sub("", line)
        # Wikilinks  [[Page|display]]  or  [[Page]]
        line = _MW_WIKILINK_PIPE_RE.sub(r"\2", line)
        line = _MW_WIKILINK_RE.sub(r"\1", line)
        # External links  [url text]
        line = _MW_EXTLINK_TEXT_RE.sub(r"\1", line)
        line = _MW_EXTLINK_BARE_RE.sub("", line)  # bare external link
        # Bold + italic  '''text'''  /  ''text''
        line = _MW_BOLD_RE.sub(r"**\1**", line)
        line = _MW_ITALIC_RE.sub(r"*\1*", line)
        # Tables (very basic): just strip table markup
        if line.startswith("{|") or line.startswith("|}") or line.startswith("|+"):
            continue
        line = _MW_HEADER_CELL_RE.sub("| ", line)  # header cell
        line = _MW_CELL_SEP_RE.sub("|", line)  # cell separator
        if _MW_ROW_SEP_RE.match(line):
            continue  # row separator
        out_lines.append(line)
    return "\n".join(out_lines)


# ── AsciiDoc (.adoc / .asciidoc / .asc) ─────────────────────────────────────


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


# ── Textile (.textile) ───────────────────────────────────────────────────


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


# ── Wiki Creole (.creole) ─────────────────────────────────────────────────


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


# ── LaTeX (.tex / .ltx) ───────────────────────────────────────────────────


def _latex_to_md(text: str) -> str:  # noqa: C901
    """Strip LaTeX markup and convert to Markdown.

    Handles the constructs most commonly found in academic documents:
    preamble removal, sectioning, \\textbf / \\textit / \\emph,
    itemize / enumerate lists, verbatim / lstlisting / minted code
    blocks, quote / abstract environments, math stripping, special
    character normalization, and citation / cross-reference simplification.
    """
    # ─ Strip comments ───────────────────────────────────────────────────
    text = re.sub(r"%[^\n]*", "", text)

    # ─ Extract body (skip preamble) ─────────────────────────────────
    bm = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
    body = bm.group(1) if bm else text

    # ─ Collect title / author / date from preamble for a header block ──
    header_lines: List[str] = []
    preamble = text[: bm.start()] if bm else ""
    for cmd, fmt in (
        (r"\\title", "# {}"),
        (r"\\author", "*{} *"),
        (r"\\date", "*{} *"),
    ):
        m = re.search(cmd + r"\{([^}]+)\}", preamble + body)
        if m:
            header_lines.append(fmt.format(m.group(1).strip()))
    if header_lines:
        header_lines.append("")
        body = re.sub(r"\\maketitle\b", "", body)

    # ─ Verbatim / code environments ───────────────────────────────
    body = re.sub(
        r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}",
        lambda m: "\n```\n" + m.group(1).strip() + "\n```\n",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{lstlisting\}[^\n]*(.*?)\\end\{lstlisting\}",
        lambda m: "\n```\n" + m.group(1).strip() + "\n```\n",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{minted\}\{(\w+)\}(.*?)\\end\{minted\}",
        lambda m: f"\n```{m.group(1)}\n" + m.group(2).strip() + "\n```\n",
        body,
        flags=re.DOTALL,
    )

    # ─ Quote / abstract environments ─────────────────────────────
    def _blockquote(m: re.Match) -> str:
        return (
            "\n" + "\n".join("> " + ln for ln in m.group(1).strip().splitlines()) + "\n"
        )

    body = re.sub(
        r"\\begin\{(quote|quotation|abstract)\}(.*?)\\end\{\1\}",
        _blockquote,
        body,
        flags=re.DOTALL,
    )

    # ─ List environments ───────────────────────────────────────────
    def _list_env(bullet: str) -> Callable[[re.Match], str]:
        def _replace(m: re.Match) -> str:
            items = re.split(r"\\item\b", m.group(1))
            result = []
            for it in items:
                it = it.strip()
                if it:
                    # \item[label] text  → **label** text
                    it = re.sub(r"^\[([^\]]+)\]\s*", r"**\1** ", it)
                    result.append(bullet + " " + it.replace("\n", " "))
            return "\n".join(result) + "\n"

        return _replace

    body = re.sub(
        r"\\begin\{itemize\}(.*?)\\end\{itemize\}",
        _list_env("*"),
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}",
        _list_env("1."),
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{description\}(.*?)\\end\{description\}",
        _list_env("*"),
        body,
        flags=re.DOTALL,
    )

    # ─ Math (strip display; keep inline content for TTS) ───────────
    for env_name in (
        "equation",
        "equation*",
        "align",
        "align*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "eqnarray",
        "eqnarray*",
        "math",
        "displaymath",
    ):
        body = re.sub(
            r"\\begin\{"
            + re.escape(env_name)
            + r"\}.*?\\end\{"
            + re.escape(env_name)
            + r"\}",
            "",
            body,
            flags=re.DOTALL,
        )
    body = re.sub(r"\$\$.*?\$\$", "", body, flags=re.DOTALL)
    body = re.sub(r"\\\[.*?\\\]", "", body, flags=re.DOTALL)
    body = re.sub(r"\\\((.*?)\\\)", r" \1 ", body, flags=re.DOTALL)
    body = re.sub(r"\$([^$\n]{1,120})\$", r" \1 ", body)

    # ─ Sectioning ────────────────────────────────────────────────
    for cmd, hashes in [
        ("part", "#"),
        ("chapter", "#"),
        ("section", "##"),
        ("subsection", "###"),
        ("subsubsection", "####"),
        ("paragraph", "#####"),
        ("subparagraph", "######"),
    ]:
        body = re.sub(
            r"\\" + cmd + r"\*?\{([^}]+)\}",
            lambda m, h=hashes: f"\n{h} {m.group(1)}\n",
            body,
        )

    # ─ Inline formatting ──────────────────────────────────────────
    body = re.sub(r"\\textbf\{([^}]+)\}", r"**\1**", body)
    body = re.sub(r"\\textit\{([^}]+)\}", r"*\1*", body)
    body = re.sub(r"\\emph\{([^}]+)\}", r"*\1*", body)
    body = re.sub(r"\\texttt\{([^}]+)\}", r"`\1`", body)
    body = re.sub(r"\\textsc\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\textsuperscript\{([^}]+)\}", r"^\1^", body)
    body = re.sub(r"\\textsubscript\{([^}]+)\}", r"~\1~", body)
    body = re.sub(r"\\underline\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\uline\{([^}]+)\}", r"\1", body)

    # ─ References, citations, footnotes ──────────────────────────
    body = re.sub(r"\\(?:cite|citep|citet|citealt|citealp)\{([^}]+)\}", r"[\1]", body)
    body = re.sub(r"\\(?:ref|pageref|eqref|nameref)\{[^}]+\}", "", body)
    body = re.sub(r"\\label\{[^}]+\}", "", body)
    body = re.sub(r"\\footnote\{([^}]{1,200})\}", r" (\1)", body)
    body = re.sub(r"\\footnotemark(?:\[\d+\])?", "", body)
    body = re.sub(r"\\footnotetext\{([^}]{1,200})\}", r" (\1)", body)

    # ─ URLs / hyperlinks ────────────────────────────────────────
    body = re.sub(r"\\url\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\href\{([^}]+)\}\{([^}]+)\}", r"[\2](\1)", body)

    # ─ Skip remaining environments entirely ────────────────────────
    body = re.sub(
        r"\\begin\{(figure|table|algorithm|tikzpicture|tabular)[^}]*\}.*?"
        r"\\end\{\1\}",
        "",
        body,
        flags=re.DOTALL | re.I,
    )

    # ─ Special characters and ligatures ─────────────────────────
    for latex, md_equiv in [
        ("---", "—"),
        ("--", "–"),
        (r"\\ldots", "…"),
        (r"\\dots", "…"),
        (r"\\cdots", "…"),
        ("``", "“"),
        ("''", "”"),
        (r"\\%", "%"),
        (r"\\\$", "$"),
        (r"\\&", "&"),
        (r"\\#", "#"),
        (r"\\{", "{"),
        (r"\\}", "}"),
        (r"\\textasciitilde", "~"),
        (r"\\textasciicircum", "^"),
        (r"\\textbackslash", r"\\"),  # re.sub replacement: r"\\" → one literal backslash
        (r"\\slash", "/"),
        (r"\\,", " "),
        (r"\\;", " "),
        (r"\\!", ""),
        (r"\\quad", "  "),
    ]:
        body = re.sub(latex, md_equiv, body)

    # ─ Strip remaining block/environment tags ──────────────────────
    body = re.sub(r"\\begin\{[^}]+\}", "", body)
    body = re.sub(r"\\end\{[^}]+\}", "", body)

    # ─ Strip remaining LaTeX commands ───────────────────────────
    # Layout / spacing commands
    body = re.sub(
        r"\\(newpage|clearpage|pagebreak|noindent|par|linebreak|newline|\\)",
        "\n",
        body,
    )
    body = re.sub(
        r"\\(medskip|bigskip|smallskip|vspace\*?|hspace\*?)(?:\{[^}]*\})?",
        " ",
        body,
    )
    # Declaration-style commands
    body = re.sub(
        r"\\(centering|raggedright|raggedleft|normalfont|bfseries"
        r"|itshape|ttfamily|large|Large|LARGE|huge|Huge|small|footnotesize)",
        "",
        body,
    )
    # Any remaining command with an argument — keep the argument text
    body = re.sub(r"\\[a-zA-Z]+\*?\{([^}]{1,200})\}", r"\1", body)
    # Any remaining bare command
    body = re.sub(r"\\[a-zA-Z]+\*?\s*", " ", body)

    # ─ Clean up braces and whitespace ─────────────────────────────
    body = body.replace("{", "").replace("}", "")
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r" {2,}", " ", body)

    return "\n".join(header_lines) + body.strip()
