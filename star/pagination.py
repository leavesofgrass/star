"""Pure paging logic for large-document rendering (Area 5, perf).

star normally lays out a whole document's HTML into a single QTextEdit.  For
very large documents (100k+ words / hundreds of "pages") the one-shot layout
stalls the UI for a noticeable fraction of a second and every subsequent
scroll/repaint carries the whole block tree.  This module holds the *pure*
(Qt-free, GUI-free) arithmetic that lets the GUI render only a **window** of the
document at a time:

* :func:`paginate` splits the document into pages at paragraph boundaries with a
  target words-per-page, returning each page's ``[start_word, end_word)`` range
  over the full ``doc.word_map`` index space.
* :class:`Paginator` tracks which contiguous run of pages is currently rendered
  and answers "does the rendered window already cover word *i*?" plus "which
  window should I render to reveal word *i*?".

Keeping this logic here (with no Qt imports) makes it unit-testable without a
display and keeps the offset-translation contract explicit: the GUI rebuilds its
word→char map for *only the rendered window*, and every feature that resolves a
word index first asks the Paginator whether that word is on screen.

DESIGN INVARIANTS
-----------------
* Pages tile the whole document with no gaps and no overlaps: page 0 starts at
  word 0, the last page ends at ``n_words``, and ``pages[k].end ==
  pages[k+1].start``.
* Page boundaries fall only at the start of a ``doc.word_map`` word that begins a
  new display block (paragraph/heading), so a rendered window is always a whole
  number of paragraphs — no word is ever split across the window edge.
* All indices are **word-map indices** (the same space TTS highlighting, caret
  navigation, Find, and Define-Word already use), never character offsets.  The
  char-offset translation is the GUI's job and is rebuilt per window.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

# Default target words per page.  A "page" here is a rendering unit, not a
# printed page; ~1,200 words keeps each windowed layout cheap while a small
# window of pages still spans several screens of continuous reading.
DEFAULT_WORDS_PER_PAGE = 1200

# How many pages on each side of the active page are rendered together, so
# reading/scrolling within the window never re-renders and a page boundary is
# only crossed occasionally.
DEFAULT_WINDOW_PAGES = 2


@dataclass(frozen=True)
class Page:
    """A half-open range of word-map indices, ``[start, end)``."""

    start: int
    end: int

    def contains(self, word_idx: int) -> bool:
        return self.start <= word_idx < self.end


def paginate(
    n_words: int,
    block_start_words: Sequence[int],
    words_per_page: int = DEFAULT_WORDS_PER_PAGE,
) -> List[Page]:
    """Split ``n_words`` words into pages of about *words_per_page* words.

    *block_start_words* is the sorted list of word-map indices that begin a new
    display block (paragraph / heading / list item / table row); a page boundary
    is only ever placed at one of these so a page is always a whole number of
    blocks.  The list must start at 0.

    Returns a gap-free, non-overlapping list of :class:`Page` covering
    ``[0, n_words)``.  An empty or single-word document yields one page.
    """
    if n_words <= 0:
        return [Page(0, 0)]
    words_per_page = max(1, int(words_per_page))
    # Candidate boundaries: every block start, de-duplicated and in range,
    # guaranteed to include 0.  Append n_words as the final closing boundary.
    bounds = sorted({0, *(b for b in block_start_words if 0 < b < n_words)})
    bounds.append(n_words)

    pages: List[Page] = []
    page_start = 0
    # Walk block boundaries, closing a page once it has accumulated at least
    # words_per_page words (rounding to the block boundary that reaches it).
    for b in bounds[1:]:
        if b - page_start >= words_per_page:
            pages.append(Page(page_start, b))
            page_start = b
    if page_start < n_words:
        pages.append(Page(page_start, n_words))
    if not pages:  # every block smaller than a page but loop closed nothing
        pages.append(Page(0, n_words))
    return pages


class Paginator:
    """Tracks the rendered window over a list of :class:`Page`.

    The GUI owns one of these while pagination is active.  It renders the pages
    ``[window_start, window_end)`` and rebuilds its word→char map for exactly
    that span.  When a word outside the window must be shown (playback crossing a
    boundary, a caret jump, a Find hit, a restore-position), it asks
    :meth:`window_for_word` for the new window, re-renders, and rebuilds the map.
    """

    def __init__(
        self,
        pages: List[Page],
        window_pages: int = DEFAULT_WINDOW_PAGES,
    ) -> None:
        self.pages: List[Page] = pages or [Page(0, 0)]
        self.window_pages = max(0, int(window_pages))
        # Index range of pages currently rendered: [window_start, window_end).
        self.window_start = 0
        self.window_end = 0
        self._set_window_around(0)

    # ── page lookup ────────────────────────────────────────────────────
    @property
    def n_pages(self) -> int:
        return len(self.pages)

    def page_of_word(self, word_idx: int) -> int:
        """Return the page index containing *word_idx* (clamped to range)."""
        if word_idx <= 0:
            return 0
        last = len(self.pages) - 1
        if word_idx >= self.pages[last].end:
            return last
        # Linear-then-clamp is fine (few pages); binary search would also work.
        lo, hi = 0, last
        while lo <= hi:
            mid = (lo + hi) // 2
            pg = self.pages[mid]
            if word_idx < pg.start:
                hi = mid - 1
            elif word_idx >= pg.end:
                lo = mid + 1
            else:
                return mid
        return min(max(0, lo), last)

    # ── window bookkeeping ─────────────────────────────────────────────
    @property
    def word_start(self) -> int:
        """First word-map index in the rendered window."""
        return self.pages[self.window_start].start

    @property
    def word_end(self) -> int:
        """One past the last word-map index in the rendered window."""
        return self.pages[self.window_end - 1].end

    def covers_word(self, word_idx: int) -> bool:
        """True when *word_idx* lies within the currently rendered window."""
        return self.word_start <= word_idx < self.word_end

    def is_whole_document(self) -> bool:
        """True when the rendered window already spans the entire document."""
        return self.window_start == 0 and self.window_end >= len(self.pages)

    def _set_window_around(self, page_idx: int) -> None:
        n = len(self.pages)
        page_idx = min(max(0, page_idx), n - 1)
        self.window_start = max(0, page_idx - self.window_pages)
        self.window_end = min(n, page_idx + self.window_pages + 1)

    def window_for_word(self, word_idx: int) -> bool:
        """Recentre the window on the page containing *word_idx*.

        Returns True if the window actually changed (the GUI must re-render),
        False if *word_idx* was already covered (nothing to do).
        """
        if self.covers_word(word_idx):
            return False
        self._set_window_around(self.page_of_word(word_idx))
        return True
