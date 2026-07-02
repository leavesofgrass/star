"""Cross-library document search.

Searches the settings library for documents by title, author, path (text
match), DOI, ISBN, and full-text over that document's annotations.  All
criteria are optional and AND-combined.

This module is pure-Python and has no optional dependencies.
"""
from ._runtime import *  # noqa: F401,F403
from .settings import Settings


def search_library(
    settings: Settings,
    query: Optional[str] = None,
    doi: Optional[str] = None,
    isbn: Optional[str] = None,
    author: Optional[str] = None,
    content: bool = False,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Return ``[(key, entry)]`` pairs matching *all* supplied criteria.

    ``query``  — substring match over title, author, path, and annotation text.
    ``doi``    — normalised exact match against ``entry["meta"]["doi"]``.
    ``isbn``   — normalised exact match against ``entry["meta"]["isbn"]``.
    ``author`` — substring match against ``entry["meta"]["author"]``.
    ``content``— when True, ``query`` also matches a document whose *full text*
      contains it (via :mod:`star.fulltext`), not just its metadata.  The metadata
      match and the content match are OR-combined for the query criterion, so a
      hit inside the document body is enough even when the title/author/path do
      not mention the term.  Best-effort: if the full-text index is unavailable
      the search silently falls back to metadata-only.

    With no criteria, every library entry is returned.
    """
    library: Dict[str, Any] = settings.get("library", {})
    annotations: Dict[str, Any] = settings.get("annotations", {})

    # When content search is requested, resolve the set of paths whose extracted
    # text contains the query once, up front, so the per-entry test is a cheap
    # membership check.  Any failure degrades gracefully to metadata-only.
    content_paths: set = set()
    if content and query:
        try:
            from .fulltext import get_index

            content_paths = get_index(settings).matching_paths(query)
        except Exception:  # noqa: BLE001 — content search is best-effort
            content_paths = set()

    results: List[Tuple[str, Dict[str, Any]]] = []
    for key, entry in library.items():
        ann_list = annotations.get(key, [])
        if _matches(key, entry, ann_list, query, doi, isbn, author):
            results.append((key, entry))
        elif content_paths and query and _entry_path(key, entry) in content_paths:
            # Metadata did not match but the document body does — but the other
            # (non-query) criteria must still hold, so re-check them with the
            # query dropped before accepting a content-only hit.
            if _matches(key, entry, ann_list, None, doi, isbn, author):
                results.append((key, entry))
    return results


def _entry_path(key: str, entry: Dict[str, Any]) -> str:
    """Best-effort absolute path for a library *entry* (falls back to *key*)."""
    return str(entry.get("path") or key)


# =============================================================================
# Internal helpers
# =============================================================================


def _norm_doi(doi: str) -> str:
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def _norm_isbn(isbn: str) -> str:
    return re.sub(r"[\s\-]", "", isbn).upper()


def _matches(
    key: str,
    entry: Dict[str, Any],
    ann_list: List[Dict[str, Any]],
    query: Optional[str],
    doi: Optional[str],
    isbn: Optional[str],
    author: Optional[str],
) -> bool:
    meta: Dict[str, Any] = entry.get("meta") or {}

    if doi is not None:
        entry_doi = _norm_doi(str(meta.get("doi") or entry.get("doi") or ""))
        if _norm_doi(doi) != entry_doi:
            return False

    if isbn is not None:
        entry_isbn = _norm_isbn(str(meta.get("isbn") or entry.get("isbn") or ""))
        if _norm_isbn(isbn) != entry_isbn:
            return False

    if author is not None:
        entry_author = str(meta.get("author") or entry.get("author") or "").lower()
        if author.lower() not in entry_author:
            return False

    if query is not None:
        q = query.lower()
        title = str(entry.get("title") or meta.get("title") or "").lower()
        auth = str(meta.get("author") or entry.get("author") or "").lower()
        haystack = f"{title} {key.lower()} {auth}"
        for ann in ann_list:
            haystack += " " + str(ann.get("note") or "").lower()
        if q not in haystack:
            return False

    return True
