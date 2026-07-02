"""StarWindow — the Qt main window, extracted from the _run_qt_gui closure.

WHY THIS MODULE EXISTS: star/gui/runner.py historically nested the entire
StarWindow(QMainWindow) (and the _RSVPOverlay widget) inside _run_qt_gui().
They are lifted here to module scope so the window can be split into focused
responsibility mixins without further growing runner.py.  See
docs/architecture.md.

IMPORT SAFETY: this module references Qt names at module scope, so it is only
import-safe when PyQt is installed.  Like graph_view.py / _qtcompat.py /
the mixin_*.py modules it must be imported lazily — runner.py imports it from inside
_run_qt_gui(), after the _QT guard — so `import star.gui` stays safe when PyQt
is absent (the graceful-degradation invariant).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document
from ..i18n import available_languages, get_language, set_language, tr
from ..settings import Settings
from ..stats import (
    ReadingStats,
)
from ..themes import BUILT_IN_PALETTES, _load_css_themes, _seed_default_css_themes
from ..tts import TTSManager, _SCReader
from .icons import make_icon
from ._qtcompat import (
    _LEFT_DOCK,
    _QUEUED,
    _RIGHT_DOCK,
    _WA_STYLED_BG,
)
from .mixin_aiddialogs import AidDialogsMixin
from .mixin_commands import CommandsMixin
from .mixin_toc import TocMixin
from .mixin_highlights import HighlightsMixin
from .mixin_presets import PresetsMixin
from .mixin_docops import DocOpsMixin
from .mixin_display import DisplayMixin
from .mixin_navigation import NavigationMixin
from .mixin_playback import PlaybackMixin
from .mixin_fontspacing import FontSpacingMixin
from .mixin_document import DocumentMixin
from .mixin_annotations import AnnotationsMixin
from .mixin_export import ExportMixin
from .mixin_transcription import TranscriptionMixin
from .mixin_citations import CitationsMixin
from .mixin_graph import GraphMixin


class _RSVPOverlay(QWidget):
    """Floating word-at-a-time panel for RSVP reading mode.

    Rendered as a child of the document editor widget so it stays within
    the document view and repositions automatically on resize.  Placement
    is one of nine named positions (3-column × 3-row grid) chosen by the
    user via the position dialog — important for readers with a restricted
    visual field who need the word in a specific screen quadrant.
    """

    # (fractional x, fractional y) within the parent, used as the
    # *corresponding* anchor of the overlay box itself.
    _POSITIONS: Dict[str, Tuple[float, float]] = {
        "top-left":      (0.02, 0.02),
        "top-center":    (0.50, 0.02),
        "top-right":     (0.98, 0.02),
        "center-left":   (0.02, 0.50),
        "center":        (0.50, 0.50),
        "center-right":  (0.98, 0.50),
        "bottom-left":   (0.02, 0.98),
        "bottom-center": (0.50, 0.98),
        "bottom-right":  (0.98, 0.98),
    }

    # Human-readable labels for the position picker dialog (row, col) in a
    # 3×3 grid, ordered top→bottom, left→right.
    _GRID: List[Tuple[int, int, str, str]] = [
        (0, 0, "top-left",      "Top\nLeft"),
        (0, 1, "top-center",    "Top\nCenter"),
        (0, 2, "top-right",     "Top\nRight"),
        (1, 0, "center-left",   "Mid\nLeft"),
        (1, 1, "center",        "Center"),
        (1, 2, "center-right",  "Mid\nRight"),
        (2, 0, "bottom-left",   "Bottom\nLeft"),
        (2, 1, "bottom-center", "Bottom\nCenter"),
        (2, 2, "bottom-right",  "Bottom\nRight"),
    ]

    def __init__(self, parent: QWidget, settings: "Settings") -> None:
        super().__init__(parent)
        self._pos_key: str = str(settings.get("qt_rsvp_position", "top-center"))
        self._font_size: int = int(settings.get("qt_rsvp_font_size", 48))
        self._show_context: bool = bool(settings.get("qt_rsvp_context", True))
        # Make child labels paint over our custom paintEvent background.
        self.setAttribute(_WA_STYLED_BG, True)
        self._setup_ui()
        self.setVisible(False)
        # Reposition whenever the parent (editor) is resized.
        parent.installEventFilter(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(2)

        self._prev_lbl = QLabel("")
        self._prev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter
                                    if hasattr(Qt, "AlignmentFlag")
                                    else Qt.AlignCenter)  # type: ignore[attr-defined]

        self._word_lbl = QLabel("")
        _align = (Qt.AlignmentFlag.AlignCenter
                  if hasattr(Qt, "AlignmentFlag")
                  else Qt.AlignCenter)  # type: ignore[attr-defined]
        self._word_lbl.setAlignment(_align)
        self._prev_lbl.setAlignment(_align)
        self._next_lbl = QLabel("")
        self._next_lbl.setAlignment(_align)

        layout.addWidget(self._prev_lbl)
        layout.addWidget(self._word_lbl)
        layout.addWidget(self._next_lbl)
        self._apply_label_styles()

    def _apply_label_styles(self) -> None:
        fs = self._font_size
        self._word_lbl.setStyleSheet(
            f"color: #e8e8e8; font-size: {fs}px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        ctx = (
            "color: rgba(200,200,200,120); font-size: 16px;"
            " background: transparent; border: none;"
        )
        self._prev_lbl.setStyleSheet(ctx)
        self._next_lbl.setStyleSheet(ctx)

    def paintEvent(self, event: Any) -> None:
        try:
            from PyQt6.QtGui import QPainter, QPainterPath
            from PyQt6.QtCore import QRectF
            _AA = QPainter.RenderHint.Antialiasing
        except ImportError:
            from PyQt5.QtGui import QPainter, QPainterPath  # type: ignore[no-redef]
            from PyQt5.QtCore import QRectF  # type: ignore[no-redef]
            _AA = QPainter.Antialiasing  # type: ignore[attr-defined]
        painter = QPainter(self)
        painter.setRenderHint(_AA)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10.0, 10.0)
        painter.fillPath(path, QColor(24, 27, 34, 230))
        painter.end()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        try:
            _resize_type = (
                event.Type.Resize
                if hasattr(event, "Type")
                else None
            )
            if obj is self.parent() and event.type() == (
                event.Type.Resize
                if hasattr(event.Type, "Resize")
                else 14  # QEvent::Resize = 14
            ):
                self._reposition()
        except Exception:
            pass
        return False  # do not consume the event

    def update_word(self, prev_word: str, curr_word: str, next_word: str) -> None:
        """Update the displayed words and reposition within the parent."""
        self._word_lbl.setText(curr_word)
        if self._show_context:
            self._prev_lbl.setText(prev_word)
            self._next_lbl.setText(next_word)
        else:
            self._prev_lbl.setText("")
            self._next_lbl.setText("")
        self.adjustSize()
        self._reposition()

    def set_position(self, key: str) -> None:
        if key in self._POSITIONS:
            self._pos_key = key
            self._reposition()

    def set_font_size(self, size: int) -> None:
        self._font_size = size
        self._apply_label_styles()
        self.adjustSize()
        self._reposition()

    def set_show_context(self, show: bool) -> None:
        self._show_context = show

    def _reposition(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        w, h = max(self.width(), 1), max(self.height(), 1)
        fx, fy = self._POSITIONS.get(self._pos_key, (0.50, 0.02))
        # Compute top-left corner so the box's own anchor matches (fx, fy).
        # e.g. top-left (0.02, 0.02): overlay's top-left corner at 2% of parent.
        #      center   (0.50, 0.50): overlay's center at 50% of parent.
        #      bottom-right (0.98, 0.98): overlay's bottom-right at 98%.
        x = int(pw * fx - w * fx)
        y = int(ph * fy - h * fy)
        margin = 8
        x = max(margin, min(x, pw - w - margin))
        y = max(margin, min(y, ph - h - margin))
        self.move(x, y)
        self.raise_()

# =========================================================================

class StarWindow(AidDialogsMixin, CommandsMixin, TocMixin, HighlightsMixin, PresetsMixin, DocOpsMixin, DisplayMixin, NavigationMixin, PlaybackMixin, FontSpacingMixin, DocumentMixin, AnnotationsMixin, ExportMixin, TranscriptionMixin, CitationsMixin, GraphMixin, QMainWindow):
    """Qt GUI window for star.

    Word-level highlight pipeline
    ─────────────────────────────
    1. TTSManager calls its _on_highlight callback with a word index.
    2. That callback emits _word_signal(idx) — a pyqtSignal — from
       whatever thread the TTS engine is running on.
    3. Because the signal is connected with QueuedConnection, Qt
       marshals the call to the GUI thread automatically.
    4. _apply_word_highlight() runs on the GUI thread, uses
       QTextEdit.setExtraSelections() to paint the highlight
       without touching the document's undo history or content,
       and calls ensureCursorVisible() to auto-scroll.
    """

    # Emitted from the TTS/timer thread; delivered to the GUI thread.
    # Carries (word_idx, session) — the session integer lets
    # _apply_word_highlight discard stale queued emissions that were
    # posted by a timer that has since been superseded by a new speak()
    # call.  Without the session stamp, a queued signal for word 0 from
    # the previous utterance scrolls the viewport back to the start of
    # the document immediately after the ToC navigation scroll.
    _word_signal = pyqtSignal(int, int)  # (word_idx, hl_session)
    # Emitted from the document-load thread to trigger _on_doc_loaded on
    # the GUI thread.  QMetaObject.invokeMethod with a plain Python method
    # name is unreliable on Windows (requires @pyqtSlot registration);
    # a proper pyqtSignal is the correct cross-thread mechanism.
    _doc_loaded_signal = pyqtSignal()
    # Emitted from the word-map build thread once the map is ready so
    # _qt_restore_reading_position can be called safely on the GUI thread.
    _restore_signal = pyqtSignal()
    # Emitted from the audio-export background thread when synthesis is
    # complete.  Carries the status-bar message to display (success or
    # error text) so the GUI thread can update safely.
    _export_audio_signal = pyqtSignal(str)
    # Batch conversion runs on a background thread; these carry progress
    # lines and the final summary back to the GUI thread.
    _batch_progress_signal = pyqtSignal(str)
    _batch_done_signal = pyqtSignal(str)
    # Hot-folder watcher log lines, surfaced in the status bar.
    _watch_signal = pyqtSignal(str)
    # Emitted from the Whisper background threads so results
    # land on the GUI thread.  transcribe: (text, source_path);
    # dictate: (text, char_pos_str, anchor).
    _transcribe_signal = pyqtSignal(str, str)
    _dictate_signal = pyqtSignal(str, str, str)
    _dictate_partial_signal = pyqtSignal(str)  # live streaming dictation preview
    _doi_signal = pyqtSignal(str)  # Crossref DOI lookup result (JSON or ERROR:)
    # Document summarization runs on a background thread (LexRank can be
    # slow on long documents); carries (summary, error_message).
    _summary_signal = pyqtSignal(str, str)
    # Translation runs on a background thread (it makes a network call);
    # carries (translated_text, error_message).
    _translate_signal = pyqtSignal(str, str)
    # Feed fetching runs on a background thread (network call); carries
    # (entries_list, error_message) — the list is passed as a Python object.
    _feed_signal = pyqtSignal(object, str)
    # Definition lookup runs on a background thread (the first WordNet access
    # loads the corpus); carries (DefinitionResult-or-None, word, error_message).
    _define_signal = pyqtSignal(object, str, str)

    # Per-theme CSS colors used by _md_to_html and _apply_qt_theme.
    #: GUI colour palettes — the single source lives in star/themes.py
    #: (:data:`BUILT_IN_PALETTES`), shared with the CSS-theme seeder.
    _PALETTES: Dict[str, Dict[str, str]] = BUILT_IN_PALETTES

    def __init__(self, settings: "Settings", initial_path: str = "") -> None:
        super().__init__()
        self.settings = settings
        # Activate the saved UI-chrome language before any widgets (and their
        # tr()-wrapped labels) are built.  Unknown codes fall back to English.
        set_language(str(settings.get("ui_language", "en")))
        self.doc: Optional[Document] = None
        self.tts_manager = TTSManager(settings)
        # Active hot-folder watcher (File ▸ Watch Folder), or None.
        self._watcher = None
        # Reading statistics & progress tracker, driven by a 1-second
        # QTimer poll set up after _setup_ui.
        self.stats = ReadingStats(settings)

        # Word index saved when the user pauses speech (Space).  -1 means no
        # saved position; used by _tts_toggle to resume from the exact word.
        self._tts_paused_at_word: int = -1

        # Maps TTS word index → absolute character offset in the Qt document.
        # Built asynchronously after each document load.
        self._qt_word_map: List[int] = []

        # QTextCharFormat applied to the currently spoken word.
        # Built from the user's highlight style/color settings so the
        # karaoke highlight can be tuned (see _rebuild_hl_fmt).
        self._hl_fmt = QTextCharFormat()
        self._rebuild_hl_fmt()

        # Cached extra-selections for the difficult-word overlay (View ▸
        # Reading Aids ▸ Highlight Difficult Words).  Computed once per
        # document when the overlay is on, then merged into the selection
        # list alongside user highlights so a TTS repaint never wipes them.
        self._vocab_selections: List[Any] = []

        # RSVP (Rapid Serial Visual Presentation) floating overlay.
        # Created lazily on first toggle; None until then.
        self._rsvp_overlay: Optional[Any] = None

        # Session counter — incremented by every new speak() invocation.
        # The timer thread closes over the session value at speak() time;
        # _apply_word_highlight drops any delivery whose session no longer
        # matches, preventing stale queued signals from scrolling the view.
        self._hl_session: int = 0

        # CSS theme registry — must be populated before _setup_ui() because
        # _setup_ui calls _apply_qt_theme → _effective_palette → _css_themes.
        # Seed default files first (no-op if they already exist), then load.
        _seed_default_css_themes()
        self._css_themes: Dict[str, Dict[str, Any]] = _load_css_themes()

        self._setup_ui()

        # Wire the TTS highlight callback → signal (thread-safe delivery).
        self._word_signal.connect(self._apply_word_highlight, _QUEUED)
        # Seed the initial callback (session 0).  _new_hl_session() replaces
        # this at the start of every new speak() call.
        self._refresh_hl_callback()

        # Wire the doc-loaded callback → signal (thread-safe delivery).
        self._doc_loaded_signal.connect(self._on_doc_loaded, _QUEUED)
        # Wire the restore-position callback → main thread.
        self._restore_signal.connect(self._qt_restore_reading_position, _QUEUED)
        # Wire the audio-export completion signal → status bar update.
        self._export_audio_signal.connect(
            lambda msg: self.statusBar().showMessage(msg), _QUEUED
        )
        # Batch-conversion progress / completion (background thread).
        self._batch_progress_signal.connect(
            lambda msg: self.statusBar().showMessage(msg), _QUEUED
        )
        self._batch_done_signal.connect(self._on_batch_done, _QUEUED)
        self._watch_signal.connect(
            lambda msg: self.statusBar().showMessage(msg), _QUEUED
        )
        # Wire the Whisper transcription / dictation result signals.
        self._transcribe_signal.connect(self._qt_on_transcribed, _QUEUED)
        self._dictate_signal.connect(self._qt_on_dictated, _QUEUED)
        self._dictate_partial_signal.connect(self._qt_on_dictate_partial, _QUEUED)
        self._doi_signal.connect(self._qt_on_doi, _QUEUED)
        # Wire the summarization result signal → GUI thread.
        self._summary_signal.connect(self._qt_on_summary, _QUEUED)
        # Wire the translation / feed-fetch result signals → GUI thread.
        self._translate_signal.connect(self._qt_on_translation, _QUEUED)
        self._feed_signal.connect(self._qt_on_feed, _QUEUED)
        self._define_signal.connect(self._qt_on_definition, _QUEUED)

        # Reading-statistics poll: a 1-second timer feeds self.stats while
        # speech is playing.
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._stats_poll)
        self._stats_timer.start(1000)

        # Debounce timer for the live HTML edit preview (re-renders ~300 ms
        # after the last keystroke so typing stays responsive).
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._qt_render_preview)

        # Speech Cursor (SC) mode state for the Qt GUI.
        # Mirrors the TUI sc mode: Tab enters it, arrows navigate
        # line-by-line with TTS, Esc / Enter exits.
        self._qt_sc_mode: bool = False
        self._qt_sc_block: int = 0  # current QTextBlock index
        # Persistent SAPI5 engine for SC line reading — same role as
        # _SCReader in the TUI.  None when not in SC mode.
        self._qt_sc_reader: Optional[_SCReader] = None

        # Sentence map: list of word-map indices at which each sentence
        # begins.  Built asynchronously alongside the word map.
        self._qt_sentence_starts: List[int] = [0]

        # JAWS-style bare-Ctrl tap → play/pause detection state.
        # _ctrl_solo is True while a Ctrl press has not yet been "used" as
        # a modifier; any other key / shortcut clears it so only a clean
        # tap toggles speech.  _ctrl_press_t bounds the tap to a short hold.
        self._ctrl_solo: bool = False
        self._ctrl_press_t: float = 0.0
        self._key_enum_cache: Optional[Tuple[Any, ...]] = None

        # Edit mode state.  False = read-only (normal), True = editable.
        self._qt_edit_mode: bool = False
        self._qt_edit_dirty: bool = False  # unsaved changes in edit mode
        # Spell-check syntax highlighter, attached only while editing and
        # only when pyspellchecker (and a Qt QSyntaxHighlighter) is present.
        self._spell_highlighter = None

        # Intercept keyboard events on the editor so Tab and arrow keys
        # can be processed for SC mode without fighting Qt's focus chain.
        self.editor.installEventFilter(self)

        if initial_path:
            self._open_path(initial_path)
        else:
            # Load the bundled welcome page as a *real document* so speech,
            # navigation, highlighting, and define-word all work on the very
            # first screen.  Falls back to the static splash if it is missing.
            welcome = self._welcome_path
            if welcome is not None:
                self._open_path(str(welcome))

    # ── Bundled documentation (README, welcome) ───────────────────────
    def _bundled_path(self, name: str) -> "Optional[Path]":
        """Resolve a bundled doc by filename, wherever star is installed.

        Searches the package root (wheel / pyz install), then the repo root
        (running from source), then this gui/ dir (legacy)."""
        here = Path(__file__).resolve().parent           # star/gui/
        for cand in (here.parent / name, here.parent.parent / name, here / name):
            if cand.is_file():
                return cand
        return None

    @property
    def _welcome_path(self) -> "Optional[Path]":
        return self._bundled_path("welcome.md")

    def _is_welcome(self, doc: Any) -> bool:
        """True if *doc* is the bundled welcome page (kept out of the library)."""
        wp = self._welcome_path
        path = getattr(doc, "path", "") or ""
        if not wp or not path:
            return False
        try:
            return Path(path).resolve() == wp.resolve()
        except OSError:
            return False

    # ── UI construction ───────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setWindowTitle(APP_TITLE)
        self.resize(
            int(self.settings["gui_width"]), int(self.settings["gui_height"])
        )

        # Document view
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        # Build the base font from family/size + letter/word spacing and
        # the optional dyslexia-friendly family override.
        self.editor.setFont(self._make_editor_font())
        # Caret browsing: a visible, keyboard-navigable text caret in the
        # read-only view when enabled (accessibility — keyboard navigation,
        # selection for highlights, define-word at caret).  Sets both the caret
        # width and the TextSelectableByKeyboard interaction flag.
        self.editor.setReadOnly(True)
        self._apply_caret_mode()
        # Live HTML preview pane shown beside the editor in edit mode
        # (hidden until toggled).  Wrapped with the editor in a splitter so
        # the user can drag the divider.
        self._preview = QTextBrowser()
        self._preview.setObjectName("preview")
        self._preview.setVisible(False)
        try:
            _horiz = Qt.Orientation.Horizontal  # PyQt6
        except AttributeError:
            _horiz = Qt.Horizontal  # type: ignore[attr-defined]  # PyQt5
        self._edit_split = QSplitter(_horiz)
        self._edit_split.addWidget(self.editor)
        self._edit_split.addWidget(self._preview)
        self._edit_split.setStretchFactor(0, 1)
        self._edit_split.setStretchFactor(1, 1)
        self.setCentralWidget(self._edit_split)
        # Apply the current theme's colors to the editor widget.
        self._apply_qt_theme(self.settings.get("theme", "dark"))

        # AT-SPI2 accessibility metadata
        self.editor.setAccessibleName("Document View")
        self.editor.setAccessibleDescription(
            "Main reading area. Space=play/pause, Ctrl+F=search, Escape=stop."
        )

        # Registry of (label, QAction, default_shortcut) for every action
        # that carries a shortcut, so they can be remapped at runtime
        # Populated by _act and _nav below.
        self._shortcut_actions = []

        # Toolbar
        self._build_toolbar()

        # ── Menu bar ─────────────────────────────────────────────────────
        self._build_menu_bar()

        # ── Table of Contents dock ─────────────────
        self._toc_dock = QDockWidget(tr("Contents"), self)
        self._toc_dock.setObjectName("toc_dock")
        self._toc_dock.setAllowedAreas(
            _LEFT_DOCK | _RIGHT_DOCK  # type: ignore[operator]
        )
        self._toc_list = QListWidget()
        self._toc_list.setMinimumWidth(180)
        # Single-click / Enter: scroll to heading and stop speech so the
        # viewport and audio stay synchronized.
        self._toc_list.itemActivated.connect(self._qt_toc_navigate)
        # Double-click: stop current speech and start reading from the
        # activated heading.
        self._toc_list.itemDoubleClicked.connect(self._qt_toc_play)
        self._toc_dock.setWidget(self._toc_list)
        self.addDockWidget(_LEFT_DOCK, self._toc_dock)
        show_toc = bool(self.settings.get("qt_show_toc", True))
        self._toc_dock.setVisible(show_toc)

        # ── Annotations / Notes dock ─────────────────────────────────────
        # Mirrors the Contents dock: a list of notes anchored at character
        # positions in the document.  Single-click scrolls to the note;
        # double-click reads from there.  Notes persist per-document in
        # settings and can be exported (Markdown / JSON / BibTeX / RIS).
        self._annot_dock = QDockWidget(tr("Notes"), self)
        self._annot_dock.setObjectName("annotations_dock")
        self._annot_dock.setAllowedAreas(
            _LEFT_DOCK | _RIGHT_DOCK  # type: ignore[operator]
        )
        _annot_panel = QWidget()
        _annot_layout = QVBoxLayout(_annot_panel)
        _annot_layout.setContentsMargins(4, 4, 4, 4)
        _annot_layout.setSpacing(4)
        # Full-text search / tag filter box (type `#tag` to filter by tag).
        self._annot_filter = QLineEdit()
        self._annot_filter.setPlaceholderText(tr("Filter notes — text or #tag…"))
        self._annot_filter.setClearButtonEnabled(True)
        self._annot_filter.textChanged.connect(
            lambda _t: self._qt_build_annotations()
        )
        _annot_layout.addWidget(self._annot_filter)
        self._annot_list = QListWidget()
        self._annot_list.setMinimumWidth(200)
        self._annot_list.setWordWrap(True)
        self._annot_list.itemActivated.connect(self._qt_annotation_navigate)
        self._annot_list.itemDoubleClicked.connect(self._qt_annotation_play)
        _annot_layout.addWidget(self._annot_list)
        _btn_row = QHBoxLayout()
        for _lbl, _fn in (
            ("Add", self._qt_add_annotation),
            ("Edit", self._qt_edit_annotation),
            ("Delete", self._qt_delete_annotation),
            ("Export…", self._qt_export_annotations),
        ):
            _b = QPushButton(tr(_lbl))
            _b.clicked.connect(lambda _chk=False, fn=_fn: fn())
            _btn_row.addWidget(_b)
        _annot_layout.addLayout(_btn_row)
        self._annot_dock.setWidget(_annot_panel)
        self.addDockWidget(_RIGHT_DOCK, self._annot_dock)
        self._annot_dock.setVisible(bool(self.settings.get("qt_show_notes", False)))

        # All keyboard shortcuts are owned by their menu QActions above
        # (see _mi / _menu).  Menu actions added to the menu bar use
        # Qt's WindowShortcut context, so they fire regardless of which
        # widget has focus — exactly like the old window-level bindings,
        # but without the duplicate QActions that caused Qt to treat a
        # shortcut as "ambiguous" and fire neither.  The screen-reader
        # scheme (Ctrl+letter forward, Ctrl+Shift+letter backward,
        # Alt+punctuation for sentences) is unchanged.

        # Show the welcome screen immediately so the window is never
        # blank at launch.  _on_doc_loaded replaces it when a file loads.
        self.editor.setHtml(self._welcome_html())
        self._apply_block_spacing()
        self.statusBar().showMessage(APP_TITLE)


    def _build_toolbar(self) -> None:
        """Build (or rebuild) the controls toolbar.

        Safe to call again after a UI-language change: the previous toolbar
        is removed first so labels are recreated through tr() in the active
        language without stacking a second toolbar."""
        existing = getattr(self, "_toolbar", None)
        if existing is not None:
            # removeToolBar only detaches it from the toolbar area; the widget
            # stays a child of the window.  Delete it too so repeated language
            # switches don't accumulate hidden toolbars.
            self.removeToolBar(existing)
            existing.setParent(None)
            existing.deleteLater()
        tb = self.addToolBar("Controls")
        self._toolbar = tb
        tb.setMovable(False)
        # Icon-only toolbar: every button is a hand-drawn vector glyph (star/gui/
        # icons.py) with a descriptive tooltip — visually uniform, no text/glyph
        # mix.  The QAction *label* is kept as the accessible name so screen
        # readers still announce each control.
        try:
            tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        except AttributeError:  # PyQt5
            tb.setToolButtonStyle(Qt.ToolButtonIconOnly)  # type: ignore[attr-defined]

        def _act(label: str, icon: str, fn: Callable, tip: str = "") -> None:
            """Add one icon button to the toolbar.

            Toolbar buttons intentionally carry **no** keyboard shortcut:
            every command's shortcut lives on its menu action instead, so each
            shortcut is owned by exactly one QAction.  *icon* names a glyph in
            icons.make_icon; *label* is the accessible name; *tip* (with the
            menu's binding) is the hover tooltip.
            """
            a = QAction(make_icon(icon), tr(label), self)
            a.setToolTip(tr(tip) if tip else tr(label))
            a.triggered.connect(fn)
            tb.addAction(a)

        # ── File ─────────────────────────────────────────────
        _act("Open", "open", self._open_dialog, "Open a file (Ctrl+O)")
        _act("Open URL", "url", self._qt_open_url, "Open a URL")
        tb.addSeparator()
        # ── Playback ──────────────────────────────────────
        _act("Play / Pause", "play_pause", self._tts_toggle, "Play / pause speech (Space)")
        _act("Stop", "stop", self._tts_stop, "Stop speech (Escape)")
        _act("Slower", "slower", lambda: self._rate_change(-20), "Slow down −20 wpm (Ctrl+−)")
        _act("Faster", "faster", lambda: self._rate_change(+20), "Speed up +20 wpm (Ctrl+=)")
        tb.addSeparator()
        # ── Navigate ──────────────────────────────────────
        _act("Previous Sentence", "prev_sentence", self._qt_skip_prev_sentence, "Previous sentence (,)")
        _act("Replay Sentence", "replay_sentence", self._qt_replay_sentence, "Replay sentence (;)")
        _act("Next Sentence", "next_sentence", self._qt_skip_next_sentence, "Next sentence (.)")
        _act("Previous Paragraph", "prev_paragraph", self._qt_skip_prev_paragraph, "Previous paragraph ([)")
        _act("Replay Paragraph", "replay_paragraph", self._qt_replay_paragraph, "Replay paragraph (r)")
        _act("Next Paragraph", "next_paragraph", self._qt_skip_next_paragraph, "Next paragraph (])")
        _act("Previous Heading", "prev_heading", self._qt_read_prev_heading, "Previous heading — read aloud (<)")
        _act("Next Heading", "next_heading", self._qt_read_next_heading, "Next heading — read aloud (>)")
        tb.addSeparator()
        # ── Voice / cursor mode ───────────────────────────
        _act("Voice", "voice", self._voice_picker_qt, "Select TTS voice (Ctrl+Shift+V)")
        _act(
            "Speech Cursor",
            "speech_cursor",
            lambda: self._qt_sc_exit() if self._qt_sc_mode else self._qt_sc_enter(),
            "Speech cursor mode — line-by-line reading (Tab)",
        )
        tb.addSeparator()
        # ── Text ───────────────────────────────────────────
        _act("Copy", "copy", self._qt_copy, "Copy selection or paragraph (Ctrl+C)")
        _act("Highlight", "highlight", self._qt_highlight, "Highlight selection in yellow")
        _act(
            "Clear Highlights",
            "clear_highlight",
            self._qt_highlight_clear,
            "Remove all highlights from this document",
        )
        tb.addSeparator()
        # ── Edit ─────────────────────────────────────────
        _act("Edit Mode", "edit", self._qt_edit_mode_toggle, "Toggle edit mode (Ctrl+E)")
        _act("Save", "save", self._qt_save, "Save document (Ctrl+S)")
        tb.addSeparator()
        # ── View ─────────────────────────────────────────
        _act("Theme", "theme", self._next_theme, "Cycle color theme (F5)")
        _act("Contents", "contents", self._qt_toggle_toc, "Toggle Contents panel (Ctrl+\\)")
        _act(
            "Notes",
            "notes",
            self._qt_toggle_annotations,
            "Toggle Notes panel (Ctrl+Shift+N)",
        )
        _act(
            "Add Note",
            "add_note",
            self._qt_add_annotation,
            "Add a note at the cursor (Ctrl+Shift+A)",
        )
        _act("Reading Level", "level", self._qt_reading_level, "Show reading level (Ctrl+L)")
        _act("Font", "font", self._qt_change_font_dialog, "Change display font")
        tb.addSeparator()
        # ── App ──────────────────────────────────────────
        _act("Help", "help", self._show_about, "Open README.md (F1)")
        _act("Quit", "quit", self.close, "Quit star (Ctrl+Q)")

    def _build_menu_bar(self) -> None:
        """Build (or rebuild) the menu bar.

        Called once at startup and again whenever the UI language changes.
        It clears the existing menus and the shortcut registry first, so a
        rebuild neither duplicates menus nor double-registers shortcuts;
        every label flows through tr() in the active language."""
        mb = self.menuBar()
        mb.clear()
        self._shortcut_actions = []

        # Every menu item gets a keyboard shortcut.  _mi() creates a menu
        # QAction, assigns its (remappable) shortcut, registers it for the
        # Customize Shortcuts dialog, and returns it.  Because the toolbar
        # buttons carry no shortcut, each binding is owned by exactly one
        # QAction — no Qt "ambiguous shortcut" conflicts.
        def _mi(
            label: str,
            shortcut: str,
            fn: Callable,
            tip: str = "",
            checkable: bool = False,
            checked: bool = False,
        ) -> "QAction":
            # Display the translated label, but key the shortcut registry on
            # the English *label* so keybinding overrides stay stable across
            # languages (the Customize Shortcuts dialog matches on it).
            a = QAction(tr(label), self)
            if checkable:
                a.setCheckable(True)
                a.setChecked(checked)
            if tip:
                a.setToolTip(tr(tip))
            a.triggered.connect(lambda _checked=False, f=fn: f())
            if shortcut:
                a.setShortcut(self._resolve_shortcut(shortcut))
                self._shortcut_actions.append((label, a, shortcut))
            return a

        # File menu
        file_menu: QMenu = mb.addMenu(tr("File"))
        file_menu.addAction(_mi("Open…", "Ctrl+O", self._open_dialog))
        file_menu.addAction(
            _mi(
                "Open Feed…",
                "Ctrl+Shift+M",
                self._qt_open_feed,
                tip="Open an RSS / Atom feed and pick an article to read",
            )
        )
        file_menu.addAction(_mi("Open URL…", "Ctrl+Shift+O", self._qt_open_url))
        file_menu.addAction(
            _mi(
                "Open Folder as Library…",
                "Ctrl+Shift+L",
                self._qt_pick_library_folder,
                tip="Scan any folder (e.g. a synced Dropbox/OneDrive folder) as a document library",
            )
        )
        file_menu.addAction(
            _mi(
                "Library / Bookshelf…",
                "Ctrl+Shift+B",
                self._qt_library,
                tip="Browse library-folder documents and recently-opened files, with progress",
            )
        )
        file_menu.addAction(
            _mi(
                "Edit Document Metadata…",
                "",
                self._qt_metadata_editor,
                tip="View and edit title, author, DOI, ISBN for the current document",
            )
        )
        file_menu.addAction(
            _mi(
                "Import Obsidian Vault…",
                "",
                self._obsidian_import,
                tip="Import a folder of Markdown notes and their links",
            )
        )
        file_menu.addAction(
            _mi(
                "Open Archive…",
                "",
                self._qt_open_archive,
                tip="Open a ZIP / TAR / 7z / RAR archive and browse its documents",
            )
        )
        file_menu.addSeparator()

        export_menu: QMenu = file_menu.addMenu(tr("Export"))
        export_menu.addAction(
            _mi("Export as Markdown…", "Ctrl+Alt+M", self._qt_export_markdown)
        )
        export_menu.addAction(
            _mi("Export as PDF…", "Ctrl+Alt+P", self._qt_export_pdf)
        )
        export_menu.addAction(
            _mi("Export as Braille (BRF)…", "Ctrl+Alt+B", self._qt_export_brf)
        )
        export_menu.addAction(
            _mi(
                "Export as Audio (MP3 / OGG / MP4)…",
                "Ctrl+Alt+A",
                self._qt_export_audio,
            )
        )
        export_menu.addAction(
            _mi(
                "Export Subtitles (SRT / VTT)…",
                "Ctrl+Alt+U",
                self._qt_export_subtitles,
                tip="Write a timestamped caption track synchronized to speech",
            )
        )
        export_menu.addAction(
            _mi(
                "Anki Flashcards…",
                "Ctrl+Alt+H",
                self._qt_export_anki,
                tip="Export this document's notes as an Anki deck (.apkg)",
            )
        )
        export_menu.addAction(
            _mi(
                "Obsidian Vault…",
                "",
                self._obsidian_export,
                tip="Export the knowledge graph as a folder of linked Markdown notes",
            )
        )
        export_menu.addSeparator()
        export_menu.addAction(
            _mi(
                "Video (MP4)…",
                "Ctrl+Alt+V",
                self._qt_export_video,
                tip="Export as a karaoke MP4 — themed document with highlighted sentence and spoken audio",
            )
        )
        # Registry-driven exporters: the remaining built-ins (HTML, EPUB) and any
        # installed third-party ``star.exporters`` plugin appear here automatically.
        _plugin_exps = self._plugin_exporters()
        if _plugin_exps:
            export_menu.addSeparator()
            for _exp_cls in _plugin_exps:
                _exts = " ".join(sorted(_exp_cls.extensions()))
                export_menu.addAction(
                    _mi(
                        f"Export as {_exp_cls.name.upper()} ({_exts})…",
                        "",
                        (lambda c=_exp_cls: self._qt_export_via_plugin(c)),
                        tip=f"Export via the '{_exp_cls.name}' exporter plugin",
                    )
                )

        file_menu.addSeparator()
        file_menu.addAction(
            _mi(
                "Batch Convert…",
                "Ctrl+Shift+C",
                self._qt_batch_convert,
                tip="Convert many files / a folder to one format",
            )
        )
        # Toggle action: text flips to "Stop Watching Folder" while active.
        self._watch_action = _mi(
            "Watch Folder…",
            "Ctrl+Shift+W",
            self._qt_watch_folder,
            tip="Auto-convert files dropped into a folder (toggle)",
        )
        file_menu.addAction(self._watch_action)

        file_menu.addSeparator()
        file_menu.addAction(_mi("Quit", "Ctrl+Q", self.close))

        # Highlight menu (Ctrl+Shift+digit picks a color)
        hl_menu: QMenu = mb.addMenu(tr("Highlight"))
        _HL_COLORS = [
            ("Yellow", "#ffff00", "Ctrl+Shift+1"),
            ("Green", "#90ee90", "Ctrl+Shift+2"),
            ("Cyan", "#add8e6", "Ctrl+Shift+3"),
            ("Pink", "#ffb6c1", "Ctrl+Shift+4"),
            ("Orange", "#ffa500", "Ctrl+Shift+5"),
        ]
        for _name, _color, _sc in _HL_COLORS:
            hl_menu.addAction(
                _mi(
                    f"Highlight {_name}",
                    _sc,
                    lambda c=_color: self._qt_highlight(c),
                )
            )
        hl_menu.addSeparator()
        hl_menu.addAction(
            _mi(
                "Clear All Highlights",
                "Ctrl+Shift+0",
                self._qt_highlight_clear,
            )
        )

        # Notes / annotations menu
        notes_menu: QMenu = mb.addMenu(tr("Notes"))
        notes_menu.addAction(
            _mi("Add Note at Cursor…", "Ctrl+Shift+A", self._qt_add_annotation)
        )
        notes_menu.addAction(
            _mi("Edit Selected Note…", "Ctrl+Shift+E", self._qt_edit_annotation)
        )
        notes_menu.addAction(
            _mi(
                "Delete Selected Note",
                "Ctrl+Shift+D",
                self._qt_delete_annotation,
            )
        )
        notes_menu.addSeparator()
        # Shared with the View menu so both show the same Ctrl+Shift+N binding.
        toggle_notes_act = _mi(
            "Toggle Notes Panel", "Ctrl+Shift+N", self._qt_toggle_annotations
        )
        notes_menu.addAction(toggle_notes_act)
        notes_menu.addAction(
            _mi("Export Notes…", "Ctrl+Alt+N", self._qt_export_annotations)
        )

        # Helper: build a menu from (label, callable, shortcut) rows
        # (None = separator).  Every command row carries a shortcut.
        def _menu(title: str, rows: List[Any]) -> "QMenu":
            menu = mb.addMenu(tr(title))
            for row in rows:
                if row is None:
                    menu.addSeparator()
                    continue
                label, fn = row[0], row[1]
                shortcut = row[2] if len(row) > 2 else ""
                menu.addAction(_mi(label, shortcut, fn))
            return menu

        # Speech menu — every playback command reachable without the keyboard.
        _menu(
            "Speech",
            [
                ("Play / Pause", self._tts_toggle, "Space"),
                ("Stop", self._tts_stop, "Escape"),
                ("Play from Cursor", self._qt_play_from_cursor, "Ctrl+Return"),
                None,
                ("Faster (+20 wpm)", lambda: self._rate_change(+20), "Ctrl+="),
                ("Slower (−20 wpm)", lambda: self._rate_change(-20), "Ctrl+-"),
                None,
                ("Choose TTS Engine…", self._qt_pick_backend, "Ctrl+Shift+G"),
                ("Choose Voice…", self._voice_picker_qt, "Ctrl+Shift+V"),
                (
                    "Speech Cursor Mode",
                    lambda: (
                        self._qt_sc_exit()
                        if self._qt_sc_mode
                        else self._qt_sc_enter()
                    ),
                    "Tab",
                ),
                None,
                (
                    "Toggle SSML Prosody",
                    lambda: (
                        self.settings.set(
                            "use_ssml", not self.settings.get("use_ssml", False)
                        ),
                        self.statusBar().showMessage(
                            "SSML prosody: "
                            + ("ON" if self.settings.get("use_ssml") else "OFF")
                        ),
                    ),
                    "Ctrl+Alt+Y",
                ),
                (
                    "Pronunciation Lexicon…",
                    self._qt_pronunciations,
                    "Ctrl+Shift+I",
                ),
            ],
        )

        # Navigate menu.  Headings read aloud on arrival (toolbar parity).
        _menu(
            "Navigate",
            [
                ("Next Sentence", self._qt_skip_next_sentence, "Alt+."),
                ("Previous Sentence", self._qt_skip_prev_sentence, "Alt+,"),
                ("Replay Sentence", self._qt_replay_sentence, "Alt+;"),
                None,
                ("Next Paragraph", self._qt_skip_next_paragraph, "Ctrl+P"),
                (
                    "Previous Paragraph",
                    self._qt_skip_prev_paragraph,
                    "Ctrl+Shift+P",
                ),
                ("Replay Paragraph", self._qt_replay_paragraph, "Ctrl+R"),
                None,
                ("Next Heading", self._qt_read_next_heading, "Ctrl+H"),
                ("Previous Heading", self._qt_read_prev_heading, "Ctrl+Shift+H"),
                None,
                ("Next Table", self._qt_skip_next_table, "Ctrl+T"),
                ("Previous Table", self._qt_skip_prev_table, "Ctrl+Shift+T"),
            ],
        )

        # Edit menu.  (Moved next to File in the menu bar below.)
        edit_menu = _menu(
            "Edit",
            [
                ("Copy", self._qt_copy, "Ctrl+C"),
                None,
                ("Toggle Edit Mode", self._qt_edit_mode_toggle, "Ctrl+E"),
                ("Save", self._qt_save, "Ctrl+S"),
                ("Check Spelling", self._qt_check_spelling, "F7"),
            ],
        )

        # Citations menu.
        _menu(
            "Citations",
            [
                ("Import…", self._qt_import_citations, "Ctrl+Alt+I"),
                ("Export…", self._qt_export_citations, "Ctrl+Alt+E"),
                None,
                ("Add Citation…", self._qt_add_citation, "Ctrl+Alt+C"),
                ("Add by DOI…", self._qt_add_citation_by_doi, "Ctrl+Alt+D"),
                (
                    "Insert Citation at Cursor…",
                    self._qt_insert_citation,
                    "Ctrl+Alt+R",
                ),
                ("Manage / Browse…", self._qt_manage_citations, "Ctrl+Alt+G"),
            ],
        )

        # Graph menu — knowledge graph of cross-annotation relations.
        # Ctrl+Shift+G/R from the spec are already taken (Choose TTS Engine /
        # Reload CSS Themes), so Show Graph View uses the one free Ctrl+Shift
        # letter; the rest are reachable via the menu and command palette.
        graph_menu: QMenu = mb.addMenu(tr("&Graph"))
        graph_menu.addAction(
            _mi(
                "Show Graph View",
                "Ctrl+Shift+Q",
                self._graph_toggle,
                tip="Toggle the knowledge-graph dock",
            )
        )
        graph_menu.addAction(_mi("Rebuild Graph", "", self._graph_rebuild))
        graph_menu.addSeparator()
        graph_menu.addAction(
            _mi(
                "Add Relation…",
                "",
                self._graph_add_relation,
                tip="Link the selected note to another annotation",
            )
        )
        graph_menu.addAction(_mi("Edit Relations…", "", self._graph_edit_relations))
        graph_menu.addSeparator()
        graph_menu.addAction(
            _mi("Extract Concepts…", "", self._graph_extract_concepts)
        )
        graph_menu.addAction(
            _mi("Auto-Suggest Relations…", "", self._graph_auto_suggest)
        )
        graph_menu.addSeparator()
        graph_export_menu: QMenu = graph_menu.addMenu(tr("Export Graph"))
        graph_export_menu.addAction(
            _mi("Export as SVG…", "", self._graph_export_svg)
        )
        graph_export_menu.addAction(
            _mi("Export as PlantUML…", "", self._graph_export_plantuml)
        )
        graph_export_menu.addAction(
            _mi("Export as DOT (GraphViz)…", "", self._graph_export_dot)
        )
        graph_export_menu.addAction(
            _mi("Export as JSON…", "", self._graph_export_json)
        )
        graph_menu.addSeparator()
        graph_formats_menu: QMenu = graph_menu.addMenu(tr("View Formats"))
        graph_formats_menu.addAction(
            _mi("Open SVG File…", "", self._graph_open_svg)
        )
        graph_formats_menu.addAction(
            _mi("Open PlantUML File…", "", self._graph_open_plantuml)
        )
        graph_formats_menu.addAction(
            _mi("Open DOT File…", "", self._graph_open_dot)
        )

        # View menu
        view_menu: QMenu = mb.addMenu(tr("View"))
        view_menu.addAction(
            _mi("Toggle Contents Panel", "Ctrl+\\", self._qt_toggle_toc)
        )
        # Shared QAction from the Notes menu (same Ctrl+Shift+N binding).
        view_menu.addAction(toggle_notes_act)
        view_menu.addSeparator()
        view_menu.addAction(_mi("Next Theme", "F5", self._next_theme))
        view_menu.addAction(_mi("Choose Theme…", "Ctrl+Alt+T", self._qt_pick_theme))
        view_menu.addAction(
            _mi(
                "Reload CSS Themes",
                "Ctrl+Shift+R",
                self._qt_reload_css_themes,
                tip=f"Rescan {THEMES_DIR} for *.css files without restarting",
            )
        )
        view_menu.addAction(
            _mi("Open Themes Folder", "Ctrl+Shift+F", self._qt_open_themes_folder)
        )
        view_menu.addSeparator()
        view_menu.addAction(
            _mi(
                "Caret Browsing",
                "F7",
                self._qt_toggle_caret_browsing,
                tip="Show a movable text caret — keyboard navigation, selection for "
                "highlights, and define-word at the caret",
                checkable=True,
                checked=bool(self.settings.get("qt_caret_browsing", True)),
            )
        )
        view_menu.addAction(
            _mi("Change Font…", "Ctrl+Alt+F", self._qt_change_font_dialog)
        )
        # Reading Level is shared with the Tools menu (one Ctrl+L owner).
        level_act = _mi("Reading Level", "Ctrl+L", self._qt_reading_level)
        view_menu.addAction(level_act)
        # Live HTML preview while editing (checkable).
        self._preview_act = _mi(
            "Live HTML Preview (edit mode)",
            "Ctrl+Shift+L",
            self._qt_toggle_preview,
            tip="Show a live-rendered HTML preview beside the Markdown source",
            checkable=True,
            checked=bool(self.settings.get("qt_edit_preview", False)),
        )
        view_menu.addAction(self._preview_act)

        # ── Reading Aids submenu (accessibility) ───────────────────
        aids_menu: QMenu = view_menu.addMenu(tr("Reading Aids"))
        aids_menu.addAction(
            _mi(
                "Text Spacing…",
                "Ctrl+Alt+W",
                self._qt_text_spacing_dialog,
                tip="Adjust line height, letter and word spacing (WCAG 1.4.12)",
            )
        )
        aids_menu.addAction(
            _mi(
                "Karaoke Highlight…",
                "Ctrl+Alt+K",
                self._qt_karaoke_dialog,
                tip="Tune the spoken-word highlight style, color, speed and lead",
            )
        )
        aids_menu.addSeparator()
        self._dyslexia_font_act = _mi(
            "Dyslexia-Friendly Font",
            "Ctrl+Alt+X",
            self._qt_toggle_dyslexia_font,
            tip="Prefer OpenDyslexic / Atkinson Hyperlegible / Lexend if installed",
            checkable=True,
            checked=bool(self.settings.get("qt_dyslexia_font", False)),
        )
        aids_menu.addAction(self._dyslexia_font_act)
        self._bionic_act = _mi(
            "Bionic Reading",
            "Ctrl+Alt+J",
            self._qt_toggle_bionic,
            tip="Embolden the leading part of each word",
            checkable=True,
            checked=bool(self.settings.get("qt_bionic_reading", False)),
        )
        aids_menu.addAction(self._bionic_act)
        self._current_line_act = _mi(
            "Current-Line Highlight",
            "Ctrl+Alt+L",
            self._qt_toggle_current_line,
            tip="Tint the line being read with a focus band",
            checkable=True,
            checked=bool(self.settings.get("qt_current_line_highlight", False)),
        )
        aids_menu.addAction(self._current_line_act)
        self._vocab_act = _mi(
            "Highlight Difficult Words",
            "Ctrl+Alt+O",
            self._qt_toggle_vocab_highlight,
            tip="Tint uncommon / academic vocabulary (by word frequency)",
            checkable=True,
            checked=bool(self.settings.get("qt_vocab_highlight", False)),
        )
        aids_menu.addAction(self._vocab_act)
        aids_menu.addAction(
            _mi(
                "Define Word…",
                "Ctrl+D",
                self._qt_define_word,
                tip="Look up the selected word (or the word under the cursor) offline",
            )
        )
        aids_menu.addSeparator()
        self._rsvp_act = _mi(
            "RSVP Mode",
            "Ctrl+Alt+E",
            self._qt_toggle_rsvp,
            tip="Rapid Serial Visual Presentation: one word at a time at a fixed point",
            checkable=True,
            checked=bool(self.settings.get("qt_rsvp_mode", False)),
        )
        aids_menu.addAction(self._rsvp_act)
        aids_menu.addAction(
            _mi(
                "RSVP Position…",
                "",
                self._qt_rsvp_position_dialog,
                tip="Choose which screen quadrant the RSVP word appears in",
            )
        )

        # ── Interface language (UI i18n) ───────────────────────────────
        # Localizes the chrome (menus, toolbar, docks).  Native language
        # names are shown untranslated so a user can always find their own.
        view_menu.addSeparator()
        lang_menu: QMenu = view_menu.addMenu(tr("Interface Language"))
        _current_lang = get_language()
        for _disp, _code in available_languages():
            _lang_act = QAction(_disp, self)
            _lang_act.setCheckable(True)
            _lang_act.setChecked(_code == _current_lang)
            _lang_act.triggered.connect(
                lambda _checked=False, c=_code: self._set_ui_language(c)
            )
            lang_menu.addAction(_lang_act)

        # Tools menu — transcription, dictation, and maintenance.
        tools_menu: QMenu = mb.addMenu(tr("Tools"))
        tools_menu.addAction(
            _mi(
                "Install Optional Features…",
                "",
                self._qt_install_optional_features,
                tip="Pick which optional capabilities to download (OCR, dictionary, "
                    "graph, speech-to-text, …)",
            )
        )
        tools_menu.addSeparator()
        tools_menu.addAction(
            _mi(
                "Transcribe Audio File…",
                "Ctrl+Alt+S",
                self._qt_transcribe_file,
            )
        )
        tools_menu.addAction(
            _mi("Dictate Note (record)…", "Ctrl+Alt+V", self._qt_dictate_note)
        )
        tools_menu.addAction(
            _mi(
                "Toggle Transcript Timestamps",
                "Ctrl+Alt+Z",
                lambda: (
                    self.settings.set(
                        "transcribe_timestamps",
                        not self.settings.get("transcribe_timestamps", False),
                    ),
                    self.statusBar().showMessage(
                        "Transcript timestamps: "
                        + (
                            "ON"
                            if self.settings.get("transcribe_timestamps")
                            else "OFF"
                        )
                    ),
                ),
            )
        )
        tools_menu.addSeparator()
        tools_menu.addAction(
            _mi(
                "Summarize Document…",
                # Ctrl+Shift+S is already Reading Statistics; the summarizer
                # uses Ctrl+Shift+U instead.
                "Ctrl+Shift+U",
                self._qt_summarize,
                tip="Condense the document to a few key sentences (LexRank)",
            )
        )
        tools_menu.addAction(
            _mi(
                "Translate Document…",
                "Ctrl+Shift+X",
                self._qt_translate,
                tip="Translate the document into another language (Google)",
            )
        )
        tools_menu.addAction(
            _mi(
                "Reading Statistics…",
                "Ctrl+Shift+S",
                self._qt_reading_stats,
                tip="Time read, progress, and most-read documents",
            )
        )
        # Reading Level shares the View menu's QAction (single Ctrl+L owner).
        tools_menu.addAction(level_act)
        tools_menu.addAction(
            _mi(
                "Clear Document Cache",
                "Ctrl+Shift+Delete",
                lambda: (
                    shutil.rmtree(CACHE_DIR, ignore_errors=True),
                    self.statusBar().showMessage("Document cache cleared"),
                ),
            )
        )

        # Profiles menu — named bundles of voice/theme/font/highlight.
        _menu(
            "Profiles",
            [
                (
                    "Save Current Settings as Profile…",
                    self._qt_save_profile,
                    "Ctrl+Shift+K",
                ),
                ("Load Profile…", self._qt_load_profile, "Ctrl+Shift+J"),
                ("Delete Profile…", self._qt_delete_profile, "Ctrl+Shift+Y"),
            ],
        )

        # Help menu.
        _menu(
            "Help",
            [
                ("Command Palette…", self._qt_command_palette, "F2"),
                ("Keyboard Shortcuts…", self._qt_show_shortcuts, "F3"),
                (
                    "Customize Shortcuts…",
                    self._qt_customize_shortcuts,
                    "Ctrl+Alt+Q",
                ),
                None,
                ("Open README (Help)", self._show_about, "F1"),
                (
                    "About star",
                    lambda: QMessageBox.about(
                        self,
                        f"About {APP_NAME}",
                        f"<b>{APP_TITLE}</b><br>Version {APP_VERSION}<br><br>"
                        f"{__copyright__}<br>{__license__}",
                    ),
                    "Ctrl+F1",
                ),
            ],
        )

        # Reorder the menu bar so the most-used menus lead: File, Edit,
        # View come first and Help stays last.  The menus are built above
        # in a dependency-friendly order (Notes before View shares the
        # panel-toggle action; View before Tools shares Reading Level), so
        # here we simply move Edit and View ahead of the rest.  insertMenu
        # relocates an already-added menu rather than duplicating it.
        mb.insertMenu(hl_menu.menuAction(), edit_menu)
        mb.insertMenu(hl_menu.menuAction(), view_menu)

    def _set_ui_language(self, code: str) -> None:
        """Switch the UI-chrome language and rebuild the menus/toolbar live.

        Persists the choice, reactivates the catalog, and rebuilds every
        surface that routes its labels through tr(): the toolbar and the menu
        bar are recreated in place, and the dock titles/placeholder we keep
        references to are retranslated.  (The annotation panel's buttons are
        built locally in _setup_ui and refresh on the next launch.)
        """
        applied = set_language(code)
        self.settings.set("ui_language", applied)
        self._build_toolbar()
        self._build_menu_bar()
        if getattr(self, "_toc_dock", None) is not None:
            self._toc_dock.setWindowTitle(tr("Contents"))
        if getattr(self, "_annot_dock", None) is not None:
            self._annot_dock.setWindowTitle(tr("Notes"))
        if getattr(self, "_annot_filter", None) is not None:
            self._annot_filter.setPlaceholderText(
                tr("Filter notes — text or #tag…")
            )
        self.statusBar().showMessage(tr("Interface language updated"))

    def _welcome_html(self) -> str:
        """Return the splash-screen HTML, styled with the current theme."""
        theme_name = str(self.settings.get("theme", "dark"))
        pal = self._effective_palette(theme_name)
        custom_css = str(pal.get("_css", ""))
        if custom_css:
            # Inject the theme CSS plus some extras for the welcome page
            # (kbd highlight, centered layout) that the theme may omit.
            style = (
                custom_css + f"kbd{{background:{pal.get('sel', '#313244')};"
                f"color:{pal['fg']};padding:1px 5px;"
                "border-radius:3px;font-family:monospace;font-size:0.9em}"
                "td{padding:2px 12px 2px 0}"
            )
        else:
            style = (
                f"body{{background:{pal['bg']};color:{pal['fg']};"
                "     font-family:Georgia,serif;margin:24px;line-height:1.6}}"
                f"h1{{color:{pal['h1']};margin-bottom:4px}}"
                f"h2{{color:{pal['h2']};margin-top:20px;margin-bottom:6px}}"
                f"kbd{{background:{pal.get('sel', '#313244')};"
                f"color:{pal['fg']};padding:1px 5px;"
                "border-radius:3px;font-family:monospace;font-size:0.9em}"
                "td{padding:2px 12px 2px 0}"
            )
        return (
            "<html><head><style>" + style + "</style></head><body>"
            f"<h1>star &#8212; Speaking Terminal Access Reader</h1>"
            f"<p>Version {APP_VERSION} &nbsp;&middot;&nbsp; {APP_TITLE}</p>"
            "<h2>Getting started</h2>"
            "<table>"
            "<tr><td><kbd>Ctrl+O</kbd></td>"
            "    <td>Open a file</td></tr>"
            "<tr><td><kbd>Space</kbd></td>"
            "    <td>Play / pause speech</td></tr>"
            "<tr><td><kbd>Esc</kbd></td>"
            "    <td>Stop speech</td></tr>"
            "<tr><td><kbd>+</kbd> / <kbd>-</kbd></td>"
            "    <td>Speed up / slow down</td></tr>"
            "<tr><td><kbd>F1</kbd></td>"
            "    <td>Help</td></tr>"
            "<tr><td><kbd>Ctrl+Q</kbd></td>"
            "    <td>Quit</td></tr>"
            "</table>"
            "<h2>Supported formats</h2>"
            "<p>PDF &nbsp; DOCX &nbsp; ODT &nbsp; EPUB &nbsp; HTML &nbsp;"
            "Markdown &nbsp; plain text &nbsp; CSV / TSV / XLSX &nbsp;"
            "DAISY / DTBook &nbsp; URLs</p>"
            "</body></html>"
        )

    def closeEvent(self, event: Any) -> None:
        # Persist position, then silence.
        self._qt_save_reading_position()
        # Flush the final reading-statistics slice.
        try:
            self.stats.tick(False, self.doc.path if self.doc else "")
            self.stats.flush()
        except Exception:
            pass
        if self._qt_sc_reader is not None:
            self._qt_sc_reader.close()
            self._qt_sc_reader = None
        # Stop a running hot-folder watcher cleanly (lets an in-progress
        # conversion finish before the window closes).
        if self._watcher is not None:
            try:
                self._watcher.stop()
            except Exception:
                pass
            self._watcher = None
        self.tts_manager.stop()
        self.settings["gui_width"] = self.width()
        self.settings["gui_height"] = self.height()
        self.settings.save()
        event.accept()


