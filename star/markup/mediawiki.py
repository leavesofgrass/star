"""MediaWiki (.wiki / .mediawiki) → Markdown heuristic converter."""
from .._runtime import *  # noqa: F401,F403
from ._regexes import (
    _MW_BOLD_RE,
    _MW_CELL_SEP_RE,
    _MW_EXTLINK_BARE_RE,
    _MW_EXTLINK_TEXT_RE,
    _MW_FILE_RE,
    _MW_HEADER_CELL_RE,
    _MW_HEADING_RE,
    _MW_ITALIC_RE,
    _MW_ROW_SEP_RE,
    _MW_TEMPLATE_RE,
    _MW_WIKILINK_PIPE_RE,
    _MW_WIKILINK_RE,
)


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
