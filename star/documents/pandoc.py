"""Pandoc routing: input-format tables and conversion entry points."""
from .._runtime import *  # noqa: F401,F403
from ..markup import _pandoc_convert


# Formats star routes through Pandoc (when it is available and prefer_pandoc is
# on) instead of its native loader, because Pandoc reads them at least as well.
# EPUB is deliberately kept native for its NCX/NAV chapter navigation;
# markdown/text need no conversion; PDF, images/OCR, code, DAISY, archives and
# URLs are not Pandoc-readable and always stay native.
_PANDOC_FIRST_FORMATS = frozenset({
    "docx", "odt", "pptx", "html", "csv", "tsv", "xlsx",
    "rst", "latex", "mediawiki", "textile", "creole", "orgmode", "notebook",
})


# Extensions only Pandoc can open (no native loader) → the "pandoc" format.
# Value is the explicit Pandoc input format, for robust conversion of the
# less-common types Pandoc may not infer from the extension alone.
_PANDOC_INPUT_EXTS = {
    ".rtf": "rtf", ".fb2": "fb2", ".docbook": "docbook", ".dbk": "docbook",
    ".jats": "jats", ".ris": "ris", ".bib": "biblatex", ".bibtex": "biblatex",
    ".opml": "opml", ".t2t": "t2t", ".muse": "muse", ".typ": "typst",
    ".typst": "typst", ".dokuwiki": "dokuwiki", ".tikiwiki": "tikiwiki",
    ".twiki": "twiki", ".vimwiki": "vimwiki", ".jira": "jira",
    ".man": "man", ".mdoc": "mdoc", ".pod": "pod", ".roff": "man",
}


def _pandoc_available() -> bool:
    """True if Pandoc can be invoked (pypandoc module or a pandoc binary)."""
    return bool(_PYPANDOC or _PANDOC_BIN)


def _pandoc_handles(fmt: str) -> bool:
    """Formats routed through Pandoc when it is enabled and available."""
    return fmt == "pandoc" or fmt in _PANDOC_FIRST_FORMATS


def _load_pandoc_first(path: str) -> Optional[str]:
    """Convert via Pandoc for a Pandoc-handled format: an explicit input format
    for the uncommon Pandoc-only extensions, auto-detection for the rest.
    Returns None if Pandoc fails or is unavailable."""
    pf = _PANDOC_INPUT_EXTS.get(Path(path).suffix.lower())
    return _pandoc_convert(path, pf) if pf else _load_via_pandoc(path)


def _load_via_pandoc(path: str) -> Optional[str]:
    """Use Pandoc binary or pypandoc to convert a file to Markdown.
    Returns None if Pandoc is not available."""
    if _PYPANDOC:
        try:
            return _pypandoc.convert_file(path, "markdown")
        except Exception:
            pass
    if _PANDOC_BIN:
        try:
            result = subprocess.run(
                [_PANDOC_BIN, "--to", "markdown", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
    return None
