"""RSS / Atom feed reading via feedparser.

Optional feature: requires the ``feedparser`` package
(``pip install feedparser``).  When it is absent the module still imports
cleanly with ``_FEEDPARSER = False``, so the rest of star runs unchanged and
the GUI shows an install hint instead of the command — the same
graceful-degradation pattern every other optional feature follows.

A feed is just a structured list of article URLs, so once an entry is chosen
it is opened through star's normal URL-loading path; this module only turns a
feed URL into that list.
"""

from ._runtime import *  # noqa: F401,F403

# Detected cheaply; feedparser (which pulls in its own parsing stack) is imported
# lazily by fetch_feed() the first time a feed is opened.
_FEEDPARSER = _module_available("feedparser")


# Cap the number of entries returned so a busy firehose feed cannot flood the
# chooser dialog; the newest entries are the ones a reader wants anyway.
_MAX_ENTRIES = 50


def fetch_feed(url: str) -> List[Dict[str, str]]:
    """Parse the RSS / Atom feed at *url* and return its entries.

    Each entry is a dict with ``title``, ``url``, ``summary``, and
    ``published`` keys (missing fields become empty strings).  At most
    ``_MAX_ENTRIES`` entries are returned, in the feed's own order (typically
    newest first).

    Raises ``RuntimeError`` with install guidance when feedparser is not
    available.
    """
    if not _FEEDPARSER:
        raise RuntimeError(
            "Feed reading requires feedparser:\n    pip install feedparser"
        )
    import feedparser  # deferred: keeps its parsing stack off the startup path

    parsed = feedparser.parse((url or "").strip())
    entries: List[Dict[str, str]] = []
    for entry in parsed.entries[:_MAX_ENTRIES]:
        link = entry.get("link", "") or ""
        if not link:
            continue
        entries.append(
            {
                "title": (entry.get("title", "") or "").strip() or link,
                "url": link,
                "summary": entry.get("summary", "") or "",
                "published": entry.get("published", "") or "",
            }
        )
    return entries
