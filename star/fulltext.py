"""Full-text content search across the folder-library.

The metadata search in :mod:`star.discovery` matches only titles, authors,
paths, and annotations.  This module adds *content* search: it builds a
lightweight, on-demand index of each library document's extracted
``plain_text`` so a query can find documents by what is *inside* them.

Design goals (per the roadmap "Full-text library search" item):

* **On-demand & lazy** — nothing is indexed at import or at document-open time.
  The index is built the first time a content search runs (or when a caller
  explicitly refreshes it), so the reading UI never pays for indexing it does
  not use.
* **Best-effort** — a document that fails to load is simply skipped; the index
  never raises for one bad file.
* **Cached & incremental** — the extracted text is cached on disk keyed by the
  file's ``(size, mtime)`` fingerprint, so a refresh only re-reads files that
  changed.  Unchanged files are served from the JSON cache.
* **Off the UI thread** — :func:`build_index_async` runs the (potentially slow)
  extraction on a worker thread and calls back when done; the GUI uses it so a
  large library never blocks the event loop.

This module has no Qt dependency and no hard optional dependencies — it reuses
``star.library`` for folder scanning and ``star.documents.load_document`` for
extraction (both already present).
"""
from ._runtime import *  # noqa: F401,F403
from .library import scan_library
from .settings import Settings

# The on-disk cache of extracted text lives next to the other star caches.  It
# is a single JSON file keyed by absolute path → {size, mtime, text, title}.
_INDEX_CACHE = CACHE_DIR / "fulltext_index.json"

# Extraction can be slow and memory-hungry on huge files; cap the amount of text
# kept per document so a 50 MB text file does not bloat the cache or a search.
_MAX_TEXT_CHARS = 2_000_000


