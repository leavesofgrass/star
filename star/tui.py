"""The curses terminal user interface (StarApp)."""
from ._runtime import *  # noqa: F401,F403
from .annotations import _annotation_matches, _format_annotations, _parse_tags
from .braille import _export_braille
from .documents import Document, _build_word_map, load_document
from .render import Line, render_markdown
from .search import LineEditor, SearchEngine
from .settings import Settings
from .stats import ReadingStats, _apply_profile_values, _delete_profile, _format_reading_stats, _library_entries, _record_library, _save_profile
from .themes import _LICENSE_TEXT, _WELCOME_TEXT
from .tts import Pyttsx3Backend, TTSManager, _SCReader
from .ttstext import _preprocess_tts_text, _text_to_ssml


# =============================================================================
# Color / theme system
# =============================================================================

# Color-pair role names → CP_* numbers
_ROLES = [
    "normal",
    "h1",
    "h2",
    "h3",
    "h4",
    "bold",
    "italic",
    "bolditalic",
    "code",
    "code_normal",
    "codeblock",
    "keyword",
    "string",
    "comment",
    "number",
    "link",
    "image",
    "quote",
    "bullet",
    "ordinal",
    "table",
    "hr",
    "current_word",  # TTS word highlight
    "search_match",  # non-current search hit
    "search_current",  # current search hit
    "status",  # status bar
    "status_hi",  # emphasized item in status bar
    "minibuf",  # minibuffer normal
    "error",  # error message
    "dim",  # hints / secondary text
    "progress",  # loading indicator
    "title_bar",  # top title bar
]
CP: Dict[str, int] = {r: i + 1 for i, r in enumerate(_ROLES)}

# (fg, bg, bold, italic, underline, dim)
_N = (7, -1, False, False, False, False)


def _t(**kw: tuple) -> Dict[str, tuple]:
    d: Dict[str, tuple] = {r: _N for r in _ROLES}
    d.update(kw)
    return d


# Dark modern theme (default) — colorblind-friendly (no red/green adjacency)
# Accent palette: cyan, blue, magenta, white.  No yellow, no green/red pairing.
THEMES: Dict[str, Dict] = {
    "dark": _t(
        normal=(7, -1, False, False, False, False),
        h1=(6, -1, True, False, False, False),  # cyan bold
        h2=(4, -1, True, False, False, False),  # blue bold
        h3=(5, -1, True, False, False, False),  # magenta bold
        h4=(7, -1, True, False, True, False),  # white bold underline
        bold=(7, -1, True, False, False, False),
        italic=(7, -1, False, True, False, False),
        bolditalic=(7, -1, True, True, False, False),
        code=(6, -1, False, False, False, False),  # cyan
        code_normal=(6, -1, False, False, False, False),
        codeblock=(6, -1, False, False, False, True),  # dim cyan
        keyword=(5, -1, True, False, False, False),  # magenta bold
        string=(6, -1, False, False, False, False),  # cyan
        comment=(4, -1, False, True, False, True),  # blue italic dim
        number=(5, -1, False, False, False, False),  # magenta
        link=(6, -1, False, False, True, False),  # cyan underline
        image=(5, -1, False, False, True, False),
        quote=(5, -1, False, True, False, False),  # magenta italic
        bullet=(6, -1, True, False, False, False),  # cyan bold
        ordinal=(6, -1, False, False, False, False),
        table=(6, -1, False, False, False, False),
        hr=(4, -1, False, False, False, True),  # blue dim
        current_word=(0, 6, True, False, False, False),  # black on cyan
        search_match=(0, 4, False, False, False, False),  # black on blue
        search_current=(0, 5, True, False, False, False),  # black on magenta
        status=(7, 4, True, False, False, False),  # white on blue
        status_hi=(6, 4, True, False, False, False),  # cyan on blue
        minibuf=(7, -1, False, False, False, False),
        error=(5, -1, True, False, False, False),  # magenta bold (no red)
        dim=(7, -1, False, False, False, True),
        progress=(6, 4, True, False, False, False),
        title_bar=(7, 4, True, False, False, False),
    ),
    "light": _t(
        normal=(0, 7, False, False, False, False),
        h1=(4, 7, True, False, False, False),  # blue bold
        h2=(5, 7, True, False, False, False),  # magenta bold
        h3=(4, 7, False, False, False, False),  # blue
        h4=(0, 7, True, False, True, False),
        bold=(0, 7, True, False, False, False),
        italic=(0, 7, False, True, False, False),
        bolditalic=(0, 7, True, True, False, False),
        code=(4, 7, False, False, False, False),
        code_normal=(4, 7, False, False, False, False),
        codeblock=(4, 7, False, False, False, True),
        keyword=(5, 7, True, False, False, False),
        string=(4, 7, False, False, False, False),
        comment=(5, 7, False, True, False, True),
        number=(5, 7, False, False, False, False),
        link=(4, 7, False, False, True, False),
        image=(5, 7, False, False, True, False),
        quote=(5, 7, False, True, False, False),
        bullet=(4, 7, True, False, False, False),
        ordinal=(4, 7, False, False, False, False),
        table=(4, 7, False, False, False, False),
        hr=(5, 7, False, False, False, True),
        current_word=(7, 4, True, False, False, False),  # white on blue
        search_match=(7, 5, False, False, False, False),  # white on magenta
        search_current=(7, 4, True, False, False, False),
        status=(7, 4, True, False, False, False),
        status_hi=(7, 5, True, False, False, False),
        minibuf=(0, 7, False, False, False, False),
        error=(5, 7, True, False, False, False),
        dim=(0, 7, False, False, False, True),
        progress=(7, 4, False, False, False, False),
        title_bar=(7, 4, True, False, False, False),
    ),
    "contrast": _t(
        # High contrast: bold white on black, cyan & magenta accents
        normal=(7, 0, False, False, False, False),
        h1=(6, 0, True, False, False, False),
        h2=(7, 0, True, False, False, False),
        h3=(5, 0, True, False, False, False),
        h4=(7, 0, True, False, True, False),
        bold=(7, 0, True, False, False, False),
        italic=(7, 0, False, True, False, False),
        bolditalic=(7, 0, True, True, False, False),
        code=(6, 0, True, False, False, False),
        code_normal=(6, 0, True, False, False, False),
        codeblock=(6, 0, False, False, False, False),
        keyword=(5, 0, True, False, False, False),
        string=(6, 0, False, False, False, False),
        comment=(7, 0, False, False, False, False),
        number=(5, 0, False, False, False, False),
        link=(6, 0, False, False, True, False),
        image=(5, 0, False, False, True, False),
        quote=(7, 0, False, False, False, False),
        bullet=(6, 0, True, False, False, False),
        ordinal=(6, 0, False, False, False, False),
        table=(7, 0, False, False, False, False),
        hr=(7, 0, False, False, False, False),
        current_word=(0, 6, True, False, False, False),
        search_match=(0, 7, False, False, False, False),
        search_current=(0, 5, True, False, False, False),
        status=(0, 7, True, False, False, False),
        status_hi=(0, 6, True, False, False, False),
        minibuf=(7, 0, True, False, False, False),
        error=(5, 0, True, False, False, False),
        dim=(7, 0, False, False, False, False),
        progress=(0, 6, False, False, False, False),
        title_bar=(0, 7, True, False, False, False),
    ),
    "phosphor": _t(
        # Classic green phosphor monochrome
        normal=(2, -1, False, False, False, False),
        h1=(2, -1, True, False, False, False),
        h2=(2, -1, True, False, True, False),
        h3=(2, -1, False, False, True, False),
        h4=(2, -1, True, False, False, False),
        bold=(2, -1, True, False, False, False),
        italic=(2, -1, False, True, False, False),
        bolditalic=(2, -1, True, True, False, False),
        code=(2, -1, True, False, False, False),
        code_normal=(2, -1, False, False, False, False),
        codeblock=(2, -1, False, False, False, True),
        keyword=(2, -1, True, False, False, False),
        string=(2, -1, False, False, False, False),
        comment=(2, -1, False, True, False, True),
        number=(2, -1, False, False, False, False),
        link=(2, -1, False, False, True, False),
        image=(2, -1, False, False, True, False),
        quote=(2, -1, False, True, False, False),
        bullet=(2, -1, True, False, False, False),
        ordinal=(2, -1, False, False, False, False),
        table=(2, -1, False, False, False, False),
        hr=(2, -1, False, False, False, True),
        current_word=(0, 2, True, False, False, False),
        search_match=(0, 2, False, False, False, False),
        search_current=(2, 0, True, False, False, False),
        status=(0, 2, True, False, False, False),
        status_hi=(0, 2, False, False, False, False),
        minibuf=(2, -1, False, False, False, False),
        error=(2, -1, True, False, False, False),
        dim=(2, -1, False, False, False, True),
        progress=(0, 2, False, False, False, False),
        title_bar=(0, 2, True, False, False, False),
    ),
}

THEME_NAMES = list(THEMES.keys())

# Roles that mark a heading line in the rendered output.
_HEADING_ROLES = frozenset({"h1", "h2", "h3", "h4"})

# Roles that mark a table line in the rendered output.
_TABLE_ROLES = frozenset({"table"})


def _setup_colors(theme_name: str) -> Dict[str, int]:
    """Initialize curses color pairs from a theme dict.
    Returns a mapping role → combined curses attribute integer."""
    if not curses.has_colors():
        return {r: curses.A_NORMAL for r in _ROLES}
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        pass

    theme = THEMES.get(theme_name, THEMES["dark"])
    _ATTR = {
        "bold": curses.A_BOLD,
        "italic": getattr(curses, "A_ITALIC", 0),
        "underline": curses.A_UNDERLINE,
        "dim": curses.A_DIM,
    }
    result: Dict[str, int] = {}
    for role in _ROLES:
        fg, bg, b, it, ul, dim = theme[role]
        cp = CP[role]
        try:
            curses.init_pair(cp, fg, bg)
        except curses.error:
            pass
        attr = curses.color_pair(cp)
        if b:
            attr |= curses.A_BOLD
        if it:
            attr |= _ATTR["italic"]
        if ul:
            attr |= curses.A_UNDERLINE
        if dim:
            attr |= curses.A_DIM
        result[role] = attr
    return result


# =============================================================================
# M-x command catalog
# =============================================================================

MX_COMMANDS = sorted(
    [
        "about",
        "backend",
        "book-next",
        "book-prev",
        "close",
        "contrast-up",
        "contrast-down",
        "export-braille",
        "export-markdown",
        "export-audio",
        "export-subtitles",
        "subtitle-format",
        "subtitle-word-level",
        "subtitles-with-audio",
        "highlight-granularity",
        "font-size-down",
        "font-size-up",
        "goto-line",
        "help",
        "license",
        "line-numbers",
        "next-heading",
        "next-paragraph",
        "read-next-heading",
        "read-prev-heading",
        "speech-cursor",
        "stop-speech",
        "abbrev-add",
        "abbrev-list",
        "pron-add",
        "pron-list",
        "pron-remove",
        "pronunciations",
        "profile-save",
        "profile-load",
        "profile-list",
        "profile-delete",
        "expand-abbreviations",
        "normalize-numbers",
        "table-mode",
        "next-sentence",
        "open",
        "open-url",
        "pause",
        "play",
        "preset-add",
        "preset-list",
        "prev-heading",
        "prev-paragraph",
        "prev-sentence",
        "replay-paragraph",
        "replay-sentence",
        "save-position",
        "clear-position",
        "jump-saved",
        "speed",
        "ssml",
        "ssml-on",
        "ssml-off",
        "rate-down",
        "rate-up",
        "reload",
        "search",
        "search-backward",
        "settings",
        "speak-line",
        "speak-selection",
        "stop",
        "syntax-highlight",
        "theme",
        "tts-backend",
        "tts-voice",
        "voice-picker",
        "volume-down",
        "volume-up",
        "voice",
        "quit",
        "wrap-width",
        "abbrev-add",
        "abbrev-list",
        "bookmark-delete",
        "bookmark-goto",
        "bookmark-list",
        "bookmark-set",
        "cache-clear",
        "chapter-goto",
        "chapter-list",
        "chapter-next",
        "chapter-prev",
        "copy",
        "expand-abbreviations",
        "footnote-mode",
        "font",
        "history-back",
        "history-forward",
        "normalize-math",
        "normalize-numbers",
        "pubmed",
        "reading-level",
        "reading-stats",
        "stats",
        "library",
        "bookshelf",
        "recent",
        "search-regex",
        "table-mode",
        "wiki",
        "annotate",
        "annotations-list",
        "annotations-search",
        "annotation-goto",
        "annotation-delete",
        "annotations-export",
        "shortcuts",
    ]
)


# =============================================================================
# Helper functions
# =============================================================================


def _addstr(win: "curses.window", y: int, x: int, s: str, attr: int = 0) -> None:
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w or not s:
        return
    s = s[: max(0, w - x)]
    if not s:
        return
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass


def _fillrow(win: "curses.window", y: int, attr: int = 0, ch: str = " ") -> None:
    h, w = win.getmaxyx()
    if y < 0 or y >= h:
        return
    try:
        win.addstr(y, 0, ch * (w - 1), attr)
    except curses.error:
        pass


# =============================================================================
# Canonical keyboard shortcuts  (GUI/TUI parity + cheat sheet)
# =============================================================================

# The GUI bindings are the canonical set.  The TUI mirrors them where the
# terminal can express the chord; where it cannot (terminals can't see
# Ctrl+Shift+<letter>), an equivalent single-key or M-x command is listed.
_SHORTCUTS: List[Tuple[str, List[Tuple[str, str, str]]]] = [
    (
        "Playback",
        [
            ("Play / pause", "Space  (or tap Ctrl)", "Space"),
            ("Stop", "Esc", "Esc / M-x stop"),
            ("Speed up / slow down", "Ctrl+= / Ctrl+-", "+ / -"),
            ("Play from cursor", "Ctrl+Return", "—"),
            ("Choose TTS engine", "Ctrl+Shift+G", "M-x tts-backend"),
            ("Choose voice", "Ctrl+Shift+V", "M-x voice-picker"),
            ("Speech-cursor mode", "Tab", "Tab"),
            ("Toggle SSML prosody", "Ctrl+Alt+Y", "M-x ssml"),
            ("Speak current line", "—", "M-x speak-line"),
        ],
    ),
    (
        "Navigation",
        [
            ("Next / prev heading", "Ctrl+H / Ctrl+Shift+H", "> / <"),
            ("Next / prev paragraph", "Ctrl+P / Ctrl+Shift+P", "] / ["),
            ("Next / prev sentence", "Alt+. / Alt+,", ". / ,"),
            ("Replay sentence", "Alt+;", ";"),
            ("Replay paragraph", "Ctrl+R", "r"),
            ("Next / prev table", "Ctrl+T / Ctrl+Shift+T", "M-x next-table"),
        ],
    ),
    (
        "Notes / Annotations",
        [
            ("Add note at cursor", "Ctrl+Shift+A", "a / M-x annotate"),
            ("Edit / delete note", "Ctrl+Shift+E / Ctrl+Shift+D", "M-x annotation-*"),
            ("Toggle Notes panel", "Ctrl+Shift+N", "M-x annotations-list"),
            ("Export notes", "Ctrl+Alt+N", "M-x annotations-export"),
            (
                "Search / filter notes",
                "(search box in panel)",
                "M-x annotations-search",
            ),
        ],
    ),
    (
        "Highlights",
        [
            ("Highlight colors 1-5", "Ctrl+Shift+1 … 5", "—"),
            ("Clear all highlights", "Ctrl+Shift+0", "—"),
        ],
    ),
    (
        "Citations",
        [
            ("Import / export", "Ctrl+Alt+I / Ctrl+Alt+E", "—"),
            ("Add citation / by DOI", "Ctrl+Alt+C / Ctrl+Alt+D", "—"),
            ("Insert at cursor", "Ctrl+Alt+R", "—"),
            ("Manage / browse", "Ctrl+Alt+G", "—"),
        ],
    ),
    (
        "View & Reading Aids",
        [
            ("Cycle / choose theme", "F5 / Ctrl+Alt+T", "F5"),
            ("Toggle Contents panel", "Ctrl+\\", "—"),
            ("Reading level", "Ctrl+L", "M-x reading-level"),
            ("Change font", "Ctrl+Alt+F", "—"),
            ("Text spacing / karaoke", "Ctrl+Alt+W / Ctrl+Alt+K", "—"),
            ("Dyslexia font / bionic", "Ctrl+Alt+X / Ctrl+Alt+J", "—"),
            ("Current-line highlight", "Ctrl+Alt+L", "—"),
            ("Reload / open CSS themes", "Ctrl+Shift+R / Ctrl+Shift+F", "—"),
            ("Line numbers / syntax", "—", "F6 / F7"),
        ],
    ),
    (
        "File & Export",
        [
            ("Open file / URL", "Ctrl+O / Ctrl+Shift+O", "Ctrl+O / M-x open-url"),
            ("Export Markdown / PDF", "Ctrl+Alt+M / Ctrl+Alt+P", "M-x export-markdown"),
            ("Export Braille / Audio", "Ctrl+Alt+B / Ctrl+Alt+A", "M-x export-*"),
            ("Export Subtitles", "Ctrl+Alt+U", "M-x export-subtitles"),
            ("Quit", "Ctrl+Q", "Ctrl+Q / q"),
        ],
    ),
    (
        "Edit",
        [
            ("Toggle edit mode", "Ctrl+E", "—"),
            ("Save", "Ctrl+S", "—"),
            ("Copy", "Ctrl+C", "M-x copy"),
        ],
    ),
    (
        "Tools & Help",
        [
            ("Transcribe / dictate", "Ctrl+Alt+S / Ctrl+Alt+V", "—"),
            ("Transcript timestamps", "Ctrl+Alt+Z", "—"),
            ("Clear document cache", "Ctrl+Shift+Delete", "M-x cache-clear"),
            ("Command palette", "F2", "M-x / F2 / :"),
            ("Keyboard cheat sheet", "F3", "M-x shortcuts"),
            ("Customize shortcuts", "Ctrl+Alt+Q", "—"),
            ("Help (README) / About", "F1 / Ctrl+F1", "F1"),
        ],
    ),
]


