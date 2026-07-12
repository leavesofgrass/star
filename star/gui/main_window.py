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
from ..i18n import is_rtl, set_language, tr
from ..settings import Settings
from ..stats import (
    ReadingStats,
)
from ..themes import BUILT_IN_PALETTES, _load_css_themes, _seed_default_css_themes
from ..tts import TTSManager, _SCReader
from ._qtcompat import (
    _LEFT_DOCK,
    _QUEUED,
    _RIGHT_DOCK,
    _WA_STYLED_BG,
)
from .._bundled import bundled_path as _bundled_path
from .._bundled import is_welcome_doc as _is_welcome_doc
from .._bundled import welcome_path as _welcome_path
from .a11y import announce
from .mixin_aiddialogs import AidDialogsMixin
from .mixin_chrome import ChromeMixin
from .mixin_commands import CommandsMixin
from .mixin_toc import TocMixin
from .mixin_highlights import HighlightsMixin
from .mixin_presets import PresetsMixin
from .mixin_docops import DocOpsMixin
from .mixin_display import DisplayMixin
from .mixin_doctools import DocToolsMixin
from .mixin_navigation import NavigationMixin
from .mixin_playback import PlaybackMixin
from .mixin_fontspacing import FontSpacingMixin
from .mixin_document import DocumentMixin
from .mixin_annotations import AnnotationsMixin
from .mixin_export import ExportMixin
from .mixin_authoring import AuthoringMixin
from .mixin_autosave import AutosaveMixin
from .mixin_history import HistoryMixin
from .mixin_transcription import TranscriptionMixin
from .mixin_citations import CitationsMixin
from .mixin_graph import GraphMixin
from .mixin_find import FindMixin
from .mixin_bookmarks_qt import BookmarksQtMixin
from .mixin_voices import VoicesMixin
from .mixin_review import ReviewMixin
from .mixin_tour import TourMixin


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


class _ReadingRulerOverlay(QWidget):
    """A movable translucent reading ruler (typoscope) over the reading view.

    A wide, adjustable horizontal band that tracks the caret line — distinct
    from the thin current-line focus tint (which paints *behind text* via an
    ExtraSelection).  This overlay floats above the text as a child of the
    editor's viewport, is mouse-transparent (it never steals clicks), and follows
    the text caret.  Height and opacity are user-adjustable.

    Teardown-safe by construction: it holds no timers and installs no event
    filters.  The only external wiring is a connection to the editor's
    ``cursorPositionChanged`` signal, made and unmade by
    :meth:`StarWindow._apply_reading_ruler`, so a hidden/closed window leaves no
    dangling connection.
    """

    def __init__(self, editor: QWidget, settings: "Settings") -> None:
        # Parent to the editor's viewport so (0, y) coordinates line up with the
        # caret rectangle QTextEdit reports.
        super().__init__(editor.viewport())
        self._editor = editor
        self._height: int = int(settings.get("qt_ruler_height", 40))
        self._opacity: int = int(settings.get("qt_ruler_opacity", 22))
        _rc = str(settings.get("qt_ruler_color", "") or "").strip()
        self._color = QColor(_rc or str(settings.get("highlight_color", "cyan")))
        if not self._color.isValid():
            self._color = QColor("#06b6d4")
        self._center_y: int = 0
        # Transparent to mouse events — reading/selecting/clicking still hit the
        # text underneath.  Attribute name differs across PyQt5/6 enum styles.
        try:
            attr = Qt.WidgetAttribute.WA_TransparentForMouseEvents
        except AttributeError:  # PyQt5
            attr = Qt.WA_TransparentForMouseEvents  # type: ignore[attr-defined]
        self.setAttribute(attr, True)
        self.setVisible(False)

    def set_height(self, px: int) -> None:
        self._height = max(16, min(int(px), 160))
        self._reposition()

    def set_opacity(self, pct: int) -> None:
        self._opacity = max(0, min(int(pct), 100))
        self.update()

    def set_color(self, color: "QColor") -> None:
        if color.isValid():
            self._color = color
            self.update()

    def follow_caret(self) -> None:
        """Recompute the band's vertical center from the editor's caret rect."""
        try:
            rect = self._editor.cursorRect()
        except Exception:
            return
        # cursorRect is in viewport coordinates — the same space as this widget.
        self._center_y = rect.center().y()
        self._reposition()

    def _reposition(self) -> None:
        vp = self.parentWidget()
        if vp is None:
            return
        w = vp.width()
        y = int(self._center_y - self._height / 2)
        # Keep the band within the viewport so it never floats off-screen.
        y = max(0, min(y, max(0, vp.height() - self._height)))
        self.setGeometry(0, y, w, self._height)
        self.raise_()
        self.update()

    def paintEvent(self, event: Any) -> None:
        try:
            from PyQt6.QtGui import QPainter
        except ImportError:
            from PyQt5.QtGui import QPainter  # type: ignore[no-redef]
        painter = QPainter(self)
        fill = QColor(self._color)
        # opacity is 0–100 (percent) → 0–255 alpha.
        fill.setAlpha(int(self._opacity / 100.0 * 255))
        painter.fillRect(self.rect(), fill)
        painter.end()


