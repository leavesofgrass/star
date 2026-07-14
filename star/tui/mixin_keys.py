"""Core keyboard dispatch (normal mode).

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr


class KeysMixin:

    # ── Key handling ───────────────────────────────────────────────────────

    def _handle_key(self, ch: int) -> None:
        if self.mode == "sc":
            self._handle_sc_key(ch)
        elif self.mode == "mx":
            self._handle_mx_key(ch)
        elif self.mode == "search":
            self._handle_search_key(ch)
        elif self.mode == "goto":
            self._handle_goto_key(ch)
        else:
            self._handle_normal_key(ch)

    def _handle_normal_key(self, ch: int) -> None:  # noqa: C901
        # ── Escape: stop speech and clear search ────────────────────────────
        if ch == 27:
            # Brief peek — keep ESC-x working as a silent power-user shortcut.
            self.scr.timeout(100)
            nk = self.scr.getch()
            self.scr.timeout(150)
            if nk in (ord("x"), ord("X")):
                self._enter_minibuffer("Command: ")
            else:
                self._tts_stop()
                self.search.query = ""
            return

        # ── Function keys ──────────────────────────────────────────────────
        if ch == curses.KEY_F1:
            self._show_help()
            return
        if ch == curses.KEY_F2:
            self._enter_minibuffer("Command: ")
            return
        if ch == curses.KEY_F3:
            self._search_next()
            return
        if ch == curses.KEY_F4:
            self._search_prev()
            return
        if ch == curses.KEY_F5:
            self._next_theme()
            return
        if ch == curses.KEY_F6:
            self.settings.set(
                "show_line_numbers", not self.settings["show_line_numbers"]
            )
            return
        if ch == curses.KEY_F7:
            self.settings.set("syntax_highlight", not self.settings["syntax_highlight"])
            self._render_doc()
            return
        if ch == curses.KEY_F8:
            self._cycle_speed_preset()  # cycle skim / normal / study / slow
            return
        if ch == curses.KEY_F9:
            if self.doc:
                self._open_async(self.doc.path)
            return
        if ch == curses.KEY_RESIZE:
            self._render_doc()
            return

        # ── Navigation (caret browsing) ─────────────────────────────────────
        # Arrows move a free word-granularity caret (mixin_caret.py) that
        # drags the viewport with it; Enter reads from the caret.  j / k keep
        # the classic caret-free scrolling for terminal muscle memory.
        if ch == curses.KEY_DOWN:
            self._caret_move_line(1)
        elif ch == curses.KEY_UP:
            self._caret_move_line(-1)
        elif ch == curses.KEY_LEFT:
            self._caret_move_word(-1)
        elif ch == curses.KEY_RIGHT:
            self._caret_move_word(1)
        elif ch == curses.KEY_NPAGE:
            self._caret_move_page(1)
        elif ch == curses.KEY_PPAGE:
            self._caret_move_page(-1)
        elif ch == curses.KEY_HOME:
            self._caret_home()
        elif ch == curses.KEY_END:
            self._caret_end()
        # j / k kept as silent shortcuts familiar to terminal users
        elif ch == ord("j"):
            self._scroll_by(1)
        elif ch == ord("k"):
            self._scroll_by(-1)

        # ── Speech ─────────────────────────────────────────────────────────
        elif ch == ord(" "):
            self._tts_toggle()
        elif ch in (curses.KEY_ENTER, 10, 13):  # Enter — read from the caret
            self._caret_play()
        elif ch in (ord("+"), ord("=")):  # speed up
            self._rate_change(+20)
        elif ch == ord("-"):  # slow down
            self._rate_change(-20)

        # ── File operations ────────────────────────────────────────────────
        elif ch == 15:  # Ctrl+O — open
            self._open_file_prompt()
        elif ch == 5:  # Ctrl+E — edit in $EDITOR (GUI parity: edit mode)
            self._edit_cmd()
        elif ch == 19:  # Ctrl+S — save/export
            self._export_markdown()
        elif ch in (17, ord("q"), ord("Q")):  # Ctrl+Q or q — quit
            self._running = False

        # ── Search ─────────────────────────────────────────────────────────
        elif ch == 6:  # Ctrl+F — find
            self._enter_minibuffer(
                tr("Search: "),
                mode="search",
                on_commit=lambda q: self._do_search(q, "forward"),
            )
        elif ch == ord("n"):
            self._search_next()
        elif ch == ord("N"):
            self._search_prev()

        # ── Sentence navigation ─────────────────────────────────────────
        # Alt+. / Alt+, / Alt+; match the Qt GUI sentence shortcuts.
        # Plain .  ,  ;  are kept as fallback (TUI muscle memory).
        elif ch == ord("."):
            self._skip_next_sentence()  # or Alt+.
        elif ch == ord(","):
            self._skip_prev_sentence()  # or Alt+,
        elif ch == ord(";"):
            self._replay_sentence()  # or Alt+;

        # ── Paragraph navigation ────────────────────────────────────────
        # p / P  — NVDA browse-mode convention, aligns with GUI Ctrl+P / Ctrl+Shift+P.
        # Ctrl+P (16) also added for direct GUI parity.
        # ]  [  kept as silent fallbacks.
        elif ch in (ord("p"), 16):
            self._skip_next_paragraph()  # p  Ctrl+P
        elif ch == ord("P"):
            self._skip_prev_paragraph()  # P  (Shift)
        elif ch == ord("]"):
            self._skip_next_paragraph()  # legacy
        elif ch == ord("["):
            self._skip_prev_paragraph()  # legacy
        # r / Ctrl+R  — replay paragraph; Ctrl+R (18) matches GUI Ctrl+R.
        elif ch in (ord("r"), 18):
            self._replay_paragraph()  # r  Ctrl+R

        # ── Heading navigation ──────────────────────────────────────────
        # h  — NVDA browse-mode convention, aligns with GUI Ctrl+H (next heading).
        # }  {  kept as silent fallbacks.  >  <  always-play variants.
        elif ch == ord("h"):
            self._skip_next_heading()  # h  (forward)
        elif ch == ord("}"):
            self._skip_next_heading()  # } legacy
        elif ch == ord("{"):
            self._skip_prev_heading()  # { legacy
        elif ch == ord(">"):
            self._read_next_heading()  # >  (always play)
        elif ch == ord("<"):
            self._read_prev_heading()  # <  (always play)

        # ── Table navigation ───────────────────────────────────────────
        # t / T  — NVDA browse-mode convention, aligns with GUI Ctrl+T / Ctrl+Shift+T.
        elif ch == ord("t"):
            self._skip_next_table()
        elif ch == ord("T"):
            self._skip_prev_table()

        # ── Chapter navigation ──────────────────────────────────────────────
        elif ch == curses.KEY_F10:
            self._chapter_prev()
        elif ch == curses.KEY_F11:
            self._chapter_next()
        elif ch == curses.KEY_F12:
            self._chapter_list()

        # ── Navigation history ──────────────────────────────────────────────
        elif ch == ord("H"):  # H = history back (capital to avoid conflict)
            self._history_back()
        elif ch == ord("L"):  # L = history forward
            self._history_forward()

        # ── Clipboard ────────────────────────────────────────────────────────
        elif ch == 3:  # Ctrl+C
            self._copy_to_clipboard()
        # ── Speech Cursor mode ────────────────────────────────────────────
        elif ch == 9:  # Tab — enter Speech Cursor mode
            self._sc_enter()

        # ── Voice picker (Ctrl+T) ────────────────────────────────────────
        elif ch == 20:  # Ctrl+T — T for TTS voice
            self._voice_picker()

        # ── Ctrl+Space — read from the caret (GUI parity; NUL byte where the
        # terminal delivers it — Enter is the always-works primary binding).
        elif ch == 0:
            self._caret_play()

        # ── Immediate speech stop (Ctrl+X; Esc also stops) ───────────────
        elif ch == 24:  # Ctrl+X
            self._tts_stop()
            self.notify("Speech stopped")

        # ── Annotations / notes ─────────────────────────────────────────────
        elif ch == ord("a"):  # add a note at the reading position
            self._annotate()
        elif ch == ord("A"):  # interactive notes browser
            self._notes_browser()

        # ── Define the word at the reading cursor ───────────────────────────
        elif ch == ord("d"):
            self._define_cmd()

        # ── Keyboard cheat sheet ────────────────────────────────────────────
        elif ch == ord("?"):
            self._show_shortcuts()

        # ── Command palette ────────────────────────────────────────────────
        elif ch == ord(":"):
            self._enter_minibuffer("Command: ")