class FullTextIndex:
    """A cached, substring-searchable index of library-document text.

    The index maps absolute path → an entry ``{size, mtime, text, title}``.
    :meth:`refresh` rescans the configured library folders, reusing cached text
    for files whose ``(size, mtime)`` fingerprint is unchanged and re-extracting
    only new or modified files.  :meth:`search` runs a case-insensitive
    substring query over the cached text.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # {abs_path: {"size": int, "mtime": float, "text": str, "title": str}}
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    # ── persistence ────────────────────────────────────────────────────
    def _load_cache(self) -> None:
        """Populate ``self._entries`` from the on-disk cache (once)."""
        if self._loaded:
            return
        self._loaded = True
        try:
            raw = json.loads(_INDEX_CACHE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                entries = raw.get("entries")
                if isinstance(entries, dict):
                    self._entries = {
                        k: v for k, v in entries.items() if isinstance(v, dict)
                    }
        except (OSError, json.JSONDecodeError, ValueError):
            self._entries = {}

    def _save_cache(self) -> None:
        """Persist ``self._entries`` to the on-disk cache (best effort)."""
        try:
            _INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": 1, "entries": self._entries}
            _INDEX_CACHE.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

    # ── indexing ───────────────────────────────────────────────────────
    @staticmethod
    def _fingerprint(path: str) -> Optional[Tuple[int, float]]:
        """Return ``(size, mtime)`` for *path*, or ``None`` if it is gone."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        return (st.st_size, st.st_mtime)

    def _extract_text(self, path: str) -> Optional[str]:
        """Load *path* and return its ``plain_text`` (``None`` on any failure)."""
        try:
            from .documents import load_document

            doc = load_document(path, self.settings)
        except Exception:  # noqa: BLE001 — one bad file must not break the index
            return None
        text = getattr(doc, "plain_text", "") or getattr(doc, "markdown", "") or ""
        if len(text) > _MAX_TEXT_CHARS:
            text = text[:_MAX_TEXT_CHARS]
        return text

    def refresh(
        self,
        *,
        entries: Optional[List[Dict[str, Any]]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> int:
        """(Re)build the index from the library folders.

        Files whose ``(size, mtime)`` fingerprint matches a cached entry are
        reused as-is; new or changed files are re-extracted.  Entries whose file
        no longer exists (or is no longer in the library) are dropped.  *entries*
        may be supplied to index a pre-scanned list (used by tests / callers that
        already scanned); otherwise the configured library folders are scanned.
        *should_stop* is polled between files so a background build can be
        cancelled cooperatively.

        Returns the number of documents in the index afterwards.
        """
        self._load_cache()
        if entries is None:
            try:
                entries = scan_library(self.settings)
            except Exception:  # noqa: BLE001
                entries = []
        old = self._entries
        fresh: Dict[str, Dict[str, Any]] = {}
        changed = False
        for e in entries:
            if should_stop is not None and should_stop():
                break
            path = e.get("path") or ""
            if not path:
                continue
            fp = self._fingerprint(path)
            if fp is None:
                continue  # file vanished between scan and index
            size, mtime = fp
            prev = old.get(path)
            if (
                prev is not None
                and prev.get("size") == size
                and prev.get("mtime") == mtime
                and "text" in prev
            ):
                fresh[path] = prev  # unchanged — reuse cached text
                continue
            text = self._extract_text(path)
            if text is None:
                # Extraction failed; keep any stale text we already had so the
                # document stays searchable rather than disappearing.
                if prev is not None:
                    fresh[path] = prev
                continue
            fresh[path] = {
                "size": size,
                "mtime": mtime,
                "text": text,
                "title": e.get("title") or Path(path).stem,
            }
            changed = True
        # Detect drops (files removed from the library) as a change too.
        if len(fresh) != len(old):
            changed = True
        self._entries = fresh
        if changed:
            self._save_cache()
        return len(self._entries)

    # ── query ──────────────────────────────────────────────────────────
    def search(
        self, query: str, *, limit: int = 200, context: int = 60
    ) -> List[Dict[str, Any]]:
        """Return documents whose text contains *query* (case-insensitive).

        Each result is a dict with ``path``, ``title``, ``count`` (number of
        matches) and ``snippet`` (a short excerpt around the first match with the
        surrounding *context* characters).  Results are sorted by match count,
        descending.  An empty or whitespace query returns ``[]``.
        """
        self._load_cache()
        q = (query or "").strip().lower()
        if not q:
            return []
        results: List[Dict[str, Any]] = []
        for path, entry in self._entries.items():
            text = entry.get("text") or ""
            low = text.lower()
            first = low.find(q)
            if first < 0:
                continue
            count = low.count(q)
            start = max(0, first - context)
            end = min(len(text), first + len(q) + context)
            snippet = text[start:end].replace("\n", " ").strip()
            if start > 0:
                snippet = "…" + snippet
            if end < len(text):
                snippet = snippet + "…"
            results.append(
                {
                    "path": path,
                    "title": entry.get("title") or Path(path).stem,
                    "count": count,
                    "snippet": snippet,
                }
            )
        results.sort(key=lambda r: (-r["count"], r["title"].lower()))
        return results[:limit]

    def matching_paths(self, query: str) -> "set[str]":
        """Return the set of absolute paths whose text contains *query*."""
        return {r["path"] for r in self.search(query, limit=100000, context=0)}

    @property
    def size(self) -> int:
        """Number of documents currently in the index."""
        self._load_cache()
        return len(self._entries)


# =============================================================================
# Module-level convenience / async helpers
# =============================================================================

# A process-wide cached index so repeated searches (and the GUI) share one
# instance and its on-disk cache.  Keyed by id(settings) so distinct Settings
# objects (e.g. in tests) get their own index.
_INDEX_CACHE_BY_SETTINGS: "Dict[int, FullTextIndex]" = {}


def get_index(settings: Settings) -> FullTextIndex:
    """Return the shared :class:`FullTextIndex` for *settings* (creating it once)."""
    key = id(settings)
    idx = _INDEX_CACHE_BY_SETTINGS.get(key)
    if idx is None:
        idx = FullTextIndex(settings)
        _INDEX_CACHE_BY_SETTINGS[key] = idx
    return idx


def build_index_async(
    settings: Settings,
    on_done: Optional[Callable[[int], None]] = None,
    *,
    should_stop: Optional[Callable[[], bool]] = None,
) -> "threading.Thread":
    """Refresh the shared index on a daemon worker thread.

    *on_done* is invoked with the resulting document count when the build
    finishes (call it back onto the GUI thread yourself if you need to touch
    widgets).  Returns the started thread so the caller can join it in tests.
    """
    idx = get_index(settings)

    def _work() -> None:
        try:
            n = idx.refresh(should_stop=should_stop)
        except Exception:  # noqa: BLE001
            n = idx.size
        if on_done is not None:
            try:
                on_done(n)
            except Exception:  # noqa: BLE001
                pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    return t


def search_content(settings: Settings, query: str, **kwargs) -> List[Dict[str, Any]]:
    """Convenience wrapper: search the shared index for *query*."""
    return get_index(settings).search(query, **kwargs)
