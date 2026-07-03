"""Precompiled regexes for the per-line conversion loops."""
from .._runtime import *  # noqa: F401,F403

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
