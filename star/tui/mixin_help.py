"""Help / license / shortcut pager screens.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from .text import _HELP_TEXT, _shortcuts_text
from ..documents import Document, load_document
from ..themes import _LICENSE_TEXT


class HelpMixin:

    # ── Help / about pager ─────────────────────────────────────────────────

    def _show_help(self) -> None:
        """Open README.md in a pager, matching the Qt GUI F1 behavior.
        Falls back to the built-in _HELP_TEXT if README.md cannot be found."""
        readme = Path(__file__).parent / "README.md"
        if readme.exists():
            try:
                tmp = load_document(str(readme), self.settings)
            except Exception:
                tmp = Document(title="star Help", markdown=_HELP_TEXT, plain_text="")
        else:
            tmp = Document(title="star Help", markdown=_HELP_TEXT, plain_text="")
        old_doc, old_rendered, old_scroll = self.doc, self.rendered, self.scroll
        self.doc = tmp
        self._render_doc()
        self.scroll = 0
        self.notify(tr("README.md  —  q / Esc to return"))
        # Pager loop
        while True:
            self.draw()
            ch = self.scr.getch()
            if ch in (ord("q"), ord("Q"), 7, 27):
                break
            elif ch in (14, curses.KEY_DOWN, ord("j")):
                self._scroll_by(1)
            elif ch in (16, curses.KEY_UP, ord("k")):
                self._scroll_by(-1)
            elif ch in (curses.KEY_NPAGE, ord(" ")):
                self._page_down()
            elif ch == curses.KEY_PPAGE:
                self._page_up()
            elif ch in (curses.KEY_HOME, 1):
                self._goto_top()
            elif ch in (curses.KEY_END, 5):
                self._goto_bottom()
        self.doc, self.rendered, self.scroll = old_doc, old_rendered, old_scroll

    def _show_license(self) -> None:
        lic_md = _LICENSE_TEXT
        tmp = Document(title="License — GPL v3", markdown=lic_md, plain_text="")
        old = (self.doc, self.rendered, self.scroll)
        self.doc = tmp
        self._render_doc()
        self.scroll = 0
        while True:
            self.draw()
            ch = self.scr.getch()
            if ch in (ord("q"), ord("Q"), 7, 27):
                break
            elif ch in (14, curses.KEY_DOWN, ord("j")):
                self._scroll_by(1)
            elif ch in (16, curses.KEY_UP, ord("k")):
                self._scroll_by(-1)
            elif ch in (curses.KEY_NPAGE, ord(" ")):
                self._page_down()
            elif ch == curses.KEY_PPAGE:
                self._page_up()
        self.doc, self.rendered, self.scroll = old

    def _show_text_pager(self, title: str, markdown: str) -> None:
        """Render *markdown* in a read-only scrollable pager (q/Esc to exit).

        Shared by the notes list and the keyboard cheat sheet; mirrors the
        navigation keys used by _show_help / _show_license.
        """
        tmp = Document(title=title, markdown=markdown, plain_text="")
        old = (self.doc, self.rendered, self.scroll)
        self.doc = tmp
        self._render_doc()
        self.scroll = 0
        while True:
            self.draw()
            ch = self.scr.getch()
            if ch in (ord("q"), ord("Q"), 7, 27):
                break
            elif ch in (14, curses.KEY_DOWN, ord("j")):
                self._scroll_by(1)
            elif ch in (16, curses.KEY_UP, ord("k")):
                self._scroll_by(-1)
            elif ch in (curses.KEY_NPAGE, ord(" ")):
                self._page_down()
            elif ch == curses.KEY_PPAGE:
                self._page_up()
            elif ch in (curses.KEY_HOME, 1):
                self._goto_top()
            elif ch in (curses.KEY_END, 5):
                self._goto_bottom()
        self.doc, self.rendered, self.scroll = old

    def _show_shortcuts(self) -> None:
        """Show the canonical keyboard cheat sheet."""
        self._show_text_pager("Keyboard Shortcuts", _shortcuts_text(plain=False))