# =========================================================================

class StarWindow(AidDialogsMixin, ChromeMixin, CommandsMixin, TocMixin, HighlightsMixin, PresetsMixin, DocOpsMixin, DisplayMixin, DocToolsMixin, NavigationMixin, PlaybackMixin, FontSpacingMixin, DocumentMixin, AnnotationsMixin, ExportMixin, TranscriptionMixin, AuthoringMixin, AutosaveMixin, HistoryMixin, CitationsMixin, GraphMixin, FindMixin, BookmarksQtMixin, VoicesMixin, ReviewMixin, TourMixin, QMainWindow):
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
    # Emitted from the word-map build thread when a document qualifies for
    # pagination, so the initial page-window render (a Qt call) happens on the
    # GUI thread.  Carries nothing; the paginator state is read from self.
    _paginate_signal = pyqtSignal()
    # Emitted from the background OpenDyslexic prefetch thread once the font files
    # are downloaded, so registration + (re)application happen on the GUI thread.
    _font_ready_signal = pyqtSignal()
    # Emitted from a feature-install worker thread with (human_name, success,
    # ready_in_session) so the outcome is reported on the GUI thread.
    _deps_installed_signal = pyqtSignal(str, bool, bool)
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
    # dictate: (text, char_pos_str, anchor, annot_key, word_idx_str) — the key
    # and word index are captured when recording starts so the note lands on
    # the document it was dictated on even if the user switches docs while
    # Whisper runs.  ERROR is signalled by char_pos_str == "ERROR".
    _transcribe_signal = pyqtSignal(str, str)
    _dictate_signal = pyqtSignal(str, str, str, str, str)
    # Voice typing (dictate into the document): (recognized_text, error) — the
    # recognized text is inserted at the editor cursor on the GUI thread.
    _voice_type_signal = pyqtSignal(str, str)
    _doi_signal = pyqtSignal(str)  # Crossref DOI lookup result (JSON or ERROR:)
    # Document summarization runs on a background thread (LexRank can be
    # slow on long documents); carries (summary, error_message).
    _summary_signal = pyqtSignal(str, str)
    # Translation runs on a background thread (it makes a network call);
    # carries (translated_text, error_message).
    _translate_signal = pyqtSignal(str, str)
    # Long documents translate in chunks (the backend caps requests at 5000
    # chars); carries a "part 3 of 8" status line from the worker thread.
    _translate_progress_signal = pyqtSignal(str)
    # Feed fetching runs on a background thread (network call); carries
    # (entries_list, error_message) — the list is passed as a Python object.
    _feed_signal = pyqtSignal(object, str)
    # Definition lookup runs on a background thread (the first WordNet access
    # loads the corpus); carries (DefinitionResult-or-None, word, error_message).
    _define_signal = pyqtSignal(object, str, str)
    # Update check runs on a background thread (star.update queries PyPI);
    # carries the UpdateResult back to the GUI thread as a plain object, plus a
    # flag distinguishing a user-initiated check (always report the outcome)
    # from the quiet startup check (report only when an update is available).
    _update_signal = pyqtSignal(object, bool)

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
        # Mirror the whole application (toolbar, menus, docks, reading view) when
        # the active UI language is right-to-left, and keep it left-to-right
        # otherwise.  Done before widgets are built so the very first layout is
        # already in the correct direction; re-applied live on a language switch.
        self._apply_layout_direction()
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
        # Built asynchronously after each document load.  When pagination is
        # active this stays full-document length, but words outside the rendered
        # window carry the sentinel -1 until the window advances to them.
        self._qt_word_map: List[int] = []

        # Large-document pagination (see star/pagination.py + docs/PERFORMANCE.md).
        # _paginator is None whenever the whole document is rendered (the normal
        # path); it is a Paginator only for documents past the size gate with the
        # opt-in setting on.  _page_block_starts is the global word index at which
        # each rendered markdown block begins, used to slice a window's markdown.
        self._paginator: Optional[Any] = None
        self._page_blocks: List[str] = []
        self._page_block_starts: List[int] = []
        # True while a cheap provisional leading window is shown pending the
        # background build's precise pagination decision.
        self._page_provisional: bool = False

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

        # Follow the OS dark/light/high-contrast preference on startup, unless
        # the user has explicitly chosen a theme (their choice always wins).
        # Runs before _setup_ui so the very first paint uses the right theme.
        self._maybe_follow_os_theme()

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
        # After the position is restored: honor tts_auto_play (slots run in
        # connection order, so the cursor is already at the saved spot).
        self._restore_signal.connect(self._qt_maybe_auto_play, _QUEUED)
        # Wire the pagination initial-window render → main thread.
        self._paginate_signal.connect(self._page_render_initial_window, _QUEUED)
        # Wire the OpenDyslexic prefetch-complete callback → main thread.
        self._font_ready_signal.connect(self._on_dyslexia_font_ready, _QUEUED)
        # Wire the feature-install completion callback → main thread.
        self._deps_installed_signal.connect(self._on_feature_installed, _QUEUED)
        # Wire the audio-export completion signal → status bar update.
        # Export completions AND failures both arrive here as plain text;
        # route failures through the persistent, announced error surface so
        # they are neither wiped by the next routine update nor silent to
        # screen readers.
        self._export_audio_signal.connect(
            lambda msg: (
                self._status_error(msg)
                if "error" in msg.lower()
                else self.statusBar().showMessage(msg)
            ),
            _QUEUED,
        )
        # Batch-conversion progress / completion (background thread).
        self._batch_progress_signal.connect(
            lambda msg: (
                self._status_error(msg)
                if "error" in msg.lower()
                else self.statusBar().showMessage(msg)
            ),
            _QUEUED,
        )
        self._batch_done_signal.connect(self._on_batch_done, _QUEUED)
        self._watch_signal.connect(
            lambda msg: self.statusBar().showMessage(msg), _QUEUED
        )
        # Wire the Whisper transcription / dictation result signals.
        self._transcribe_signal.connect(self._qt_on_transcribed, _QUEUED)
        self._dictate_signal.connect(self._qt_on_dictated, _QUEUED)
        self._voice_type_signal.connect(self._qt_on_voice_typed, _QUEUED)
        self._doi_signal.connect(self._qt_on_doi, _QUEUED)
        # Wire the summarization result signal → GUI thread.
        self._summary_signal.connect(self._qt_on_summary, _QUEUED)
        # Wire the translation / feed-fetch result signals → GUI thread.
        self._translate_signal.connect(self._qt_on_translation, _QUEUED)
        self._translate_progress_signal.connect(
            lambda msg: self.statusBar().showMessage(msg), _QUEUED
        )
        self._feed_signal.connect(self._qt_on_feed, _QUEUED)
        self._define_signal.connect(self._qt_on_definition, _QUEUED)
        # Update-check result → GUI thread (see mixin_tour.py / update wiring).
        self._update_signal.connect(self._qt_on_update_result, _QUEUED)

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

        # Navigation-history stack (back/forward) — see BookmarksQtMixin.
        self._init_nav_history()

        # Find bar is created lazily on first Ctrl+F; declare the handle so
        # code that checks ``getattr(self, "_find_bar", None)`` is safe pre-init.
        self._find_bar = None

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
        # True once an edit is persisted, so the read-view word/sentence maps are
        # out of date and must be rebuilt on exit.  Gating the background rebuild
        # on this (instead of rebuilding on every exit) keeps the daemon-thread
        # churn — the Qt-teardown flake's trigger — off the common no-change path.
        self._qt_maps_stale: bool = False
        # Spell-check syntax highlighter, attached only while editing and
        # only when pyspellchecker (and a Qt QSyntaxHighlighter) is present.
        self._spell_highlighter = None

        # Intercept keyboard events on the editor so Tab and arrow keys
        # can be processed for SC mode without fighting Qt's focus chain.
        self.editor.installEventFilter(self)
        # QTextEdit delivers mouse events to its viewport, not the widget, so a
        # separate filter there lets clicking an in-document anchor (footnote
        # marker / backlink) jump to it.
        self.editor.viewport().installEventFilter(self)

        # Capture the real default application font BEFORE any dyslexia override,
        # so toggling the dyslexia font off can restore it exactly. A
        # default-constructed QFont() has no resolve mask and does NOT override
        # widgets (menus, docks) that already resolved to OpenDyslexic — hence the
        # explicit snapshot.
        _app = QApplication.instance()
        self._default_app_font = QFont(_app.font()) if _app is not None else None

        # If a reading font was left selected (chooser or legacy dyslexia
        # toggle), apply it across the whole UI now that the toolbar/menus exist
        # (using an already-fetched / installed family — no network on the GUI
        # thread at launch).
        if self._reading_font_key() != "default":
            self._apply_dyslexia_font(True, fetch=False)
        # Fetch the selected reading font automatically in the background — like
        # the other optional dependencies — so it is ready when wanted without a
        # wait. When it lands, _on_dyslexia_font_ready registers it and re-applies
        # if selected.  Honors auto_install / STAR_NO_AUTOINSTALL.
        self._maybe_prefetch_dyslexia_font()

        # Reading ruler / typoscope overlay: created lazily on first toggle
        # (None until then).  Restore it if it was left on.
        self._reading_ruler: Optional[Any] = None
        if self.settings.get("qt_reading_ruler", False):
            self._apply_reading_ruler(True)

        # Autosave / crash recovery for in-progress edits (see AutosaveMixin).
        # Create the timer before any document loads so entering edit mode can
        # start it.
        self._autosave_init()

        if initial_path:
            self._open_path(initial_path)
        else:
            # Load the bundled welcome page as a *real document* so speech,
            # navigation, highlighting, and define-word all work on the very
            # first screen.  Falls back to the static splash if it is missing.
            welcome = self._welcome_path
            if welcome is not None:
                self._open_path(str(welcome))

        # Onboarding & discoverability, deferred to the next event-loop turn so
        # the window is on screen first (and construction stays fast/testable):
        #   • the first-run guided tour (once, gated by the tour_seen setting);
        #   • an optional quiet update check (only if the user opted in).
        # singleShot(0) means neither fires until the Qt event loop runs, so a
        # test that merely constructs the window is unaffected.
        QTimer.singleShot(0, self._maybe_run_first_run_tour)
        QTimer.singleShot(0, self._maybe_startup_update_check)
        # Offer to recover any unsaved work a previous session left behind.
        QTimer.singleShot(0, self._autosave_check_on_startup)
        # If the settings file was corrupt, _load reset to defaults and saved a
        # backup — tell the user once instead of resetting invisibly.
        if getattr(self.settings, "load_error", ""):
            QTimer.singleShot(0, self._report_settings_reset)

    def _report_settings_reset(self) -> None:
        """Show + announce the settings-file reset recorded by Settings._load."""
        msg = str(getattr(self.settings, "load_error", ""))
        if not msg:
            return
        self.statusBar().showMessage(msg, 30000)
        announce(self, msg)

    # ── Bundled documentation (README, welcome) ───────────────────────
    # Thin delegates to star/_bundled.py — shared with the TUI so both UIs
    # agree on what counts as "the welcome page" (recents/library gating).
    def _bundled_path(self, name: str) -> "Optional[Path]":
        return _bundled_path(name)

    @property
    def _welcome_path(self) -> "Optional[Path]":
        return _welcome_path()

    def _is_welcome(self, doc: Any) -> bool:
        return _is_welcome_doc(doc)

    def _open_documentation(self) -> None:
        """Open the bundled documentation (Help ▸ Open Documentation).

        Prefers the human-written guide bundled under ``docs/`` (the usage
        guide, then the docs index), and falls back to the README — all opened
        as *real documents* in the main window so they get full TTS, search, and
        navigation, exactly like the F1 README help.  Never raises: if nothing
        bundled is found it just reports it in the status bar.
        """
        for name in ("docs/usage_guide.md", "docs/README.md", "README.md"):
            path = self._bundled_path(name)
            if path is not None:
                self._open_path(str(path))
                return
        self.statusBar().showMessage(
            tr("Documentation not found in this install"), 6000
        )

    # ── Auto-update wiring (star/update.py) ────────────────────────────
    def _qt_check_for_updates(self) -> None:
        """Manually check PyPI for a newer star release (Help ▸ Check for Updates…).

        Runs the check on a background thread (star.update queries PyPI over the
        network) and reports the outcome via _update_signal → the GUI thread.
        A user-initiated check always reports its result, including "you're up
        to date" and offline failures.
        """
        self.statusBar().showMessage(tr("Checking for updates…"))
        self._run_update_check(user_initiated=True)

    def _maybe_startup_update_check(self) -> None:
        """Quiet startup update check, gated by the auto_check_updates setting.

        OFF by default (privacy / offline first): star does nothing unless the
        user has explicitly opted in.  When on, it runs one best-effort, cached
        check in the background and only surfaces a result if a newer release
        exists — a failed/no-op check stays silent.
        """
        if not bool(self.settings.get("auto_check_updates", False)):
            return
        self._run_update_check(user_initiated=False)

    def _run_update_check(self, user_initiated: bool) -> None:
        """Spawn the background thread that queries PyPI and emits the result.

        *user_initiated* is carried through to the handler so the quiet startup
        check can stay silent unless an update is available, while a manual
        check always reports.  A manual check bypasses the on-disk cache so the
        user gets a live answer; the startup check uses the cache.
        """
        from .. import update as _update

        def _work() -> None:
            try:
                result = _update.check_for_update(
                    current=APP_VERSION, use_cache=not user_initiated
                )
            except Exception:  # noqa: BLE001 — an update check must never crash.
                result = None
            self._update_signal.emit(result, user_initiated)

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_update_result(self, result: Any, user_initiated: bool) -> None:
        """GUI-thread handler for a completed update check.

        Shows a message box (with a link to the release) when a newer version is
        available.  For a manual check with no update it confirms the app is
        current or reports that the check could not complete; the quiet startup
        check stays silent in those cases.
        """
        available = bool(getattr(result, "update_available", False))
        latest = getattr(result, "latest", None)
        url = getattr(result, "url", "") or ""
        if available and latest:
            msg = tr(
                "A new version of star is available: {latest} "
                "(you have {current})."
            ).format(latest=latest, current=APP_VERSION)
            self.statusBar().showMessage(msg, 12000)
            announce(self, msg)
            if not self._modal_ok():  # result landed on a closing window
                return
            box = QMessageBox(self)
            box.setWindowTitle(tr("Update available"))
            box.setTextFormat(Qt.TextFormat.RichText if hasattr(Qt, "TextFormat")
                               else Qt.RichText)  # type: ignore[attr-defined]
            link = f'<a href="{url}">{url}</a>' if url else ""
            box.setText(
                f"{msg}<br><br>" + tr("Release notes and download:") + f"<br>{link}"
            )
            box.exec()
            return
        # No update (or the check could not complete).  Only report for a manual
        # check — the startup check must stay quiet.
        if not user_initiated:
            return
        if latest:
            done = tr("You're running the latest version of star ({current}).").format(
                current=APP_VERSION
            )
        else:
            done = tr("Could not check for updates (offline or PyPI unreachable).")
        self.statusBar().showMessage(done, 8000)
        announce(self, done)

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
        # Custom right-click menu: Qt's standard edit actions (Undo/Redo/Cut/
        # Copy/Paste/Select All) + a Format submenu while editing, so Undo and
        # Redo are always reachable from the context menu too.
        try:
            _ccm = Qt.ContextMenuPolicy.CustomContextMenu
        except AttributeError:  # PyQt5
            _ccm = Qt.CustomContextMenu  # type: ignore[attr-defined]
        self.editor.setContextMenuPolicy(_ccm)
        self.editor.customContextMenuRequested.connect(self._qt_editor_context_menu)
        # Live HTML preview pane shown beside the editor in edit mode
        # (hidden until toggled).  Wrapped with the editor in a splitter so
        # the user can drag the divider.
        self._preview = QTextBrowser()
        self._preview.setObjectName("preview")
        self._preview.setAccessibleName(tr("HTML preview"))
        self._preview.setAccessibleDescription(
            tr("Live-rendered preview of the document shown while editing.")
        )
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
        self._toc_dock.setAccessibleName(tr("Table of Contents panel"))
        self._toc_list = QListWidget()
        self._toc_list.setAccessibleName(tr("Table of contents"))
        self._toc_list.setAccessibleDescription(
            tr("Document headings. Enter scrolls to a heading; "
               "double-click or double-Enter reads from it.")
        )
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
        self._annot_dock.setAccessibleName(tr("Notes panel"))
        _annot_panel = QWidget()
        _annot_layout = QVBoxLayout(_annot_panel)
        _annot_layout.setContentsMargins(4, 4, 4, 4)
        _annot_layout.setSpacing(4)
        # Full-text search / tag filter box (type `#tag` to filter by tag).
        self._annot_filter = QLineEdit()
        self._annot_filter.setPlaceholderText(tr("Filter notes — text or #tag…"))
        self._annot_filter.setAccessibleName(tr("Filter notes"))
        self._annot_filter.setAccessibleDescription(
            tr("Type text to filter notes, or #tag to filter by tag.")
        )
        self._annot_filter.setClearButtonEnabled(True)
        self._annot_filter.textChanged.connect(
            lambda _t: self._qt_build_annotations()
        )
        _annot_layout.addWidget(self._annot_filter)
        self._annot_list = QListWidget()
        self._annot_list.setAccessibleName(tr("Notes"))
        self._annot_list.setAccessibleDescription(
            tr("Notes anchored in the document. Enter scrolls to a note; "
               "double-click or double-Enter reads from it.")
        )
        self._annot_list.setMinimumWidth(200)
        self._annot_list.setWordWrap(True)
        self._annot_list.itemActivated.connect(self._qt_annotation_navigate)
        self._annot_list.itemDoubleClicked.connect(self._qt_annotation_play)
        _annot_layout.addWidget(self._annot_list)
        _btn_row = QHBoxLayout()
        for _lbl, _fn, _desc in (
            ("Add", self._qt_add_annotation, tr("Add a note at the cursor")),
            ("Edit", self._qt_edit_annotation, tr("Edit the selected note")),
            ("Delete", self._qt_delete_annotation, tr("Delete the selected note")),
            ("Export…", self._qt_export_annotations, tr("Export all notes to a file")),
        ):
            _b = QPushButton(tr(_lbl))
            _b.setAccessibleDescription(_desc)
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


    def _apply_layout_direction(self) -> None:
        """Mirror the app for RTL locales; keep LTR locales left-to-right.

        Sets the application-wide layout direction from the active UI language
        (``is_rtl``): ``RightToLeft`` for Arabic/Hebrew/Persian/Urdu, else the
        explicit ``LeftToRight`` (so switching *back* from an RTL language
        restores normal direction rather than leaving the app mirrored).
        ``QApplication.setLayoutDirection`` cascades to every existing and
        future widget — toolbar, menus, docks, and the reading view — so no
        per-widget wiring is needed.  A no-op (LTR) for the default English UI,
        keeping left-to-right locales visually identical to before.
        """
        app = QApplication.instance()
        if app is None:
            return
        try:
            ltr = Qt.LayoutDirection.LeftToRight
            rtl = Qt.LayoutDirection.RightToLeft
        except AttributeError:  # PyQt5 enum style
            ltr = Qt.LeftToRight  # type: ignore[attr-defined]
            rtl = Qt.RightToLeft  # type: ignore[attr-defined]
        app.setLayoutDirection(rtl if is_rtl() else ltr)

    def _set_ui_language(self, code: str) -> None:
        """Switch the UI-chrome language and rebuild the menus/toolbar live.

        Persists the choice, reactivates the catalog, and rebuilds every
        surface that routes its labels through tr(): the toolbar and the menu
        bar are recreated in place, and the dock titles/placeholder we keep
        references to are retranslated.  (The annotation panel's buttons are
        built locally in _setup_ui and refresh on the next launch.)  The
        application layout direction is re-applied first so switching to (or
        away from) an RTL language mirrors (or un-mirrors) the whole UI live.
        """
        applied = set_language(code)
        self.settings.set("ui_language", applied)
        # Flip/restore RTL mirroring before rebuilding the chrome so the
        # freshly-built toolbar and menus lay out in the right direction.
        self._apply_layout_direction()
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
        # Re-render the reading view so the document's ``dir`` attribute tracks
        # the new locale's direction (RTL adds ``dir="rtl"``; switching back to
        # an LTR language drops it).  Skip in edit mode, where the editor holds
        # raw Markdown the user is editing — matching the theme-change path.
        if not getattr(self, "_qt_edit_mode", False) and getattr(self, "editor", None) is not None:
            if self.doc is not None:
                self.editor.setHtml(self._md_to_html(self.doc.markdown or ""))
            else:
                self.editor.setHtml(self._welcome_html())
            self._apply_block_spacing()
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

    def _modal_ok(self) -> bool:
        """True when a queued-signal handler may open a modal dialog.

        Background threads deliver results through queued signals, so a
        summary / definition / update result can land AFTER the window has
        started closing — most visibly under offscreen test runs, where a
        modal opened on a closing window has nobody to dismiss it and blocks
        that xdist worker forever (the suite "hang at 93%").  Handlers gate
        their dialogs on this and fall back to the status-bar message they
        already show.
        """
        return not getattr(self, "_closing", False)

    def closeEvent(self, event: Any) -> None:
        # From here on, queued-signal handlers must not open modal dialogs
        # (see _modal_ok) — a background result arriving mid-teardown would
        # block forever with no user to dismiss it.
        self._closing = True
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
        # Release the microphone if voice typing is still recording on close.
        _vt_rec = getattr(self, "_qt_vt_recorder", None)
        if _vt_rec is not None:
            try:
                _vt_rec.cancel()
            except Exception:
                pass
            self._qt_vt_recorder = None
        # Stop a running hot-folder watcher cleanly (lets an in-progress
        # conversion finish before the window closes).
        if self._watcher is not None:
            try:
                self._watcher.stop()
            except Exception:
                pass
            self._watcher = None
        self.tts_manager.stop()
        # Disconnect + hide the reading-ruler overlay so its caret-tracking slot
        # can never fire into a half-destroyed widget during teardown.
        if getattr(self, "_reading_ruler", None) is not None:
            try:
                self._apply_reading_ruler(False)
            except Exception:
                pass
        # Stop the periodic timers so a closed window can never fire _stats_poll /
        # the preview refresh into a half-destroyed object during teardown (a
        # source of Qt shutdown segfaults, e.g. the pytest-qt CI legs).
        for _tname in ("_stats_timer", "_preview_timer", "_autosave_timer"):
            _t = getattr(self, _tname, None)
            if _t is not None:
                try:
                    _t.stop()
                except Exception:
                    pass
        self.settings["gui_width"] = self.width()
        self.settings["gui_height"] = self.height()
        self.settings.save()
        event.accept()


