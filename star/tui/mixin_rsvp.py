"""RSVP (rapid serial visual presentation) reading mode.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ._screen import _addstr, _fillrow_range


class RsvpMixin:

    # ── RSVP reading mode (TUI) ───────────────────────────────────────────

    _RSVP_POSITIONS: List[str] = [
        "top-left", "top-center", "top-right",
        "center-left", "center", "center-right",
        "bottom-left", "bottom-center", "bottom-right",
    ]

    def _rsvp_mode_cmd(self) -> None:
        """Toggle RSVP mode on/off (M-x rsvp-mode)."""
        self._rsvp_mode = not self._rsvp_mode
        self.settings["tui_rsvp_mode"] = self._rsvp_mode
        if not self._rsvp_mode:
            self._rsvp_curr_word = ""
            self._rsvp_prev_word = ""
            self._rsvp_next_word = ""
        state = "ON" if self._rsvp_mode else "OFF"
        self.notify(f"RSVP mode: {state}")

    def _rsvp_position_cmd(self, pos: str = "") -> None:
        """Set the RSVP overlay position (M-x rsvp-position [key]).

        With no argument, cycles through the nine positions in order.
        With a key (e.g. ``bottom-right``), jumps directly to that position.
        """
        positions = self._RSVP_POSITIONS
        if pos and pos in positions:
            self._rsvp_position = pos
        else:
            # Cycle to next
            try:
                idx = positions.index(self._rsvp_position)
            except ValueError:
                idx = -1
            self._rsvp_position = positions[(idx + 1) % len(positions)]
        self.settings["tui_rsvp_position"] = self._rsvp_position
        self.notify(f"RSVP position: {self._rsvp_position}")

    # RSVP position → (row_fraction, col_fraction) within the content area.
    # Fractions are applied to (view_h, w) with the overlay anchored from the
    # same relative corner so the box stays fully inside the viewport.
    _RSVP_FRAC: Dict[str, Tuple[float, float]] = {
        "top-left":      (0.02, 0.02),
        "top-center":    (0.02, 0.50),
        "top-right":     (0.02, 0.98),
        "center-left":   (0.50, 0.02),
        "center":        (0.50, 0.50),
        "center-right":  (0.50, 0.98),
        "bottom-left":   (0.98, 0.02),
        "bottom-center": (0.98, 0.50),
        "bottom-right":  (0.98, 0.98),
    }

    def _draw_rsvp(self, h: int, w: int) -> None:
        """Draw the RSVP word overlay on top of the document content."""
        if not self._rsvp_mode or not self._rsvp_curr_word:
            return

        ctx = self._rsvp_curr_word and bool(self._rsvp_prev_word or self._rsvp_next_word)
        rows_needed = 3 if ctx else 1
        words_display = [
            (self._rsvp_prev_word, False),
            (self._rsvp_curr_word, True),
            (self._rsvp_next_word, False),
        ] if ctx else [(self._rsvp_curr_word, True)]

        # Box width: longest word + 2-char side padding each side.
        box_w = max((len(wd) for wd, _ in words_display if wd), default=4) + 4
        box_w = max(box_w, 8)

        # Content-area row bounds (title bar row 0; status = h-3..h-1).
        view_top = 1
        view_bottom = h - 3

        fy, fx = self._RSVP_FRAC.get(self._rsvp_position, (0.02, 0.50))
        view_h = max(1, view_bottom - view_top)
        # Compute top-left of box, anchoring from the matching quadrant.
        raw_row = int(view_top + view_h * fy - rows_needed * fy)
        raw_col = int(w * fx - box_w * fx)
        row = max(view_top, min(raw_row, view_bottom - rows_needed - 1))
        col = max(0, min(raw_col, w - box_w - 1))

        # Draw background strip.
        bg_attr = self._a("status")
        for r in range(rows_needed):
            _fillrow_range(self.scr, row + r, col, box_w, bg_attr)

        # Draw words.
        for i, (word, is_current) in enumerate(words_display):
            if not word:
                continue
            attr = self._a("current_word") if is_current else self._a("dim")
            # Center the word within the box.
            inner_w = box_w - 2
            text = word[:inner_w].center(inner_w)
            _addstr(self.scr, row + i, col + 1, text, attr)