def _shortcuts_text(plain: bool = False) -> str:
    """Render the canonical shortcut scheme as text.

    *plain* True produces a column layout for the curses pager; otherwise a
    Markdown table suitable for the Qt help dialog.
    """
    if plain:
        lines = ["Keyboard Shortcuts  (GUI bindings are canonical)", ""]
        for section, rows in _SHORTCUTS:
            lines.append(f"== {section} ==")
            for action, gui, tui in rows:
                lines.append(f"  {action:<26} GUI: {gui:<24} TUI: {tui}")
            lines.append("")
        return "\n".join(lines)
    md = [
        "# Keyboard Shortcuts",
        "",
        "GUI bindings are canonical; the TUI mirrors them where the terminal allows.",
        "",
    ]
    for section, rows in _SHORTCUTS:
        md.append(f"## {section}")
        md.append("")
        md.append("| Action | GUI | TUI |")
        md.append("|---|---|---|")
        for action, gui, tui in rows:
            md.append(f"| {action} | `{gui}` | `{tui}` |")
        md.append("")
    return "\n".join(md)


# =============================================================================
# Main TUI Application
# =============================================================================


class StarApp:
    """Main curses application for star — Speaking Terminal Access Reader."""

    VERSION_STRING = f"{APP_NAME} {APP_VERSION} — {APP_TITLE}"

    def __init__(
        self, stdscr: "curses.window", settings: Settings, initial_path: str = ""
    ) -> None:
        self.scr = stdscr
        self.settings = settings
        self.doc: Optional[Document] = None
        self.rendered: List[Line] = []  # rendered display lines
        self.scroll = 0  # top visible display line
        self.tts = TTSManager(settings)
        # Reading statistics & progress tracker, driven by a poll from the
        # main run loop.
        self.stats = ReadingStats(settings)
        self.search = SearchEngine()
        self.search_active = False
        self.search_dir = "forward"

        # UI state
        self.theme_name: str = settings["theme"]
        self.attrs: Dict[str, int] = {}
        self.message = ""
        self.message_t = 0.0
        self.message_dur = 4.0
        self.mode = "normal"  # "normal" | "mx" | "search" | "goto"
        self.mx_ed = LineEditor()
        self.mx_completions: List[str] = []
        self.mx_comp_idx = -1
        self.mx_history: List[str] = []
        self.mx_hist_pos = -1
        # When set, _mx_update_completions draws from this list instead of
        # MX_COMMANDS.  Used by the voice picker and any other minibuffer
        # that needs its own completion source.
        self._mx_custom_completions: Optional[List[str]] = None
        self.search_ed = LineEditor()
        self.goto_ed = LineEditor()
        self.loading = False
        self.loading_msg = ""
        self._load_queue: "queue.Queue[Optional[Document]]" = queue.Queue()
        self._running = True
        self._highlight_line = -1  # display line of current TTS word
        self._highlight_col_start = -1
        self._highlight_col_end = -1
        # Sentence-level highlight span: (start_word, end_word)
        # word-map indices inclusive, or None when word-level highlighting is
        # active.  Set by _on_highlight when highlight_granularity is
        # "sentence" / "both".
        self._highlight_sent: Optional[Tuple[int, int]] = None
        # Navigation history
        self._nav_history: List[int] = []
        self._nav_hist_pos: int = -1

        # Speech Cursor mode state
        self._sc_line: int = 0  # display-line index of the reading cursor
        self._sc_reader: Optional[_SCReader] = None  # persistent line reader

        # Word index saved when the user pauses speech (Space).  -1 means no
        # saved position.  Used by _tts_toggle to resume from the exact word
        # where reading was paused rather than restarting from the scroll top.
        self._tts_paused_at_word: int = -1

        # Sentence map: list of word-map indices where each sentence begins.
        # Built asynchronously (same thread as the word map) after each load.
        self._sentence_starts: List[int] = [0]

        # Initialize curses
        curses.curs_set(1)
        self.scr.keypad(True)
        self.scr.timeout(150)
        os.environ.setdefault("ESCDELAY", "25")

        self._init_colors()

        # TTS word highlight callback
        self.tts.set_on_highlight(self._on_highlight)

        if initial_path:
            self._open_async(initial_path)

    def _init_colors(self) -> None:
        self.attrs = _setup_colors(self.theme_name)

    def _a(self, role: str) -> int:
        return self.attrs.get(role, curses.A_NORMAL)

    # ── Message ────────────────────────────────────────────────────────────

    def notify(self, msg: str, dur: float = 4.0, error: bool = False) -> None:
        self.message = msg
        self.message_t = time.monotonic()
        self.message_dur = dur
        if error:
            pass  # Could pipe to log

    # ── Highlight callback from TTS ────────────────────────────────────────

    def _on_highlight(self, word_idx: int) -> None:
        """Called from the TTS/timer background thread — must NOT call any
        curses functions (not thread-safe).  Only update plain attributes;
        the main draw loop reads them on the next tick and adjusts scroll."""
        if not self.settings["highlight_current_word"]:
            return
        if self.doc and 0 <= word_idx < len(self.doc.word_map):
            wp = self.doc.word_map[word_idx]
            self._highlight_line = wp.disp_line
            self._highlight_col_start = wp.disp_col
            self._highlight_col_end = wp.disp_col + wp.tts_len
            # Sentence-level highlight: resolve the span of the sentence that
            # contains this word so the draw loop can band-highlight it.
            gran = str(self.settings.get("highlight_granularity", "word"))
            if gran in ("sentence", "both"):
                ss = self._sentence_starts
                si = self._find_sentence_idx(word_idx)
                start_w = ss[si] if si < len(ss) else word_idx
                end_w = (
                    ss[si + 1] - 1 if si + 1 < len(ss) else len(self.doc.word_map) - 1
                )
                self._highlight_sent = (start_w, max(start_w, end_w))
            else:
                self._highlight_sent = None
        else:
            self._highlight_line = -1
            self._highlight_col_start = -1
            self._highlight_col_end = -1
            self._highlight_sent = None

    # ── Async document loading ─────────────────────────────────────────────

    def _open_async(self, path: str) -> None:
        self.loading = True
        self.loading_msg = (
            f"Loading {Path(path).name if not path.startswith('http') else path} …"
        )

        def _work() -> None:
            try:
                doc = load_document(path, self.settings)
                self._load_queue.put(doc)
            except Exception as e:
                err_doc = Document(
                    path=path,
                    title="Error",
                    format="error",
                    markdown=f"# Load Error\n\n```\n{e}\n```\n",
                )
                err_doc.plain_text = str(e)
                self._load_queue.put(err_doc)

        threading.Thread(target=_work, daemon=True).start()

    def _poll_load_queue(self) -> None:
        try:
            doc = self._load_queue.get_nowait()
        except queue.Empty:
            return
        self.loading = False
        # Persist the current document's position before replacing it.
        self._save_reading_position()
        self.doc = doc
        # Build word map in background too
        self._render_doc()
        self.scroll = 0
        self._tts_stop()  # also clears any saved pause position for old doc
        self.notify(f"Opened: {doc.title}")
        recents: List[str] = self.settings["recent_files"]
        if doc.path and doc.path not in recents:
            recents.insert(0, doc.path)
            self.settings["recent_files"] = recents[:20]
        self.settings["last_path"] = doc.path
        _record_library(self.settings, doc)  # library / bookshelf
        if self.settings["tts_auto_play"]:
            self._tts_play()

    def _render_doc(self) -> None:
        if not self.doc:
            return
        h, w = self.scr.getmaxyx()
        wrap = int(self.settings["wrap_width"]) or (w - 2)
        self.rendered = render_markdown(
            self.doc.markdown,
            wrap,
            tab_width=int(self.settings["tab_width"]),
            syntax=bool(self.settings["syntax_highlight"]),
        )

        # Build word map and sentence map asynchronously (non-blocking)
        def _build() -> None:
            flat = ["".join(t for t, _ in line) for line in self.rendered]
            self.doc.word_map = _build_word_map(self.doc.plain_text, flat)
            self.tts.set_word_map(self.doc.word_map)
            self._build_sentence_map()  # depends on word_map
            self._restore_reading_position()  # scroll to last position

        threading.Thread(target=_build, daemon=True).start()

    # ── Sentence map ──────────────────────────────────────────────────

    def _build_sentence_map(self) -> None:
        """Populate self._sentence_starts with word-map indices at which each
        sentence begins.  Runs in the background thread that also builds the
        word map, so self.doc.word_map is guaranteed to exist on entry."""
        if not self.doc or not self.doc.plain_text or not self.doc.word_map:
            self._sentence_starts = [0]
            return

        text = self.doc.plain_text
        wm = self.doc.word_map

        # Collect the character offsets where new sentences begin.
        char_starts = [0]
        for m in _SENTENCE_SPLIT_RE.finditer(text):
            char_starts.append(m.end())

        # Map each char offset to the first word at or after that offset.
        # Both char_starts and wm are ordered, so a single forward walk suffices.
        word_starts: List[int] = []
        wi = 0
        for cs in char_starts:
            while wi < len(wm) and wm[wi].tts_offset < cs:
                wi += 1
            word_starts.append(min(wi, len(wm) - 1))

        # Deduplicate while preserving order.
        seen: set = set()
        result: List[int] = []
        for ws in word_starts:
            if ws not in seen:
                seen.add(ws)
                result.append(ws)

        self._sentence_starts = result if result else [0]

    def _find_sentence_idx(self, word_idx: int) -> int:
        """Return the index in _sentence_starts of the sentence that contains
        *word_idx* (binary search; O(log n))."""
        ss = self._sentence_starts
        lo, hi, result = 0, len(ss) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if ss[mid] <= word_idx:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def _current_word_for_nav(self) -> int:
        """Return the best estimate of the current reading word index.

        Priority order:
        1. Live TTS highlight (engine is actively speaking).
        2. Saved pause position (_tts_paused_at_word) set when the user
           pressed Space to pause — this is the word we stopped on, so
           replay/sentence-jump commands operate at the right place even
           while speech is not running.
        3. First word at or below the current scroll position (viewport
           fallback when no speech has started or the document was just
           opened).
        """
        if self.tts.speaking:
            # Prefer the last callback-confirmed position (actual audio
            # position) over the timer estimate (which may be ahead).
            cb = self.tts.last_cb_word_idx
            if cb >= 0:
                return cb
            idx = self.tts.current_word_idx
            if idx >= 0:
                return idx
        if self._tts_paused_at_word >= 0:
            return self._tts_paused_at_word
        if self.doc and self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= self.scroll:
                    return i
        return 0

    # ── TTS controls ──────────────────────────────────────────────────

    def _tts_play(self) -> None:
        """Start speaking from the current scroll position.
        Slices plain_text at the first word on-screen so the engine never
        re-reads content that is already above the viewport."""
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        start_word = 0
        if self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= self.scroll:
                    start_word = i
                    break
        self._tts_play_from_word(start_word)
        self.notify(
            f"Reading at {self.settings['tts_rate']} wpm via {self.tts.backend_name}"
        )

    def _tts_play_from_word(self, word_idx: int) -> None:
        """Start or restart TTS from a specific word-map index.

        Slices ``plain_text`` so the engine only reads from *word_idx*
        onwards.  When SSML is enabled the slice is wrapped with prosody
        markup; ``text_offset=-1`` tells TTSManager to skip word-callback
        offset arithmetic (the timer provides highlight accuracy instead).
        """
        if not self.doc:
            return
        wm = self.doc.word_map
        if wm and word_idx < len(wm):
            text_offset = wm[word_idx].tts_offset
        else:
            text_offset = 0
            word_idx = 0
        text_slice = self.doc.plain_text[text_offset:]

        # Apply speak-time normalizations (abbrev expansion, number words).
        text_slice = _preprocess_tts_text(text_slice, self.settings)

        if self.settings.get("use_ssml", False):
            text_for_engine = _text_to_ssml(
                text_slice,
                backend=self.tts.backend_name,
                sentence_ms=int(self.settings.get("ssml_sentence_pause_ms", 350)),
                clause_ms=int(self.settings.get("ssml_clause_pause_ms", 150)),
            )
            # SSML shifts char offsets — use -1 sentinel, rely on timer only.
            self.tts.speak(text_for_engine, start_word_idx=word_idx, text_offset=-1)
        else:
            self.tts.speak(text_slice, start_word_idx=word_idx, text_offset=text_offset)

    def _tts_stop(self) -> None:
        """Full stop — clears both speech and any saved pause position."""
        self.tts.stop()
        self._highlight_line = -1
        self._highlight_col_start = -1
        self._highlight_col_end = -1
        self._tts_paused_at_word = -1

    def _tts_toggle(self) -> None:
        """Pause/resume speech.

        * While speaking  → pause and remember the current word index so that
          the next press resumes from exactly that word.
        * While paused    → resume from the saved word index.
        * While stopped   → start from the current scroll position (same as
          before, so opening a fresh file and pressing Space still works).
        """
        if self.tts.speaking:
            # Save the last callback-confirmed position when available — it
            # reflects actual audio position rather than the timer's forward
            # estimate.  Pausing at the timer's ahead position would cause
            # resume to skip words; pausing at the callback position may
            # repeat a word or two but is far less disorienting.
            cb = self.tts.last_cb_word_idx
            saved = cb if cb >= 0 else self.tts.current_word_idx
            self._tts_stop()  # resets _tts_paused_at_word to -1
            if saved >= 0:
                self._tts_paused_at_word = saved  # restore the paused position
        elif self._tts_paused_at_word >= 0:
            w = self._tts_paused_at_word
            self._tts_paused_at_word = -1
            self._tts_play_from_word(w)
            self.notify(
                f"Resuming at {self.settings['tts_rate']} wpm via {self.tts.backend_name}"
            )
        else:
            self._tts_play()

    def _tts_speak_current_line(self) -> None:
        if not self.rendered or self.scroll >= len(self.rendered):
            return
        line = self.rendered[self.scroll]
        text = "".join(t for t, _ in line).strip()
        if text:
            self.tts.stop()
            text = _preprocess_tts_text(text, self.settings)
            if self.settings.get("use_ssml", False):
                text = _text_to_ssml(
                    text,
                    backend=self.tts.backend_name,
                    sentence_ms=int(self.settings.get("ssml_sentence_pause_ms", 350)),
                    clause_ms=int(self.settings.get("ssml_clause_pause_ms", 150)),
                )
            self.tts._backend.speak(text)

    # ── Sentence / paragraph navigation ──────────────────────────────────

    def _sentence_jump(
        self, dest_word: int, label: str, always_play: bool = False
    ) -> None:
        """Stop TTS, scroll to dest_word's display line, and restart speech.

        Restarts if speech was already active *or* if *always_play* is True
        (used by replay commands that must always begin reading).
        """
        self._history_push()  # record position before jump
        if not self.doc or not self.doc.word_map:
            return
        dest_word = max(0, min(dest_word, len(self.doc.word_map) - 1))
        dest_line = self.doc.word_map[dest_word].disp_line
        was_speaking = self.tts.speaking
        self.tts.stop()
        self._tts_paused_at_word = -1  # navigation breaks the pause/resume chain
        self._highlight_line = self._highlight_col_start = self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        if was_speaking or always_play:
            self._tts_play_from_word(dest_word)
        self.notify(label)

    def _skip_next_sentence(self) -> None:
        if not self.doc or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        si = self._find_sentence_idx(cur)
        nsi = si + 1
        if nsi >= len(self._sentence_starts):
            self.notify("No next sentence")
            return
        dest = self._sentence_starts[nsi]
        # Preview the first few words of the destination sentence
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        total = len(self._sentence_starts)
        self._sentence_jump(dest, f"→ Sentence {nsi + 1}/{total}: “{preview}…”")

    def _skip_prev_sentence(self) -> None:
        if not self.doc or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        si = self._find_sentence_idx(cur)
        # If we are well into the current sentence, jump to its start first.
        # A "well into" threshold of 3 words feels natural (like double-tap rewind).
        if cur - self._sentence_starts[si] > 3:
            psi = si
        else:
            psi = max(0, si - 1)
        dest = self._sentence_starts[psi]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        total = len(self._sentence_starts)
        self._sentence_jump(dest, f"← Sentence {psi + 1}/{total}: “{preview}…”")

    def _replay_sentence(self) -> None:
        """Jump to the start of the current sentence and always begin reading.

        Uses *always_play=True* so that a single, authoritative
        _tts_play_from_word call is made inside _sentence_jump regardless of
        whether speech was already active.  The old pattern of checking
        ``self.tts.speaking`` after the jump caused a Windows/SAPI5 race: the
        previous speech thread\'s finally-block could set _speaking=False
        after the new thread had already set it to True, making the guard fire
        a second _tts_play_from_word call that killed the first thread.
        """
        if not self.doc or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        si = self._find_sentence_idx(cur)
        dest = self._sentence_starts[si]
        preview = " ".join(
            self.doc.word_map[i].word
            for i in range(dest, min(dest + 5, len(self.doc.word_map)))
        )
        self._sentence_jump(
            dest, f"↺ Replaying sentence: “{preview}…”", always_play=True
        )

    def _find_current_paragraph_start(self) -> int:
        """Return the first display line of the paragraph that contains
        the current scroll position."""
        i = self.scroll
        n = len(self.rendered)
        # If we landed on a blank line, step forward to content first
        while i < n - 1 and not self.rendered[i]:
            i += 1
        # Walk backward while the previous line is content (non-blank)
        while i > 0 and self.rendered[i - 1]:
            i -= 1
        return max(0, i)

    def _replay_paragraph(self) -> None:
        """Jump to the start of the current paragraph and always begin reading."""
        if not self.doc or not self.doc.word_map:
            return
        dest_line = self._find_current_paragraph_start()
        self.tts.stop()
        self._tts_paused_at_word = -1  # navigation breaks the pause/resume chain
        self._highlight_line = self._highlight_col_start = self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        # Find the word at dest_line
        dest_word = 0
        if self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= dest_line:
                    dest_word = i
                    break
        self._tts_play_from_word(dest_word)
        self.notify(f"↺ Replaying paragraph from line {dest_line + 1}")

    # ── Reading position memory ──────────────────────────

    def _save_reading_position(self) -> None:
        """Persist the current reading offset for the open document."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return
        cur = self._current_word_for_nav()
        if cur < 0 or cur >= len(self.doc.word_map):
            return
        offset = self.doc.word_map[cur].tts_offset
        total_chars = len(self.doc.plain_text)
        pct = int(100 * offset / max(1, total_chars))
        positions = dict(self.settings.get("reading_positions", {}))
        positions[self.doc.path] = {
            "offset": offset,
            "pct": pct,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if len(positions) > 200:
            evict = sorted(positions, key=lambda k: positions[k].get("ts", ""))[:50]
            for k in evict:
                del positions[k]
        self.settings.set("reading_positions", positions)

    def _restore_reading_position(self, force: bool = False) -> bool:
        """Scroll to the saved position for the current document.
        Safe to call from a background thread (only writes plain attributes)."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return False
        if not force and not self.settings.get("tts_auto_resume", True):
            return False
        saved = self.settings.get("reading_positions", {}).get(self.doc.path)
        if not saved:
            return False
        target_offset = int(saved.get("offset", 0))
        pct = int(saved.get("pct", 0))
        ts = str(saved.get("ts", ""))[:10]
        wm = self.doc.word_map
        best = len(wm) - 1
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        dest_line = wm[best].disp_line if best < len(wm) else 0
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        self.notify(f"Resumed at {pct}%  (saved {ts})", dur=5.0)
        return True

    def _clear_reading_position(self) -> None:
        """Delete the saved position for the current document."""
        if not self.doc or not self.doc.path:
            return
        positions = dict(self.settings.get("reading_positions", {}))
        if self.doc.path in positions:
            del positions[self.doc.path]
            self.settings.set("reading_positions", positions)
            self.notify("Reading position cleared")
        else:
            self.notify("No saved position for this document")

    # ── Speed presets ───────────────────────────────────────────────────

    def _set_speed_preset(self, name: str) -> None:
        """Apply a named speed preset or a raw wpm integer."""
        name = (name or "").strip()
        if not name:
            presets = self.settings.get("speed_presets", {})
            lines = "  ".join(f"{k}={v}wpm" for k, v in presets.items())
            self.notify(
                f"Current: {self.settings['tts_rate']} wpm  |  {lines}", dur=6.0
            )
            return
        if name.isdigit():
            wpm = max(50, min(600, int(name)))
            self.tts.set_rate(wpm)
            self.notify(f"Speed: {wpm} wpm")
            return
        presets = self.settings.get("speed_presets", {})
        if name in presets:
            wpm = int(presets[name])
            self.tts.set_rate(wpm)
            self.notify(f"Speed preset “{name}”: {wpm} wpm")
        else:
            self.notify(
                f"Unknown preset “{name}”.  Known: {', '.join(presets)}",
                error=True,
            )

    def _preset_add(self, name: str) -> None:
        """Save the current TTS rate under *name* as a new speed preset."""
        name = (name or "").strip()
        if not name:
            self.notify("Usage: preset-add <name>", error=True)
            return
        wpm = int(self.settings["tts_rate"])
        presets = dict(self.settings.get("speed_presets", {}))
        presets[name] = wpm
        self.settings.set("speed_presets", presets)
        self.notify(f"Preset “{name}” saved: {wpm} wpm")

    def _preset_list(self) -> None:
        """Show all speed presets in the status bar."""
        presets = self.settings.get("speed_presets", {})
        if not presets:
            self.notify("No speed presets defined")
            return
        parts = [
            f"{k}: {v} wpm" for k, v in sorted(presets.items(), key=lambda x: x[1])
        ]
        self.notify("Presets — " + "  |  ".join(parts), dur=7.0)

    def _cycle_speed_preset(self) -> None:
        """Cycle through speed presets in ascending WPM order (F8)."""
        presets = self.settings.get("speed_presets", {})
        if not presets:
            self.notify("No speed presets defined")
            return
        ordered = sorted(presets.items(), key=lambda x: x[1])
        cur_rate = int(self.settings["tts_rate"])
        nxt = ordered[0]
        for name, wpm in ordered:
            if wpm > cur_rate:
                nxt = (name, wpm)
                break
        self.tts.set_rate(nxt[1])
        self.notify(f"Speed: “{nxt[0]}” — {nxt[1]} wpm")

    # ── SSML toggle ─────────────────────────────────────────────────────

    # ── Bookmarks, history, search & utility commands ───────────────────
    def _bookmark_set(self, name: str = "") -> None:
        "Set a named bookmark at the current reading position."
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        bookmarks = dict(self.settings.get("bookmarks", {}))
        doc_bm = dict(bookmarks.get(doc_path, {}))
        if not name:
            n = 1
            while f"mark{n}" in doc_bm:
                n += 1
            name = f"mark{n}"
        cur = self._current_word_for_nav()
        offset = self.doc.word_map[cur].tts_offset
        total_chars = len(self.doc.plain_text)
        pct = int(100 * offset / max(1, total_chars))
        doc_bm[name] = {
            "offset": offset,
            "pct": pct,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        bookmarks[doc_path] = doc_bm
        self.settings.set("bookmarks", bookmarks)
        self.notify(f"Bookmark set: {name}  ({pct}%)")

    def _bookmark_goto(self, name: str) -> None:
        "Jump to a named bookmark in the current document."
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        name = (name or "").strip()
        if not name:
            self.notify("Usage: bookmark-goto <name>", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        doc_bm = self.settings.get("bookmarks", {}).get(doc_path, {})
        if name not in doc_bm:
            self.notify(f"Bookmark '{name}' not found.", error=True)
            return
        target_offset = int(doc_bm[name].get("offset", 0))
        wm = self.doc.word_map
        # Find the word whose tts_offset is closest to the saved offset.
        best, best_dist = 0, abs(wm[0].tts_offset - target_offset)
        for i, wp in enumerate(wm):
            dist = abs(wp.tts_offset - target_offset)
            if dist < best_dist:
                best_dist, best = dist, i
            if wp.tts_offset > target_offset + best_dist:
                break  # offsets are monotonically increasing; no closer match ahead
        self._history_push()
        self._sentence_jump(best, f"Jumping to bookmark '{name}'")

    def _bookmark_list(self) -> None:
        "List all bookmarks for the current document in the status bar."
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        doc_bm = self.settings.get("bookmarks", {}).get(doc_path, {})
        if not doc_bm:
            self.notify("No bookmarks for this document.")
            return
        parts = [
            f"{k} ({v.get('pct', '?')}%, {str(v.get('ts', ''))[:10]})"
            for k, v in sorted(doc_bm.items())
        ]
        self.notify("Bookmarks — " + "  |  ".join(parts), dur=8.0)

    def _bookmark_delete(self, name: str) -> None:
        "Remove a named bookmark from the current document."
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        name = (name or "").strip()
        if not name:
            self.notify("Usage: bookmark-delete <name>", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        bookmarks = dict(self.settings.get("bookmarks", {}))
        doc_bm = dict(bookmarks.get(doc_path, {}))
        if name not in doc_bm:
            self.notify(f"Bookmark '{name}' not found.", error=True)
            return
        del doc_bm[name]
        bookmarks[doc_path] = doc_bm
        self.settings.set("bookmarks", bookmarks)
        self.notify(f"Bookmark '{name}' deleted.")

    # ── Navigation history ──────────────────────────────

    def _history_push(self, offset: int = -1) -> None:
        "Record the current TTS offset in the navigation history before a jump."
        if not self.doc or not self.doc.word_map:
            return
        if offset < 0:
            cur = self._current_word_for_nav()
            if 0 <= cur < len(self.doc.word_map):
                offset = self.doc.word_map[cur].tts_offset
            else:
                return
        # When branching off mid-history (user navigated back then jumped elsewhere),
        # discard all forward entries so the list stays consistent.
        if self._nav_hist_pos >= 0:
            self._nav_history = self._nav_history[: self._nav_hist_pos + 1]
            self._nav_hist_pos = -1
        self._nav_history.append(offset)
        max_size = int(self.settings.get("nav_history_size", 50))
        if len(self._nav_history) > max_size:
            self._nav_history = self._nav_history[-max_size:]

    def _history_back(self) -> None:
        "Navigate to the previous position in the navigation history."
        if not self._nav_history:
            self.notify("Navigation history is empty.")
            return
        total = len(self._nav_history)
        if self._nav_hist_pos == -1:
            # First back-step: jump to the most recently saved position.
            new_pos = total - 1
        elif self._nav_hist_pos > 0:
            new_pos = self._nav_hist_pos - 1
        else:
            self.notify("No earlier history.")
            return
        self._nav_hist_pos = new_pos
        self.notify(f"History: position {new_pos + 1}/{total}")
        self._jump_to_offset(self._nav_history[new_pos])

    def _history_forward(self) -> None:
        "Navigate forward after having gone back in navigation history."
        if self._nav_hist_pos < 0:
            self.notify("No forward history.")
            return
        total = len(self._nav_history)
        new_pos = self._nav_hist_pos + 1
        if new_pos >= total:
            self._nav_hist_pos = -1
            self.notify("History: at present position.")
            return
        self._nav_hist_pos = new_pos
        self.notify(f"History: position {new_pos + 1}/{total}")
        self._jump_to_offset(self._nav_history[new_pos])

    def _jump_to_offset(self, target_offset: int) -> None:
        "Scroll to the word in the current document closest to *target_offset*."
        if not self.doc or not self.doc.word_map:
            return
        wm = self.doc.word_map
        best = len(wm) - 1
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        dest_line = wm[best].disp_line
        was_speaking = self.tts.speaking
        self.tts.stop()
        self._highlight_line = self._highlight_col_start = self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        if was_speaking:
            self._tts_play_from_word(best)

    # ── Chapter navigation ──────────────────────────────

    def _chapter_next(self) -> None:
        "Jump to the next chapter in the document."
        if not self.doc or not self.doc.word_map:
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        cur = self._current_word_for_nav()
        current_ch_idx = 0
        for i, (_, _, widx) in enumerate(chapters):
            if widx <= cur:
                current_ch_idx = i
        next_idx = current_ch_idx + 1
        if next_idx >= len(chapters):
            self.notify("Already at the last chapter.")
            return
        title, _, dest_word = chapters[next_idx]
        self._history_push()
        self._sentence_jump(
            dest_word, f"Chapter {next_idx + 1}/{len(chapters)}: {title}"
        )

    def _chapter_prev(self) -> None:
        "Jump to the previous chapter, or to the current chapter start if well into it."
        if not self.doc or not self.doc.word_map:
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        cur = self._current_word_for_nav()
        current_ch_idx = 0
        for i, (_, _, widx) in enumerate(chapters):
            if widx <= cur:
                current_ch_idx = i
        _, _, ch_start_word = chapters[current_ch_idx]
        # Mirror the double-tap rewind idiom used by sentence navigation:
        # if the reader is more than 5 words into the chapter, replay its start;
        # otherwise go one chapter back.
        if cur - ch_start_word > 5:
            dest_idx = current_ch_idx
        elif current_ch_idx == 0:
            self.notify("Already at the first chapter.")
            return
        else:
            dest_idx = current_ch_idx - 1
        title, _, dest_word = chapters[dest_idx]
        self._history_push()
        self._sentence_jump(
            dest_word, f"Chapter {dest_idx + 1}/{len(chapters)}: {title}"
        )

    def _chapter_list(self) -> None:
        "Show all chapter titles for the current document in the status bar."
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        parts = [f"{i + 1}. {title}" for i, (title, _, _) in enumerate(chapters)]
        self.notify("Chapters — " + "  |  ".join(parts), dur=10.0)

    def _chapter_goto(self, name_or_num: str) -> None:
        "Jump to a chapter by 1-based number or partial case-insensitive title match."
        if not self.doc or not self.doc.word_map:
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        name_or_num = (name_or_num or "").strip()
        if not name_or_num:
            self._chapter_list()
            return
        if name_or_num.isdigit():
            n = int(name_or_num) - 1  # convert to 0-based index
            if 0 <= n < len(chapters):
                title, _, dest_word = chapters[n]
                self._history_push()
                self._sentence_jump(
                    dest_word, f"Chapter {n + 1}/{len(chapters)}: {title}"
                )
            else:
                self.notify(
                    f"Chapter number out of range (1–{len(chapters)}).", error=True
                )
            return
        # Partial title match — take the first hit.
        needle = name_or_num.lower()
        for i, (title, _, dest_word) in enumerate(chapters):
            if needle in title.lower():
                self._history_push()
                self._sentence_jump(
                    dest_word, f"Chapter {i + 1}/{len(chapters)}: {title}"
                )
                return
        self.notify(f"No chapter matching '{name_or_num}'.", error=True)

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

    # ── Footnote mode toggle ──────────────────

    def _set_footnote_mode(self, mode: str) -> None:
        "Set footnote reading mode (inline | deferred | skip) and reload."
        mode = (mode or "").strip().lower()
        if not mode:
            cur = self.settings.get("footnote_mode", "inline")
            self.notify(
                f"Footnote mode: {cur}  —  options: inline  deferred  skip",
                dur=5.0,
            )
            return
        if mode not in ("inline", "deferred", "skip"):
            self.notify(
                f"Unknown footnote mode {mode!r}.  Use: inline, deferred, or skip.",
                error=True,
            )
            return
        self.settings.set("footnote_mode", mode)
        self.notify(f"Footnote mode: {mode}  (reloading document)")
        if self.doc and self.doc.path:
            self._open_async(self.doc.path)

    # ── Clipboard copy (TUI stub) ──────────────────

    def _copy_current_line(self) -> str:
        "Return the text of the current top-visible display line."
        if not self.rendered or self.scroll >= len(self.rendered):
            return ""
        return "".join(t for t, _ in self.rendered[self.scroll]).strip()

    def _copy_to_clipboard(self) -> None:
        """Copy the current top-visible line to the system clipboard.

        Uses pyperclip when available; otherwise shows the text in the
        status bar so the user can select it manually. Never raises."""
        text = self._copy_current_line()
        if not text:
            self.notify("Nothing to copy (empty line).", error=True)
            return
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(text)
            truncated = text[:60] + ("…" if len(text) > 60 else "")
            self.notify(f"Copied to clipboard: {truncated}")
        except Exception:
            # pyperclip unavailable or clipboard inaccessible — surface the text.
            self.notify(f"Copy (select manually): {text}", dur=10.0)

    # ── Recent files ──────────────────

    def _recent_files(self) -> None:
        "Show the recent-files list and open the selected entry via minibuffer."
        recent: List[str] = self.settings.get("recent_files", [])
        if not recent:
            self.notify("No recent files.")
            return
        # Preview up to 10 entries in the status bar.
        preview_parts = [f"{i + 1}. {path}" for i, path in enumerate(recent[:10])]
        self.notify("Recent: " + "  |  ".join(preview_parts), dur=8.0)

        def _on_pick(value: str) -> None:
            value = value.strip()
            if not value:
                return
            if value.isdigit():
                n = int(value) - 1
                if 0 <= n < len(recent):
                    self._open_async(recent[n])
                else:
                    self.notify(f"No recent file #{int(value)}.", error=True)
            else:
                # User typed a path directly.
                self._open_async(value)

        self._enter_minibuffer(
            prompt=f"Open recent [1–{min(len(recent), 10)}] or path: ",
            on_commit=_on_pick,
        )

    # ── Reading statistics & library ─────────────

    def _reading_stats(self) -> None:
        """Show the reading-statistics dashboard in a pager (M-x reading-stats)."""
        try:
            self.stats.flush()  # make the current session's numbers fresh
        except Exception:
            pass
        path = self.doc.path if self.doc else ""
        title = self.doc.title if self.doc else ""
        text = _format_reading_stats(self.settings, path, title)
        self._show_text_pager("Reading Statistics", text)

    def _library_browser(self) -> None:
        """List library documents and open the chosen one (M-x library)."""
        entries = _library_entries(self.settings)
        if not entries:
            self.notify("Library is empty. Open a document to add it.")
            return
        preview = [
            f"{i + 1}. {e['title']} ({e['pct']}%)" for i, e in enumerate(entries[:12])
        ]
        self.notify("Library: " + "  |  ".join(preview), dur=8.0)

        def _on_pick(value: str) -> None:
            value = value.strip()
            if not value:
                return
            if value.isdigit():
                n = int(value) - 1
                if 0 <= n < len(entries):
                    self._open_async(entries[n]["path"])
                else:
                    self.notify(f"No library item #{int(value)}.", error=True)
            else:
                self._open_async(value)

        self._enter_minibuffer(
            prompt=f"Open library [1–{min(len(entries), 12)}] or path: ",
            on_commit=_on_pick,
        )

    # ── Wikipedia and PubMed shortcuts ──────────────────

    def _open_wikipedia(self, query: str) -> None:
        "Fetch and open the Wikipedia article for query via the URL loader."
        query = (query or "").strip()
        if not query:
            self.notify("Usage: wikipedia <query>", error=True)
            return
        # Use the standard wiki URL; _open_async → _load_url handles HTML → Markdown.
        encoded = urllib.parse.quote(query.replace(" ", "_"))
        url = f"https://en.wikipedia.org/wiki/{encoded}"
        self.notify(f"Opening Wikipedia: {query}")
        self._open_async(url)

    def _open_pubmed(self, pmid: str) -> None:
        "Fetch and open a PubMed abstract by PMID via the URL loader."
        pmid = (pmid or "").strip()
        if not pmid:
            self.notify("Usage: pubmed <PMID>", error=True)
            return
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={urllib.parse.quote(pmid)}&rettype=abstract&retmode=text"
        )
        self.notify(f"Opening PubMed abstract: PMID {pmid}")
        self._open_async(url)

    def _cache_clear(self) -> None:
        "Delete all cached document files to free disk space."
        import shutil as _shutil

        try:
            if CACHE_DIR.exists():
                _shutil.rmtree(CACHE_DIR)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                self.notify("Document cache cleared")
            else:
                self.notify("Cache is already empty")
        except OSError as e:
            self.notify(f"Cache clear error: {e}", error=True)

    def _ssml_toggle(self) -> None:
        val = not bool(self.settings.get("use_ssml", False))
        state = "ON" if val else "OFF"
        self.settings.set("use_ssml", val)
        self.notify(f"SSML prosody: {state}")

    # ── Voice picker ───────────────────────────────────────────────────

    def _voice_picker(self) -> None:
        """Open an interactive voice-selection minibuffer.

        Voice *names* are used as the completion source so the user never
        has to type or copy a raw Windows registry path.  Substring search
        is used (type \"zira\" to find \"Microsoft Zira Desktop\").
        Pressing Enter applies the voice and speaks a brief test phrase.
        """
        voices = self.tts.list_voices()
        if not voices:
            self.notify(
                "No voices found. Is pyttsx3 installed and the backend set to pyttsx3?",
                error=True,
            )
            return

        # Build display strings and a lookup from display name → voice dict.
        # Append the language tag for clarity; deduplicate if names collide.
        name_map: Dict[str, Dict[str, str]] = {}
        ordered: List[str] = []
        for v in voices:
            name = v.get("name", v.get("id", "Unknown"))
            lang = v.get("lang", "")
            display = f"{name}  [{lang}]" if lang else name
            key, n = display, 1
            while key in name_map:
                n += 1
                key = f"{display} ({n})"
            ordered.append(key)
            name_map[key] = v

        # Pre-fill the current voice name so the user sees their selection.
        current_id = str(self.settings.get("tts_voice", ""))
        initial = ""
        for key, v in name_map.items():
            if v.get("id") == current_id:
                initial = key
                break

        def on_select(chosen: str) -> None:
            chosen = chosen.strip()
            match = name_map.get(chosen)
            if not match:
                # Fuzzy: first case-insensitive substring hit
                low = chosen.lower()
                for key, v in name_map.items():
                    if low in key.lower():
                        match = v
                        break
            if not match:
                self.notify(f"Voice not found: {chosen!r}", error=True)
                return
            self._apply_voice(match.get("id", ""), match.get("name", chosen))

        self._enter_minibuffer(
            "Voice (Tab to browse, type to filter): ",
            initial=initial,
            on_commit=on_select,
            completions=ordered,
        )

    def _apply_voice(self, voice_id: str, voice_name: str = "") -> None:
        """Apply *voice_id* to the active backend, persist it, and speak a
        brief confirmation phrase so the user can immediately hear the change."""
        self.tts._backend.set_voice(voice_id)
        self.settings.set("tts_voice", voice_id)
        label = voice_name or voice_id or "system default"
        self.notify(f"Voice: {label}")
        # Stop any current speech then speak a one-line test so the user
        # can hear the new voice without pressing Space.
        self.tts.stop()
        self.tts._backend.speak(f"Voice changed to {label}.")

    # ── Abbreviation helpers ───────────────────────────────────────────────

    def _abbrev_add(self, arg: str) -> None:
        """Add or update a custom abbreviation expansion.
        Usage:  abbrev-add <abbrev.> <expansion words>
        Example: abbrev-add RCT randomized controlled trial
        """
        parts = arg.strip().split(None, 1)
        if len(parts) < 2:
            self.notify(
                "Usage: abbrev-add <abbreviation> <expansion>   "
                "e.g.  abbrev-add RCT randomized controlled trial",
                error=True,
            )
            return
        abbr, expansion = parts[0], parts[1].strip()
        custom = dict(self.settings.get("abbrev_expansions") or {})
        custom[abbr] = expansion
        self.settings.set("abbrev_expansions", custom)
        self.notify(f"Abbreviation saved: {abbr!r} \u2192 {expansion!r}")

    def _abbrev_list(self) -> None:
        """Show all active custom abbreviation expansions."""
        custom = self.settings.get("abbrev_expansions") or {}
        if not custom:
            self.notify("No custom abbreviations defined.  Use abbrev-add to add one.")
            return
        pairs = "  |  ".join(f"{k} → {v}" for k, v in sorted(custom.items()))
        self.notify(f"Custom abbreviations: {pairs}", dur=8.0)

    # ── Pronunciation lexicon helpers ────────────────────────────────────

    def _pron_add(self, arg: str) -> None:
        """Add or update a pronunciation override.
        Usage:  pron-add <term> <spoken form>
        Example: pron-add Xa cept zah-sept
        """
        parts = arg.strip().split(None, 1)
        if len(parts) < 2:
            self.notify(
                "Usage: pron-add <term> <spoken form>   "
                "e.g.  pron-add CHF congestive heart failure",
                error=True,
            )
            return
        term, spoken = parts[0], parts[1].strip()
        lex = dict(self.settings.get("pronunciations") or {})
        lex[term] = spoken
        self.settings.set("pronunciations", lex)
        self.notify(f"Pronunciation saved: {term!r} → {spoken!r}")

    def _pron_remove(self, term: str) -> None:
        """Remove a pronunciation override by term."""
        term = term.strip()
        lex = dict(self.settings.get("pronunciations") or {})
        if term in lex:
            del lex[term]
            self.settings.set("pronunciations", lex)
            self.notify(f"Pronunciation removed: {term!r}")
        else:
            self.notify(f"No pronunciation for {term!r}.", error=True)

    def _pron_list(self) -> None:
        """Show all pronunciation overrides."""
        lex = self.settings.get("pronunciations") or {}
        if not lex:
            self.notify("No pronunciations defined.  Use pron-add to add one.")
            return
        pairs = "  |  ".join(f"{k} → {v}" for k, v in sorted(lex.items()))
        self.notify(f"Pronunciations: {pairs}", dur=8.0)

    # ── Voice & profile presets ──────────────────────────────────────────

    def _apply_loaded_settings(self) -> None:
        """Re-apply runtime state after a profile's values were written to
        settings (theme colors, TTS backend / voice / rate / volume)."""
        self.theme_name = self.settings.get("theme", self.theme_name)
        self._init_colors()
        try:
            self.tts.change_backend(str(self.settings.get("tts_backend", "auto")))
            voice = str(self.settings.get("tts_voice", ""))
            if voice:
                self.tts._backend.set_voice(voice)
            self.tts.set_rate(int(self.settings.get("tts_rate", 265)))
            self.tts.set_volume(float(self.settings.get("tts_volume", 1.0)))
        except Exception:
            pass

    def _profile_save(self, name: str) -> None:
        """Save the current settings as a named profile (M-x profile-save)."""
        if not _save_profile(self.settings, name):
            self.notify("Usage: profile-save <name>", error=True)
            return
        self.notify(f"Profile saved: {name.strip()!r}")

    def _profile_load(self, name: str) -> None:
        """Apply a saved profile (M-x profile-load <name>)."""
        name = name.strip()
        profiles = self.settings.get("profiles", {}) or {}
        if not name:
            if profiles:
                self.notify("Profiles: " + ", ".join(sorted(profiles)), dur=8.0)
            else:
                self.notify("No profiles saved.  Use profile-save <name>.")
            return
        if _apply_profile_values(self.settings, name) is None:
            self.notify(f"No profile named {name!r}.", error=True)
            return
        self._apply_loaded_settings()
        self.notify(f"Profile loaded: {name!r}")

    def _profile_list(self) -> None:
        """List saved profiles."""
        profiles = self.settings.get("profiles", {}) or {}
        if not profiles:
            self.notify("No profiles saved.  Use profile-save <name>.")
            return
        self.notify("Profiles: " + ", ".join(sorted(profiles)), dur=8.0)

    def _profile_delete(self, name: str) -> None:
        """Delete a saved profile."""
        name = name.strip()
        if _delete_profile(self.settings, name):
            self.notify(f"Profile deleted: {name!r}")
        else:
            self.notify(f"No profile named {name!r}.", error=True)

    # ── Table mode helper ─────────────────────────────────────────────────

    def _set_table_mode(self, mode: str) -> None:
        """Set table reading mode.  Valid values: structured | flat | skip.
        Reloads the document so the change takes effect immediately.
        """
        mode = (mode or "").strip().lower()
        if not mode:
            cur = self.settings.get("table_reading_mode", "structured")
            self.notify(
                f"Table mode: {cur}  \u2014  options: structured  flat  skip",
                dur=5.0,
            )
            return
        if mode not in ("structured", "flat", "skip"):
            self.notify(
                f"Unknown table mode {mode!r}.  Use: structured, flat, or skip.",
                error=True,
            )
            return
        self.settings.set("table_reading_mode", mode)
        self.notify(f"Table reading mode: {mode}  (reloading document)")
        if self.doc and self.doc.path:
            self._open_async(self.doc.path)  # reload with new mode baked in

    def _compute_reading_level_tui(self) -> str:
        """Compute Flesch-Kincaid reading level for the current document."""
        if not self.doc or not self.doc.plain_text:
            return "No document loaded"
        text = self.doc.plain_text[:50000]  # cap for speed
        words = text.split()
        n_words = max(1, len(words))
        sentences = re.split(r"[.!?]+", text)
        n_sentences = max(1, len([s for s in sentences if s.strip()]))

        def _syllables(word: str) -> int:
            word = word.lower().rstrip(".,;:!?")
            if not word:
                return 1
            count = len(re.findall(r"[aeiou]+", word))
            if word.endswith("e") and count > 1:
                count -= 1
            return max(1, count)

        n_syllables = sum(_syllables(w) for w in words)
        ease = (
            206.835 - 1.015 * (n_words / n_sentences) - 84.6 * (n_syllables / n_words)
        )
        grade = 0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
        ease = max(0.0, min(100.0, ease))
        grade = max(0.0, grade)
        if grade < 6:
            level = "elementary"
        elif grade < 9:
            level = "middle school"
        elif grade < 13:
            level = "high school"
        elif grade < 16:
            level = "college"
        else:
            level = "graduate"
        return (
            f"Reading level: Grade {grade:.1f} ({level})  "
            f"Ease: {ease:.0f}/100  "
            f"({n_words:,} words, {n_sentences:,} sentences)"
        )

    # ── Skip navigation (paragraph / heading) ────────────────────────────────────────────────────

    def _navigate_to(self, line: int) -> None:
        """Scroll to *line* and, if TTS was already playing, restart speech
        from the new position so the reader continues without interruption."""
        was_speaking = self.tts.speaking
        if was_speaking:
            self.tts.stop()
            self._highlight_line = -1
            self._highlight_col_start = -1
            self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(line, total - 1) if total else 0)
        if was_speaking:
            self._tts_play()

    def _is_heading_line(self, line_idx: int) -> bool:
        """Return True if the rendered line at *line_idx* is a heading."""
        if 0 <= line_idx < len(self.rendered):
            return any(role in _HEADING_ROLES for _, role in self.rendered[line_idx])
        return False

    def _find_next_paragraph(self, from_line: int) -> int:
        """Return the first line of the paragraph that starts after the one
        containing *from_line*.  Falls back to the last line if none found."""
        n = len(self.rendered)
        i = from_line + 1
        # Walk forward through the current paragraph
        while i < n and self.rendered[i]:
            i += 1
        # Skip blank separator lines
        while i < n and not self.rendered[i]:
            i += 1
        return min(i, n - 1)

    def _find_prev_paragraph(self, from_line: int) -> int:
        """Return the first line of the paragraph that starts before the one
        containing *from_line*.  Falls back to line 0 if none found."""
        i = from_line - 1
        # Skip blank lines backward
        while i > 0 and not self.rendered[i]:
            i -= 1
        # Walk back through the previous paragraph's content
        while i > 0 and self.rendered[i]:
            i -= 1
        # Now i is on a blank line (or 0) — step forward to the first content line
        if not self.rendered[i]:  # blank
            i += 1
        return max(0, i)

    def _find_next_heading(self, from_line: int) -> Optional[int]:
        """Return the line index of the next heading after *from_line*, or
        None if there is no heading below the current position."""
        for i in range(from_line + 1, len(self.rendered)):
            if self._is_heading_line(i):
                return i
        return None

    def _find_prev_heading(self, from_line: int) -> Optional[int]:
        """Return the line index of the previous heading before *from_line*,
        or None if there is no heading above the current position."""
        for i in range(from_line - 1, -1, -1):
            if self._is_heading_line(i):
                return i
        return None

    def _skip_next_paragraph(self) -> None:
        if not self.rendered:
            return
        dest = self._find_next_paragraph(self.scroll)
        self._navigate_to(dest)
        self.notify(f"Paragraph →  line {dest + 1}")

    def _skip_prev_paragraph(self) -> None:
        if not self.rendered:
            return
        dest = self._find_prev_paragraph(self.scroll)
        self._navigate_to(dest)
        self.notify(f"Paragraph ←  line {dest + 1}")

    def _is_table_line(self, line_idx: int) -> bool:
        """Return True if the rendered line at *line_idx* contains table content."""
        if 0 <= line_idx < len(self.rendered):
            return any(role in _TABLE_ROLES for _, role in self.rendered[line_idx])
        return False

    def _find_next_table(self, from_line: int) -> Optional[int]:
        """Return the first line of the next table after *from_line*, or None."""
        n = len(self.rendered)
        i = from_line + 1
        # Skip through any table we're currently inside
        while i < n and self._is_table_line(i):
            i += 1
        for j in range(i, n):
            if self._is_table_line(j):
                return j
        return None

    def _find_prev_table(self, from_line: int) -> Optional[int]:
        """Return the first line of the previous table before *from_line*, or None."""
        i = from_line - 1
        # Skip through any table we're currently inside
        while i >= 0 and self._is_table_line(i):
            i -= 1
        # Scan backward for any table line
        while i >= 0 and not self._is_table_line(i):
            i -= 1
        if i < 0:
            return None
        # Walk back to the start of this table block
        while i > 0 and self._is_table_line(i - 1):
            i -= 1
        return i

    def _skip_next_table(self) -> None:
        dest = self._find_next_table(self.scroll)
        if dest is None:
            self.notify("No table below current position")
            return
        self._navigate_to(dest)
        self.notify(f"▼ Table — line {dest + 1}")

    def _skip_prev_table(self) -> None:
        dest = self._find_prev_table(self.scroll)
        if dest is None:
            self.notify("No table above current position")
            return
        self._navigate_to(dest)
        self.notify(f"▲ Table — line {dest + 1}")

    def _skip_next_heading(self) -> None:
        if not self.rendered:
            return
        dest = self._find_next_heading(self.scroll)
        if dest is None:
            self.notify("No heading below current position")
            return
        self._navigate_to(dest)
        # Show the heading text in the notification
        heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
        self.notify(f"↓ Heading: {heading_text[:50]}")

    def _skip_prev_heading(self) -> None:
        if not self.rendered:
            return
        dest = self._find_prev_heading(self.scroll)
        if dest is None:
            self.notify("No heading above current position")
            return
        self._navigate_to(dest)
        heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
        self.notify(f"↑ Heading: {heading_text[:50]}")

    # ── Read-from-heading  (’>’ / ’<’) ──────────────────────────────────────

    def _line_to_word(self, line: int) -> int:
        """Return the word-map index of the first word at or after *line*.
        Returns 0 when the word map is unavailable."""
        if self.doc and self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= line:
                    return i
        return 0

    def _read_next_heading(self) -> None:
        """Jump to the next heading and *always* begin TTS reading from it.

        Unlike ’}’ (which only resumes speech if it was already playing),
        this command starts the engine unconditionally so the user can
        move through headings while the document is stopped.
        """
        if not self.rendered:
            return
        dest_line = self._find_next_heading(self.scroll)
        if dest_line is None:
            self.notify("No heading below current position")
            return
        dest_word = self._line_to_word(dest_line)
        heading_text = "".join(t for t, _ in self.rendered[dest_line]).strip()
        self._sentence_jump(
            dest_word,
            f"⏩ Reading from: {heading_text[:60]}",
            always_play=True,
        )

    def _read_prev_heading(self) -> None:
        """Jump to the previous heading and *always* begin TTS reading from it.

        Unlike ’{’ (which only resumes speech if it was already playing),
        this command starts the engine unconditionally.
        """
        if not self.rendered:
            return
        dest_line = self._find_prev_heading(self.scroll)
        if dest_line is None:
            self.notify("No heading above current position")
            return
        dest_word = self._line_to_word(dest_line)
        heading_text = "".join(t for t, _ in self.rendered[dest_line]).strip()
        self._sentence_jump(
            dest_word,
            f"⏪ Reading from: {heading_text[:60]}",
            always_play=True,
        )

    # ── Speech Cursor (SC) mode ───────────────────────────────────────────

    def _sc_enter(self) -> None:
        """Activate Speech Cursor mode.

        Stops any running speech, positions the reading cursor at the last
        highlighted word (or the current scroll line) and switches to 'sc'
        mode where every navigation keystroke moves the cursor and reads
        just that single line.
        """
        self._tts_stop()
        if self._highlight_line >= 0:
            self._sc_line = self._highlight_line
        else:
            self._sc_line = self.scroll
        # Build the persistent engine now so the first line has no startup lag.
        if _PYTTSX3 and isinstance(self.tts._backend, Pyttsx3Backend):
            self._sc_reader = _SCReader(
                rate=int(self.settings["tts_rate"]),
                volume=float(self.settings["tts_volume"]),
            )
            self._sc_reader.start()
        else:
            self._sc_reader = None
        self.mode = "sc"
        self.notify(
            "Speech Cursor ON  ↑↓:line  ,/.:sent  [/]:para  {/}:head  t/T:table"
            "  Enter:read-on  Space:pause  Esc:exit",
            dur=7.0,
        )

    def _sc_exit(self, start_reading: bool = False) -> None:
        """Exit Speech Cursor mode.  Speech is **always** stopped first.

        If *start_reading* is True (Enter key), continuous TTS then starts
        from the cursor position so the user can resume full reading from
        wherever they browsed to.  Every other exit leaves the engine silent.
        """
        self.mode = "normal"
        # Stop the persistent SC reader first — this reaches the live SAPI5
        # engine directly without the 200–500 ms Engine() construction race.
        if self._sc_reader is not None:
            self._sc_reader.close()
            self._sc_reader = None
        self._tts_stop()  # also silence the main TTS backend
        if start_reading:
            dest_word = self._line_to_word(self._sc_line)
            self.scroll = self._sc_line
            self._tts_paused_at_word = -1
            self._tts_play_from_word(dest_word)
            self.notify(f"Reading from line {self._sc_line + 1}")

    def _sc_read_line(self, line_idx: int) -> None:
        """Stop current speech and read exactly one rendered line.

        This is the fundamental SC mode action: the cursor sits on a line,
        the engine reads that line and stops, then waits for the next
        navigation keystroke.  Blank lines are announced as \"blank\" so
        the user knows they have crossed a paragraph boundary.

        Plain text is always used regardless of the global *use_ssml* setting
        — SSML is unnecessary for a single short line and plain text keeps
        word-boundary callbacks active for accurate highlighting.
        """
        if not self.rendered or not (0 <= line_idx < len(self.rendered)):
            return
        self.tts.stop()  # stop the main TTS backend / timer
        text = "".join(t for t, _ in self.rendered[line_idx]).strip()
        if not text:
            # Announce blank lines so the user knows they've crossed a
            # paragraph boundary.
            if self._sc_reader is not None:
                self._sc_reader.speak("blank")
            else:
                self.tts._backend.speak("blank")
            return
        text = _preprocess_tts_text(text, self.settings)
        if self._sc_reader is not None:
            # Use the persistent reader: engine already warm, stop() is
            # always effective (no Engine() construction race on exit).
            self._sc_reader.speak(text)
        else:
            # Fallback for non-pyttsx3 backends (eSpeak, DECtalk).
            self.tts._backend.speak(text)

    def _sc_move(self, dest_line: int, label: str = "") -> None:
        """Move the SC cursor to *dest_line*, scroll it into view, and read
        just that single line — no continuous document reading."""
        total = len(self.rendered)
        if not total:
            return
        dest_line = max(0, min(dest_line, total - 1))
        self._sc_line = dest_line
        # Keep cursor comfortably visible
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        margin = int(self.settings.get("scroll_margin", 3))
        if dest_line < self.scroll + margin:
            self.scroll = max(0, dest_line - margin)
        elif dest_line >= self.scroll + view_h - margin:
            self.scroll = max(0, dest_line - view_h + margin + 1)
        # Speak only this line
        self._sc_read_line(dest_line)
        if label:
            self.notify(label)

    def _handle_sc_key(self, ch: int) -> None:  # noqa: C901
        """Key handler for Speech Cursor (sc) mode."""
        # ── Exit / speech-control ─────────────────────────────────────────
        if ch == 27:  # Escape — exit + stop
            self._sc_exit(start_reading=False)
            return
        if ch == 9:  # Tab — exit SC mode and stop speech
            self._sc_exit(start_reading=False)
            return
        if ch in (curses.KEY_ENTER, 10, 13):  # Enter — exit + continuous read
            self._sc_exit(start_reading=True)
            return
        if ch == ord(" "):
            self._tts_toggle()
            return
        if ch in (0, 24):  # Ctrl+Space / Ctrl+X — full stop
            self._tts_stop()
            return

        if not self.rendered:
            return
        total = len(self.rendered)

        # ── Line navigation ───────────────────────────────────────────────
        if ch in (curses.KEY_DOWN, ord("j")):
            dest = min(self._sc_line + 1, total - 1)
            text = "".join(t for t, _ in self.rendered[dest]).strip()
            self._sc_move(dest, f"Line {dest + 1}: {text[:60]}")

        elif ch in (curses.KEY_UP, ord("k")):
            dest = max(self._sc_line - 1, 0)
            text = "".join(t for t, _ in self.rendered[dest]).strip()
            self._sc_move(dest, f"Line {dest + 1}: {text[:60]}")

        # ── Sentence navigation ───────────────────────────────────────────
        elif ch == ord("."):
            if not self.doc or not self.doc.word_map:
                return
            cur = self._line_to_word(self._sc_line)
            si = self._find_sentence_idx(cur)
            nsi = si + 1
            if nsi >= len(self._sentence_starts):
                self.notify("No next sentence")
                return
            dest_word = self._sentence_starts[nsi]
            dest_line = self.doc.word_map[dest_word].disp_line
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest_word, min(dest_word + 5, len(self.doc.word_map)))
            )
            total_s = len(self._sentence_starts)
            self._sc_move(
                dest_line,
                f"→ Sentence {nsi + 1}/{total_s}: “{preview}…”",
            )

        elif ch == ord(","):
            if not self.doc or not self.doc.word_map:
                return
            cur = self._line_to_word(self._sc_line)
            si = self._find_sentence_idx(cur)
            psi = si if cur - self._sentence_starts[si] > 3 else max(0, si - 1)
            dest_word = self._sentence_starts[psi]
            dest_line = self.doc.word_map[dest_word].disp_line
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest_word, min(dest_word + 5, len(self.doc.word_map)))
            )
            total_s = len(self._sentence_starts)
            self._sc_move(
                dest_line,
                f"← Sentence {psi + 1}/{total_s}: “{preview}…”",
            )

        # ── Paragraph navigation ──────────────────────────────────────────
        elif ch in (ord("]"), curses.KEY_NPAGE):
            dest = self._find_next_paragraph(self._sc_line)
            self._sc_move(dest, f"\u00b6 Next paragraph \u2014 line {dest + 1}")

        elif ch in (ord("["), curses.KEY_PPAGE):
            dest = self._find_prev_paragraph(self._sc_line)
            self._sc_move(dest, f"\u00b6 Prev paragraph \u2014 line {dest + 1}")

        # ── Heading navigation ────────────────────────────────────────────
        elif ch in (ord("}"), ord(">")):
            dest = self._find_next_heading(self._sc_line)
            if dest is None:
                self.notify("No heading below")
            else:
                heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
                self._sc_move(dest, f"\u23e9 Heading: {heading_text[:60]}")

        elif ch in (ord("{"), ord("<")):
            dest = self._find_prev_heading(self._sc_line)
            if dest is None:
                self.notify("No heading above")
            else:
                heading_text = "".join(t for t, _ in self.rendered[dest]).strip()
                self._sc_move(dest, f"\u23ea Heading: {heading_text[:60]}")

        # ── Table navigation ──────────────────────────────────────────────
        elif ch == ord("t"):
            dest = self._find_next_table(self._sc_line)
            if dest is None:
                self.notify("No table below")
            else:
                self._sc_move(dest, f"Table at line {dest + 1}")

        elif ch == ord("T"):
            dest = self._find_prev_table(self._sc_line)
            if dest is None:
                self.notify("No table above")
            else:
                self._sc_move(dest, f"Table at line {dest + 1}")

        # ── Re-read current line ──────────────────────────────────────────
        elif ch == ord("r"):
            line_text = "".join(t for t, _ in self.rendered[self._sc_line]).strip()
            self._sc_read_line(self._sc_line)
            self.notify(f"↺ Line {self._sc_line + 1}: {line_text[:60]}")

        # ── Document boundaries ───────────────────────────────────────────
        elif ch == curses.KEY_HOME:
            self._sc_move(0, "Top of document")

        elif ch == curses.KEY_END:
            self._sc_move(total - 1, "End of document")

    def _rate_change(self, delta: int) -> None:
        new_rate = max(50, min(600, int(self.settings["tts_rate"]) + delta))
        self.tts.set_rate(new_rate)
        if self._sc_reader is not None:
            self._sc_reader.update_rate(new_rate)
        self.notify(f"Speech rate: {new_rate} wpm")

    def _volume_change(self, delta: float) -> None:
        new_vol = max(0.0, min(1.0, float(self.settings["tts_volume"]) + delta))
        self.tts.set_volume(new_vol)
        self.notify(f"Volume: {int(new_vol * 100)}%")

    # ── Scrolling ─────────────────────────────────────────────────────────

    def _scroll_by(self, delta: int) -> None:
        total = len(self.rendered)
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        self.scroll = max(0, min(total - 1, self.scroll + delta))

    def _page_down(self) -> None:
        h, _ = self.scr.getmaxyx()
        self._scroll_by(max(1, h - 5))

    def _page_up(self) -> None:
        h, _ = self.scr.getmaxyx()
        self._scroll_by(-max(1, h - 5))

    def _goto_top(self) -> None:
        self.scroll = 0

    def _goto_bottom(self) -> None:
        self.scroll = max(0, len(self.rendered) - 1)

    def _scroll_to_line(self, display_line: int) -> None:
        h, _ = self.scr.getmaxyx()
        view_h = max(1, h - 4)
        margin = int(self.settings["scroll_margin"])
        self.scroll = max(0, min(len(self.rendered) - 1, display_line - view_h // 3))

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

    # ── File operations ────────────────────────────────────────────────────

    def _open_file_prompt(self) -> None:
        """Open a file path via minibuffer prompt."""
        last = str(self.settings.get("last_path", "")) or ""
        default = (
            (str(Path(last).parent) + os.sep) if last and Path(last).is_file() else ""
        )
        self._enter_minibuffer(
            "Find file: ", initial=default, on_commit=self._open_file_cb
        )

    def _open_file_cb(self, path: str) -> None:
        path = path.strip().rstrip("/\\")
        if not path:
            return
        path = os.path.expanduser(os.path.expandvars(path))
        if path.startswith(("http://", "https://")):
            self._open_async(path)
        elif os.path.exists(path):
            self._open_async(path)
        else:
            self.notify(f"File not found: {path}", error=True)

    def _open_url_prompt(self) -> None:
        self._enter_minibuffer(
            "Open URL: ", on_commit=lambda u: self._open_async(u.strip())
        )

    def _export_markdown(self) -> None:
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        p = Path(self.doc.path)
        default = (
            str(p.parent / (p.stem + "_export.md")) if self.doc.path else "export.md"
        )
        self._enter_minibuffer(
            "Export Markdown to: ", initial=default, on_commit=self._export_md_cb
        )

    def _export_md_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest or not self.doc:
            return
        try:
            Path(dest).write_text(self.doc.markdown, encoding="utf-8")
            self.notify(f"Exported → {dest}")
        except OSError as e:
            self.notify(f"Export error: {e}", error=True)

    def _export_braille_cmd(self) -> None:
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        table = str(self.settings["braille_table"])
        brf = _export_braille(
            self.doc.plain_text,
            table,
            use_liblouis=bool(self.settings.get("braille_grade2", False)),
        )
        p = Path(self.doc.path) if self.doc.path else Path("export")
        dest = str(p.parent / (p.stem + ".brf"))
        try:
            Path(dest).write_text(brf, encoding="utf-8")
            self.notify(f"BRF exported → {dest}")
        except OSError as e:
            self.notify(f"BRF export error: {e}", error=True)

    def _export_audio_cmd(self, fmt: str = "") -> None:
        """Prompt for an output path and export TTS audio (M-x export-audio).

        *fmt* is the default file extension (wav, mp3, ogg, mp4).  When empty
        the ``audio_export_format`` setting is used (WAV by default — it needs
        no external tools).  Synthesis runs synchronously, so the TUI will be
        unresponsive until it finishes.  Use a shorter document or the
        espeak/pyttsx3 backend for faster results.
        """
        fmt = (fmt or str(self.settings.get("audio_export_format", "wav"))).lstrip(".")
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + f".{fmt}"))
        self._enter_minibuffer(
            f"Export audio ({fmt}) to: ",
            initial=default,
            on_commit=self._export_audio_cb,
        )

    def _export_audio_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest or not self.doc:
            return
        text = _preprocess_tts_text(self.doc.plain_text, self.settings)
        # Optionally emit a synchronized caption track alongside the audio.
        sub_path: Optional[str] = None
        sub_fmt = str(self.settings.get("subtitle_format", "srt")).lower()
        if self.settings.get("export_subtitles_with_audio", False):
            sub_path = str(Path(dest).with_suffix(f".{sub_fmt}"))
        self.notify("Exporting audio… please wait", dur=5.0)
        try:
            self.tts.export_audio(
                text,
                dest,
                subtitle_path=sub_path,
                subtitle_format=sub_fmt,
                subtitle_word_level=bool(
                    self.settings.get("subtitle_word_level", False)
                ),
            )
            msg = f"Audio exported → {dest}"
            if sub_path:
                msg += f"  (+ {Path(sub_path).name})"
            self.notify(msg)
        except Exception as exc:
            self.notify(f"Audio export error: {exc}", error=True)

    def _export_subtitles_cmd(self) -> None:
        """Prompt for a path and export a timestamped SRT/VTT caption track
        synchronized to the document's synthesized speech (M-x
        export-subtitles).  Synthesis runs synchronously.
        """
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        fmt = str(self.settings.get("subtitle_format", "srt")).lower()
        if fmt not in ("srt", "vtt"):
            fmt = "srt"
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + f".{fmt}"))
        self._enter_minibuffer(
            f"Export subtitles ({fmt}) to: ",
            initial=default,
            on_commit=self._export_subtitles_cb,
        )

    def _export_subtitles_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest or not self.doc:
            return
        fmt = "vtt" if dest.lower().endswith(".vtt") else "srt"
        text = _preprocess_tts_text(self.doc.plain_text, self.settings)
        self.notify("Generating subtitles… please wait", dur=5.0)
        try:
            self.tts.export_subtitles(
                text,
                dest,
                fmt=fmt,
                word_level=bool(self.settings.get("subtitle_word_level", False)),
            )
            self.notify(f"Subtitles exported → {dest}")
        except Exception as exc:
            self.notify(f"Subtitle export error: {exc}", error=True)

    def _set_subtitle_format(self, fmt: str) -> None:
        """Set the caption format used for subtitle export (srt | vtt)."""
        fmt = (fmt or "").strip().lower()
        if fmt not in ("srt", "vtt"):
            cur = str(self.settings.get("subtitle_format", "srt"))
            self.notify(f"Subtitle format: {cur}.  Use 'subtitle-format srt|vtt'.")
            return
        self.settings.set("subtitle_format", fmt)
        self.notify(f"Subtitle format: {fmt}")

    def _set_highlight_granularity(self, gran: str) -> None:
        """Set how the spoken text is highlighted (word | sentence | both)."""
        gran = (gran or "").strip().lower()
        if gran not in ("word", "sentence", "both"):
            cur = str(self.settings.get("highlight_granularity", "word"))
            self.notify(
                f"Highlight granularity: {cur}.  "
                "Use 'highlight-granularity word|sentence|both'."
            )
            return
        self.settings.set("highlight_granularity", gran)
        # Clear any stale sentence span so the change takes effect immediately.
        if gran == "word":
            self._highlight_sent = None
        self.notify(f"Highlight granularity: {gran}")

    def _goto_line_prompt(self) -> None:
        self._enter_minibuffer("Go to line: ", on_commit=self._goto_line_cb)

    def _goto_line_cb(self, s: str) -> None:
        try:
            ln = max(1, int(s.strip())) - 1
            self._scroll_to_line(min(ln, len(self.rendered) - 1))
        except ValueError:
            self.notify(f"Invalid line: {s}", error=True)

    # ── Theme ─────────────────────────────────────────────────────────────

    def _next_theme(self) -> None:
        idx = (
            THEME_NAMES.index(self.theme_name) if self.theme_name in THEME_NAMES else 0
        )
        self.theme_name = THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
        self.settings["theme"] = self.theme_name
        self._init_colors()
        self.notify(f"Theme: {self.theme_name}")

    def _set_theme(self, name: str) -> None:
        if name in THEMES:
            self.theme_name = name
            self.settings["theme"] = name
            self._init_colors()
            self.notify(f"Theme: {name}")
        else:
            self.notify(
                f"Unknown theme '{name}'.  Available: {', '.join(THEME_NAMES)}",
                error=True,
            )

    # ── Minibuffer ─────────────────────────────────────────────────────────

    def _enter_minibuffer(
        self,
        prompt: str = "M-x: ",
        initial: str = "",
        on_commit: Optional[Callable[[str], None]] = None,
        mode: str = "mx",
        completions: Optional[List[str]] = None,
    ) -> None:
        self.mode = mode
        if mode == "mx":
            self.mx_ed = LineEditor(initial)
            self.mx_comp_idx = -1
            self.mx_hist_pos = -1
            self._mx_custom_completions = completions  # None → use MX_COMMANDS
            self._mx_update_completions()
            self._mx_prompt = prompt
            self._mx_callback = on_commit or self.execute_command
        elif mode == "search":
            self.search_ed = LineEditor(initial)
            self._search_prompt = prompt
        elif mode == "goto":
            self.goto_ed = LineEditor(initial)

    def _mx_update_completions(self) -> None:
        source = self._mx_custom_completions
        if source is not None:
            # Custom completion list (e.g. voice names): case-insensitive
            # substring match so typing "zira" finds "Microsoft Zira Desktop".
            q = self.mx_ed.value.strip().lower()
            self.mx_completions = (
                [c for c in source if q in c.lower()] if q else list(source)
            )
        else:
            # Normal M-x: prefix match against command names.
            prefix = (
                self.mx_ed.value.split()[0].lower() if self.mx_ed.value.strip() else ""
            )
            self.mx_completions = (
                [c for c in MX_COMMANDS if c.startswith(prefix)]
                if prefix
                else list(MX_COMMANDS)
            )

    def _mx_tab(self) -> None:
        matches = self.mx_completions
        if not matches:
            return
        if len(matches) == 1:
            self.mx_ed.set_value(matches[0] + " ")
            self.mx_comp_idx = 0
            return
        lcp = matches[0]
        for m in matches[1:]:
            while lcp and not m.startswith(lcp):
                lcp = lcp[:-1]
            if not lcp:
                break
        cur = self.mx_ed.value.rstrip()
        if len(lcp) > len(cur):
            self.mx_ed.set_value(lcp)
            self.mx_comp_idx = 0
        else:
            if self.mx_comp_idx < 0:
                self.mx_comp_idx = 0
            else:
                self.mx_comp_idx = (self.mx_comp_idx + 1) % len(matches)
            self.mx_ed.set_value(matches[self.mx_comp_idx])
        self._mx_update_completions()

    def _cancel_minibuffer(self) -> None:
        self.mode = "normal"
        self.search.query = ""
        self._mx_custom_completions = None

    # ── M-x command executor ──────────────────────────────────────────────

    def execute_command(self, cmd_line: str) -> None:
        cmd_line = cmd_line.strip()
        if not cmd_line:
            return
        parts = cmd_line.split()
        cmd = parts[0].lower()
        args = parts[1:]
        arg = args[0] if args else ""

        cmd_map = {
            "open": self._open_file_prompt,
            "open-url": self._open_url_prompt,
            "close": lambda: (
                setattr(self, "doc", None)
                or self._render_doc()
                or self.notify("Document closed")
            ),
            "reload": lambda: (
                self._open_async(self.doc.path)
                if self.doc
                else self.notify("No document", error=True)
            ),
            "export-markdown": self._export_markdown,
            "export-braille": self._export_braille_cmd,
            "export-audio": lambda: self._export_audio_cmd(arg or ""),
            "export-subtitles": self._export_subtitles_cmd,
            "subtitle-format": lambda: self._set_subtitle_format(arg),
            "subtitle-word-level": lambda: (
                self.settings.set(
                    "subtitle_word_level",
                    not self.settings.get("subtitle_word_level", False),
                ),
                self.notify(
                    "Subtitle word-level cues: "
                    + ("ON" if self.settings.get("subtitle_word_level") else "OFF")
                ),
            ),
            "subtitles-with-audio": lambda: (
                self.settings.set(
                    "export_subtitles_with_audio",
                    not self.settings.get("export_subtitles_with_audio", False),
                ),
                self.notify(
                    "Captions alongside audio export: "
                    + (
                        "ON"
                        if self.settings.get("export_subtitles_with_audio")
                        else "OFF"
                    )
                ),
            ),
            "highlight-granularity": lambda: self._set_highlight_granularity(arg),
            "play": self._tts_play,
            "stop": self._tts_stop,
            "pause": self._tts_toggle,
            "speak-line": self._tts_speak_current_line,
            "search": lambda: self._enter_minibuffer(
                "Search: ",
                mode="search",
                on_commit=lambda q: self._do_search(q, "forward"),
            ),
            "search-backward": lambda: self._enter_minibuffer(
                "Search ↑: ",
                mode="search",
                on_commit=lambda q: self._do_search(q, "backward"),
            ),
            "goto-line": self._goto_line_prompt,
            "theme": lambda: self._set_theme(arg) if arg else self._next_theme(),
            "line-numbers": lambda: (
                self.settings.set(
                    "show_line_numbers", not self.settings["show_line_numbers"]
                ),
                self.notify(
                    f"Line numbers {'on' if self.settings['show_line_numbers'] else 'off'}"
                ),
            ),
            "syntax-highlight": lambda: (
                self.settings.set(
                    "syntax_highlight", not self.settings["syntax_highlight"]
                ),
                self._render_doc(),
                self.notify(
                    f"Syntax highlight {'on' if self.settings['syntax_highlight'] else 'off'}"
                ),
            ),
            "wrap-width": lambda: self._enter_minibuffer(
                "Wrap width (0=auto): ",
                on_commit=lambda v: (
                    self.settings.set(
                        "wrap_width", int(v) if v.strip().isdigit() else 0
                    ),
                    self._render_doc(),
                    self.notify(f"Wrap: {self.settings['wrap_width'] or 'auto'}"),
                ),
            ),
            "rate-up": lambda: self._rate_change(+20),
            "rate-down": lambda: self._rate_change(-20),
            "volume-up": lambda: self._volume_change(+0.1),
            "volume-down": lambda: self._volume_change(-0.1),
            "tts-backend": lambda: self._enter_minibuffer(
                "TTS backend (pyttsx3/espeak/festival/piper/coqui/dectalk/none): ",
                on_commit=lambda v: (
                    self.tts.change_backend(v.strip()),
                    self.notify(f"TTS: {self.tts.backend_name}"),
                ),
            ),
            # tts-voice now opens the interactive picker (same as voice-picker
            # and Ctrl+T) so the user sees names rather than opaque IDs.
            "tts-voice": self._voice_picker,
            "voice-picker": self._voice_picker,
            "font-size-up": lambda: self.notify(
                "Font size is set in your terminal emulator."
            ),
            "font-size-down": lambda: self.notify(
                "Font size is set in your terminal emulator."
            ),
            "help": lambda: self._show_help(),
            "about": lambda: self.notify(
                f"{self.VERSION_STRING}  |  {__copyright__}  |  {__license__}", dur=6.0
            ),
            "license": lambda: self._show_license(),
            "quit": lambda: setattr(self, "_running", False),
            "settings": lambda: self.notify(f"Settings: {SETTINGS_FILE}"),
            # ── Skip navigation ──────────────────────────────────────────
            "next-paragraph": self._skip_next_paragraph,
            "prev-paragraph": self._skip_prev_paragraph,
            "next-heading": self._skip_next_heading,
            "prev-heading": self._skip_prev_heading,
            "read-next-heading": self._read_next_heading,
            "read-prev-heading": self._read_prev_heading,
            "speech-cursor": self._sc_enter,
            "stop-speech": self._tts_stop,
            "next-sentence": self._skip_next_sentence,
            "prev-sentence": self._skip_prev_sentence,
            "replay-sentence": self._replay_sentence,
            "replay-paragraph": self._replay_paragraph,
            # Reading position memory
            "save-position": self._save_reading_position,
            "jump-saved": lambda: self._restore_reading_position(force=True),
            "clear-position": self._clear_reading_position,
            # Speed presets
            "speed": lambda: self._set_speed_preset(arg),
            "preset-add": lambda: self._preset_add(arg),
            "preset-list": self._preset_list,
            # Bookmarks
            "bookmark-set": lambda: self._bookmark_set(arg),
            "bookmark-goto": lambda: self._bookmark_goto(arg),
            "bookmark-list": lambda: self._bookmark_list(),
            "bookmark-delete": lambda: self._bookmark_delete(arg),
            # Chapter navigation
            "chapter-next": lambda: self._chapter_next(),
            "chapter-prev": lambda: self._chapter_prev(),
            "chapter-list": lambda: self._chapter_list(),
            "chapter-goto": lambda: self._chapter_goto(arg),
            # Navigation history
            "history-back": lambda: self._history_back(),
            "history-forward": lambda: self._history_forward(),
            # Search
            "search-regex": lambda: self._enter_minibuffer(
                "Regex: ",
                mode="search",
                on_commit=lambda q: self._do_search_regex(q),
            ),
            # Utility
            "copy": lambda: self._copy_to_clipboard(),
            "recent": lambda: self._recent_files(),
            # Reading statistics & library
            "reading-stats": lambda: self._reading_stats(),
            "stats": lambda: self._reading_stats(),
            "library": lambda: self._library_browser(),
            "bookshelf": lambda: self._library_browser(),
            "wiki": lambda: self._open_wikipedia(arg),
            "pubmed": lambda: self._open_pubmed(arg),
            # Cache
            "cache-clear": lambda: self._cache_clear(),
            # Footnotes
            "footnote-mode": lambda: self._set_footnote_mode(arg),
            # Math normalization
            "normalize-math": lambda: (
                self.settings.set(
                    "normalize_math",
                    not self.settings.get("normalize_math", True),
                ),
                self.notify(
                    "Math normalization: "
                    + ("ON" if self.settings.get("normalize_math") else "OFF")
                ),
            ),
            # Reading level
            "reading-level": lambda: self.notify(
                self._compute_reading_level_tui(), dur=8.0
            ),
            # SSML
            "ssml": lambda: self._ssml_toggle(),
            "ssml-on": lambda: (
                self.settings.set("use_ssml", True),
                self.notify("SSML prosody: ON"),
            ),
            "ssml-off": lambda: (
                self.settings.set("use_ssml", False),
                self.notify("SSML prosody: OFF"),
            ),
            # Abbreviation expansion
            "expand-abbreviations": lambda: (
                self.settings.set(
                    "expand_abbreviations",
                    not self.settings.get("expand_abbreviations", True),
                ),
                self.notify(
                    "Abbreviation expansion: "
                    + ("ON" if self.settings.get("expand_abbreviations") else "OFF")
                ),
            ),
            "abbrev-add": lambda: self._abbrev_add(arg),
            "abbrev-list": lambda: self._abbrev_list(),
            # Pronunciation lexicon
            "pron-add": lambda: self._pron_add(" ".join(args)),
            "pron-remove": lambda: self._pron_remove(arg),
            "pron-list": lambda: self._pron_list(),
            "pronunciations": lambda: (
                self.settings.set(
                    "use_pronunciations",
                    not self.settings.get("use_pronunciations", True),
                ),
                self.notify(
                    "Pronunciation lexicon: "
                    + ("ON" if self.settings.get("use_pronunciations") else "OFF")
                ),
            ),
            # Voice & profile presets
            "profile-save": lambda: self._profile_save(" ".join(args)),
            "profile-load": lambda: self._profile_load(" ".join(args)),
            "profile-list": lambda: self._profile_list(),
            "profile-delete": lambda: self._profile_delete(" ".join(args)),
            # Number normalization
            "normalize-numbers": lambda: (
                self.settings.set(
                    "normalize_numbers",
                    not self.settings.get("normalize_numbers", True),
                ),
                self.notify(
                    "Number normalization: "
                    + ("ON" if self.settings.get("normalize_numbers") else "OFF")
                ),
            ),
            # Table reading mode
            "table-mode": lambda: self._set_table_mode(arg),
            # Annotations / notes (TUI notes panel)
            "annotate": self._annotate,
            "notes": self._notes_browser,
            "annotations-list": lambda: self._annotations_list(arg),
            "annotations-search": self._annotations_search,
            "annotation-goto": lambda: self._annotation_goto(arg),
            "annotation-delete": lambda: self._annotation_delete(arg),
            "annotations-export": self._annotations_export,
            # Keyboard cheat sheet
            "shortcuts": self._show_shortcuts,
        }

        fn = cmd_map.get(cmd)
        if fn:
            try:
                fn()
            except Exception as e:
                self.notify(f"Command error: {e}", error=True)
        else:
            self.notify(f"Unknown command '{cmd}'.  Press F1 for help.", error=True)

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
        self.notify("README.md  —  q / Esc to return")
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

    # ── Annotations / notes (TUI) ──────────────────────────────────────────

    def _annot_key(self) -> str:
        """Per-document key under which annotations are stored."""
        if not self.doc:
            return ""
        return self.doc.path or self.doc.title or ""

    def _load_annotations(self) -> List[Dict[str, Any]]:
        """Saved notes for the current document, sorted by position."""
        key = self._annot_key()
        if not key:
            return []
        store = self.settings.get("annotations", {}) or {}
        items = [dict(a) for a in store.get(key, [])]
        items.sort(key=lambda a: int(a.get("word_idx", a.get("char_pos", 0)) or 0))
        return items

    def _store_annotations(self, items: List[Dict[str, Any]]) -> None:
        key = self._annot_key()
        if not key:
            return
        store = dict(self.settings.get("annotations", {}) or {})
        if items:
            store[key] = items
        else:
            store.pop(key, None)
        self.settings.set("annotations", store)

    def _annotate(self) -> None:
        """Add a note at the current reading position (key 'a' / M-x annotate)."""
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        self._enter_minibuffer("Note: ", on_commit=self._annotate_note_cb)

    def _annotate_note_cb(self, note: str) -> None:
        note = note.strip()
        if not note:
            return
        self._pending_note = note
        self._enter_minibuffer(
            "Tags (optional, comma-separated): ", on_commit=self._annotate_tags_cb
        )

    def _annotate_tags_cb(self, tag_str: str) -> None:
        note = getattr(self, "_pending_note", "")
        if not note:
            return
        self._pending_note = ""
        wm = self.doc.word_map if self.doc else []
        word_idx = self._current_word_for_nav()
        if word_idx < 0:
            word_idx = 0
        anchor = ""
        if wm and 0 <= word_idx < len(wm):
            dl = wm[word_idx].disp_line
            if 0 <= dl < len(self.rendered):
                anchor = "".join(t for t, _ in self.rendered[dl]).strip()[:120]
        items = self._load_annotations()
        items.append(
            {
                "char_pos": 0,  # Qt-only; TUI anchors by word_idx
                "word_idx": int(word_idx),
                "anchor": anchor,
                "note": note,
                "tags": _parse_tags(tag_str),
                "cite": "",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        self._store_annotations(items)
        tags = _parse_tags(tag_str)
        self.notify(
            f"Note added ({len(items)} total)"
            + (f"  tags: {', '.join(tags)}" if tags else "")
        )

    def _annotations_list(self, query: str = "") -> None:
        """Show all notes (optionally filtered) in a pager (M-x annotations-list)."""
        items = self._load_annotations()
        if not items:
            self.notify("No notes yet. Press 'a' or M-x annotate to add one.")
            return
        rows = [(i, a) for i, a in enumerate(items) if _annotation_matches(a, query)]
        if not rows:
            self.notify(f"No notes match '{query}'.")
            return
        title = self.doc.title if self.doc else "document"
        lines = [f"# Notes — {title}", ""]
        if query:
            lines.append(f"*Filter: {query} — {len(rows)}/{len(items)} shown*")
            lines.append("")
        for i, a in rows:
            first = (a.get("note", "") or "").splitlines()
            head = first[0] if first else "(empty)"
            lines.append(f"## [{i}] {head}")
            if a.get("anchor"):
                lines.append(f"> {a['anchor']}")
            meta = "  ".join(f"#{t}" for t in a.get("tags", []) or [])
            if a.get("cite"):
                meta += ("  " if meta else "") + f"@{a['cite']}"
            if meta:
                lines.append(f"`{meta}`")
            lines.append(a.get("note", ""))
            if a.get("ts"):
                lines.append(f"*{a['ts']}*")
            lines.append("")
        lines.append("---")
        lines.append(
            "M-x annotation-goto <n> · annotation-delete <n> · annotations-export"
        )
        self._show_text_pager("Notes", "\n".join(lines))

    def _annotations_search(self) -> None:
        self._enter_minibuffer(
            "Filter notes (text or #tag): ",
            on_commit=lambda q: self._annotations_list(q),
        )

    def _annotation_goto(self, arg: str) -> None:
        items = self._load_annotations()
        try:
            i = int(str(arg).strip())
        except (ValueError, TypeError):
            self.notify("Usage: annotation-goto <n>", error=True)
            return
        if not (0 <= i < len(items)):
            self.notify(f"No note #{i}", error=True)
            return
        wm = self.doc.word_map if self.doc else []
        wi = int(items[i].get("word_idx", 0) or 0)
        if wm and 0 <= wi < len(wm):
            self._scroll_to_line(wm[wi].disp_line)
            self.notify(f"Note #{i}: {items[i].get('note', '')[:50]}")
        else:
            self.notify("Note position unavailable", error=True)

    def _annotation_delete(self, arg: str) -> None:
        items = self._load_annotations()
        try:
            i = int(str(arg).strip())
        except (ValueError, TypeError):
            self.notify("Usage: annotation-delete <n>", error=True)
            return
        if not (0 <= i < len(items)):
            self.notify(f"No note #{i}", error=True)
            return
        del items[i]
        self._store_annotations(items)
        self.notify(f"Note #{i} deleted ({len(items)} left)")

    def _annotations_export(self) -> None:
        items = self._load_annotations()
        if not items:
            self.notify("No notes to export.", error=True)
            return
        p = Path(self.doc.path) if self.doc and self.doc.path else Path("notes")
        default = str(p.parent / (p.stem + "_notes.md"))
        self._enter_minibuffer(
            "Export notes to (.md/.json/.bib/.ris/.txt): ",
            initial=default,
            on_commit=self._annotations_export_cb,
        )

    def _annotations_export_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest:
            return
        items = self._load_annotations()
        meta = getattr(self.doc, "metadata", {}) or {}
        title = self.doc.title if self.doc else "notes"
        author = meta.get("author") or meta.get("creator") or ""
        try:
            content = _format_annotations(
                items,
                Path(dest).suffix.lower(),
                title,
                author,
                self.doc.path if self.doc else "",
            )
            Path(dest).write_text(content, encoding="utf-8")
            self.notify(f"Exported {len(items)} note(s) → {dest}")
        except OSError as e:
            self.notify(f"Export error: {e}", error=True)

    # ── Saved note-filter presets ───────────────────────────────────────

    def _notes_presets(self) -> Dict[str, str]:
        return dict(self.settings.get("annotation_filter_presets", {}) or {})

    def _notes_preset_save(self, name: str, query: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        presets = self._notes_presets()
        presets[name] = query
        self.settings.set("annotation_filter_presets", presets)

    # ── Inline prompt helpers (used inside the interactive notes browser) ──

    def _inline_prompt(self, prompt: str, initial: str = "") -> Optional[str]:
        """Read a line of text on the bottom row; return it, or None on Esc."""
        buf = list(initial)
        while True:
            h, w = self.scr.getmaxyx()
            _fillrow(self.scr, h - 1, self._a("minibuf"))
            shown = (prompt + "".join(buf))[: w - 1]
            _addstr(self.scr, h - 1, 0, shown, self._a("minibuf"))
            try:
                self.scr.move(h - 1, min(len(shown), w - 1))
            except curses.error:
                pass
            self.scr.refresh()
            ch = self.scr.getch()
            if ch in (10, 13, curses.KEY_ENTER):
                return "".join(buf)
            if ch in (27, 7):
                return None
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if buf:
                    buf.pop()
            elif 32 <= ch < 127:
                buf.append(chr(ch))

    def _inline_confirm(self, prompt: str) -> bool:
        """Show *prompt* on the bottom row; return True only on 'y'."""
        h, w = self.scr.getmaxyx()
        _fillrow(self.scr, h - 1, self._a("minibuf"))
        _addstr(self.scr, h - 1, 0, prompt[: w - 1], self._a("minibuf"))
        self.scr.refresh()
        return self.scr.getch() in (ord("y"), ord("Y"))

    # ── Interactive notes browser ───────────────────────────────────────

    def _notes_browser(self) -> None:
        """A dedicated, interactive notes mode for the TUI.

        Arrow keys / j,k select; Enter jumps to the note; r reads from it;
        e edits, d deletes, / filters, p cycles saved filter presets, s saves
        the current filter as a preset, x exports, q/Esc exits.
        """
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        flt = ""
        sel = 0
        preset_names = list(self._notes_presets().keys())
        preset_idx = -1
        while True:
            all_items = self._load_annotations()
            rows = [
                (i, a) for i, a in enumerate(all_items) if _annotation_matches(a, flt)
            ]
            if rows:
                sel = max(0, min(sel, len(rows) - 1))
            else:
                sel = 0
            h, w = self.scr.getmaxyx()
            view_h = max(1, h - 2)
            top = 0 if sel < view_h else sel - view_h + 1
            self.scr.erase()
            hdr = f" Notes — {(self.doc.title or '')[:38]}  ({len(rows)}/{len(all_items)})"
            if flt:
                hdr += f"  filter: {flt}"
            _fillrow(self.scr, 0, self._a("title_bar"))
            _addstr(self.scr, 0, 0, hdr[: w - 1], self._a("title_bar"))
            if rows:
                for vi in range(top, min(len(rows), top + view_h)):
                    i, a = rows[vi]
                    note = (a.get("note", "") or "").splitlines()
                    head = note[0] if note else "(empty)"
                    tags = " ".join(f"#{t}" for t in a.get("tags", []) or [])
                    cite = f" @{a['cite']}" if a.get("cite") else ""
                    line = f"[{i}] {head}{('   ' + tags) if tags else ''}{cite}"
                    attr = curses.A_REVERSE if vi == sel else self._a("normal")
                    _addstr(self.scr, 1 + vi - top, 0, line[: w - 1].ljust(w - 1), attr)
            else:
                _addstr(
                    self.scr,
                    2,
                    2,
                    "No notes match.  /=filter  a=add (after exit)  q=quit",
                    self._a("dim"),
                )
            foot = (
                " ↑↓ move  ↵ jump  r read  e edit  d delete  / filter"
                "  p preset  s save  x export  q quit "
            )
            _fillrow(self.scr, h - 1, self._a("status"))
            _addstr(self.scr, h - 1, 0, foot[: w - 1], self._a("status"))
            self.scr.refresh()

            ch = self.scr.getch()
            if ch in (ord("q"), ord("Q"), 27, 7):
                return
            elif ch in (curses.KEY_DOWN, ord("j")):
                sel = min(sel + 1, max(0, len(rows) - 1))
            elif ch in (curses.KEY_UP, ord("k")):
                sel = max(sel - 1, 0)
            elif ch == curses.KEY_NPAGE:
                sel = min(sel + view_h, max(0, len(rows) - 1))
            elif ch == curses.KEY_PPAGE:
                sel = max(sel - view_h, 0)
            elif ch == curses.KEY_HOME:
                sel = 0
            elif ch == curses.KEY_END:
                sel = max(0, len(rows) - 1)
            elif ch in (10, 13, curses.KEY_ENTER) and rows:
                self._annotation_goto(str(rows[sel][0]))
                return
            elif ch == ord("r") and rows:
                self._tts_play_from_word(int(rows[sel][1].get("word_idx", 0) or 0))
            elif ch == ord("e") and rows:
                i = rows[sel][0]
                new = self._inline_prompt(f"Edit [{i}]: ", rows[sel][1].get("note", ""))
                if new is not None and new.strip():
                    items = self._load_annotations()
                    if 0 <= i < len(items):
                        items[i]["note"] = new.strip()
                        items[i]["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        self._store_annotations(items)
            elif ch == ord("d") and rows:
                i = rows[sel][0]
                if self._inline_confirm(f"Delete note [{i}]? (y/n) "):
                    self._annotation_delete(str(i))
                    sel = max(0, sel - 1)
            elif ch == ord("/"):
                res = self._inline_prompt("Filter (text or #tag): ", flt)
                if res is not None:
                    flt = res.strip()
                    sel = 0
            elif ch == ord("p"):
                preset_names = list(self._notes_presets().keys())
                if preset_names:
                    preset_idx = (preset_idx + 1) % len(preset_names)
                    name = preset_names[preset_idx]
                    flt = self._notes_presets()[name]
                    sel = 0
                    self.notify(f"Preset: {name}  ({flt})")
                else:
                    self.notify("No saved presets. Press s to save one.")
            elif ch == ord("s"):
                name = self._inline_prompt("Save current filter as preset: ")
                if name and name.strip():
                    self._notes_preset_save(name, flt)
                    self.notify(f"Saved preset '{name.strip()}'")
            elif ch == ord("x"):
                return self._annotations_export()

    # ── Main run loop ──────────────────────────────────────────────────

    def run(self) -> None:
        while self._running:
            try:
                self._poll_load_queue()
                self._stats_poll()
                self.draw()
                ch = self.scr.getch()
                if ch == -1:
                    continue
                self._handle_key(ch)
            except KeyboardInterrupt:
                break
            except Exception:
                pass
        self.tts.stop()
        try:
            self.stats.tick(False, self.doc.path if self.doc else "")
            self.stats.flush()
        except Exception:
            pass
        self._save_reading_position()  # remember where we stopped
        self.settings.save()

    def _stats_poll(self) -> None:
        """Feed the reading-statistics tracker once per loop iteration."""
        try:
            path = self.doc.path if self.doc else ""
            speaking = self.tts.speaking
            wm = self.doc.word_map if self.doc else []
            widx = self.tts.current_word_idx if speaking else -1
            self.stats.tick(speaking, path, widx, len(wm))
        except Exception:
            pass

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

        # ── Navigation ─────────────────────────────────────────────────────
        if ch == curses.KEY_DOWN:
            self._scroll_by(1)
        elif ch == curses.KEY_UP:
            self._scroll_by(-1)
        elif ch == curses.KEY_NPAGE:
            self._page_down()
        elif ch == curses.KEY_PPAGE:
            self._page_up()
        elif ch == curses.KEY_HOME:
            self._goto_top()
        elif ch == curses.KEY_END:
            self._goto_bottom()
        # j / k kept as silent shortcuts familiar to terminal users
        elif ch == ord("j"):
            self._scroll_by(1)
        elif ch == ord("k"):
            self._scroll_by(-1)

        # ── Speech ─────────────────────────────────────────────────────────
        elif ch == ord(" "):
            self._tts_toggle()
        elif ch in (ord("+"), ord("=")):  # speed up
            self._rate_change(+20)
        elif ch == ord("-"):  # slow down
            self._rate_change(-20)

        # ── File operations ────────────────────────────────────────────────
        elif ch == 15:  # Ctrl+O — open
            self._open_file_prompt()
        elif ch == 19:  # Ctrl+S — save/export
            self._export_markdown()
        elif ch in (17, ord("q"), ord("Q")):  # Ctrl+Q or q — quit
            self._running = False

        # ── Search ─────────────────────────────────────────────────────────
        elif ch == 6:  # Ctrl+F — find
            self._enter_minibuffer(
                "Search: ",
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

        # ── Immediate speech stop (Ctrl+X or Ctrl+Space) ─────────────────
        elif ch in (0, 24):  # Ctrl+Space / Ctrl+X
            self._tts_stop()
            self.notify("Speech stopped")

        # ── Annotations / notes ─────────────────────────────────────────────
        elif ch == ord("a"):  # add a note at the reading position
            self._annotate()
        elif ch == ord("A"):  # interactive notes browser
            self._notes_browser()

        # ── Keyboard cheat sheet ────────────────────────────────────────────
        elif ch == ord("?"):
            self._show_shortcuts()

        # ── Command palette ────────────────────────────────────────────────
        elif ch == ord(":"):
            self._enter_minibuffer("Command: ")

    def _handle_mx_key(self, ch: int) -> None:
        if ch in (curses.KEY_ENTER, 10, 13):
            cmd = self.mx_ed.value.strip()
            if cmd:
                if not self.mx_history or self.mx_history[-1] != cmd:
                    self.mx_history.append(cmd)
                    if len(self.mx_history) > 200:
                        self.mx_history.pop(0)
            self.mode = "normal"
            self.mx_hist_pos = -1
            if cmd:
                cb = getattr(self, "_mx_callback", None)
                if cb:
                    cb(cmd)
            return
        if ch in (7, 27):
            self._cancel_minibuffer()
            return
        if ch == 9:
            self._mx_tab()
            return
        if ch == curses.KEY_UP:
            if self.mx_history:
                if self.mx_hist_pos < len(self.mx_history) - 1:
                    self.mx_hist_pos += 1
                self.mx_ed.set_value(self.mx_history[-(self.mx_hist_pos + 1)])
            return
        if ch == curses.KEY_DOWN:
            if self.mx_hist_pos > 0:
                self.mx_hist_pos -= 1
                self.mx_ed.set_value(self.mx_history[-(self.mx_hist_pos + 1)])
            elif self.mx_hist_pos == 0:
                self.mx_hist_pos = -1
                self.mx_ed.set_value("")
            return
        r = self.mx_ed.feed(ch)
        if r is True:
            self.mx_comp_idx = -1
            self._mx_update_completions()

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

    def _handle_goto_key(self, ch: int) -> None:
        if ch in (curses.KEY_ENTER, 10, 13):
            s = self.goto_ed.value.strip()
            self.mode = "normal"
            self._goto_line_cb(s)
            return
        if ch in (7, 27):
            self._cancel_minibuffer()
            return
        self.goto_ed.feed(ch)

    # ── Drawing ────────────────────────────────────────────────────────────

    def draw(self) -> None:
        h, w = self.scr.getmaxyx()
        if h < 8 or w < 20:
            self.scr.erase()
            _addstr(self.scr, 0, 0, "Terminal too small (need 20×8 minimum)")
            self.scr.refresh()
            return
        self.scr.erase()
        self._draw_title(h, w)
        self._draw_document(h, w)
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
                    f" {self.doc.title[:40] if self.doc else 'No document'}  "
                    f"Line {self.scroll + 1}/{total}  {pct}%"
                    f"{search_info}"
                )
                if self.doc
                else f" {APP_TITLE}"
            )
            _fillrow(self.scr, status_row, self._a("status"))
            _addstr(self.scr, status_row, 0, bar[: w - 1], self._a("status"))

        # Hints bar
        hints = (
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
            full = prompt + val + comp_str
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
            prompt = getattr(self, "_search_prompt", "Search: ")
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
            prompt = "Go to line: "
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
                idle = (
                    "  SC CURSOR  \u2191\u2193:line  ,/.:sent  [/]:para  {/}:head"
                    "  t/T:table  Enter:read-on  Space:pause  Esc:exit  Tab:normal"
                )
            else:
                idle = (
                    f"  F2:commands  Ctrl-O:open  Space:play/pause"
                    f"  Tab:speech-cursor  F1:help  Esc:stop  \u2502  {self.tts.backend_name}"
                )
            _addstr(self.scr, mb_row, 0, idle[: w - 1], self._a("dim"))


# =============================================================================
# Embedded help text
# =============================================================================

_HELP_TEXT = (
    """\
# star — Speaking Terminal Access Reader"""
    + APP_VERSION
    + """

star is a reading application with built-in text-to-speech designed for
students with print disabilities.

---

## Quick Start

Open a file:          `Ctrl+O`  or  `star document.pdf`
Start / pause:        `Space`
Stop reading:         `Esc`
Scroll up / down:     Arrow keys or Page Up / Page Down
Search:               `Ctrl+F`    then `F3` / `Shift+F3` to step through hits
Commands:             `F2`
Quit:                 `Ctrl+Q`  or  `q`

---

## Navigation

| Key | Action |
|---|---|
| `↑` / `↓` | Scroll one line |
| `Page Down` | Next page |
| `Page Up` | Previous page |
| `Home` | Beginning of document |
| `End` | End of document |

---

## Skip Navigation — Fine to Coarse

All skip keys **restart speech automatically** if reading is already in
progress — no need to press Space again after skipping.

| Key | Granularity | Action |
|---|---|---|
| `,` | Sentence | Jump to previous sentence * |
| `.` | Sentence | Jump to next sentence |
| `;` | Sentence | **Replay** current sentence from its beginning |
| `r` | Paragraph | **Replay** current paragraph from its beginning |
| `[` | Paragraph | Jump to previous paragraph |
| `]` | Paragraph | Jump to next paragraph |
| `{` (Shift+[) | Heading | Scroll to previous heading (resume if playing) |
| `}` (Shift+]) | Heading | Scroll to next heading (resume if playing) |
| `<` (Shift+,) | Heading | **Read** from previous heading (always starts TTS) |
| `>` (Shift+.) | Heading | **Read** from next heading (always starts TTS) |

---

## Speech Cursor Mode (`Tab`)

Press `Tab` to enter **Speech Cursor mode** — a dedicated navigation mode
where every movement key also starts TTS reading from the new position.
This lets you browse a document by unit (line, sentence, paragraph, heading,
table) and hear each one immediately without holding a separate play key.

| Key | Action |
|---|---|
| `↑` / `k` | Previous line — read it |
| `↓` / `j` | Next line — read it |
| `,` | Previous sentence — read it |
| `.` | Next sentence — read it |
| `[` / Page Up | Previous paragraph — read it |
| `]` / Page Down | Next paragraph — read it |
| `{` / `<` | Previous heading — read it |
| `}` / `>` | Next heading — read it |
| `t` | Next table — read it |
| `T` | Previous table — read it |
| `r` | Re-read current cursor line |
| `Space` | Pause / resume |
| `Ctrl+X` | Stop speech (cursor stays) |
| `Enter` | Exit SC mode and start continuous reading from cursor |
| `Esc` | Exit SC mode and stop speech |
| `Tab` | Exit SC mode, leave speech running |

The SC cursor is shown as a full-width reverse-video bar.  The title bar
shows `● SC CURSOR` when the mode is active.

## Instant Speech Stop

`Ctrl+X` (or `Ctrl+Space`) stops all TTS output immediately from any mode.

Note: If you are more than 3 words into the current sentence, `,` replays
the current sentence first; press it again to go to the previous one.

The status bar shows a preview of the sentence you land on (first
5 words) and its number within the document.

All commands are also available in the command palette (`F2`):
`next-sentence`, `prev-sentence`, `replay-sentence`, `replay-paragraph`,
`next-paragraph`, `prev-paragraph`, `next-heading`, `prev-heading`,
`read-next-heading`, `read-prev-heading`.

---

## Speech

| Key | Action |
|---|---|
| `Space` | Play / pause from the current position |
| `Esc` | Stop speech and clear search |
| `+` or `=` | Speed up (+20 wpm) |
| `-` | Slow down (−20 wpm) |

The word currently being spoken is highlighted in the document.

---

## File Operations

| Key | Action |
|---|---|
| `Ctrl+O` | Open a file (Tab completes the path) |
| `Ctrl+S` | Export document as a Markdown file |
| `Ctrl+Q` or `q` | Quit |
| `F9` | Reload the current document |

---

## Search

| Key | Action |
|---|---|
| `Ctrl+F` | Open search box |
| `F3` | Jump to next match |
| `F4` | Jump to previous match |
| `n` / `N` | Next / previous match (when no text box is open) |
| `Esc` | Clear search and stop speech |

---

## Chapter Navigation  (for EPUB, DAISY, and long documents)

| Key | Action |
|---|---|
| `F10` | Previous chapter |
| `F11` | Next chapter |
| `F12` | List all chapters |
| `H` | History back |
| `L` | History forward |

Also available in the command palette: `chapter-next`, `chapter-prev`, `chapter-list`, `chapter-goto`, `history-back`, `history-forward`, `bookmark-set`, `bookmark-goto`, `bookmark-list`.

---

## Command Palette  (press `F2` to open)

Type any command name and press **Enter**.  Press **Tab** to cycle through
completions.  Use `↑` / `↓` to recall previous commands.  Press **Esc** to cancel.

| Command | Description |
|---|---|
| `open` | Open a file |
| `open-url` | Open a URL |
| `export-markdown` | Export document as Markdown |
| `export-braille` | Export as BRF braille file (requires liblouis) |
| `export-audio [fmt]` | Export TTS audio as MP3/OGG/MP4/WAV (requires ffmpeg or pydub) |
| `play` | Start reading |
| `stop` | Stop reading |
| `pause` | Toggle play/pause |
| `speak-line` | Speak the current line |
| `next-paragraph` | Jump to next paragraph (restarts speech) |
| `prev-paragraph` | Jump to previous paragraph (restarts speech) |
| `next-heading` | Jump to next heading (restarts speech) |
| `prev-heading` | Jump to previous heading (restarts speech) |
| `rate-up` | Increase reading speed |
| `rate-down` | Decrease reading speed |
| `volume-up` | Increase volume |
| `volume-down` | Decrease volume |
| `tts-backend` | Switch TTS engine |
| `tts-voice` | Set TTS voice |
| `search` | Search forward |
| `search-backward` | Search backward |
| `goto-line` | Jump to line number |
| `theme [name]` | Switch color theme |
| `line-numbers` | Toggle line numbers |
| `syntax-highlight` | Toggle syntax highlighting |
| `wrap-width` | Set text wrap width |
| `reload` | Reload current document |
| `settings` | Show settings file path |
| `help` | Show this help |
| `about` | Version information |
| `license` | Show license |
| `quit` | Quit star |

---

## Themes  (`F5` to cycle, or `F2` then `theme dark`)

| Name | Description |
|---|---|
| `dark` | Modern dark — blue/cyan/magenta accents (default) |
| `light` | Light background with blue/magenta accents |
| `contrast` | High contrast — bold white on black |
| `phosphor` | Monochrome green phosphor terminal |

---

## Supported File Formats

PDF, DOCX, ODT, EPUB, HTML, DAISY/DTBook, Markdown, plain text,
CSV/TSV (rendered as tables), XLSX (rendered as tables),
LaTeX, Org-mode, Jupyter Notebook, R, R Markdown, Python, Rust, C/C++,
JavaScript, URLs (http/https).

OCR of image-based PDFs and image files (PNG, JPEG, etc.) is supported
when `pytesseract` and `pymupdf` are installed.

---

## Screen Reader & Braille

star works with NVDA, JAWS, Orca, and VoiceOver.  The terminal cursor
is always parked at the start of the minibuffer so screen readers
following the hardware cursor will track the correct position.

Braille display output via BrlTTY is automatic on Linux; on Windows,
NVDA and JAWS drive Braille displays via their built-in support.

BRF (Braille Ready Format) export: open the command palette (`F2`) and
type `export-braille`  (requires `pip install louis`)

---

Press `q` or `Esc` to close this help screen.
"""
)
