"""The curses terminal user interface (StarApp)."""
from .._runtime import *  # noqa: F401,F403
from ..i18n import set_language
from .theming import _setup_colors
from ..documents import Document
from ..render import Line
from ..search import LineEditor, SearchEngine
from ..settings import Settings
from ..stats import ReadingStats
from ..tts import TTSManager, _SCReader
from .mixin_document import DocumentMixin
from .mixin_playback import PlaybackMixin
from .mixin_navigation import NavigationMixin
from .mixin_speechcursor import SpeechCursorMixin
from .mixin_bookmarks import BookmarksMixin
from .mixin_search import SearchMixin
from .mixin_voice import VoiceMixin
from .mixin_export import ExportMixin
from .mixin_display import DisplayMixin
from .mixin_commands import CommandsMixin
from .mixin_graph import GraphMixin
from .mixin_help import HelpMixin
from .mixin_docops import DocOpsMixin
from .mixin_rsvp import RsvpMixin
from .mixin_annotations import AnnotationsMixin
from .mixin_caret import CaretMixin
from .mixin_keys import KeysMixin
from .mixin_draw import DrawMixin


class StarApp(
    DocumentMixin, PlaybackMixin, NavigationMixin, SpeechCursorMixin, BookmarksMixin, SearchMixin, VoiceMixin, ExportMixin, DisplayMixin, CommandsMixin, GraphMixin, HelpMixin, DocOpsMixin, RsvpMixin, AnnotationsMixin, CaretMixin, KeysMixin, DrawMixin,
):
    """Main curses application for star — Speaking Terminal Access Reader."""

    VERSION_STRING = f"{APP_NAME} {APP_VERSION} — {APP_TITLE}"

    def __init__(
        self, stdscr: "curses.window", settings: Settings, initial_path: str = ""
    ) -> None:
        self.scr = stdscr
        self.settings = settings
        # Activate the persisted UI language so every tr()-wrapped TUI string
        # (status line, hints, minibuffer prompts) renders localised.  The Qt
        # GUI does this in its own window; the TUI has its own entry path, so it
        # must activate the catalog here.  Unknown codes fall back to English.
        set_language(str(settings.get("ui_language", "en")))
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

        # Caret browsing (normal mode) — a freely movable word-granularity
        # caret (see mixin_caret.py).  _caret_word is a word-map index; -1 =
        # unplaced (movers place it lazily, other code falls back to the old
        # viewport heuristics).  _caret_goal_col is the sticky column for
        # vertical movement; _caret_manual_ts timestamps the last deliberate
        # move so follow-speech / auto-scroll briefly yield to the user.
        # Written from the TTS thread too (_on_highlight) — plain attribute
        # writes only, safe without a lock in CPython.
        self._caret_word: int = -1
        self._caret_goal_col: int = -1
        self._caret_manual_ts: float = 0.0

        # Word index saved when the user pauses speech (Space).  -1 means no
        # saved position.  Used by _tts_toggle to resume from the exact word
        # where reading was paused rather than restarting from the scroll top.
        self._tts_paused_at_word: int = -1

        # RSVP (Rapid Serial Visual Presentation) state — updated from
        # _on_highlight (background thread) and consumed by the draw loop
        # (main thread).  Only plain attribute writes happen here, which is
        # safe without a lock in CPython.
        self._rsvp_mode: bool = bool(settings.get("tui_rsvp_mode", False))
        self._rsvp_position: str = str(settings.get("tui_rsvp_position", "top-center"))
        self._rsvp_prev_word: str = ""
        self._rsvp_curr_word: str = ""
        self._rsvp_next_word: str = ""

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

        # If the settings file was corrupt, _load reset to defaults and saved a
        # backup — tell the user once instead of resetting invisibly.
        if getattr(settings, "load_error", ""):
            self.notify(str(settings.load_error), dur=10.0, error=True)

        if initial_path:
            self._open_async(initial_path)
        else:
            # Load the bundled welcome page as a *real document* so speech,
            # sentence navigation, and define-word all work on the very first
            # screen (GUI parity — see star/gui/main_window.py).  Falls back to
            # the static _WELCOME_TEXT splash if welcome.md is missing.
            welcome = self._welcome_path
            if welcome is not None:
                self._open_async(str(welcome))

    # ── Bundled documentation (welcome page) ──────────────────────────
    def _bundled_path(self, name: str) -> Optional[Path]:
        """Resolve a bundled doc by filename, wherever star is installed.

        Searches the package root (wheel / pyz install), then the repo root
        (running from source), then this tui/ dir (defensive)."""
        here = Path(__file__).resolve().parent           # star/tui/
        for cand in (here.parent / name, here.parent.parent / name, here / name):
            if cand.is_file():
                return cand
        return None

    @property
    def _welcome_path(self) -> Optional[Path]:
        return self._bundled_path("welcome.md")

    def _is_welcome(self, doc: Any) -> bool:
        """True if *doc* is the bundled welcome page (kept out of recents,
        the library, and reading positions)."""
        wp = self._welcome_path
        path = getattr(doc, "path", "") or ""
        if not wp or not path:
            return False
        try:
            return Path(path).resolve() == wp.resolve()
        except OSError:
            return False

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
        # One-shot engine-failure note (e.g. a cloud voice dying mid-session
        # and being swapped for a local engine on the TTS thread).
        try:
            err = str(getattr(self.tts, "last_engine_error", "") or "")
            if err:
                self.tts.last_engine_error = ""
                self.notify(err, dur=8.0, error=True)
        except Exception:
            pass
