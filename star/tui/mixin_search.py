"""In-document search (plain + regex).

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403


class SearchMixin:

    # ── Regex search (StarApp wrapper) ──────────────────

    def _do_search_regex(self, pattern: str) -> None:
        "Wrapper that calls search_regex and updates status."
        pattern = (pattern or "").strip()
        if not pattern or not self.rendered:
            self.notify("Usage: search-regex <pattern>", error=True)
            return
        found = self.search.search_regex(pattern, self.rendered, from_line=self.scroll)
        if found:
            m = self.search.current_match
            if m:
                self._scroll_to_line(m[0])
            self.notify(f"{self.search.match_count} match(es) for regex /{pattern}/")
        else:
            self.notify(f"No regex matches for /{pattern}/", error=True)

    # ── Search ─────────────────────────────────────────────────────────────

    def _do_search(self, query: str, direction: str = "forward") -> None:
        if not query or not self.rendered:
            return
        found = self.search.search(query, self.rendered, from_line=self.scroll)
        if found:
            m = self.search.current_match
            if m:
                self._scroll_to_line(m[0])
                self.notify(f"{self.search.match_count} match(es) for '{query}'")
        else:
            self.notify(f"No matches for '{query}'", error=True)

    def _search_next(self) -> None:
        m = self.search.next_match()
        if m:
            self._scroll_to_line(m[0])
        else:
            self.notify("No search active", error=True)

    def _search_prev(self) -> None:
        m = self.search.prev_match()
        if m:
            self._scroll_to_line(m[0])
        else:
            self.notify("No search active", error=True)

    def _handle_search_key(self, ch: int) -> None:
        if ch in (curses.KEY_ENTER, 10, 13):
            q = self.search_ed.value.strip()
            self.mode = "normal"
            cb = getattr(self, "_mx_callback", None)
            if cb and q:
                cb(q)
            return
        if ch in (7, 27):
            self._cancel_minibuffer()
            return
        self.search_ed.feed(ch)
