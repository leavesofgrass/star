"""In-document search engine and the curses line editor."""
from ._runtime import *  # noqa: F401,F403
from .render import Line


# =============================================================================
# Search engine
# =============================================================================


class SearchEngine:
    """Forward/backward incremental search with fuzzy matching."""

    def __init__(self) -> None:
        self.query = ""
        self._matches: List[Tuple[int, int, int]] = []  # (line, col_start, col_end)
        self._idx = -1

    @property
    def matches(self) -> List[Tuple[int, int, int]]:
        return self._matches

    @property
    def current_match(self) -> Optional[Tuple[int, int, int]]:
        if 0 <= self._idx < len(self._matches):
            return self._matches[self._idx]
        return None

    @property
    def match_count(self) -> int:
        return len(self._matches)

    @property
    def match_index(self) -> int:
        return self._idx

    def search(self, query: str, rendered: List[Line], from_line: int = 0) -> bool:
        """Run a new search.  Returns True if any matches found."""
        self.query = query
        self._matches = []
        self._idx = -1
        if not query:
            return False
        q_lower = query.lower()
        for li, segs in enumerate(rendered):
            text = "".join(t for t, _ in segs)
            tl = text.lower()
            col = 0
            while True:
                pos = tl.find(q_lower, col)
                if pos < 0:
                    break
                self._matches.append((li, pos, pos + len(query)))
                col = pos + 1
        if self._matches:
            # Start from from_line
            for i, (li, _, _) in enumerate(self._matches):
                if li >= from_line:
                    self._idx = i
                    break
            else:
                self._idx = 0
        return bool(self._matches)

    def next_match(self) -> Optional[Tuple[int, int, int]]:
        if not self._matches:
            return None
        self._idx = (self._idx + 1) % len(self._matches)
        return self._matches[self._idx]

    def prev_match(self) -> Optional[Tuple[int, int, int]]:
        if not self._matches:
            return None
        self._idx = (self._idx - 1) % len(self._matches)
        return self._matches[self._idx]

    def search_regex(
        self, pattern: str, rendered: "List[Line]", from_line: int = 0
    ) -> bool:
        """Run a regex search. Falls back to plain search if pattern is invalid."""
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return self.search(pattern, rendered, from_line)
        self.query = pattern
        self._matches = []
        self._idx = -1
        for li, segs in enumerate(rendered):
            text = "".join(t for t, _ in segs)
            for m in rx.finditer(text):
                self._matches.append((li, m.start(), m.end()))
        if self._matches:
            for i, (li, _, _) in enumerate(self._matches):
                if li >= from_line:
                    self._idx = i
                    break
            else:
                self._idx = 0
        return bool(self._matches)


# =============================================================================
# Line editor (Emacs-style — shared with the other projects in this suite)
# =============================================================================


class LineEditor:
    """Single-line text editor.  Supports arrow keys, Home/End/Delete and
    the standard Ctrl shortcuts Windows and Mac users expect."""

    def __init__(self, value: str = ""):
        self.buf = list(str(value))
        self.pos = len(self.buf)
        self.hint = ""
        self.hint_full = ""
        self._kill_ring = ""

    def feed(self, ch: int) -> Optional[bool]:
        """
        Returns:
          False  — confirmed (Enter)
          None   — canceled (C-g / Esc)
          True   — still editing
        """
        if ch in (curses.KEY_ENTER, 10, 13):
            return False
        if ch in (7, 27):
            return None

        # ── Cursor movement ──────────────────────────────────────────────
        if ch in (curses.KEY_LEFT,):
            self.pos = max(0, self.pos - 1)
        elif ch in (curses.KEY_RIGHT,):
            self.pos = min(len(self.buf), self.pos + 1)
        elif ch in (curses.KEY_HOME, 1):  # Home or Ctrl+A
            self.pos = 0
        elif ch in (curses.KEY_END, 5):  # End or Ctrl+E
            self.pos = len(self.buf)
        # ── Deletion ──────────────────────────────────────────────────────
        elif ch in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
            if self.pos > 0:
                self.buf.pop(self.pos - 1)
                self.pos -= 1
        elif ch in (curses.KEY_DC, 4):  # Delete key or Ctrl+D
            if self.pos < len(self.buf):
                self.buf.pop(self.pos)
        elif ch == 23:  # Ctrl+W / Ctrl+Backspace — delete word backward
            end = self.pos
            while self.pos > 0 and self.buf[self.pos - 1] == " ":
                self.pos -= 1
            while self.pos > 0 and self.buf[self.pos - 1] != " ":
                self.pos -= 1
            self._kill_ring = "".join(self.buf[self.pos : end])
            self.buf[self.pos : end] = []
        elif ch == 11:  # Ctrl+K — delete to end of line
            self._kill_ring = "".join(self.buf[self.pos :])
            self.buf = self.buf[: self.pos]
        elif ch == 21:  # Ctrl+U — delete to start of line
            self._kill_ring = "".join(self.buf[: self.pos])
            self.buf = self.buf[self.pos :]
            self.pos = 0
        elif ch == 25:  # Ctrl+Y — paste last deleted text
            for c in self._kill_ring:
                self.buf.insert(self.pos, c)
                self.pos += 1
        elif 32 <= ch <= 126 or ch > 127:
            try:
                self.buf.insert(self.pos, chr(ch))
                self.pos += 1
            except (ValueError, OverflowError):
                pass
        return True

    def accept_hint(self) -> None:
        if not self.hint or self.pos != len(self.buf):
            return
        if self.hint_full:
            text = "".join(self.buf)
            sep = max(text.rfind(" "), text.rfind("/"))
            new_val = (text[: sep + 1] if sep >= 0 else "") + self.hint_full
            self.buf = list(new_val)
        else:
            for c in self.hint:
                self.buf.append(c)
        self.pos = len(self.buf)
        self.hint = self.hint_full = ""

    @property
    def value(self) -> str:
        return "".join(self.buf)

    def set_value(self, v: str) -> None:
        self.buf = list(v)
        self.pos = len(self.buf)
