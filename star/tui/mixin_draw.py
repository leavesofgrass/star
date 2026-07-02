"""Curses screen drawing (title, document, status, minibuffer).

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from ._screen import _addstr, _fillrow
from ..themes import _WELCOME_TEXT


class DrawMixin:

    # ── Drawing ────────────────────────────────────────────────────────────

    def draw(self) -> None:
        h, w = self.scr.getmaxyx()
        if h < 8 or w < 20:
            self.scr.erase()
            _addstr(self.scr, 0, 0, tr("Terminal too small (need 20×8 minimum)"))
            self.scr.refresh()
            return
        self.scr.erase()
        self._draw_title(h, w)
        self._draw_document(h, w)
        self._draw_rsvp(h, w)
        self._draw_status(h, w)
        self._draw_minibuffer(h, w)
        # ── Cursor positioning for screen-reader accessibility ─────────────
        # In input modes (_draw_minibuffer already moved the cursor to the
        # insertion point).  In normal reading mode the cursor must sit on the
        # document text so that terminal screen readers (NVDA, JAWS, Orca …)
        # can follow the reading position rather than being permanently locked
        # onto the minibuffer row at the bottom of the screen.
        try:
            if self.mode not in ("mx", "search", "goto"):
                view_top = 1  # row 0 is the title bar
                view_h = max(1, h - 3 - view_top)
                if (
                    self.mode == "sc"
                    and self.scroll <= self._sc_line < self.scroll + view_h
                ):
                    # In SC mode the cursor sits on the reading-cursor line.
                    cur_row = view_top + (self._sc_line - self.scroll)
                elif (
                    self._highlight_line >= 0
                    and self.scroll <= self._highlight_line < self.scroll + view_h
                ):
                    # Cursor tracks the currently spoken word line.
                    cur_row = view_top + (self._highlight_line - self.scroll)
                else:
                    # Idle / paused: sit on the first visible document line.
                    cur_row = view_top
                self.scr.move(cur_row, 0)
        except curses.error:
            pass
        self.scr.refresh()

    def _draw_title(self, h: int, w: int) -> None:
        """Top title bar: app name | document title | TTS status | rate."""
        title = self.doc.title if self.doc else APP_TITLE
        if self.mode == "sc":
            tts_state = "▶ SC+Speaking" if self.tts.speaking else "● SC CURSOR"
        else:
            tts_state = "▶ Speaking" if self.tts.speaking else "■ Stopped"
        rate = str(self.settings["tts_rate"])
        rhs = f" {tts_state}  {rate} wpm  {self.tts.backend_name} "
        lhs = f" {APP_NAME}  │  {title} "
        gap = max(1, w - len(lhs) - len(rhs) - 1)
        bar = lhs + " " * gap + rhs
        _fillrow(self.scr, 0, self._a("title_bar"))
        _addstr(self.scr, 0, 0, bar[: w - 1], self._a("title_bar"))

    def _draw_document(self, h: int, w: int) -> None:
        """Render visible document lines into the content area (rows 1 … h-3)."""
        view_top = 1
        view_bottom = h - 3
        view_h = max(1, view_bottom - view_top)

        # Scroll to keep the current speech position visible.
        #
        # We track the *callback-confirmed* word position rather than the
        # timer's visual highlight, because the timer can race ahead of the
        # audio (engine-startup lag, SSML pauses).  When the user triggers a
        # navigation command (replay-sentence, skip, etc.) the destination is
        # also derived from the callback position, so the viewport is already
        # close to the destination — no dramatic snap-back.
        # In SSML mode (or before the first callback fires) no confirmed
        # position is available; we fall back to _highlight_line so the
        # screen still scrolls during reading.
        cb = self.tts.last_cb_word_idx
        if cb >= 0 and self.doc and cb < len(self.doc.word_map):
            _scroll_line = self.doc.word_map[cb].disp_line
        elif self._highlight_line >= 0:
            _scroll_line = self._highlight_line
        else:
            _scroll_line = -1

        if _scroll_line >= 0:
            margin = int(self.settings["scroll_margin"])
            if _scroll_line < self.scroll + margin:
                self.scroll = max(0, _scroll_line - margin)
            elif _scroll_line >= self.scroll + view_h - margin:
                self.scroll = max(0, _scroll_line - view_h + margin + 1)

        if self.loading:
            mid = view_top + view_h // 2
            _addstr(self.scr, mid, 4, self.loading_msg, self._a("progress"))
            return

        if not self.rendered:
            welcome = _WELCOME_TEXT.splitlines()
            for i, ln in enumerate(welcome[:view_h]):
                role = (
                    "h1"
                    if ln.startswith("# ")
                    else ("h2" if ln.startswith("## ") else "normal")
                )
                _addstr(self.scr, view_top + i, 2, ln, self._a(role))
            return

        total = len(self.rendered)
        cur_match = self.search.current_match

        # Sentence-level highlight: precompute, per display
        # line, the column span covered by the current sentence so the inner
        # loop can band-highlight it.  Empty for word-level highlighting.
        gran = str(self.settings.get("highlight_granularity", "word"))
        sent_cols: Dict[int, Tuple[int, int]] = {}
        if (
            gran in ("sentence", "both")
            and self._highlight_sent is not None
            and self.doc
            and self.doc.word_map
        ):
            s_w, e_w = self._highlight_sent
            e_w = min(e_w, len(self.doc.word_map) - 1)
            for i in range(max(0, s_w), e_w + 1):
                wp = self.doc.word_map[i]
                cs2, ce2 = wp.disp_col, wp.disp_col + wp.tts_len
                if wp.disp_line in sent_cols:
                    a0, b0 = sent_cols[wp.disp_line]
                    sent_cols[wp.disp_line] = (min(a0, cs2), max(b0, ce2))
                else:
                    sent_cols[wp.disp_line] = (cs2, ce2)

        # SC mode: remember which display-line the reading cursor is on so
        # the inner loop can highlight it.
        sc_cursor_row: int = -1
        if self.mode == "sc" and self.rendered:
            visible_sc = self.scroll <= self._sc_line < self.scroll + view_h
            if visible_sc:
                sc_cursor_row = view_top + (self._sc_line - self.scroll)

        for vi in range(view_h):
            li = self.scroll + vi
            row = view_top + vi
            if li >= total:
                break

            segs = self.rendered[li]
            col = 0
            show_ln = bool(self.settings["show_line_numbers"])
            if show_ln:
                ln_str = f"{li + 1:>4} "
                _addstr(self.scr, row, 0, ln_str, self._a("dim"))
                col = len(ln_str)

            for text, role in segs:
                if not text or col >= w - 1:
                    break
                attr = self._a(role)

                # Apply search highlighting character-by-character if needed
                if cur_match and cur_match[0] == li:
                    _, cs, ce = cur_match
                    self._draw_highlighted_text(
                        row, col, text, role, cs, ce, w, current=True
                    )
                elif any(m[0] == li for m in self.search.matches):
                    for m in self.search.matches:
                        if m[0] == li:
                            self._draw_highlighted_text(
                                row, col, text, role, m[1], m[2], w, current=False
                            )
                            break
                else:
                    # TTS highlight — word, sentence, or both.
                    sc_span = sent_cols.get(li)
                    word_here = (
                        li == self._highlight_line and self._highlight_col_start >= 0
                    )
                    if self.settings["highlight_current_word"] and (
                        word_here or sc_span
                    ):
                        hl_attr = self._a("current_word")
                        wcs, wce = self._highlight_col_start, self._highlight_col_end
                        txt = text[: w - col - 1]
                        for ci, c in enumerate(txt):
                            tpos = col + ci
                            in_word = word_here and wcs <= tpos < wce
                            in_sent = sc_span is not None and (
                                sc_span[0] <= tpos < sc_span[1]
                            )
                            if gran == "sentence":
                                a = hl_attr if in_sent else attr
                            elif gran == "both":
                                if in_word:
                                    a = hl_attr | curses.A_BOLD | curses.A_UNDERLINE
                                elif in_sent:
                                    a = hl_attr
                                else:
                                    a = attr
                            else:  # word
                                a = hl_attr if in_word else attr
                            _addstr(self.scr, row, tpos, c, a)
                        col += len(txt)
                    else:
                        avail = max(0, w - col - 1)
                        chunk = text[:avail]
                        _addstr(self.scr, row, col, chunk, attr)
                        col += len(chunk)

        # Scroll indicators
        if self.scroll > 0:
            _addstr(self.scr, view_top, w - 4, " ▲ ", self._a("dim"))
        if self.scroll + view_h < total:
            _addstr(self.scr, view_bottom - 1, w - 4, " ▼ ", self._a("dim"))

        # ── SC mode cursor bar ────────────────────────────────────────────────
        # Draw a full-width reverse-video bar over the SC cursor line so the
        # reading position is clearly visible even while the word highlight
        # is on a different line.
        if sc_cursor_row >= 0:
            try:
                self.scr.chgat(sc_cursor_row, 0, -1, curses.A_REVERSE)
            except curses.error:
                pass

    def _draw_highlighted_text(
        self,
        row: int,
        base_col: int,
        text: str,
        role: str,
        hl_start: int,
        hl_end: int,
        w: int,
        current: bool,
    ) -> None:
        hl_attr = self._a("search_current" if current else "search_match")
        norm_attr = self._a(role)
        col = base_col
        for i, c in enumerate(text[: w - base_col - 1]):
            tpos = base_col + i
            attr = hl_attr if hl_start <= tpos < hl_end else norm_attr
            _addstr(self.scr, row, tpos, c, attr)
            col += 1

    def _draw_status(self, h: int, w: int) -> None:
        """Status bar (second-to-last row) and hints (third-to-last row)."""
        status_row = h - 3
        hints_row = h - 2

        # Timed message
        if self.message and (time.monotonic() - self.message_t) < self.message_dur:
            _fillrow(self.scr, status_row, self._a("status"))
            _addstr(
                self.scr, status_row, 0, f" {self.message}"[: w - 1], self._a("status")
            )
        else:
            self.message = ""
            total = len(self.rendered)
            pct = int(100 * (self.scroll + 1) / max(1, total)) if total else 100
            search_info = (
                f"  [{self.search.match_index + 1}/{self.search.match_count}]"
                if self.search.match_count
                else ""
            )
            bar = (
                (
                    f" {self.doc.title[:40] if self.doc else tr('No document')}  "
                    f"{tr('Line')} {self.scroll + 1}/{total}  {pct}%"
                    f"{search_info}"
                )
                if self.doc
                else f" {APP_TITLE}"
            )
            _fillrow(self.scr, status_row, self._a("status"))
            _addstr(self.scr, status_row, 0, bar[: w - 1], self._a("status"))

        # Hints bar.  The whole shortcut cheat-line is one translatable unit so
        # translators can localise the labels while keeping the key names (which
        # are fixed bindings) intact — mirroring how the Qt catalogs treat
        # tooltip shortcut hints.
        hints = tr(
            "  Space:play/pause  Tab:speech-cursor  Ctrl+T:voice  Ctrl+X:stop  "
            ",/.:sent  [/]:para  {/}:head-scroll  </>:read-head  "
            ";:replay-sent  r:replay-para  "
            "Ctrl-F:search  +/-:speed  F2:commands  F1:help  Ctrl-Q:quit"
        )
        _fillrow(self.scr, hints_row, self._a("dim"))
        _addstr(self.scr, hints_row, 0, hints[: w - 1], self._a("dim"))

    def _draw_minibuffer(self, h: int, w: int) -> None:
        """Bottom minibuffer row."""
        mb_row = h - 1
        if self.mode == "mx":
            prompt = getattr(self, "_mx_prompt", "M-x: ")
            ed = self.mx_ed
            val = ed.value
            comps = self.mx_completions[:6]
            comp_str = (
                "  "
                + "  ".join(
                    f"[{c}]" if i == self.mx_comp_idx else c
                    for i, c in enumerate(comps)
                )
                if comps
                else ""
            )
            _fillrow(self.scr, mb_row, self._a("minibuf"))
            _addstr(self.scr, mb_row, 0, (prompt + val)[: w - 1], self._a("minibuf"))
            if comp_str and len(prompt + val) < w - 2:
                _addstr(
                    self.scr,
                    mb_row,
                    len(prompt + val),
                    comp_str[: w - len(prompt) - len(val) - 1],
                    self._a("dim"),
                )
            try:
                cx = min(len(prompt) + ed.pos, w - 1)
                self.scr.move(mb_row, cx)
            except curses.error:
                pass
        elif self.mode == "search":
            prompt = getattr(self, "_search_prompt", tr("Search: "))
            ed = self.search_ed
            _fillrow(self.scr, mb_row, self._a("minibuf"))
            _addstr(
                self.scr, mb_row, 0, (prompt + ed.value)[: w - 1], self._a("minibuf")
            )
            try:
                self.scr.move(mb_row, min(len(prompt) + ed.pos, w - 1))
            except curses.error:
                pass
        elif self.mode == "goto":
            prompt = tr("Go to line: ")
            ed = self.goto_ed
            _fillrow(self.scr, mb_row, self._a("minibuf"))
            _addstr(
                self.scr, mb_row, 0, (prompt + ed.value)[: w - 1], self._a("minibuf")
            )
            try:
                self.scr.move(mb_row, min(len(prompt) + ed.pos, w - 1))
            except curses.error:
                pass
        else:
            _fillrow(self.scr, mb_row, self._a("dim"))
            if self.mode == "sc":
                idle = tr(
                    "  SC CURSOR  \u2191\u2193:line  ,/.:sent  [/]:para  {/}:head"
                    "  t/T:table  Enter:read-on  Space:pause  Esc:exit  Tab:normal"
                )
            else:
                idle = (
                    tr(
                        "  F2:commands  Ctrl-O:open  Space:play/pause"
                        "  Tab:speech-cursor  F1:help  Esc:stop  \u2502  "
                    )
                    + self.tts.backend_name
                )
            _addstr(self.scr, mb_row, 0, idle[: w - 1], self._a("dim"))
