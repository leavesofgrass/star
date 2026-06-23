"""The Qt GUI (StarWindow / help window), built lazily in _run_qt_gui."""
from ._runtime import *  # noqa: F401,F403
from .annotations import _annotation_matches, _format_annotations, _parse_tags
from .braille import _export_braille
from .citations import (
    _citation_label,
    _fetch_citation_by_doi,
    _format_citations,
    _import_citations,
)
from .convert import resolve_format, run_batch, supported_formats
from .documents import Document, _build_word_map, load_document
from .feeds import _FEEDPARSER, fetch_feed
from .flashcards import _GENANKI, export_anki_deck
from .settings import Settings
from .spellcheck import _SPELL, SpellHighlighter, misspelled_words
from .stats import (
    ReadingStats,
    _apply_profile_values,
    _delete_profile,
    _fmt_duration,
    _format_reading_stats,
    _library_entries,
    _record_library,
    _save_profile,
)
from .summarize import _SUMY, summarize_document
from .themes import _load_css_themes, _seed_default_css_themes
from .transcribe import _record_audio_to_wav, _transcribe_audio
from .translate import _DEEP_TRANSLATOR, COMMON_LANGUAGES, translate_text
from .tts import Pyttsx3Backend, TTSManager, _SCReader
from .ttstext import _preprocess_tts_text, _strip_markdown_for_tts
from .tui import _HELP_TEXT, THEME_NAMES, _shortcuts_text
from .vocab import _WORDFREQ, DEFAULT_THRESHOLD, find_difficult_words
from .watch import HotFolderWatcher, _make_logger

# =============================================================================
# Optional Qt GUI
# =============================================================================


def _run_qt_gui(settings: Settings, initial_path: str = "") -> None:
    """Launch the optional Qt-based GUI mode."""
    if not _QT:
        print(
            "Qt GUI requires PyQt6 or PyQt5:\n"
            "  pip install PyQt6\nor\n  pip install PyQt5",
            file=sys.stderr,
        )
        sys.exit(1)

    # QTextCursor.MoveMode enum was reorganized in PyQt6; handle both.
    try:
        _KEEP_ANCHOR = QTextCursor.MoveMode.KeepAnchor  # PyQt6
    except AttributeError:
        _KEEP_ANCHOR = QTextCursor.KeepAnchor  # PyQt5  # type: ignore[attr-defined]

    # QueuedConnection constant also changed location.
    try:
        _QUEUED = Qt.ConnectionType.QueuedConnection  # PyQt6
    except AttributeError:
        _QUEUED = Qt.QueuedConnection  # PyQt5  # type: ignore[attr-defined]

    # DockWidgetArea enum (PyQt6 uses nested enum; PyQt5 uses top-level).
    try:
        _LEFT_DOCK = Qt.DockWidgetArea.LeftDockWidgetArea  # PyQt6
        _RIGHT_DOCK = Qt.DockWidgetArea.RightDockWidgetArea  # PyQt6
    except AttributeError:
        _LEFT_DOCK = Qt.LeftDockWidgetArea  # type: ignore[attr-defined]  # PyQt5
        _RIGHT_DOCK = Qt.RightDockWidgetArea  # type: ignore[attr-defined]  # PyQt5

    # ItemDataRole.UserRole enum (PyQt6 nested; PyQt5 top-level).
    try:
        _USER_ROLE = Qt.ItemDataRole.UserRole  # PyQt6
    except AttributeError:
        _USER_ROLE = Qt.UserRole  # type: ignore[attr-defined]  # PyQt5

    # Enums used by the reading-accessibility features (spacing, reading
    # aids, highlight tuning).  Each was reorganized between PyQt5 and 6.
    try:
        _PROPORTIONAL = QTextBlockFormat.LineHeightTypes.ProportionalHeight  # PyQt6
    except AttributeError:
        _PROPORTIONAL = QTextBlockFormat.ProportionalHeight  # type: ignore[attr-defined]
    try:
        _DOC_SELECTION = QTextCursor.SelectionType.Document  # PyQt6
    except AttributeError:
        _DOC_SELECTION = QTextCursor.Document  # type: ignore[attr-defined]
    try:
        _FULL_WIDTH_SEL = QTextFormat.Property.FullWidthSelection  # PyQt6
    except AttributeError:
        _FULL_WIDTH_SEL = QTextFormat.FullWidthSelection  # type: ignore[attr-defined]
    try:
        _PCT_SPACING = QFont.SpacingType.PercentageSpacing  # PyQt6
    except AttributeError:
        _PCT_SPACING = QFont.PercentageSpacing  # type: ignore[attr-defined]
    try:
        _SINGLE_UNDERLINE = QTextCharFormat.UnderlineStyle.SingleUnderline  # PyQt6
        _WAVE_UNDERLINE = QTextCharFormat.UnderlineStyle.WaveUnderline
    except AttributeError:
        _SINGLE_UNDERLINE = QTextCharFormat.SingleUnderline  # type: ignore[attr-defined]
        _WAVE_UNDERLINE = QTextCharFormat.WaveUnderline  # type: ignore[attr-defined]

    # High DPI support — must be set before QApplication().
    # Use the module-level Qt object so PyQt6's C-extension type checks
    # receive the exact enum type they were compiled against.
    if settings.get("qt_hidpi", True):
        try:
            # PyQt6: HighDpiScaleFactorRoundingPolicy is the recommended knob.
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough  # type: ignore[attr-defined]
            )
        except (AttributeError, TypeError):
            # PyQt5 (or an older PyQt6 build): fall back to the AA_* attributes.
            try:
                QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore[attr-defined]
                QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore[attr-defined]
            except AttributeError:
                pass  # Qt version has no HiDPI API — safe to ignore

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)

    # ── Global exception hook ─────────────────────────────────────────
    # In PyQt6, an unhandled Python exception inside a connected slot is
    # re-raised in the GUI thread and can escape app.exec(), causing the
    # process to print a traceback to a briefly-visible console window on
    # Windows and then exit.  This hook catches anything that slips through
    # and writes it to star_crash.log next to the settings file so the user
    # can read it after the window closes.
    _log_path = SETTINGS_FILE.parent / "star_crash.log"

    def _excepthook(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
        import traceback as _tb

        msg = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
        # Write to log file first (always succeeds).
        try:
            _log_path.write_text(msg, encoding="utf-8")
        except Exception:
            pass
        # Try to show a Qt message box.
        try:
            QMessageBox.critical(
                None,
                f"{APP_NAME} — Unexpected Error",
                f"An unexpected error occurred.\n\n"
                f"{msg[:1200]}\n\n"
                f"Full details saved to:\n{_log_path}",
            )
        except Exception:
            pass  # if Qt itself is broken, silently give up

    sys.excepthook = _excepthook

    class StarWindow(QMainWindow):
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

        # Per-theme CSS colors used by _md_to_html and _apply_qt_theme.
        _PALETTES: Dict[str, Dict[str, str]] = {
            "dark": {
                "bg": "#16181d",
                "fg": "#c6ccd4",
                "sel": "#2c313a",
                "h1": "#82aaff",
                "h2": "#89ddff",
                "h3": "#c792ea",
                "h4": "#f78c6c",
                "code": "#7fdbab",
            },
            "light": {
                "bg": "#fafafa",
                "fg": "#24273a",
                "sel": "#bcd0f0",
                "h1": "#1e66f5",
                "h2": "#209fb5",
                "h3": "#8839ef",
                "h4": "#e64553",
                "code": "#40a02b",
            },
            "contrast": {
                "bg": "#000000",
                "fg": "#ffffff",
                "sel": "#404040",
                "h1": "#ffff00",
                "h2": "#00ffff",
                "h3": "#ff80ff",
                "h4": "#80ff80",
                "code": "#00ff80",
            },
            "phosphor": {
                "bg": "#001200",
                "fg": "#00cc00",
                "sel": "#004400",
                "h1": "#00ff00",
                "h2": "#00ee00",
                "h3": "#00cc00",
                "h4": "#00aa00",
                "code": "#009900",
            },
        }

        def __init__(self) -> None:
            super().__init__()
            self.settings = settings
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
            # Hide the blinking text cursor — this is a reader, not an editor.
            self.editor.setCursorWidth(0)
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
            tb = self.addToolBar("Controls")
            tb.setMovable(False)

            def _act(label: str, shortcut: str, fn: Callable, tip: str = "") -> None:
                """Add one clickable button to the toolbar.

                Toolbar buttons intentionally carry **no** keyboard shortcut:
                every command's shortcut lives on its menu action instead, so
                each shortcut is owned by exactly one QAction (Qt fires neither
                action when two share a shortcut).  The *shortcut* argument is
                kept only so the tooltips can advertise the menu's binding.
                """
                a = QAction(label, self)
                a.setToolTip(tip or label)
                a.triggered.connect(fn)
                tb.addAction(a)

            # ── File ─────────────────────────────────────────────
            _act("Open", "Ctrl+O", self._open_dialog, "Open a file (Ctrl+O)")
            _act("URL", "", self._qt_open_url, "Open a URL")
            tb.addSeparator()
            # ── Playback ──────────────────────────────────────
            _act(
                "Play/Pause ▶⏸",
                "Space",
                self._tts_toggle,
                "Play / pause speech (Space)",
            )
            _act("Stop ■", "Escape", self._tts_stop, "Stop speech (Escape)")
            _act(
                "− Speed",
                "Ctrl+-",
                lambda: self._rate_change(-20),
                "Slow down −20 wpm (Ctrl+−)",
            )
            _act(
                "+ Speed",
                "Ctrl+=",
                lambda: self._rate_change(+20),
                "Speed up +20 wpm (Ctrl+=)",
            )
            tb.addSeparator()
            # ── Navigate ──────────────────────────────────────
            # Sentence: previous  replay  next
            _act("◀ S", "", self._qt_skip_prev_sentence, "Previous sentence (,)")
            _act("↺ S", "", self._qt_replay_sentence, "Replay sentence (;)")
            _act("S ▶", "", self._qt_skip_next_sentence, "Next sentence (.)")
            # Paragraph: previous  replay  next
            _act("◀ ¶", "", self._qt_skip_prev_paragraph, "Previous paragraph ([)")
            _act("↺ ¶", "", self._qt_replay_paragraph, "Replay paragraph (r)")
            _act("¶ ▶", "", self._qt_skip_next_paragraph, "Next paragraph (])")
            # Heading: previous  next  (always starts reading)
            _act(
                "◀ H",
                "",
                self._qt_read_prev_heading,
                "Previous heading — read aloud (<)",
            )
            _act("H ▶", "", self._qt_read_next_heading, "Next heading — read aloud (>)")
            tb.addSeparator()
            # ── Voice / cursor mode ───────────────────────────
            _act(
                "Voice…",
                "Ctrl+Shift+V",
                self._voice_picker_qt,
                "Select TTS voice (Ctrl+Shift+V)",
            )
            _act(
                "SC ○",
                "Tab",
                lambda: self._qt_sc_exit() if self._qt_sc_mode else self._qt_sc_enter(),
                "Speech cursor mode — line-by-line reading (Tab)",
            )
            tb.addSeparator()
            # ── Text ───────────────────────────────────────────
            _act(
                "Copy", "Ctrl+C", self._qt_copy, "Copy selection or paragraph (Ctrl+C)"
            )
            _act(
                "Highlight",
                "",  # Ctrl+H is now heading navigation
                self._qt_highlight,
                "Highlight selection in yellow",
            )
            _act(
                "Clear Highlights",
                "",
                self._qt_highlight_clear,
                "Remove all highlights from this document",
            )
            tb.addSeparator()
            # ── Edit ─────────────────────────────────────────
            _act(
                "Edit", "Ctrl+E", self._qt_edit_mode_toggle, "Toggle edit mode (Ctrl+E)"
            )
            _act("Save", "Ctrl+S", self._qt_save, "Save document (Ctrl+S)")
            tb.addSeparator()
            # ── View ─────────────────────────────────────────
            _act("Theme", "F5", self._next_theme, "Cycle color theme (F5)")
            _act(
                "ToC",
                "Ctrl+\\",
                self._qt_toggle_toc,
                "Toggle Contents panel (Ctrl+\\\\)",
            )
            _act(
                "Notes",
                "",  # Ctrl+Shift+N is bound as a window-level shortcut
                self._qt_toggle_annotations,
                "Toggle Notes panel (Ctrl+Shift+N)",
            )
            _act(
                "+ Note",
                "",  # Ctrl+Shift+A is bound as a window-level shortcut
                self._qt_add_annotation,
                "Add a note at the cursor (Ctrl+Shift+A)",
            )
            _act(
                "Level", "Ctrl+L", self._qt_reading_level, "Show reading level (Ctrl+L)"
            )
            _act("Font", "", self._qt_change_font_dialog, "Change display font")
            tb.addSeparator()
            # ── App ──────────────────────────────────────────
            _act("Help", "F1", self._show_about, "Open README.md (F1)")
            _act("Quit", "Ctrl+Q", self.close, "Quit star (Ctrl+Q)")

            # ── Menu bar ─────────────────────────────────────────────────────
            mb = self.menuBar()

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
                a = QAction(label, self)
                if checkable:
                    a.setCheckable(True)
                    a.setChecked(checked)
                if tip:
                    a.setToolTip(tip)
                a.triggered.connect(lambda _checked=False, f=fn: f())
                if shortcut:
                    a.setShortcut(self._resolve_shortcut(shortcut))
                    self._shortcut_actions.append((label, a, shortcut))
                return a

            # File menu
            file_menu: QMenu = mb.addMenu("File")
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
                    "Library / Bookshelf…",
                    "Ctrl+Shift+B",
                    self._qt_library,
                    tip="Browse opened documents with progress",
                )
            )
            file_menu.addSeparator()

            export_menu: QMenu = file_menu.addMenu("Export")
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
            hl_menu: QMenu = mb.addMenu("Highlight")
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
            notes_menu: QMenu = mb.addMenu("Notes")
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
                menu = mb.addMenu(title)
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

            # View menu
            view_menu: QMenu = mb.addMenu("View")
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
            aids_menu: QMenu = view_menu.addMenu("Reading Aids")
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

            # Tools menu — transcription, dictation, and maintenance.
            tools_menu: QMenu = mb.addMenu("Tools")
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

            # ── Table of Contents dock ─────────────────
            self._toc_dock = QDockWidget("Contents", self)
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
            self._annot_dock = QDockWidget("Notes", self)
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
            self._annot_filter.setPlaceholderText("Filter notes — text or #tag…")
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
                _b = QPushButton(_lbl)
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

        # ── Document loading ─────────────────────────────────────────────────────

        def _qt_open_url(self) -> None:
            """Prompt for a URL and open it as a document."""
            url, ok = QInputDialog.getText(self, "Open URL", "Enter a web address:")
            if ok and url.strip():
                self._open_path(url.strip())

        def _open_dialog(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Document",
                "",
                "All Supported "
                "(*.pdf *.doc *.dot *.docx *.ppt *.pptx *.odt "
                "*.epub *.html *.htm *.md *.txt "
                "*.rst *.rest *.adoc *.asciidoc *.asc "
                "*.wiki *.mediawiki *.textile *.creole "
                "*.tex *.ltx *.org "
                "*.csv *.tsv *.xlsx *.r *.rmd)"
                ";;Word / PowerPoint (*.doc *.dot *.docx *.ppt *.pptx)"
                ";;Wiki / Markup "
                "(*.rst *.rest *.adoc *.asciidoc *.asc "
                "*.wiki *.mediawiki *.textile *.creole)"
                ";;LaTeX (*.tex *.ltx)"
                ";;Org-mode (*.org)"
                ";;PDF (*.pdf)"
                ";;All Files (*)",
            )
            if path:
                self._open_path(path)

        def _open_path(self, path: str) -> None:
            # Save where we were in the *current* document before replacing it.
            self._qt_save_reading_position()
            self.statusBar().showMessage(f"Loading {Path(path).name} …")
            QApplication.processEvents()
            self._pending_doc: Optional[Document] = None

            def _work() -> None:
                try:
                    self._pending_doc = load_document(path, self.settings)
                except Exception as _exc:  # noqa: BLE001
                    # Never let the background thread die silently and leave
                    # the UI frozen.  Create a minimal error document instead
                    # so _on_doc_loaded always has something to display.
                    _err = Document(
                        path=path,
                        title=f"Error — {Path(path).name}",
                        markdown=(
                            f"# Could not open {Path(path).name}\n\n"
                            f"```\n{_exc}\n```\n\n"
                            "Check that the file exists and is not locked."
                        ),
                        plain_text=str(_exc),
                        format="error",
                    )
                    self._pending_doc = _err
                # Signal the GUI thread to call _on_doc_loaded.
                # Using a pyqtSignal guarantees safe cross-thread delivery;
                # QMetaObject.invokeMethod with a plain string requires the
                # method to be a registered @pyqtSlot and fails silently on
                # Windows when that registration is missing.
                self._doc_loaded_signal.emit()

            threading.Thread(target=_work, daemon=True).start()

        def _on_doc_loaded(self) -> None:
            # Wrap the entire slot body so that any exception is caught here
            # rather than propagating through PyQt6’s event loop and crashing
            # app.exec() — the symptom on Windows is a brief console window
            # that closes too quickly to read the traceback.
            try:
                self._on_doc_loaded_impl()
            except Exception as _exc:  # noqa: BLE001
                import traceback as _tb

                detail = _tb.format_exc()
                self.statusBar().showMessage(f"Error displaying document: {_exc}")
                try:
                    QMessageBox.critical(
                        self,
                        "Document Display Error",
                        f"Could not display the document.\n\n{detail[:1000]}",
                    )
                except Exception:
                    pass

        def _on_doc_loaded_impl(self) -> None:
            """Inner implementation of _on_doc_loaded, called inside a
            try/except wrapper to prevent slot exceptions from escaping
            into the Qt event loop."""
            doc = getattr(self, "_pending_doc", None)
            if not doc:
                return
            self.doc = doc
            self.editor.setHtml(self._md_to_html(doc.markdown or ""))
            self._apply_block_spacing()  # line-height (reset by setHtml)
            self.editor.setExtraSelections([])  # clear leftover TTS highlights
            # Build the ToC panel from the new document's headings.
            self._qt_build_toc()
            # Populate the Notes panel from saved annotations for this document.
            self._qt_build_annotations()
            # Restore any saved user highlights for this document.
            self._qt_apply_user_highlights()
            # Rebuild the difficult-word overlay for the new document (no-op
            # unless the overlay is toggled on); also repaints the highlights.
            self._qt_refresh_vocab_highlight()

            # Read Qt plain text NOW (main thread required) then hand off.
            qt_plain = self.editor.document().toPlainText()

            def _build() -> None:
                try:
                    plain = doc.plain_text or ""
                    # TTSManager word map (line-based, used for timer highlighting)
                    flat = qt_plain.splitlines()
                    doc.word_map = _build_word_map(plain, flat)
                    self.tts_manager.set_word_map(doc.word_map)
                    # Qt char-offset map (used by _apply_word_highlight)
                    self._build_qt_word_map(plain, qt_plain)
                    # Sentence map — same algorithm as StarApp._build_sentence_map
                    wm = doc.word_map
                    if wm and plain:
                        char_starts = [0]
                        for _m in _SENTENCE_SPLIT_RE.finditer(plain):
                            char_starts.append(_m.end())
                        _wi = 0
                        word_starts: List[int] = []
                        for cs in char_starts:
                            while _wi < len(wm) and wm[_wi].tts_offset < cs:
                                _wi += 1
                            word_starts.append(min(_wi, len(wm) - 1))
                        seen: set = set()
                        result: List[int] = []
                        for ws in word_starts:
                            if ws not in seen:
                                seen.add(ws)
                                result.append(ws)
                        self._qt_sentence_starts = result if result else [0]
                    # Signal the main thread to restore the reading position
                    # now that the word map and sentence map are both ready.
                    self._restore_signal.emit()
                except Exception:
                    pass  # word map is best-effort; TTS works without it

            threading.Thread(target=_build, daemon=True).start()
            # Record this document in the library / bookshelf.
            _record_library(self.settings, doc)
            self.statusBar().showMessage(f"Opened: {doc.title}")

        # ── Word-position mapping ─────────────────────────────────────────

        def _build_qt_word_map(self, plain_text: str, qt_text: str) -> None:
            """Populate self._qt_word_map: a list where index i is the
            absolute character offset of the i-th TTS word inside the Qt
            document text.

            Uses a rolling forward search so that repeated words match in
            document order.  Runs in a background thread (no Qt calls).

            Words whose only occurrence in the document text is *before*
            search_from (e.g. column-header names repeated in structured
            table-row narration) are assigned last_good_pos so the highlight
            advances linearly rather than jumping backward to the header row.
            """
            result: List[int] = []
            qt_lower = qt_text.lower()
            token_re = re.compile(r"\b\w[\w'-]*")
            search_from = 0
            last_good_pos = 0  # last position from a forward-matched word

            for m in token_re.finditer(plain_text):
                word = m.group().lower()
                pos = qt_lower.find(word, search_from)
                if pos >= 0:
                    result.append(pos)
                    search_from = pos + 1  # advance past this occurrence
                    last_good_pos = pos
                else:
                    # Forward search failed.  Check if the word exists at all.
                    global_pos = qt_lower.find(word, 0)
                    if global_pos >= 0:
                        # Only a backward match exists (e.g. a table column
                        # header repeated in row narration).  Use last_good_pos
                        # so the highlight doesn't jump back to the header.
                        result.append(last_good_pos)
                    else:
                        result.append(0)  # not found anywhere
                    # Don't update search_from; we haven't moved forward.

            self._qt_word_map = result

        # ── HTML rendering ────────────────────────────────────────────────

        def _effective_palette(self, theme_name: str) -> Dict[str, Any]:
            """Return the palette dict for *theme_name*.

            Lookup order:
              1. Custom CSS themes loaded from THEMES_DIR (have key '_css').
              2. Built-in _PALETTES.
              3. Fallback: dark built-in palette.

            Uses getattr so this method is safe to call even before
            _css_themes is assigned (e.g. during very early init).
            """
            css_themes: Dict[str, Any] = getattr(self, "_css_themes", {})
            if theme_name in css_themes:
                return css_themes[theme_name]
            return self._PALETTES.get(theme_name, self._PALETTES["dark"])

        @property
        def _all_theme_names(self) -> List[str]:
            """Built-in theme names followed by any custom CSS theme names."""
            extra = [n for n in sorted(self._css_themes) if n not in THEME_NAMES]
            return THEME_NAMES + extra

        def _md_to_html(self, md: str) -> str:
            """Convert internal Markdown to styled HTML for QTextEdit.

            When the active theme came from a CSS file the raw CSS is
            injected verbatim so every selector the user wrote is honored.
            For built-in palettes the CSS is generated from the palette dict.
            """
            theme_name = self.settings.get("theme", "dark")
            pal = self._effective_palette(theme_name)
            custom_css: str = str(pal.get("_css", ""))

            out: List[str] = []
            for line in (md or "").splitlines():
                if line.startswith("# "):
                    out.append(f"<h1>{line[2:]}</h1>")
                elif line.startswith("## "):
                    out.append(f"<h2>{line[3:]}</h2>")
                elif line.startswith("### "):
                    out.append(f"<h3>{line[4:]}</h3>")
                elif line.startswith("#### "):
                    out.append(f"<h4>{line[5:]}</h4>")
                elif not line.strip():
                    out.append("<br>")
                else:
                    line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
                    line = re.sub(r"\*(.+?)\*", r"<i>\1</i>", line)
                    line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
                    out.append(f"<p>{line}</p>")
            body = "\n".join(out)
            # Bionic-reading: embolden the leading part of each word so the
            # eye is pulled forward through the text (a dyslexia reading aid).
            if self.settings.get("qt_bionic_reading", False):
                body = self._bionic_html(body)
            fam = self._effective_font_family()
            if custom_css:
                style = custom_css
            else:
                style = (
                    f"body{{background:{pal['bg']};color:{pal['fg']};"
                    f"      font-family:{fam},sans-serif;margin:14px;}}"
                    f"h1{{color:{pal['h1']}}}"
                    f"h2{{color:{pal['h2']}}}"
                    f"h3{{color:{pal['h3']}}}"
                    f"h4{{color:{pal['h4']}}}"
                    f"code{{color:{pal['code']};font-family:monospace;}}"
                )
            return (
                "<html><head><style>" + style + "</style></head>"
                f"<body>{body}</body></html>"
            )

        # ── Reading accessibility: fonts, spacing & reading aids ──────────

        # Candidate dyslexia-friendly families, in order of preference.
        # OpenDyslexic is purpose-built; the others are widely available
        # fallbacks with the high legibility traits dyslexic readers benefit
        # from (open apertures, distinct letterforms, generous spacing).
        _DYSLEXIA_FONTS = (
            "OpenDyslexic",
            "OpenDyslexic3",
            "OpenDyslexicAlta",
            "Atkinson Hyperlegible",
            "Lexend",
            "Lexend Deca",
            "Comic Sans MS",
            "Comic Neue",
        )

        def _find_dyslexia_font(self) -> str:
            """Return the first installed dyslexia-friendly family, or "".

            QFontDatabase.families() is a static method in PyQt6 but an
            instance method in PyQt5, so both call styles are attempted.
            """
            try:
                fams = QFontDatabase.families()  # PyQt6 (static)
            except TypeError:
                fams = QFontDatabase().families()  # PyQt5 (instance)
            except Exception:
                return ""
            available = {str(f).lower() for f in fams}
            for cand in self._DYSLEXIA_FONTS:
                if cand.lower() in available:
                    return cand
            return ""

        def _effective_font_family(self) -> str:
            """The display family, honoring the dyslexia-font preference.

            When 'qt_dyslexia_font' is on and a dyslexia-friendly family is
            installed it wins; otherwise the user's chosen family is used.
            """
            if self.settings.get("qt_dyslexia_font", False):
                fam = self._find_dyslexia_font()
                if fam:
                    return fam
            return str(self.settings.get("qt_font_family", "Georgia"))

        def _make_editor_font(self) -> "QFont":
            """Construct the editor's base QFont from family, size, and the
            letter/word-spacing accessibility settings.

            Letter and word spacing are applied through QFont (Qt's rich-text
            CSS subset does not support letter-spacing/word-spacing), while
            line height is applied separately via _apply_block_spacing.
            """
            fam = self._effective_font_family()
            size = int(self.settings.get("font_size", 0)) or int(
                self.settings.get("qt_font_size", 14)
            )
            f = QFont(fam, max(6, size))
            ls = float(self.settings.get("qt_letter_spacing", 0.0))
            # PercentageSpacing: 100 == normal; we store *extra* percent.
            f.setLetterSpacing(_PCT_SPACING, 100.0 + ls)
            ws = float(self.settings.get("qt_word_spacing", 0.0))
            f.setWordSpacing(ws)
            return f

        def _apply_block_spacing(self) -> None:
            """Apply the line-height multiplier to every block in the document.

            Run after each setHtml() because block formats are per-document
            and are reset whenever the HTML is replaced.
            """
            try:
                mult = float(self.settings.get("qt_line_height", 1.5))
            except (TypeError, ValueError):
                mult = 1.5
            pct = max(100.0, mult * 100.0)
            cur = QTextCursor(self.editor.document())
            cur.select(_DOC_SELECTION)
            bf = QTextBlockFormat()
            # setLineHeight's second arg is an int height-type.  PyQt5 enums
            # are plain ints; PyQt6 enums expose the int via .value.
            ht = getattr(_PROPORTIONAL, "value", _PROPORTIONAL)
            bf.setLineHeight(pct, int(ht))
            cur.mergeBlockFormat(bf)

        def _apply_text_spacing(self) -> None:
            """Re-apply font (letter/word spacing) and block (line-height)
            spacing to the live document, then refresh."""
            self.editor.setFont(self._make_editor_font())
            self._apply_block_spacing()

        def _bionic_word(self, m: "re.Match") -> str:
            """Embolden the leading ~40% of a single word for bionic reading."""
            w = m.group(0)
            if len(w) <= 1:
                return f"<b>{w}</b>"
            n = max(1, round(len(w) * 0.4))
            return f"<b>{w[:n]}</b>{w[n:]}"

        def _bionic_html(self, html: str) -> str:
            """Apply bionic-reading emphasis to the text runs of an HTML body.

            Splits on tags and HTML entities so markup and entities are left
            intact; text inside <code> spans is skipped (code stays verbatim).
            """
            parts = re.split(r"(<[^>]+>|&[a-zA-Z]+;|&#\d+;)", html)
            in_code = False
            out: List[str] = []
            word_re = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
            for p in parts:
                if not p:
                    continue
                if p.startswith("<"):
                    low = p.lower()
                    if low.startswith("<code"):
                        in_code = True
                    elif low.startswith("</code"):
                        in_code = False
                    out.append(p)
                elif p.startswith("&"):
                    out.append(p)  # HTML entity — leave untouched
                elif in_code:
                    out.append(p)
                else:
                    out.append(word_re.sub(self._bionic_word, p))
            return "".join(out)

        def _rebuild_hl_fmt(self) -> None:
            """Rebuild the spoken-word highlight format from the user's
            'highlight_style' and 'highlight_color' settings.

            Styles: background (filled), underline, box (wavy underline),
            bold (colored bold text), color (colored text).
            """
            style = str(self.settings.get("highlight_style", "background"))
            color = QColor(str(self.settings.get("highlight_color", "cyan")))
            if not color.isValid():
                color = QColor("#06b6d4")  # cyan-500 fallback
            fmt = QTextCharFormat()
            if style == "underline":
                fmt.setFontUnderline(True)
                fmt.setUnderlineColor(color)
                fmt.setUnderlineStyle(_SINGLE_UNDERLINE)
                fmt.setFontWeight(700)
            elif style == "box":
                fmt.setUnderlineColor(color)
                fmt.setUnderlineStyle(_WAVE_UNDERLINE)
                fmt.setFontWeight(700)
            elif style == "bold":
                fmt.setForeground(color)
                fmt.setFontWeight(900)
            elif style == "color":
                fmt.setForeground(color)
                fmt.setFontWeight(700)
            else:  # "background" (default)
                fmt.setBackground(color)
                # Pick a readable foreground based on the fill's luminance.
                lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
                fmt.setForeground(QColor("#000000" if lum > 140 else "#ffffff"))
                fmt.setFontWeight(700)
            self._hl_fmt = fmt

        # ── TTS controls ──────────────────────────────────────────────────

        def _refresh_hl_callback(self) -> None:
            """Re-register the TTS highlight callback, capturing the current
            session number.

            Every new speech invocation must call this *after* incrementing
            self._hl_session so that the closed-over ``_s`` value matches the
            session that _apply_word_highlight expects.  Any emission still in
            the Qt event queue from a prior session carries the old ``_s`` and
            is therefore silently dropped by _apply_word_highlight.
            """
            _s = self._hl_session
            self.tts_manager.set_on_highlight(
                lambda idx, __s=_s: self._word_signal.emit(idx, __s)
            )

        def _tts_play(self) -> None:
            """Start speech from the beginning (word 0)."""
            if not self.doc:
                return
            self._hl_session += 1  # new session — must come first
            self._refresh_hl_callback()  # re-wire before any stop/speak
            self.editor.setExtraSelections([])  # clear stale highlight
            self.tts_manager.stop()
            self._tts_paused_at_word = -1
            wm = getattr(self.doc, "word_map", [])
            text_offset = wm[0].tts_offset if wm else 0
            text_slice = self.doc.plain_text[text_offset:]
            self.tts_manager.speak(
                text_slice, start_word_idx=0, text_offset=text_offset
            )
            self.statusBar().showMessage(
                f"Reading at {self.settings['tts_rate']} wpm …"
            )

        def _tts_play_from_word(self, word_idx: int) -> None:
            """Resume or start speech from a specific word-map index."""
            if not self.doc:
                return
            self._hl_session += 1  # new session — must come first
            self._refresh_hl_callback()  # re-wire before any stop/speak
            self.editor.setExtraSelections([])
            self.tts_manager.stop()
            self._tts_paused_at_word = -1
            wm = getattr(self.doc, "word_map", [])
            if wm and word_idx < len(wm):
                text_offset = wm[word_idx].tts_offset
            else:
                text_offset = 0
                word_idx = 0
            text_slice = self.doc.plain_text[text_offset:]
            self.tts_manager.speak(
                text_slice, start_word_idx=word_idx, text_offset=text_offset
            )
            self.statusBar().showMessage(
                f"Resuming at {self.settings['tts_rate']} wpm …"
            )

        def _qt_play_from_cursor(self) -> None:
            """Start speech from the current text-cursor or selection position.

            If text is selected (e.g. the user click-dragged or used
            Shift+arrow), speech begins at the *start* of the selection so
            the user hears the passage they highlighted.  If there is no
            selection, speech begins at the plain cursor position (the
            word whose character offset is closest to or just after the
            cursor).

            Shortcut: Ctrl+Return.
            """
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            cursor = self.editor.textCursor()
            # Use selection start so clicking and highlighting a passage
            # then pressing Ctrl+Return reads from the top of the highlight.
            char_pos = (
                cursor.selectionStart() if cursor.hasSelection() else cursor.position()
            )
            word_idx = self._qt_char_to_word(char_pos)
            self._tts_play_from_word(word_idx)

        def _tts_toggle(self) -> None:
            """Pause/resume speech (Space bar).

            * While speaking → pause, saving the current word so the next
              press resumes from exactly that word.
            * While paused   → resume from the saved word index.
            * While stopped  → start from the beginning.
            """
            if self.tts_manager.speaking:
                saved = self.tts_manager.current_word_idx
                self._tts_stop()  # clears _tts_paused_at_word
                if saved >= 0:
                    self._tts_paused_at_word = saved
            elif self._tts_paused_at_word >= 0:
                w = self._tts_paused_at_word
                self._tts_paused_at_word = -1
                self._tts_play_from_word(w)
            else:
                self._tts_play()

        def _tts_stop(self) -> None:
            """Full stop — saves position, clears speech."""
            self._qt_save_reading_position()
            self.tts_manager.stop()
            self.editor.setExtraSelections([])  # clear highlight immediately
            self._tts_paused_at_word = -1
            self.statusBar().showMessage("Stopped.")

        # ── Word highlight (called on GUI thread via _word_signal) ─────────

        def _apply_word_highlight(self, word_idx: int, session: int) -> None:
            """Paint the currently spoken word using QTextEdit.setExtraSelections().

            setExtraSelections() is non-destructive: it does not modify the
            document, does not touch the undo stack, and is cleared simply
            by passing an empty list.  User highlights are merged so they
            are not erased on each TTS word advance.

            The *session* parameter is compared against self._hl_session to
            reject stale deliveries.  Qt's QueuedConnection buffers signal
            emissions; when _tts_play_from_word() starts a new utterance, a
            signal from the *old* timer that was already in the queue can
            fire AFTER the viewport has scrolled to the ToC target and
            immediately scroll it back.  Dropping any delivery whose session
            doesn't match the current one eliminates that race entirely.
            """
            # Discard stale deliveries from superseded speech sessions.
            if session != self._hl_session:
                return

            # Build base list from persistent user highlights so they are
            # never erased by TTS word advances.
            selections = self._get_user_highlight_selections()

            if word_idx < 0 or not self._qt_word_map:
                self.editor.setExtraSelections(selections)
                return

            # Lead/lag tuning: shift the *visual* highlight ahead of (or
            # behind) the spoken word so the cursor can be made to anticipate
            # the audio for users who track best slightly ahead.
            try:
                lead = int(self.settings.get("highlight_lead_words", 0))
            except (TypeError, ValueError):
                lead = 0
            vis_idx = word_idx + lead
            vis_idx = max(0, min(vis_idx, len(self._qt_word_map) - 1))

            char_pos = self._qt_word_map[vis_idx]

            # Word length from the word map built in _build_qt_word_map.
            word_len = 1
            if self.doc and vis_idx < len(self.doc.word_map):
                word_len = max(1, self.doc.word_map[vis_idx].tts_len)

            # Clamp to actual document length.
            doc_obj = self.editor.document()
            doc_len = doc_obj.characterCount()
            if char_pos >= doc_len:
                return
            word_len = min(word_len, doc_len - char_pos - 1)
            if word_len <= 0:
                return

            # Build the selection cursor that spans exactly this word.
            cursor = QTextCursor(doc_obj)
            cursor.setPosition(char_pos)
            cursor.setPosition(char_pos + word_len, _KEEP_ANCHOR)

            # Optional current-line band: a full-width tint behind the line
            # being read, drawn *under* the word highlight (a reading aid).
            if self.settings.get("qt_current_line_highlight", False):
                pal = self._effective_palette(self.settings.get("theme", "dark"))
                band = QColor(str(pal.get("sel", "#2c313a")))
                line_fmt = QTextCharFormat()
                line_fmt.setBackground(band)
                # Property id is an int; PyQt6 enums expose it via .value.
                _fw = getattr(_FULL_WIDTH_SEL, "value", _FULL_WIDTH_SEL)
                line_fmt.setProperty(int(_fw), True)
                line_cur = QTextCursor(doc_obj)
                line_cur.setPosition(char_pos)
                line_sel = QTextEdit.ExtraSelection()
                line_sel.format = line_fmt
                line_sel.cursor = line_cur
                selections = selections + [line_sel]

            # Sentence-level highlight.  Resolve the character
            # span of the sentence containing this word.  In "sentence" mode
            # the whole sentence carries the highlight format; in "both" mode
            # the sentence gets a softer band and the word is marked on top.
            gran = str(self.settings.get("highlight_granularity", "word"))
            sent_cursor = None
            if gran in ("sentence", "both") and self._qt_sentence_starts:
                ss = self._qt_sentence_starts
                si = self._qt_find_sentence_idx(vis_idx)
                s_word = ss[si] if si < len(ss) else vis_idx
                e_word = (
                    ss[si + 1] - 1 if si + 1 < len(ss) else len(self._qt_word_map) - 1
                )
                s_word = max(0, min(s_word, len(self._qt_word_map) - 1))
                e_word = max(s_word, min(e_word, len(self._qt_word_map) - 1))
                s_char = self._qt_word_map[s_word]
                e_char = self._qt_word_map[e_word]
                e_len = 1
                if self.doc and e_word < len(self.doc.word_map):
                    e_len = max(1, self.doc.word_map[e_word].tts_len)
                e_char = min(e_char + e_len, doc_len - 1)
                if e_char > s_char:
                    sent_cursor = QTextCursor(doc_obj)
                    sent_cursor.setPosition(s_char)
                    sent_cursor.setPosition(e_char, _KEEP_ANCHOR)

            if gran == "sentence" and sent_cursor is not None:
                # Highlight the entire sentence; no separate per-word mark.
                sel = QTextEdit.ExtraSelection()
                sel.format = self._hl_fmt
                sel.cursor = sent_cursor
                self.editor.setExtraSelections(selections + [sel])
            elif gran == "both" and sent_cursor is not None:
                # Softer band over the sentence + the word marked on top.
                pal = self._effective_palette(self.settings.get("theme", "dark"))
                band_fmt = QTextCharFormat()
                band_fmt.setBackground(QColor(str(pal.get("sel", "#2c313a"))))
                band_sel = QTextEdit.ExtraSelection()
                band_sel.format = band_fmt
                band_sel.cursor = sent_cursor
                word_sel = QTextEdit.ExtraSelection()
                word_sel.format = self._hl_fmt
                word_sel.cursor = cursor
                self.editor.setExtraSelections(selections + [band_sel, word_sel])
            else:
                # Word-level (default).  Wrap format + cursor in an
                # ExtraSelection and apply, prepending the persistent user
                # highlights (and line band).
                sel = QTextEdit.ExtraSelection()
                sel.format = self._hl_fmt
                sel.cursor = cursor
                self.editor.setExtraSelections(selections + [sel])

            # Scroll so the highlighted word is always visible.
            # setTextCursor + ensureCursorVisible is the reliable approach;
            # the cursor width is 0 so no blinking caret is visible.
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

            # Status bar: word text + reading progress.
            if self.doc and word_idx < len(self.doc.word_map):
                word_text = self.doc.word_map[word_idx].word
                pct = int(100 * word_idx / max(1, len(self.doc.word_map)))
                self.statusBar().showMessage(
                    f"▶  “{word_text}”  —  {pct}%  —  {self.settings['tts_rate']} wpm"
                )

        # ── Speech Cursor mode (Qt) ─────────────────────────────────────

        def _key_enums(self) -> Tuple[Any, ...]:
            """Resolve and cache the Qt event-type / Control-key enums once.

            Returns ``(KeyPress, KeyRelease, ShortcutOverride, Shortcut,
            Key_Control)`` for whichever PyQt binding is active.
            """
            if self._key_enum_cache is not None:
                return self._key_enum_cache
            try:
                from PyQt6.QtCore import QEvent

                ET = QEvent.Type
                vals = (
                    ET.KeyPress,
                    ET.KeyRelease,
                    ET.ShortcutOverride,
                    ET.Shortcut,
                    Qt.Key.Key_Control,
                )
            except (ImportError, AttributeError):
                from PyQt5.QtCore import QEvent  # type: ignore

                vals = (
                    QEvent.KeyPress,  # type: ignore[attr-defined]
                    QEvent.KeyRelease,  # type: ignore[attr-defined]
                    QEvent.ShortcutOverride,  # type: ignore[attr-defined]
                    QEvent.Shortcut,  # type: ignore[attr-defined]
                    Qt.Key_Control,  # type: ignore[attr-defined]
                )
            self._key_enum_cache = vals
            return vals

        def _ctrl_tap_track(self, event: Any) -> None:
            """JAWS-style bare-Ctrl tap → play/pause.

            Tracks Ctrl key presses/releases on the editor.  A clean tap
            (Ctrl pressed and released with no other key, shortcut-override,
            or fired shortcut in between) toggles speech.  Using Ctrl as a
            modifier in a chord never triggers it.  Opt out via the
            ``qt_ctrl_pause`` setting.
            """
            if not self.settings.get("qt_ctrl_pause", True):
                return
            kp, kr, so, sh, k_ctrl = self._key_enums()
            et = event.type()
            if et == sh:
                # A shortcut fired — Ctrl was part of a chord, not a tap.
                self._ctrl_solo = False
                return
            if et in (kp, so):
                try:
                    k = event.key()
                    repeat = event.isAutoRepeat()
                except Exception:
                    return
                if et == kp and k == k_ctrl and not repeat:
                    self._ctrl_solo = True
                    self._ctrl_press_t = time.monotonic()
                elif k != k_ctrl:
                    # Any other key (or shortcut-override) cancels the tap.
                    self._ctrl_solo = False
            elif et == kr:
                try:
                    k = event.key()
                    repeat = event.isAutoRepeat()
                except Exception:
                    return
                if k == k_ctrl and not repeat:
                    tap = (
                        self._ctrl_solo
                        and (time.monotonic() - self._ctrl_press_t) < 0.6
                    )
                    self._ctrl_solo = False
                    if tap and not self._qt_edit_mode:
                        self._tts_toggle()

        def eventFilter(self, obj: Any, event: Any) -> bool:
            """Intercept keyboard events on the editor.

            Ctrl (tapped alone) — play / pause speech (JAWS habit)
            Tab    — enter / exit Speech Cursor mode
            While in SC mode:
              ↑ / ↓  — previous / next block, read it
              Enter  — exit SC mode and start continuous reading
              Esc    — exit SC mode, stop speech
            """
            if obj is not self.editor:
                return super().eventFilter(obj, event)

            # JAWS-style bare-Ctrl tap toggles speech (never consumes the event).
            self._ctrl_tap_track(event)

            try:
                from PyQt6.QtCore import QEvent  # noqa: F401

                kp = QEvent.Type.KeyPress
                Key = Qt.Key
            except (ImportError, AttributeError):
                from PyQt5.QtCore import QEvent  # type: ignore

                kp = QEvent.KeyPress  # type: ignore
                Key = Qt  # type: ignore

            if event.type() != kp:
                return super().eventFilter(obj, event)

            key = event.key()

            try:
                k_tab = Key.Key_Tab
                k_up = Key.Key_Up
                k_dn = Key.Key_Down
                k_esc = Key.Key_Escape
                k_ret = Key.Key_Return
                k_ent = Key.Key_Enter
            except AttributeError:  # PyQt5 uses Qt.Key_Tab etc. directly
                k_tab = Qt.Key_Tab  # type: ignore
                k_up = Qt.Key_Up  # type: ignore
                k_dn = Qt.Key_Down  # type: ignore
                k_esc = Qt.Key_Escape  # type: ignore
                k_ret = Qt.Key_Return  # type: ignore
                k_ent = Qt.Key_Enter  # type: ignore

            if key == k_tab:
                if self._qt_sc_mode:
                    self._qt_sc_exit()
                else:
                    self._qt_sc_enter()
                return True  # consume; don't let Tab move focus

            if not self._qt_sc_mode:
                return super().eventFilter(obj, event)

            if key in (k_esc,):
                self._qt_sc_exit()
                return True
            if key in (k_ret, k_ent):
                self._qt_sc_exit(start_reading=True)
                return True
            if key == k_up:
                self._qt_sc_move(-1)
                return True
            if key == k_dn:
                self._qt_sc_move(+1)
                return True

            return super().eventFilter(obj, event)

        def _qt_sc_enter(self) -> None:
            """Enter Qt Speech Cursor mode.

            Stops any running TTS, positions the reading cursor at the
            visible text-cursor position, and builds the persistent
            _SCReader engine so the first line has no startup lag.
            """
            self.tts_manager.stop()
            self.editor.setExtraSelections([])
            # Position SC cursor at the block under the text cursor.
            tc = self.editor.textCursor()
            self._qt_sc_block = tc.blockNumber()
            # Build the persistent reader so the first keystroke has no
            # SAPI5 engine-creation delay and stop() is always effective.
            if _PYTTSX3 and isinstance(self.tts_manager._backend, Pyttsx3Backend):
                self._qt_sc_reader = _SCReader(
                    rate=int(self.settings["tts_rate"]),
                    volume=float(self.settings["tts_volume"]),
                )
                self._qt_sc_reader.start()
            else:
                self._qt_sc_reader = None
            self._qt_sc_mode = True
            self._qt_sc_highlight()
            self.setWindowTitle(f"● SC CURSOR — {APP_TITLE}")
            self.statusBar().showMessage(
                "Speech Cursor ON  ↑↓:line  Enter:read-on  Esc/Tab:exit"
            )

        def _qt_sc_exit(self, start_reading: bool = False) -> None:
            """Exit Qt Speech Cursor mode.  Speech is always stopped first."""
            self._qt_sc_mode = False
            # Stop the persistent reader before stopping the main manager
            # so the SAPI5 engine is always reachable.
            if self._qt_sc_reader is not None:
                self._qt_sc_reader.close()
                self._qt_sc_reader = None
            self.tts_manager.stop()
            self.editor.setExtraSelections([])
            self.setWindowTitle(APP_TITLE)
            if start_reading:
                # Start continuous reading from the SC cursor position.
                doc_obj = self.editor.document()
                block = doc_obj.findBlockByNumber(self._qt_sc_block)
                if block.isValid():
                    char_pos = block.position()
                    wm = getattr(self.doc, "word_map", [])
                    if wm:
                        qwm = self._qt_word_map
                        wi = 0
                        for i, off in enumerate(qwm):
                            if off >= char_pos:
                                wi = i
                                break
                        self._tts_play_from_word(wi)
                        self.statusBar().showMessage(
                            f"Reading from line {self._qt_sc_block + 1}"
                        )
                        return
                self._tts_play()
            else:
                self.statusBar().showMessage("Speech Cursor OFF")

        def _qt_sc_move(self, delta: int) -> None:
            """Move the SC cursor by *delta* blocks and read the new block."""
            doc_obj = self.editor.document()
            n_blocks = doc_obj.blockCount()
            if n_blocks == 0:
                return
            self._qt_sc_block = max(0, min(self._qt_sc_block + delta, n_blocks - 1))
            self._qt_sc_highlight()
            self._qt_sc_read_block()

        def _qt_sc_highlight(self) -> None:
            """Highlight the current SC cursor block with a bar selection."""
            doc_obj = self.editor.document()
            block = doc_obj.findBlockByNumber(self._qt_sc_block)
            if not block.isValid():
                return
            tc = QTextCursor(block)
            self.editor.setTextCursor(tc)
            self.editor.ensureCursorVisible()
            tc2 = QTextCursor(block)
            tc2.select(
                QTextCursor.SelectionType.BlockUnderCursor
                if hasattr(QTextCursor, "SelectionType")
                else QTextCursor.BlockUnderCursor  # type: ignore
            )
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#313244"))
            sel = QTextEdit.ExtraSelection()
            sel.cursor = tc2
            sel.format = fmt
            self.editor.setExtraSelections([sel])

        def _qt_sc_read_block(self) -> None:
            """Speak the plain text of the current SC cursor block.

            Uses the persistent _SCReader when the pyttsx3 backend is
            active so that stop() is always effective and there is no
            200–500 ms SAPI5 engine-construction window between navigation
            keystrokes.  Falls back to direct backend.speak() for eSpeak
            and other subprocess-based backends where termination is
            trivially reliable.
            """
            doc_obj = self.editor.document()
            block = doc_obj.findBlockByNumber(self._qt_sc_block)
            text = block.text().strip() if block.isValid() else ""
            # Stop the main TTS manager (clears timer, highlight, etc.) then
            # drive speech through the SC reader or backend directly.
            self.tts_manager.stop()
            if not text:
                if self._qt_sc_reader is not None:
                    self._qt_sc_reader.speak("blank")
                else:
                    self.tts_manager._backend.speak("blank")
                self.statusBar().showMessage(
                    f"SC  —  line {self._qt_sc_block + 1}: (blank)"
                )
                return
            text = _preprocess_tts_text(text, self.settings)
            if self._qt_sc_reader is not None:
                self._qt_sc_reader.speak(text)
            else:
                self.tts_manager._backend.speak(text)
            self.statusBar().showMessage(
                f"SC  —  line {self._qt_sc_block + 1}: {text[:80]}"
            )

        # ── Navigation (sentence · paragraph · heading) ────────────────────────

        # ─ helpers ─────────────────────────────────────────────────────────

        def _qt_current_word_for_nav(self) -> int:
            """Best estimate of the current reading position (word index).

            Priority:
            1. Callback-confirmed audio word (most accurate when speaking).
            2. Timer estimate (when speaking but no callback yet).
            3. QTextEdit text-cursor position (when TTS is idle).
               The editor cursor is moved by _apply_word_highlight during TTS
               and by _qt_navigate_to_word during manual navigation, so it
               always reflects the last reading or navigation point.  This
               ensures _qt_save_reading_position records a useful position
               even after TTS has been stopped.
            """
            if self.tts_manager.speaking:
                cb = self.tts_manager.last_cb_word_idx
                if cb >= 0:
                    return cb
                idx = self.tts_manager.current_word_idx
                if idx >= 0:
                    return idx
            # TTS idle: derive position from the editor’s text cursor.
            qwm = self._qt_word_map
            if qwm:
                char_pos = self.editor.textCursor().position()
                for i, off in enumerate(qwm):
                    if off >= char_pos:
                        return i
                return len(qwm) - 1  # cursor is past the last mapped word
            return 0

        def _qt_find_sentence_idx(self, word_idx: int) -> int:
            """Binary-search _qt_sentence_starts for the sentence containing
            *word_idx* (same algorithm as StarApp._find_sentence_idx)."""
            ss = self._qt_sentence_starts
            lo, hi, result = 0, len(ss) - 1, 0
            while lo <= hi:
                mid = (lo + hi) // 2
                if ss[mid] <= word_idx:
                    result = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            return result

        def _qt_navigate_to_word(
            self, word_idx: int, always_play: bool = False
        ) -> None:
            """Stop TTS, scroll the editor to *word_idx*, and restart speech
            if it was already running (or if *always_play* is True)."""
            was_speaking = self.tts_manager.speaking
            self.tts_manager.stop()
            self.editor.setExtraSelections([])
            wm = getattr(self.doc, "word_map", []) if self.doc else []
            if not wm or word_idx >= len(wm):
                return
            qwm = self._qt_word_map
            if word_idx < len(qwm):
                cursor = QTextCursor(self.editor.document())
                cursor.setPosition(qwm[word_idx])
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()
            if was_speaking or always_play:
                self._tts_play_from_word(word_idx)

        def _qt_block_to_word(self, block_num: int) -> int:
            """Return the word-map index of the first word inside QTextBlock
            *block_num*, searching forward through _qt_word_map."""
            block = self.editor.document().findBlockByNumber(block_num)
            if not block.isValid():
                return 0
            char_pos = block.position()
            for i, off in enumerate(self._qt_word_map):
                if off >= char_pos:
                    return i
            return 0

        def _qt_current_block(self) -> int:
            """Block number that best represents the current reading position.
            Uses the word map when speaking, otherwise the text cursor."""
            cur_word = self._qt_current_word_for_nav()
            qwm = self._qt_word_map
            if cur_word < len(qwm):
                char_pos = qwm[cur_word]
                cursor = QTextCursor(self.editor.document())
                cursor.setPosition(char_pos)
                return cursor.blockNumber()
            return self.editor.textCursor().blockNumber()

        def _qt_is_heading_block(self, block_num: int) -> bool:
            """Return True if the QTextBlock at *block_num* is a heading."""
            block = self.editor.document().findBlockByNumber(block_num)
            if not block.isValid():
                return False
            try:
                return block.blockFormat().headingLevel() > 0
            except AttributeError:
                return False  # Qt < 5.12 — heading level API unavailable

        # ─ sentence ──────────────────────────────────────────────────────────

        def _qt_skip_next_sentence(self) -> None:
            """Jump to the next sentence; restart speech if it was playing."""
            if not self.doc or not self.doc.word_map:
                return
            cur = self._qt_current_word_for_nav()
            si = self._qt_find_sentence_idx(cur)
            nsi = si + 1
            if nsi >= len(self._qt_sentence_starts):
                self.statusBar().showMessage("No next sentence")
                return
            dest = self._qt_sentence_starts[nsi]
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest, min(dest + 5, len(self.doc.word_map)))
            )
            total = len(self._qt_sentence_starts)
            self._qt_navigate_to_word(dest)
            self.statusBar().showMessage(f"→ Sentence {nsi + 1}/{total}: “{preview}…”")

        def _qt_skip_prev_sentence(self) -> None:
            """Jump to the previous sentence (or replay the current one if
            more than 3 words in); restart speech if it was playing."""
            if not self.doc or not self.doc.word_map:
                return
            cur = self._qt_current_word_for_nav()
            si = self._qt_find_sentence_idx(cur)
            psi = si if cur - self._qt_sentence_starts[si] > 3 else max(0, si - 1)
            dest = self._qt_sentence_starts[psi]
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest, min(dest + 5, len(self.doc.word_map)))
            )
            total = len(self._qt_sentence_starts)
            self._qt_navigate_to_word(dest)
            self.statusBar().showMessage(f"← Sentence {psi + 1}/{total}: “{preview}…”")

        def _qt_replay_sentence(self) -> None:
            """Jump to the start of the current sentence and *always* begin
            reading, matching the TUI\'s ’;’ key behavior."""
            if not self.doc or not self.doc.word_map:
                return
            cur = self._qt_current_word_for_nav()
            si = self._qt_find_sentence_idx(cur)
            dest = self._qt_sentence_starts[si]
            preview = " ".join(
                self.doc.word_map[i].word
                for i in range(dest, min(dest + 5, len(self.doc.word_map)))
            )
            self._qt_navigate_to_word(dest, always_play=True)
            self.statusBar().showMessage(f"↺ Replaying: “{preview}…”")

        # ─ paragraph ─────────────────────────────────────────────────────────

        def _qt_skip_next_paragraph(self) -> None:
            """Jump to the next paragraph; restart speech if it was playing."""
            doc_obj = self.editor.document()
            n = doc_obj.blockCount()
            cur_block = self._qt_current_block()
            i = cur_block + 1
            # Skip through any remaining content of the current paragraph
            while i < n and doc_obj.findBlockByNumber(i).text().strip():
                i += 1
            # Skip blank separator blocks
            while i < n and not doc_obj.findBlockByNumber(i).text().strip():
                i += 1
            if i >= n:
                self.statusBar().showMessage("No next paragraph")
                return
            self._qt_navigate_to_word(self._qt_block_to_word(i))
            self.statusBar().showMessage(f"¶  Next paragraph — block {i + 1}")

        def _qt_skip_prev_paragraph(self) -> None:
            """Jump to the previous paragraph; restart speech if it was playing."""
            doc_obj = self.editor.document()
            cur_block = self._qt_current_block()
            i = cur_block - 1
            # Skip blank lines backward
            while i > 0 and not doc_obj.findBlockByNumber(i).text().strip():
                i -= 1
            # Walk back through the previous paragraph’s content
            while i > 0 and doc_obj.findBlockByNumber(i - 1).text().strip():
                i -= 1
            i = max(0, i)
            self._qt_navigate_to_word(self._qt_block_to_word(i))
            self.statusBar().showMessage(f"¶  Prev paragraph — block {i + 1}")

        def _qt_replay_paragraph(self) -> None:
            """Jump to the start of the current paragraph and *always* begin
            reading, matching the TUI\'s ’r’ key behavior."""
            doc_obj = self.editor.document()
            cur_block = self._qt_current_block()
            # Walk back to the first block of this paragraph
            i = cur_block
            while i > 0 and doc_obj.findBlockByNumber(i - 1).text().strip():
                i -= 1
            # Step forward past any leading blank lines
            n = doc_obj.blockCount()
            while i < n - 1 and not doc_obj.findBlockByNumber(i).text().strip():
                i += 1
            self._qt_navigate_to_word(self._qt_block_to_word(i), always_play=True)
            self.statusBar().showMessage(f"↺ Replaying paragraph from block {i + 1}")

        # ─ heading ───────────────────────────────────────────────────────────

        def _qt_skip_next_heading(self) -> None:
            """Scroll to next heading; restart speech if it was playing."""
            doc_obj = self.editor.document()
            n = doc_obj.blockCount()
            start = self._qt_current_block() + 1
            for i in range(start, n):
                if self._qt_is_heading_block(i):
                    heading_text = doc_obj.findBlockByNumber(i).text().strip()
                    self._qt_navigate_to_word(self._qt_block_to_word(i))
                    self.statusBar().showMessage(f"↓ Heading: {heading_text[:60]}")
                    return
            self.statusBar().showMessage("No heading below current position")

        def _qt_skip_prev_heading(self) -> None:
            """Scroll to previous heading; restart speech if it was playing."""
            doc_obj = self.editor.document()
            start = self._qt_current_block() - 1
            for i in range(start, -1, -1):
                if self._qt_is_heading_block(i):
                    heading_text = doc_obj.findBlockByNumber(i).text().strip()
                    self._qt_navigate_to_word(self._qt_block_to_word(i))
                    self.statusBar().showMessage(f"↑ Heading: {heading_text[:60]}")
                    return
            self.statusBar().showMessage("No heading above current position")

        def _qt_read_next_heading(self) -> None:
            """Jump to next heading and *always* begin reading (TUI ’>’)."""
            doc_obj = self.editor.document()
            n = doc_obj.blockCount()
            start = self._qt_current_block() + 1
            for i in range(start, n):
                if self._qt_is_heading_block(i):
                    heading_text = doc_obj.findBlockByNumber(i).text().strip()
                    self._qt_navigate_to_word(
                        self._qt_block_to_word(i), always_play=True
                    )
                    self.statusBar().showMessage(
                        f"⏩ Reading from: {heading_text[:60]}"
                    )
                    return
            self.statusBar().showMessage("No heading below current position")

        def _qt_read_prev_heading(self) -> None:
            """Jump to previous heading and *always* begin reading (TUI '<')."""
            doc_obj = self.editor.document()
            start = self._qt_current_block() - 1
            for i in range(start, -1, -1):
                if self._qt_is_heading_block(i):
                    heading_text = doc_obj.findBlockByNumber(i).text().strip()
                    self._qt_navigate_to_word(
                        self._qt_block_to_word(i), always_play=True
                    )
                    self.statusBar().showMessage(
                        f"⏪ Reading from: {heading_text[:60]}"
                    )
                    return
            self.statusBar().showMessage("No heading above current position")

        # ─ table ──────────────────────────────────────────────────────────────

        def _qt_is_table_block(self, block_num: int) -> bool:
            """Return True when block *block_num* is a markdown table line.

            In the current renderer, table rows appear as plain paragraphs
            whose text starts with the pipe character '|'.
            """
            block = self.editor.document().findBlockByNumber(block_num)
            if not block.isValid():
                return False
            return block.text().lstrip().startswith("|")

        def _qt_skip_next_table(self) -> None:
            """Jump to the first row of the next table (Ctrl+T)."""
            doc_obj = self.editor.document()
            n = doc_obj.blockCount()
            cur = self._qt_current_block()
            # Skip out of any table we're currently inside.
            i = cur + 1
            while (
                i < n and self._qt_is_table_block(i - 1) and self._qt_is_table_block(i)
            ):
                i += 1
            # Skip non-table blocks to find the next table start.
            while i < n and not self._qt_is_table_block(i):
                i += 1
            if i >= n:
                self.statusBar().showMessage("No table below current position")
                return
            self._qt_navigate_to_word(self._qt_block_to_word(i))
            preview = doc_obj.findBlockByNumber(i).text()[:60]
            self.statusBar().showMessage(f"▼ Table: {preview}")

        def _qt_skip_prev_table(self) -> None:
            """Jump to the first row of the previous table (Ctrl+Shift+T)."""
            doc_obj = self.editor.document()
            cur = self._qt_current_block()
            # Skip back through the current table (if any).
            i = cur - 1
            while i > 0 and self._qt_is_table_block(i):
                i -= 1
            # Skip non-table blocks backward to find the end of the prev table.
            while i > 0 and not self._qt_is_table_block(i):
                i -= 1
            if i < 0 or not self._qt_is_table_block(i):
                self.statusBar().showMessage("No table above current position")
                return
            # Walk to the first row of that table.
            while i > 0 and self._qt_is_table_block(i - 1):
                i -= 1
            self._qt_navigate_to_word(self._qt_block_to_word(i))
            preview = doc_obj.findBlockByNumber(i).text()[:60]
            self.statusBar().showMessage(f"▲ Table: {preview}")

        # ─ document editing ───────────────────────────────────────────────

        def _qt_edit_mode_toggle(self) -> None:
            """Toggle between read mode and edit mode (Ctrl+E).

            In *read mode* the editor displays rendered HTML and is
            read-only.  In *edit mode* the raw Markdown source is shown
            as plain text so the user can make changes with any standard
            text-editing shortcut (Ctrl+Z/Y, Ctrl+X/C/V, arrow keys,
            Delete, Home, End, …).  Ctrl+S saves; Ctrl+E exits without
            saving.
            """
            if not self._qt_edit_mode:
                self._qt_enter_edit_mode()
            else:
                self._qt_exit_edit_mode(save=False)

        def _qt_enter_edit_mode(self) -> None:
            """Switch the editor to editable Markdown source view."""
            if not self.doc:
                self.statusBar().showMessage("No document to edit")
                return
            self.tts_manager.stop()
            self.editor.setReadOnly(False)
            self.editor.setCursorWidth(2)  # visible text cursor
            # Show raw Markdown so the user edits the source, not HTML.
            self.editor.setPlainText(self.doc.markdown or "")
            self.editor.document().setModified(False)
            self._qt_edit_mode = True
            self._qt_edit_dirty = False
            self.editor.document().contentsChanged.connect(
                self._qt_on_edit_contents_changed
            )
            # Attach the red-squiggle spell highlighter while editing (only when
            # pyspellchecker and a Qt QSyntaxHighlighter are both available).
            if _SPELL and SpellHighlighter is not None:
                try:
                    self._spell_highlighter = SpellHighlighter(self.editor.document())
                except Exception:  # noqa: BLE001
                    self._spell_highlighter = None
            # If the live-preview preference is on, show the preview pane now
            # and render the current source into it.
            if self.settings.get("qt_edit_preview", False):
                self._preview.setVisible(True)
                self._qt_render_preview()
                self.statusBar().showMessage(
                    "✏  EDIT MODE — Markdown source + live preview  ·  "
                    "Ctrl+S: save  ·  Ctrl+E: discard & exit"
                )
            else:
                self.statusBar().showMessage(
                    "✏  EDIT MODE — Markdown source  ·  "
                    "Ctrl+S: save  ·  Ctrl+E: discard & exit  ·  "
                    "Ctrl+Shift+L: live preview"
                )

        def _qt_on_edit_contents_changed(self) -> None:
            """Mark the document dirty when the user types in edit mode and,
            when the live preview is visible, schedule a debounced re-render."""
            if not self._qt_edit_dirty:
                self._qt_edit_dirty = True
                title = self.doc.title if self.doc else "document"
                self.statusBar().showMessage(
                    f"✏  EDIT MODE  ·  {title}  [modified — Ctrl+S to save]"
                )
            if self._qt_edit_mode and self._preview.isVisible():
                # Re-render ~300 ms after the last keystroke (keeps typing snappy).
                self._preview_timer.start(300)

        def _qt_exit_edit_mode(self, save: bool = False) -> None:
            """Leave edit mode, optionally saving first."""
            if not self._qt_edit_mode:
                return
            if save:
                self._qt_save()
            # Disconnect the dirty listener.
            try:
                self.editor.document().contentsChanged.disconnect(
                    self._qt_on_edit_contents_changed
                )
            except (RuntimeError, TypeError):
                pass
            # Detach the spell highlighter so it stops re-checking the read-only view.
            if self._spell_highlighter is not None:
                try:
                    self._spell_highlighter.setDocument(None)
                except Exception:  # noqa: BLE001
                    pass
                self._spell_highlighter = None
            self._qt_edit_mode = False
            self._qt_edit_dirty = False
            # The preview pane is only meaningful while editing; hide it.
            self._preview.setVisible(False)
            # Re-render the (possibly updated) Markdown.
            md = self.doc.markdown if self.doc else ""
            self.editor.setReadOnly(True)
            self.editor.setCursorWidth(0)
            self.editor.setHtml(self._md_to_html(md))
            self._apply_block_spacing()
            self._qt_apply_user_highlights()
            self.statusBar().showMessage("Read mode")

        def _qt_check_spelling(self) -> None:
            """Count and report misspelled words in the current text (F7).

            Works whether or not the live red-squiggle highlighter is running:
            it checks the editable source in edit mode, otherwise the loaded
            document's plain text.
            """
            if not _SPELL:
                QMessageBox.information(
                    self,
                    "Spell check unavailable",
                    "Spell checking requires pyspellchecker:\n\n"
                    "    pip install pyspellchecker",
                )
                return
            if self._qt_edit_mode:
                text = self.editor.toPlainText()
            elif self.doc:
                text = self.doc.plain_text or ""
            else:
                self.statusBar().showMessage("Open a document to check spelling")
                return
            bad = sorted(misspelled_words(text))
            if not bad:
                QMessageBox.information(
                    self, "Spell check", "No misspelled words found."
                )
                return
            preview = ", ".join(bad[:25])
            if len(bad) > 25:
                preview += ", …"
            QMessageBox.information(
                self,
                "Spell check",
                f"{len(bad)} misspelled word(s) found:\n\n{preview}",
            )

        # ─ live HTML preview (edit mode) ──────────────────────────────────

        def _qt_render_preview(self) -> None:
            """Render the current editor source into the live preview pane."""
            if not self._preview.isVisible():
                return
            md = (
                self.editor.toPlainText()
                if self._qt_edit_mode
                else (self.doc.markdown if self.doc else "")
            )
            # Preserve the reader's scroll position across re-renders.
            bar = self._preview.verticalScrollBar()
            pos = bar.value() if bar else 0
            self._preview.setHtml(self._md_to_html(md))
            if bar:
                bar.setValue(min(pos, bar.maximum()))

        def _qt_toggle_preview(self) -> None:
            """Toggle the live HTML preview pane (Ctrl+Shift+L).

            The preview is meaningful only while editing the Markdown source,
            so turning it on outside edit mode enters edit mode first.
            """
            new = not bool(self.settings.get("qt_edit_preview", False))
            self.settings["qt_edit_preview"] = new
            if hasattr(self, "_preview_act"):
                self._preview_act.setChecked(new)
            if new:
                if not self._qt_edit_mode:
                    if not self.doc:
                        self.statusBar().showMessage("Open a document to preview")
                        return
                    # Entering edit mode shows the preview itself.
                    self._qt_enter_edit_mode()
                else:
                    self._preview.setVisible(True)
                    self._qt_render_preview()
                self.statusBar().showMessage("Live HTML preview: ON")
            else:
                self._preview.setVisible(False)
                self.statusBar().showMessage("Live HTML preview: OFF")

        # ─ reading statistics & library ───────────

        def _stats_poll(self) -> None:
            """Feed the reading-statistics tracker (called by a 1 s QTimer)."""
            try:
                path = self.doc.path if self.doc else ""
                speaking = self.tts_manager.speaking
                wm = getattr(self.doc, "word_map", []) if self.doc else []
                widx = self.tts_manager.current_word_idx if speaking else -1
                self.stats.tick(speaking, path, widx, len(wm))
            except Exception:
                pass

        def _qt_reading_stats(self) -> None:
            """Show the reading-statistics dashboard in a dialog."""
            try:
                self.stats.flush()
            except Exception:
                pass
            path = self.doc.path if self.doc else ""
            title = self.doc.title if self.doc else ""
            html = self._md_to_html(_format_reading_stats(self.settings, path, title))
            dlg = QDialog(self)
            dlg.setWindowTitle("Reading Statistics")
            dlg.resize(560, 520)
            lay = QVBoxLayout(dlg)
            view = QTextBrowser()
            view.setHtml(html)
            lay.addWidget(view)
            try:
                _ok_btn = QDialogButtonBox.StandardButton.Ok
            except AttributeError:
                _ok_btn = QDialogButtonBox.Ok  # type: ignore[attr-defined]
            buttons = QDialogButtonBox(_ok_btn)
            buttons.accepted.connect(dlg.accept)
            lay.addWidget(buttons)
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()

        def _qt_summarize(self) -> None:
            """Summarize the current document with LexRank and show the result.

            Runs on a background thread because LexRank can take a moment on a
            long document; the result is delivered to the GUI thread via
            _summary_signal.
            """
            if not _SUMY:
                QMessageBox.information(
                    self,
                    "Summarization unavailable",
                    "Document summarization requires sumy:\n\n    pip install sumy",
                )
                return
            if not self.doc:
                self.statusBar().showMessage("Open a document to summarize")
                return
            text = self.doc.plain_text or ""
            if not text.strip():
                self.statusBar().showMessage("Nothing to summarize")
                return
            n = int(self.settings.get("summary_sentences", 7))
            self.statusBar().showMessage("Summarizing…")

            def _work() -> None:
                try:
                    summary = summarize_document(text, n)
                    self._summary_signal.emit(summary, "")
                except Exception as exc:  # noqa: BLE001
                    self._summary_signal.emit("", str(exc))

            threading.Thread(target=_work, daemon=True).start()

        def _qt_on_summary(self, summary: str, error: str) -> None:
            """Main-thread handler: show the summary (or an error) in a dialog."""
            if error:
                QMessageBox.warning(self, "Summarization failed", error)
                self.statusBar().showMessage("Summarization failed")
                return
            if not summary:
                self.statusBar().showMessage("Summary was empty")
                return
            title = self.doc.title if self.doc else "Document"
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Summary — {title}")
            dlg.resize(560, 420)
            lay = QVBoxLayout(dlg)
            view = QTextEdit()
            view.setReadOnly(True)
            view.setPlainText(summary)
            view.setAccessibleName("Document summary")
            lay.addWidget(view)
            try:
                _ok_btn = QDialogButtonBox.StandardButton.Ok
            except AttributeError:
                _ok_btn = QDialogButtonBox.Ok  # type: ignore[attr-defined]
            buttons = QDialogButtonBox(_ok_btn)
            buttons.accepted.connect(dlg.accept)
            lay.addWidget(buttons)
            self.statusBar().showMessage("Summary ready")
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()

        def _qt_translate(self) -> None:
            """Translate the current document into another language.

            Opens a dialog with a language picker and a result pane; the
            network call runs on a background thread and its result is
            delivered to the GUI thread via _translate_signal.
            """
            if not _DEEP_TRANSLATOR:
                QMessageBox.information(
                    self,
                    "Translation unavailable",
                    "Document translation requires deep-translator:\n\n"
                    "    pip install deep-translator",
                )
                return
            if not self.doc or not (self.doc.plain_text or "").strip():
                QMessageBox.information(
                    self, "Nothing to translate", "Open a document first."
                )
                return

            dlg = QDialog(self)
            dlg.setWindowTitle(f"Translate — {self.doc.title}")
            dlg.resize(560, 460)
            lay = QVBoxLayout(dlg)

            row = QHBoxLayout()
            row.addWidget(QLabel("Translate to:"))
            combo = QComboBox()
            for name, code in COMMON_LANGUAGES:
                combo.addItem(name, code)
            row.addWidget(combo, 1)
            go_btn = QPushButton("Translate")
            row.addWidget(go_btn)
            lay.addLayout(row)

            view = QTextEdit()
            view.setReadOnly(True)
            view.setAccessibleName("Translation result")
            lay.addWidget(view)
            self._translate_view = view
            self._translate_btn = go_btn

            try:
                _close_btn = QDialogButtonBox.StandardButton.Close
            except AttributeError:
                _close_btn = QDialogButtonBox.Close  # type: ignore[attr-defined]
            buttons = QDialogButtonBox(_close_btn)
            buttons.rejected.connect(dlg.reject)
            lay.addWidget(buttons)

            def _do() -> None:
                code = str(combo.itemData(combo.currentIndex()) or "en")
                self._qt_do_translate(code)

            go_btn.clicked.connect(_do)
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()
            # Drop the widget references so a late result is ignored safely.
            self._translate_view = None
            self._translate_btn = None

        def _qt_do_translate(self, code: str) -> None:
            """Kick off a background translation of the current document."""
            if not self.doc:
                return
            text = self.doc.plain_text or ""
            truncated = len(text) > 15000
            text = text[:15000]
            if getattr(self, "_translate_btn", None) is not None:
                self._translate_btn.setEnabled(False)
            if getattr(self, "_translate_view", None) is not None:
                self._translate_view.setPlainText("Translating…")
            self.statusBar().showMessage(
                "Translating first 15000 characters…"
                if truncated
                else "Translating…"
            )

            def _work() -> None:
                try:
                    result = translate_text(text, target_lang=code)
                    self._translate_signal.emit(result, "")
                except Exception as exc:  # noqa: BLE001
                    self._translate_signal.emit("", str(exc))

            threading.Thread(target=_work, daemon=True).start()

        def _qt_on_translation(self, result: str, error: str) -> None:
            """Main-thread handler: show the translation (or an error)."""
            btn = getattr(self, "_translate_btn", None)
            view = getattr(self, "_translate_view", None)
            try:
                if btn is not None:
                    btn.setEnabled(True)
                if error:
                    if view is not None:
                        view.setPlainText("")
                    QMessageBox.warning(self, "Translation failed", error)
                    self.statusBar().showMessage("Translation failed")
                    return
                if view is not None:
                    view.setPlainText(result or "")
                self.statusBar().showMessage("Translation ready")
            except RuntimeError:
                # The dialog (and its widgets) was closed before the result
                # arrived; nothing left to update.
                pass

        def _qt_open_feed(self) -> None:
            """Prompt for a feed URL, fetch it, and pick an article to open."""
            if not _FEEDPARSER:
                QMessageBox.information(
                    self,
                    "Feed reading unavailable",
                    "Reading RSS / Atom feeds requires feedparser:\n\n"
                    "    pip install feedparser",
                )
                return
            url, ok = QInputDialog.getText(
                self, "Open Feed", "Enter an RSS / Atom feed URL:"
            )
            if not ok or not url.strip():
                return
            url = url.strip()
            self.statusBar().showMessage(f"Fetching feed {url} …")

            def _work() -> None:
                try:
                    entries = fetch_feed(url)
                    self._feed_signal.emit(entries, "")
                except Exception as exc:  # noqa: BLE001
                    self._feed_signal.emit([], str(exc))

            threading.Thread(target=_work, daemon=True).start()

        def _qt_on_feed(self, entries: Any, error: str) -> None:
            """Main-thread handler: list the feed's entries; open the chosen one."""
            if error or not entries:
                QMessageBox.information(
                    self, "Feed", "No entries found — check the URL."
                )
                self.statusBar().showMessage("No feed entries")
                return

            dlg = QDialog(self)
            dlg.setWindowTitle("Feed")
            dlg.resize(620, 460)
            lay = QVBoxLayout(dlg)
            lay.addWidget(QLabel("Choose an article to open:"))
            lst = QListWidget()
            for ent in entries:
                published = ent.get("published", "")
                label = ent.get("title", "") or ent.get("url", "")
                if published:
                    label = f"{label}  —  {published}"
                item = QListWidgetItem(label)
                item.setData(_USER_ROLE, ent.get("url", ""))
                if ent.get("summary"):
                    item.setToolTip(re.sub(r"<[^>]+>", "", ent["summary"])[:400])
                lst.addItem(item)
            lay.addWidget(lst)

            try:
                _btns = (
                    QDialogButtonBox.StandardButton.Open
                    | QDialogButtonBox.StandardButton.Cancel
                )
            except AttributeError:
                _btns = QDialogButtonBox.Open | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
            buttons = QDialogButtonBox(_btns)
            lay.addWidget(buttons)

            chosen = {"url": ""}

            def _accept_current() -> None:
                item = lst.currentItem()
                if item is not None:
                    chosen["url"] = str(item.data(_USER_ROLE) or "")
                dlg.accept()

            def _accept_item(item: Any) -> None:
                chosen["url"] = str(item.data(_USER_ROLE) or "")
                dlg.accept()

            buttons.accepted.connect(_accept_current)
            buttons.rejected.connect(dlg.reject)
            lst.itemDoubleClicked.connect(_accept_item)

            dlg.exec() if _QT == "PyQt6" else dlg.exec_()
            if chosen["url"]:
                self._open_path(chosen["url"])

        def _qt_library(self) -> None:
            """Browse the library/bookshelf; open the chosen document.

            A searchable list of every document opened in star, showing
            progress and time read, newest first.  Enter / double-click opens
            the selected document.
            """
            entries = _library_entries(self.settings)
            if not entries:
                self.statusBar().showMessage(
                    "Library is empty — open a document to add it"
                )
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("Library / Bookshelf")
            dlg.resize(620, 460)
            lay = QVBoxLayout(dlg)
            box = QLineEdit()
            box.setPlaceholderText(
                "Filter by title or path…  (Enter opens, Esc closes)"
            )
            lst = QListWidget()
            lay.addWidget(box)
            lay.addWidget(lst)

            def _populate(query: str = "") -> None:
                lst.clear()
                terms = query.lower().split()
                for e in entries:
                    hay = (e["title"] + " " + e["path"]).lower()
                    if not all(t in hay for t in terms):
                        continue
                    fmt = e["format"] or "?"
                    tm = _fmt_duration(e["seconds"]) if e["seconds"] else "—"
                    last = str(e.get("last_opened", ""))[:10]
                    label = (
                        f"{e['pct']:>3}%  {e['title']}\n"
                        f"        {fmt}  ·  {tm} read  ·  {last}"
                    )
                    it = QListWidgetItem(label)
                    it.setData(_USER_ROLE, e["path"])
                    it.setToolTip(e["path"])
                    lst.addItem(it)
                if lst.count():
                    lst.setCurrentRow(0)

            def _open() -> None:
                it = lst.currentItem() or (lst.item(0) if lst.count() else None)
                if it is None:
                    return
                path = it.data(_USER_ROLE)
                dlg.accept()
                if path:
                    self._open_path(str(path))

            _populate()
            box.textChanged.connect(_populate)
            box.returnPressed.connect(_open)
            lst.itemActivated.connect(lambda _it: _open())
            box.setFocus()
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()

        def _qt_save(self) -> None:
            """Save the current document.

            In *edit mode*: the edited Markdown is written back to the
            original file (for .md / .markdown / .txt / .rst / .org);
            for any other format a Save-As dialog is shown.  The document
            is then re-rendered and the TTS word maps are rebuilt.

            In *read mode*: falls through to the Markdown export dialog
            (same as File → Export → Export as Markdown…).
            """
            if not self._qt_edit_mode:
                # Not editing — offer markdown export.
                self._qt_export_markdown()
                return

            if not self.doc:
                return

            # Capture the edited source from the plain-text editor.
            new_md = self.editor.toPlainText()

            # --- persist to disk -------------------------------------------
            orig = Path(self.doc.path) if self.doc.path else None
            text_exts = {
                ".md",
                ".markdown",
                ".txt",
                ".rst",
                ".org",
                ".adoc",
                ".asc",
                ".asciidoc",
            }
            if orig and orig.suffix.lower() in text_exts:
                try:
                    orig.write_text(new_md, encoding="utf-8")
                    saved_path = str(orig)
                except OSError as exc:
                    self.statusBar().showMessage(f"Save error: {exc}")
                    return
            else:
                # Binary or non-text format — prompt for a .md path.
                stem = orig.stem if orig else "document"
                parent = str(orig.parent) if orig else ""
                dest, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save As Markdown",
                    str(Path(parent) / (stem + ".md")),
                    "Markdown (*.md *.markdown)",
                )
                if not dest:
                    return
                try:
                    Path(dest).write_text(new_md, encoding="utf-8")
                    saved_path = dest
                except OSError as exc:
                    self.statusBar().showMessage(f"Save error: {exc}")
                    return

            # --- update in-memory document ---------------------------------
            self.doc.markdown = new_md
            self.doc.plain_text = _strip_markdown_for_tts(
                new_md,
                skip_code=bool(self.settings.get("tts_skip_code", True)),
                table_mode=str(self.settings.get("table_reading_mode", "structured")),
            )
            self._qt_edit_dirty = False

            # --- exit edit mode and re-render ------------------------------
            try:
                self.editor.document().contentsChanged.disconnect(
                    self._qt_on_edit_contents_changed
                )
            except (RuntimeError, TypeError):
                pass
            self._qt_edit_mode = False
            self.editor.setReadOnly(True)
            self.editor.setCursorWidth(0)
            self.editor.setHtml(self._md_to_html(new_md))
            self._apply_block_spacing()
            self._qt_apply_user_highlights()
            self._qt_build_toc()
            self._qt_build_annotations()

            # Rebuild word maps asynchronously (same flow as _on_doc_loaded_impl)
            qt_plain = self.editor.document().toPlainText()
            doc_ref = self.doc

            def _rebuild() -> None:
                try:
                    flat = qt_plain.splitlines()
                    doc_ref.word_map = _build_word_map(doc_ref.plain_text, flat)
                    self.tts_manager.set_word_map(doc_ref.word_map)
                    self._build_qt_word_map(doc_ref.plain_text, qt_plain)
                except Exception:
                    pass

            import threading as _threading

            _threading.Thread(target=_rebuild, daemon=True).start()

            self.statusBar().showMessage(f"Saved → {saved_path}")

        # ── Reading position memory ──────────────────────────────────────

        def _qt_save_reading_position(self) -> None:
            """Persist the current reading offset for the open document.
            Identical logic to StarApp._save_reading_position."""
            if not self.doc or not self.doc.path or not self.doc.word_map:
                return
            cur = self._qt_current_word_for_nav()
            wm = self.doc.word_map
            if cur < 0 or cur >= len(wm):
                return
            offset = wm[cur].tts_offset
            total_chars = len(self.doc.plain_text or "")
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

        def _qt_restore_reading_position(self) -> None:
            """Scroll to the saved position for the current document and
            optionally resume TTS.  Called on the GUI thread via
            _restore_signal after the word map has been built."""
            if not self.doc or not self.doc.path or not self.doc.word_map:
                return
            if not self.settings.get("tts_auto_resume", True):
                return
            saved = self.settings.get("reading_positions", {}).get(self.doc.path)
            if not saved:
                return
            target_offset = int(saved.get("offset", 0))
            pct = int(saved.get("pct", 0))
            ts = str(saved.get("ts", ""))[:10]
            # Find the word-map entry whose tts_offset is at or beyond the
            # saved offset.
            wm = self.doc.word_map
            best = len(wm) - 1
            for i, wp in enumerate(wm):
                if wp.tts_offset >= target_offset:
                    best = i
                    break
            # Scroll the editor to that position and move the text cursor
            # there.  Moving the cursor is essential: _qt_current_word_for_nav
            # reads the cursor position when TTS is idle, so without this
            # a subsequent _qt_save_reading_position call (e.g. from
            # closeEvent before the user ever starts TTS) would see position 0
            # and overwrite the just-restored offset with the start of the doc.
            qwm = self._qt_word_map
            if best < len(qwm):
                cursor = QTextCursor(self.editor.document())
                cursor.setPosition(qwm[best])
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()
            self.statusBar().showMessage(f"Resumed at {pct}%  (saved {ts})", 5000)

        # ── Display options ─────────────────────────────────────────────────────

        def _rate_change(self, delta: int) -> None:
            new_rate = max(50, min(600, int(self.settings["tts_rate"]) + delta))
            self.tts_manager.set_rate(new_rate)
            if self._qt_sc_reader is not None:
                self._qt_sc_reader.update_rate(new_rate)
            self.statusBar().showMessage(f"Rate: {new_rate} wpm")

        def _voice_picker_qt(self) -> None:
            """Open a native voice-selection dialog.

            Lists all voices available from the active TTS backend by their
            friendly name (not the raw Windows registry ID).  The user picks
            one from a scrollable list; pressing OK applies the voice and
            speaks a short confirmation so the change is immediately audible.
            Ctrl+T opens this dialog from anywhere in the GUI.
            """
            voices = self.tts_manager.list_voices()
            if not voices:
                self.statusBar().showMessage(
                    "No TTS voices found. Is pyttsx3 installed "
                    "and the backend set to pyttsx3?"
                )
                return

            # Build display strings (name + language tag).
            items: List[str] = []
            for v in voices:
                name = v.get("name", v.get("id", "Unknown"))
                lang = v.get("lang", "")
                items.append(f"{name}  [{lang}]" if lang else name)

            # Highlight the current voice.
            current_id = str(self.settings.get("tts_voice", ""))
            current_idx = 0
            for i, v in enumerate(voices):
                if v.get("id") == current_id:
                    current_idx = i
                    break

            chosen, ok = QInputDialog.getItem(
                self,
                "Select TTS Voice",
                "Choose a voice  (Ctrl+T to reopen):",
                items,
                current_idx,
                False,  # not editable — must pick from the list
            )
            if not ok:
                return

            idx = items.index(chosen)
            v = voices[idx]
            voice_id = v.get("id", "")
            voice_name = v.get("name", voice_id)
            self.tts_manager._backend.set_voice(voice_id)
            self.settings.set("tts_voice", voice_id)
            self.statusBar().showMessage(f"Voice: {voice_name}")
            # Stop any running speech and speak a brief test phrase so the
            # user hears the new voice without having to press Play.
            self.tts_manager.stop()
            self.editor.setExtraSelections([])
            self.tts_manager._backend.speak(f"Voice changed to {voice_name}.")

        def _apply_qt_theme(self, theme_name: str) -> None:
            """Apply *theme_name* to the editor widget and re-render.

            Uses _effective_palette so CSS-file themes are honored for
            both the QTextEdit stylesheet and the HTML body styling.
            """
            pal = self._effective_palette(theme_name)
            font_size = int(self.settings.get("font_size", 0)) or 14
            sheet = (
                "QTextEdit, QTextBrowser {"
                f"  background-color: {pal['bg']};"
                f"  color: {pal['fg']};"
                f"  font-size: {font_size}pt;"
                f"  selection-background-color: {pal['sel']};"
                "}"
            )
            self.editor.setStyleSheet(sheet)
            if hasattr(self, "_preview"):
                self._preview.setStyleSheet(sheet)
            # In edit mode the editor holds raw Markdown source the user is
            # editing — re-rendering it as HTML would destroy their edits.
            # Only refresh the rendered view when NOT editing; the live
            # preview pane is refreshed instead.
            if getattr(self, "_qt_edit_mode", False):
                if hasattr(self, "_preview") and self._preview.isVisible():
                    self._qt_render_preview()
                return
            # Re-render so the HTML body styles match the new theme.
            if self.doc is not None:
                self.editor.setHtml(self._md_to_html(self.doc.markdown))
            else:
                self.editor.setHtml(self._welcome_html())
            # Line height is a per-document block format reset by setHtml.
            self._apply_block_spacing()

        def _next_theme(self) -> None:
            """Cycle to the next theme (built-in + custom CSS)."""
            all_themes = self._all_theme_names
            current = str(self.settings.get("theme", "dark"))
            idx = all_themes.index(current) if current in all_themes else 0
            new_theme = all_themes[(idx + 1) % len(all_themes)]
            self.settings["theme"] = new_theme
            self._apply_qt_theme(new_theme)
            self.statusBar().showMessage(f"Theme: {new_theme}")

        def _qt_pick_theme(self) -> None:
            """Open a dialog listing all available themes for direct selection."""
            all_themes = self._all_theme_names
            current = str(self.settings.get("theme", "dark"))
            current_idx = all_themes.index(current) if current in all_themes else 0
            chosen, ok = QInputDialog.getItem(
                self,
                "Choose Theme",
                "Select a color theme:",
                all_themes,
                current_idx,
                False,
            )
            if ok and chosen:
                self.settings["theme"] = chosen
                self._apply_qt_theme(chosen)
                self.statusBar().showMessage(f"Theme: {chosen}")

        def _qt_reload_css_themes(self) -> None:
            """Re-scan THEMES_DIR and reload all *.css theme files.

            Useful after dropping a new .css file in the themes folder
            without restarting the application.  The current theme is
            re-applied immediately if it was a CSS theme that changed.
            """
            self._css_themes = _load_css_themes()
            n = len(self._css_themes)
            current = str(self.settings.get("theme", "dark"))
            # Re-apply in case the active theme's CSS was modified on disk.
            self._apply_qt_theme(current)
            self.statusBar().showMessage(
                f"CSS themes reloaded — {n} file(s) found in {THEMES_DIR}"
            )

        def _qt_open_themes_folder(self) -> None:
            """Open THEMES_DIR in the system file manager."""
            try:
                THEMES_DIR.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            import subprocess as _sp

            try:
                if sys.platform == "win32":
                    _sp.Popen(["explorer", str(THEMES_DIR)])
                elif sys.platform == "darwin":
                    _sp.Popen(["open", str(THEMES_DIR)])
                else:
                    _sp.Popen(["xdg-open", str(THEMES_DIR)])
                self.statusBar().showMessage(f"Opened: {THEMES_DIR}")
            except OSError as exc:
                self.statusBar().showMessage(f"Could not open folder: {exc}")

        def _show_about(self) -> None:
            """Open README.md as a document (F1 help).

            README.md ships alongside the package modules and is the
            canonical reference for every feature, keyboard shortcut, and
            setting.  Opening it in the main window gives the user full TTS,
            navigation, highlighting, and search — far more useful than a
            limited modal dialog.
            """
            readme = Path(__file__).parent / "README.md"
            if readme.exists():
                self._open_path(str(readme))
            else:
                self.statusBar().showMessage(
                    f"{APP_TITLE} v{APP_VERSION} — README.md not found", 6000
                )

        def _set_font(self, family: str = "", size: int = 0) -> None:
            """Change the display font family and/or size.

            Persists both *qt_font_family* and *qt_font_size*, then calls
            _apply_qt_theme so the QTextEdit stylesheet (which embeds the
            font-size) is refreshed in the same step.  Without this, a theme
            cycle after a size change would silently revert to the old size.
            """
            if family:
                self.settings["qt_font_family"] = family
            if size > 0:
                self.settings["qt_font_size"] = size
                # Keep font_size in sync so _apply_qt_theme always reads the
                # correct value regardless of which key it checks.
                self.settings["font_size"] = size
            fam = self._effective_font_family()
            fsz = int(self.settings.get("qt_font_size", 14))
            # setFont sets the base font for the widget (with letter/word
            # spacing); _apply_qt_theme then re-renders the HTML with the
            # matching font-size in the stylesheet and re-applies line height.
            self.editor.setFont(self._make_editor_font())
            self._apply_qt_theme(str(self.settings.get("theme", "dark")))
            self.statusBar().showMessage(f"Font: {fam} {fsz}pt")

        def _qt_copy(self) -> None:
            "Copy selected text or current paragraph to the clipboard."
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                text = cursor.selectedText()
            else:
                try:
                    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                except AttributeError:
                    cursor.select(QTextCursor.BlockUnderCursor)  # PyQt5
                text = cursor.selectedText()
            if text:
                QApplication.clipboard().setText(text)
                self.statusBar().showMessage(f"Copied {len(text)} chars")

        def _qt_reading_level(self) -> None:
            "Show Flesch-Kincaid reading level for the current document."
            if not self.doc or not self.doc.plain_text:
                self.statusBar().showMessage("No document loaded")
                return
            text = self.doc.plain_text[:50000]
            words = text.split()
            n_words = max(1, len(words))
            sentences = re.split(r"[.!?]+", text)
            n_sentences = max(1, len([s for s in sentences if s.strip()]))

            def _syl(w):
                w = w.lower().rstrip(".,;:!?")
                c = len(re.findall(r"[aeiou]+", w))
                if w.endswith("e") and c > 1:
                    c -= 1
                return max(1, c)

            n_syllables = sum(_syl(w) for w in words)
            ease = (
                206.835
                - 1.015 * (n_words / n_sentences)
                - 84.6 * (n_syllables / n_words)
            )
            grade = (
                0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
            )
            ease = max(0.0, min(100.0, ease))
            grade = max(0.0, grade)
            level = (
                "elementary"
                if grade < 6
                else "middle school"
                if grade < 9
                else "high school"
                if grade < 13
                else "college"
                if grade < 16
                else "graduate"
            )
            self.statusBar().showMessage(
                f"Reading level: Grade {grade:.1f} ({level})  Ease: {ease:.0f}/100",
                8000,
            )

        # ── Export methods ───────────────────────────────────────────────

        def _qt_batch_convert(self) -> None:
            """Convert many files / a folder to one format (File ▸ Batch Convert).

            Select multiple files (or, if none are chosen, a folder), pick one
            output format and one output directory, then run the shared,
            failure-isolated batch core on a background thread.
            """
            sel, _ = QFileDialog.getOpenFileNames(
                self, "Select documents to convert (Cancel to choose a folder)", ""
            )
            paths: List[str] = list(sel)
            if not paths:
                folder = QFileDialog.getExistingDirectory(
                    self, "Select a folder of documents to convert"
                )
                if folder:
                    paths = [folder]
            if not paths:
                return
            fmts = supported_formats()
            cur = str(self.settings.get("batch_format", "markdown"))
            idx = fmts.index(cur) if cur in fmts else 0
            fmt, ok = QInputDialog.getItem(
                self, "Batch Convert", "Convert everything to:", fmts, idx, False
            )
            if not ok or not fmt:
                return
            fmt = resolve_format(fmt)
            self.settings.set("batch_format", fmt)
            out_dir = QFileDialog.getExistingDirectory(
                self, "Choose the output directory"
            )
            if not out_dir:
                return

            def _work() -> None:
                def _progress(done: int, total: int, result) -> None:
                    state = "ok" if result.ok else "FAILED"
                    self._batch_progress_signal.emit(
                        f"Batch {done}/{total}: {Path(result.source).name} — {state}"
                    )

                summary = run_batch(
                    paths, out_dir, fmt, self.settings, progress=_progress
                )
                lines = [
                    "Batch conversion complete.",
                    "",
                    f"Succeeded: {len(summary.succeeded)} / {summary.total}",
                    f"Failed: {len(summary.failed)}",
                    f"Output: {out_dir}",
                ]
                if summary.log_path:
                    lines.append(f"Log: {summary.log_path}")
                if summary.failed:
                    lines.append("")
                    lines.append("Failures:")
                    for r in summary.failed[:20]:
                        lines.append(f"  • {Path(r.source).name}: {r.error}")
                    if len(summary.failed) > 20:
                        lines.append(
                            f"  …and {len(summary.failed) - 20} more (see log)."
                        )
                self._batch_done_signal.emit("\n".join(lines))

            self.statusBar().showMessage("Batch conversion started…")
            threading.Thread(target=_work, daemon=True).start()

        def _on_batch_done(self, msg: str) -> None:
            self.statusBar().showMessage("Batch conversion complete.")
            QMessageBox.information(self, "Batch Convert", msg)

        def _qt_watch_folder(self) -> None:
            """Start or stop hot-folder watching from the GUI (toggle).

            Converts files dropped into a chosen folder in the background using
            the same pipeline as ``star --watch``, so the GUI stays fully usable
            (and keyboard-driven) while it runs.  Invoking it again stops it.
            """
            if self._watcher is not None:
                try:
                    self._watcher.stop()
                finally:
                    self._watcher = None
                self._watch_action.setText("Watch Folder…")
                self.statusBar().showMessage("Stopped watching folder.")
                return
            in_dir = QFileDialog.getExistingDirectory(self, "Select a folder to watch")
            if not in_dir:
                return
            out_dir = QFileDialog.getExistingDirectory(
                self, "Choose the output directory"
            )
            if not out_dir:
                return
            fmts = supported_formats()
            cur = str(self.settings.get("watch_format", "markdown"))
            idx = fmts.index(cur) if cur in fmts else 0
            fmt, ok = QInputDialog.getItem(
                self, "Watch Folder", "Convert new files to:", fmts, idx, False
            )
            if not ok or not fmt:
                return
            fmt = resolve_format(fmt)
            self.settings.set("watch_format", fmt)
            # The watcher's own logger writes <output>/star-watch.log (+ stderr);
            # add a handler that mirrors each line into the status bar.
            import logging

            logger = _make_logger(Path(out_dir))

            class _StatusHandler(logging.Handler):
                def emit(_self, record: "logging.LogRecord") -> None:
                    try:
                        self._watch_signal.emit(record.getMessage())
                    except Exception:
                        pass

            logger.addHandler(_StatusHandler())
            try:
                self._watcher = HotFolderWatcher(
                    in_dir, out_dir, fmt, self.settings, logger=logger
                )
                self._watcher.start()
            except Exception as exc:
                self._watcher = None
                self.statusBar().showMessage(f"Watch error: {exc}")
                return
            self._watch_action.setText("Stop Watching Folder")
            self.statusBar().showMessage(f"Watching {in_dir} → {out_dir}  [{fmt}]")

        def _qt_export_markdown(self) -> None:
            """Save the current document as a Markdown file."""
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            p = Path(self.doc.path) if self.doc.path else Path("export")
            default = str(p.parent / (p.stem + ".md"))
            dest, _ = QFileDialog.getSaveFileName(
                self, "Export as Markdown", default, "Markdown (*.md *.markdown)"
            )
            if not dest:
                return
            try:
                Path(dest).write_text(self.doc.markdown, encoding="utf-8")
                self.statusBar().showMessage(f"Exported Markdown → {dest}")
            except OSError as e:
                self.statusBar().showMessage(f"Export error: {e}")

        def _qt_export_pdf(self) -> None:
            """Save the current document as a PDF (via Qt's built-in printer).

            User highlights are rendered into the PDF because we temporarily
            apply them as document char-format before printing, then reload
            the HTML to revert.
            """
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            p = Path(self.doc.path) if self.doc.path else Path("export")
            default = str(p.parent / (p.stem + ".pdf"))
            dest, _ = QFileDialog.getSaveFileName(
                self, "Export as PDF", default, "PDF Files (*.pdf)"
            )
            if not dest:
                return
            try:
                try:
                    from PyQt6.QtPrintSupport import QPrinter  # type: ignore

                    _pdf_format = QPrinter.OutputFormat.PdfFormat
                    _hi_res = QPrinter.PrinterMode.HighResolution
                except ImportError:
                    from PyQt5.QtPrintSupport import QPrinter  # type: ignore

                    _pdf_format = QPrinter.PdfFormat
                    _hi_res = QPrinter.HighResolution
            except ImportError:
                self.statusBar().showMessage(
                    "PDF export requires PyQt6.QtPrintSupport or PyQt5.QtPrintSupport"
                )
                return

            printer = QPrinter(_hi_res)
            printer.setOutputFormat(_pdf_format)
            printer.setOutputFileName(dest)

            # Apply user highlights to the document temporarily so they
            # are baked into the PDF output.
            doc_obj = self.editor.document()
            path_key = (self.doc.path or "__no_path__") if self.doc else "__no_path__"
            highlights = self.settings._data.get("user_highlights", {}).get(
                path_key, []
            )
            for hl in highlights:
                cur = QTextCursor(doc_obj)
                cur.setPosition(hl.get("start", 0))
                cur.setPosition(hl.get("end", 0), _KEEP_ANCHOR)
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(hl.get("color", "#ffff00")))
                cur.mergeCharFormat(fmt)

            doc_obj.print_(printer)
            self.statusBar().showMessage(f"Exported PDF → {dest}")

            # Revert: reload the original HTML (erases inline format changes).
            self.editor.setHtml(self._md_to_html(self.doc.markdown or ""))
            self._qt_apply_user_highlights()

        def _qt_export_brf(self) -> None:
            """Save the current document as a Braille-Ready File (.brf)."""
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            p = Path(self.doc.path) if self.doc.path else Path("export")
            default = str(p.parent / (p.stem + ".brf"))
            dest, _ = QFileDialog.getSaveFileName(
                self, "Export as Braille", default, "Braille (*.brf)"
            )
            if not dest:
                return
            table = str(self.settings.get("braille_table", "en-ueb-g2.ctb"))
            brf = _export_braille(
                self.doc.plain_text,
                table,
                use_liblouis=bool(self.settings.get("braille_grade2", False)),
            )
            try:
                Path(dest).write_text(brf, encoding="utf-8")
                self.statusBar().showMessage(f"Exported BRF → {dest}")
            except OSError as e:
                self.statusBar().showMessage(f"Export error: {e}")

        def _qt_export_audio(self) -> None:
            """Export the full document as a TTS audio file.

            Synthesis runs in a background thread so the GUI stays responsive.
            **WAV is the default** because it needs no external tools; MP3,
            OGG, and MP4 output additionally require **ffmpeg** (recommended)
            or **pydub** (``pip install pydub``).
            """
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            p = Path(self.doc.path) if self.doc.path else Path("export")
            fmt = str(self.settings.get("audio_export_format", "wav")).lstrip(".")
            default = str(p.parent / (p.stem + f".{fmt}"))
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Export as Audio",
                default,
                "Audio Files (*.wav *.mp3 *.ogg *.mp4);;All Files (*)",
            )
            if not dest:
                return
            text = _preprocess_tts_text(self.doc.plain_text, self.settings)
            fmt = Path(dest).suffix.upper().lstrip(".") or "MP3"
            # Optionally emit a synchronized caption track next to the audio.
            sub_path: Optional[str] = None
            sub_fmt = str(self.settings.get("subtitle_format", "srt")).lower()
            if self.settings.get("export_subtitles_with_audio", False):
                sub_path = str(Path(dest).with_suffix(f".{sub_fmt}"))
            word_level = bool(self.settings.get("subtitle_word_level", False))
            self.statusBar().showMessage(
                f"Exporting {fmt} audio … this may take a while"
            )

            def _do_export() -> None:
                try:
                    self.tts_manager.export_audio(
                        text,
                        dest,
                        subtitle_path=sub_path,
                        subtitle_format=sub_fmt,
                        subtitle_word_level=word_level,
                    )
                    msg = f"Audio exported → {dest}"
                    if sub_path:
                        msg += f"  (+ {Path(sub_path).name})"
                    self._export_audio_signal.emit(msg)
                except Exception as exc:
                    self._export_audio_signal.emit(f"Audio export error: {exc}")

            threading.Thread(target=_do_export, daemon=True).start()

        def _qt_export_subtitles(self) -> None:
            """Export a timestamped SRT/VTT caption track synchronized to the
            document's synthesized speech.

            The format is chosen from the file extension (``.srt`` or ``.vtt``).
            Synthesis runs in a background thread so the GUI stays responsive.
            """
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            p = Path(self.doc.path) if self.doc.path else Path("export")
            fmt = str(self.settings.get("subtitle_format", "srt")).lower()
            if fmt not in ("srt", "vtt"):
                fmt = "srt"
            default = str(p.parent / (p.stem + f".{fmt}"))
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Export Subtitles",
                default,
                "Subtitles (*.srt *.vtt);;All Files (*)",
            )
            if not dest:
                return
            out_fmt = "vtt" if dest.lower().endswith(".vtt") else "srt"
            text = _preprocess_tts_text(self.doc.plain_text, self.settings)
            word_level = bool(self.settings.get("subtitle_word_level", False))
            self.statusBar().showMessage("Generating subtitles … this may take a while")

            def _do_export() -> None:
                try:
                    self.tts_manager.export_subtitles(
                        text, dest, fmt=out_fmt, word_level=word_level
                    )
                    self._export_audio_signal.emit(f"Subtitles exported → {dest}")
                except Exception as exc:
                    self._export_audio_signal.emit(f"Subtitle export error: {exc}")

            threading.Thread(target=_do_export, daemon=True).start()

        def _qt_pick_backend(self) -> None:
            """Choose the active TTS engine (pyttsx3 / espeak / piper / …).

            Lets the user switch to a neural backend such as Piper
            without editing settings.json.  Switching to a backend with no
            available voice keeps the previous engine and explains why.
            """
            engines = [
                "auto",
                "pyttsx3",
                "espeak",
                "festival",
                "piper",
                "coqui",
                "dectalk",
                "none",
            ]
            current = str(self.settings.get("tts_backend", "auto"))
            cur_idx = engines.index(current) if current in engines else 0
            chosen, ok = QInputDialog.getItem(
                self,
                "Choose TTS Engine",
                "Speech backend:",
                engines,
                cur_idx,
                False,
            )
            if not ok:
                return
            backend_name = "silent" if chosen == "none" else chosen
            self.tts_manager.change_backend(backend_name)
            active = self.tts_manager.backend_name
            if chosen in ("piper", "coqui") and active != chosen:
                hint = (
                    "Install the piper binary and a .onnx voice model, then set"
                    " 'piper_model' in settings.json."
                    if chosen == "piper"
                    else "Install Coqui TTS (pip install TTS)."
                )
                self.statusBar().showMessage(
                    f"{chosen} unavailable — using {active}. {hint}"
                )
            else:
                self.statusBar().showMessage(f"TTS engine: {active}")

        # ── Voice & profile presets ───────────────────────────────────────

        def _qt_apply_loaded_settings(self) -> None:
            """Re-apply runtime state after a profile's values were written to
            settings: backend/voice/rate/volume, theme, font, spacing, the
            karaoke highlight format, and the checkable reading-aid actions."""
            try:
                self.tts_manager.change_backend(
                    str(self.settings.get("tts_backend", "auto"))
                )
                voice = str(self.settings.get("tts_voice", ""))
                if voice:
                    self.tts_manager._backend.set_voice(voice)
                self.tts_manager.set_rate(int(self.settings.get("tts_rate", 265)))
                self.tts_manager.set_volume(float(self.settings.get("tts_volume", 1.0)))
            except Exception:
                pass
            # Visual settings.
            self.editor.setFont(self._make_editor_font())
            self._rebuild_hl_fmt()
            self._apply_qt_theme(str(self.settings.get("theme", "dark")))
            self._apply_text_spacing()
            # Sync the checkable reading-aid menu actions.
            for attr, key in (
                ("_dyslexia_font_act", "qt_dyslexia_font"),
                ("_bionic_act", "qt_bionic_reading"),
                ("_current_line_act", "qt_current_line_highlight"),
                ("_vocab_act", "qt_vocab_highlight"),
            ):
                act = getattr(self, attr, None)
                if act is not None:
                    act.setChecked(bool(self.settings.get(key, False)))
            # A profile may have flipped the difficult-word overlay; rebuild it.
            self._qt_refresh_vocab_highlight()

        def _qt_save_profile(self) -> None:
            """Save the current settings as a named profile."""
            name, ok = QInputDialog.getText(
                self,
                "Save Profile",
                "Profile name (voice, rate, theme, font, spacing, highlight):",
            )
            if not ok or not name.strip():
                return
            _save_profile(self.settings, name)
            self.statusBar().showMessage(f"Profile saved: {name.strip()}")

        def _qt_load_profile(self) -> None:
            """Pick a saved profile and apply it in one step."""
            profiles = self.settings.get("profiles", {}) or {}
            if not profiles:
                self.statusBar().showMessage(
                    "No profiles saved — use Profiles → Save Current Settings"
                )
                return
            names = sorted(profiles)
            chosen, ok = QInputDialog.getItem(
                self, "Load Profile", "Apply which profile?", names, 0, False
            )
            if not ok or chosen not in profiles:
                return
            _apply_profile_values(self.settings, chosen)
            self._qt_apply_loaded_settings()
            self.statusBar().showMessage(f"Profile loaded: {chosen}")

        def _qt_delete_profile(self) -> None:
            """Pick a saved profile and delete it."""
            profiles = self.settings.get("profiles", {}) or {}
            if not profiles:
                self.statusBar().showMessage("No profiles to delete")
                return
            names = sorted(profiles)
            chosen, ok = QInputDialog.getItem(
                self, "Delete Profile", "Delete which profile?", names, 0, False
            )
            if not ok or chosen not in profiles:
                return
            _delete_profile(self.settings, chosen)
            self.statusBar().showMessage(f"Profile deleted: {chosen}")

        # ── Pronunciation lexicon editor ───────────────────────────

        def _qt_pronunciations(self) -> None:
            """Open the pronunciation-lexicon editor.

            Maps domain terms (drug names, anatomy, acronyms) to a spoken form
            so TTS pronounces them correctly.  Entries apply to every backend
            and are stored in settings under ``pronunciations``.
            """
            dlg = QDialog(self)
            dlg.setWindowTitle("Pronunciation Lexicon")
            dlg.resize(560, 460)
            lay = QVBoxLayout(dlg)

            enabled = QCheckBox("Apply pronunciations while reading")
            enabled.setChecked(bool(self.settings.get("use_pronunciations", True)))
            enabled.toggled.connect(
                lambda v: self.settings.set("use_pronunciations", bool(v))
            )
            lay.addWidget(enabled)

            info = QLabel(
                "Term → spoken form.  Matching is whole-word and case-insensitive."
            )
            info.setWordWrap(True)
            lay.addWidget(info)

            lst = QListWidget()
            lay.addWidget(lst)

            def _refresh() -> None:
                lst.clear()
                lex = self.settings.get("pronunciations", {}) or {}
                for term in sorted(lex):
                    item = QListWidgetItem(f"{term}  →  {lex[term]}")
                    item.setData(_USER_ROLE, term)
                    lst.addItem(item)

            def _store(lex: Dict[str, str]) -> None:
                self.settings.set("pronunciations", lex)
                _refresh()

            def _add() -> None:
                term, ok = QInputDialog.getText(
                    dlg, "Add Pronunciation", "Term (as written):"
                )
                if not ok or not term.strip():
                    return
                spoken, ok2 = QInputDialog.getText(
                    dlg, "Add Pronunciation", f"Spoken form for “{term.strip()}”:"
                )
                if not ok2 or not spoken.strip():
                    return
                lex = dict(self.settings.get("pronunciations", {}) or {})
                lex[term.strip()] = spoken.strip()
                _store(lex)

            def _edit() -> None:
                item = lst.currentItem()
                if item is None:
                    return
                term = item.data(_USER_ROLE)
                lex = dict(self.settings.get("pronunciations", {}) or {})
                spoken, ok = QInputDialog.getText(
                    dlg,
                    "Edit Pronunciation",
                    f"Spoken form for “{term}”:",
                    text=str(lex.get(term, "")),
                )
                if not ok:
                    return
                if spoken.strip():
                    lex[term] = spoken.strip()
                else:
                    lex.pop(term, None)
                _store(lex)

            def _delete() -> None:
                item = lst.currentItem()
                if item is None:
                    return
                term = item.data(_USER_ROLE)
                lex = dict(self.settings.get("pronunciations", {}) or {})
                lex.pop(term, None)
                _store(lex)

            row = QHBoxLayout()
            for _lbl, _fn in (
                ("Add…", _add),
                ("Edit…", _edit),
                ("Delete", _delete),
            ):
                b = QPushButton(_lbl)
                b.clicked.connect(lambda _chk=False, f=_fn: f())
                row.addWidget(b)
            lay.addLayout(row)

            lst.itemActivated.connect(lambda _it: _edit())
            _refresh()
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()

        # ── User highlights ────────────────────────────────────────────────

        def _qt_highlight(self, color: str = "#ffff00") -> None:
            """Highlight the current selection in the given color and persist it.

            If no text is selected, shows a hint in the status bar.
            Default color is yellow; the Highlight menu exposes five presets.
            Shortcut: Ctrl+H (applies yellow highlight).
            """
            cursor = self.editor.textCursor()
            if not cursor.hasSelection():
                self.statusBar().showMessage(
                    "Select text first, then press Ctrl+H or choose Highlight menu"
                )
                return
            if not self.doc:
                return
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            path_key = self.doc.path or "__no_path__"
            hl_store: dict = self.settings._data.setdefault("user_highlights", {})
            hl_list: list = hl_store.setdefault(path_key, [])
            hl_list.append({"start": start, "end": end, "color": color})
            self.settings.save()
            self._qt_apply_user_highlights()
            self.statusBar().showMessage(f"Highlight added ({color})")

        def _qt_highlight_clear(self) -> None:
            """Remove all user highlights for the current document."""
            if not self.doc:
                return
            path_key = self.doc.path or "__no_path__"
            hl_store: dict = self.settings._data.get("user_highlights", {})
            if path_key in hl_store:
                hl_store[path_key] = []
            self.settings.save()
            self.editor.setExtraSelections([])
            self.statusBar().showMessage("Highlights cleared")

        def _qt_apply_user_highlights(self) -> None:
            """Re-apply all persisted user highlights for the current document
            as extra selections (non-destructive, does not modify the document)."""
            self.editor.setExtraSelections(self._get_user_highlight_selections())

        def _get_user_highlight_selections(self) -> list:
            """Return a list of ExtraSelection objects for all saved user highlights.
            Called both by _qt_apply_user_highlights and _apply_word_highlight
            so TTS word highlights are always merged on top."""
            if not self.doc:
                return []
            path_key = self.doc.path or "__no_path__"
            highlights = self.settings._data.get("user_highlights", {}).get(
                path_key, []
            )
            doc_obj = self.editor.document()
            doc_len = doc_obj.characterCount()
            selections = []
            for hl in highlights:
                start = hl.get("start", 0)
                end = hl.get("end", 0)
                if start >= end or end > doc_len:
                    continue
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(hl.get("color", "#ffff00")))
                cur = QTextCursor(doc_obj)
                cur.setPosition(start)
                cur.setPosition(end, _KEEP_ANCHOR)
                sel = QTextEdit.ExtraSelection()
                sel.format = fmt
                sel.cursor = cur
                selections.append(sel)
            # Difficult-word overlay paints *under* user highlights (so a user
            # highlight always wins where they overlap) and under the TTS word
            # highlight, which _apply_word_highlight appends on top of all of
            # these.
            return self._vocab_selections + selections

        def _compute_vocab_selections(self) -> None:
            """Rebuild the difficult-word overlay's extra-selection cache.

            Scans the rendered document once, flags words whose English Zipf
            frequency is below the threshold, and stores one ExtraSelection per
            occurrence so _get_user_highlight_selections can merge them in
            cheaply on every repaint (including each TTS word step).
            """
            self._vocab_selections = []
            if not (_WORDFREQ and self.doc):
                return
            plain = self.editor.document().toPlainText()
            if not plain:
                return
            difficult = find_difficult_words(plain)
            if not difficult:
                return
            doc_obj = self.editor.document()
            doc_len = doc_obj.characterCount()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#fffacd"))  # lemon chiffon (light yellow)
            selections: List[Any] = []
            for m in re.finditer(r"[A-Za-z]+", plain):
                if m.group(0).lower() not in difficult:
                    continue
                start, end = m.start(), m.end()
                if end > doc_len:
                    break
                cur = QTextCursor(doc_obj)
                cur.setPosition(start)
                cur.setPosition(end, _KEEP_ANCHOR)
                sel = QTextEdit.ExtraSelection()
                sel.format = fmt
                sel.cursor = cur
                selections.append(sel)
                if len(selections) >= 5000:
                    # Soft cap: a pathologically long document can't flood the
                    # overlay with selections (and slow every repaint).
                    break
            self._vocab_selections = selections

        def _qt_refresh_vocab_highlight(self) -> None:
            """Recompute the overlay (when on) and repaint all extra-selections."""
            if self.settings.get("qt_vocab_highlight", False):
                self._compute_vocab_selections()
            else:
                self._vocab_selections = []
            self._qt_apply_user_highlights()

        def _qt_toggle_vocab_highlight(self) -> None:
            """Toggle the difficult-word overlay on the current document."""
            if not _WORDFREQ:
                QMessageBox.information(
                    self,
                    "Vocabulary overlay unavailable",
                    "Highlighting difficult words requires wordfreq:\n\n"
                    "    pip install wordfreq",
                )
                if hasattr(self, "_vocab_act"):
                    self._vocab_act.setChecked(False)
                return
            new = not bool(self.settings.get("qt_vocab_highlight", False))
            self.settings["qt_vocab_highlight"] = new
            if hasattr(self, "_vocab_act"):
                self._vocab_act.setChecked(new)
            self._qt_refresh_vocab_highlight()
            self.statusBar().showMessage(
                "Highlight difficult words: " + ("ON" if new else "OFF")
            )

        # ── Table of Contents panel ───────────────────────────────────────────

        def _qt_build_toc(self) -> None:
            """Populate the Contents dock from the current document headings.

            Each item stores two roles:
              _USER_ROLE     – the raw heading title (used for display).
              _USER_ROLE + 1 – the pre-computed character offset of that
                               heading inside the rendered QTextDocument.

            The character offset is found with a *rolling forward search* so
            that repeated section titles (e.g. "Introduction" in multiple
            chapters) each resolve to their own occurrence rather than always
            the first.  -1 is stored when the title cannot be located.
            """
            self._toc_list.clear()
            if not self.doc:
                return
            search_from = 0  # advance past each match to avoid re-matching
            for line in (self.doc.markdown or "").splitlines():
                m = re.match(r"^(#{1,6})\s+(.*)", line)
                if not m:
                    continue
                level = len(m.group(1))
                title = m.group(2).strip()
                if not title:
                    continue
                indent = "\u2002" * (level - 1) * 2  # en-spaces for visual indent
                item = QListWidgetItem(indent + title)
                item.setData(_USER_ROLE, title)
                # Locate this heading in the rendered document using a
                # rolling cursor so identical heading titles in different
                # chapters resolve to their own paragraph, not always the
                # first occurrence (which is the bug that made ToC always
                # start speech from word 0).
                c = self.editor.document().find(title, search_from)
                if not c.isNull():
                    char_pos: int = c.selectionStart()
                    search_from = c.selectionEnd() + 1
                else:
                    char_pos = -1
                item.setData(_USER_ROLE + 1, char_pos)
                self._toc_list.addItem(item)

        def _qt_char_to_word(self, char_pos: int) -> int:
            """Return the word-map index of the first TTS word at or after
            *char_pos* (a character offset in the rendered QTextDocument).

            Handles three edge cases robustly:
              • *char_pos* is before the first word  → returns 0.
              • *char_pos* is past the last word     → returns the last index.
              • _qt_word_map is still empty (async build in progress)
                → falls back to a proportional estimate using doc.word_map
                  length so at least the correct region of the document is
                  reached rather than always word 0.
            """
            wm = self._qt_word_map
            if wm:
                for i, off in enumerate(wm):
                    if off >= char_pos:
                        return i
                # char_pos is past every mapped word — start from the last.
                return len(wm) - 1

            # Fallback: word map not yet built by the background thread.
            # Estimate position proportionally so the user lands in roughly
            # the right place instead of always restarting from word 0.
            if self.doc and self.doc.word_map:
                doc_len = self.editor.document().characterCount()
                if doc_len > 1:
                    pct = char_pos / doc_len
                    return max(
                        0,
                        min(
                            int(pct * len(self.doc.word_map)),
                            len(self.doc.word_map) - 1,
                        ),
                    )
            return 0

        def _qt_toc_navigate(self, item: QListWidgetItem) -> None:
            """Single-click / Enter: scroll the viewport to the heading.

            Intentionally does *not* stop or redirect speech — the user
            may be browsing the ToC while the book reads.  To jump speech
            to a heading, double-click instead.
            """
            char_pos_data = item.data(_USER_ROLE + 1)
            char_pos: int = char_pos_data if char_pos_data is not None else -1
            if char_pos < 0:
                # Heading wasn't found at build time — try a live search.
                title = item.data(_USER_ROLE) or ""
                c = self.editor.document().find(title)
                if c.isNull():
                    return
                char_pos = c.selectionStart()
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(char_pos)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            title = item.data(_USER_ROLE) or ""
            self.statusBar().showMessage(
                f"Navigated to: {title}  \u00b7  double-click to start reading here"
            )

        def _qt_toc_play(self, item: QListWidgetItem) -> None:
            """Double-click: stop current speech and start reading from the heading.

            Word-index resolution uses a direct search of *doc.plain_text* —
            the same text the speech engine will speak — rather than the
            Qt-char-offset → _qt_word_map indirection.  The indirection fails
            silently in several common situations:

              • _qt_word_map is still being built asynchronously.
              • Char positions become stale after a theme re-render.
              • document().find() matches the title in body text that
                precedes the actual heading, giving char_pos ≈ 0.

            Duplicate heading titles are handled by counting the number of
            items before this one in the ToC list that carry the same title
            and picking the corresponding occurrence in plain_text.
            """
            if not self.doc:
                return
            title = item.data(_USER_ROLE) or ""
            if not title:
                return

            # ── Scroll the viewport to the heading ───────────────────────
            char_pos_data = item.data(_USER_ROLE + 1)
            char_pos: int = char_pos_data if char_pos_data is not None else -1
            if char_pos < 0:
                c = self.editor.document().find(title)
                if not c.isNull():
                    char_pos = c.selectionStart()
            if char_pos >= 0:
                scroll_cur = QTextCursor(self.editor.document())
                scroll_cur.setPosition(char_pos)
                self.editor.setTextCursor(scroll_cur)
                self.editor.ensureCursorVisible()

            # ── Determine which occurrence of this title we want ─────────
            # Some documents have identical headings in multiple chapters
            # (e.g. “Introduction” repeated).  Count prior ToC rows with the
            # same title to pick the correct occurrence in plain_text.
            row = self._toc_list.row(item)
            occurrence = sum(
                1
                for r in range(row)
                if (
                    (self._toc_list.item(r) or QListWidgetItem()).data(_USER_ROLE)
                    == title
                )
            )

            # ── Search doc.plain_text for the heading ────────────────────
            plain = self.doc.plain_text or ""
            plain_lower = plain.lower()
            title_lower = title.lower()
            search_pos = 0
            tts_pos = -1
            for _ in range(occurrence + 1):
                idx = plain_lower.find(title_lower, search_pos)
                if idx < 0:
                    break
                tts_pos = idx
                search_pos = idx + max(1, len(title_lower))

            # ── Map plain-text position → word index ────────────────────
            wm = getattr(self.doc, "word_map", [])
            if tts_pos >= 0 and wm:
                word_idx = len(wm) - 1  # default: last word
                for i, wp in enumerate(wm):
                    if wp.tts_offset >= tts_pos:
                        word_idx = i
                        break
            else:
                # word_map not ready yet (rare) — fall back to Qt mapping
                word_idx = self._qt_char_to_word(char_pos) if char_pos >= 0 else 0

            # ── Start speech from the heading ────────────────────────────
            self._tts_play_from_word(word_idx)
            self.statusBar().showMessage(f"▶  Reading from: {title}")

        def _qt_toggle_toc(self) -> None:
            """Toggle the visibility of the Contents dock panel."""
            visible = not self._toc_dock.isVisible()
            self._toc_dock.setVisible(visible)
            self.settings["qt_show_toc"] = visible

        # ── Annotations / Notes panel ────────────────────────────────────────

        def _annot_key(self) -> str:
            """Per-document key under which annotations are stored."""
            if not self.doc:
                return ""
            return self.doc.path or self.doc.title or ""

        def _qt_load_annotations(self) -> List[Dict[str, Any]]:
            """Return a mutable copy of the saved annotations for this document,
            sorted by document position."""
            key = self._annot_key()
            if not key:
                return []
            store = self.settings.get("annotations", {}) or {}
            items = [dict(a) for a in store.get(key, [])]
            items.sort(key=lambda a: int(a.get("char_pos", 0)))
            return items

        def _qt_store_annotations(self, items: List[Dict[str, Any]]) -> None:
            """Persist *items* as the annotation list for this document."""
            key = self._annot_key()
            if not key:
                return
            store = dict(self.settings.get("annotations", {}) or {})
            if items:
                store[key] = items
            else:
                store.pop(key, None)
            self.settings.set("annotations", store)

        def _qt_build_annotations(self) -> None:
            """Populate the Notes dock list from saved annotations.

            Each row stores the annotation's char position (_USER_ROLE + 1)
            and its index in the saved list (_USER_ROLE) so edit/delete can
            target the right entry even when the visible list is filtered.
            The filter box performs full-text search over the note, anchor,
            and tags; a `#tag` term filters by tag.
            """
            self._annot_list.clear()
            items = self._qt_load_annotations()
            query = self._annot_filter.text() if hasattr(self, "_annot_filter") else ""
            doc_len = max(1, self.editor.document().characterCount())
            shown = 0
            for idx, a in enumerate(items):
                if not _annotation_matches(a, query):
                    continue
                shown += 1
                note = str(a.get("note", "")).strip()
                anchor = str(a.get("anchor", "")).strip()
                tags = a.get("tags", []) or []
                cite = str(a.get("cite", "")).strip()
                pct = int(100 * int(a.get("char_pos", 0)) / doc_len)
                first = note.splitlines()[0] if note else "(empty note)"
                label = f"{pct:>3}%  {first}"
                meta = ""
                if tags:
                    meta += "  ".join(f"#{t}" for t in tags)
                if cite:
                    meta += ("  " if meta else "") + f"@{cite}"
                if anchor:
                    label += f"\n        “{anchor[:48]}”"
                if meta:
                    label += f"\n        {meta}"
                item = QListWidgetItem(label)
                item.setData(_USER_ROLE, idx)
                item.setData(_USER_ROLE + 1, int(a.get("char_pos", 0)))
                item.setToolTip(note or anchor)
                self._annot_list.addItem(item)
            if query and hasattr(self, "_annot_dock"):
                self._annot_dock.setWindowTitle(f"Notes ({shown}/{len(items)})")
            elif hasattr(self, "_annot_dock"):
                self._annot_dock.setWindowTitle(
                    f"Notes ({len(items)})" if items else "Notes"
                )

        def _qt_current_anchor(self) -> Tuple[int, str]:
            """Return (char_pos, anchor_text) for a new note.

            Uses the selection if there is one (so the user can annotate a
            specific passage), otherwise the cursor's paragraph as context.
            """
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                char_pos = cursor.selectionStart()
                anchor = cursor.selectedText()
            else:
                char_pos = cursor.position()
                anchor = cursor.block().text()
            # selectedText() uses U+2029 for line breaks; normalize whitespace.
            anchor = " ".join(anchor.split())[:120]
            return char_pos, anchor

        def _qt_add_annotation(self) -> None:
            """Prompt for note text and attach it at the current position."""
            if not self.doc:
                self.statusBar().showMessage("Open a document before adding notes")
                return
            char_pos, anchor = self._qt_current_anchor()
            text, ok = QInputDialog.getMultiLineText(
                self,
                "Add Note",
                f"Note for: “{anchor[:60]}”" if anchor else "Note:",
                "",
            )
            if not ok or not text.strip():
                return
            # Optional tags (comma/space separated; leading # optional).
            tag_str, _ok2 = QInputDialog.getText(
                self, "Tags (optional)", "Tags, comma-separated:"
            )
            tags = _parse_tags(tag_str)
            items = self._qt_load_annotations()
            items.append(
                {
                    "char_pos": int(char_pos),
                    "word_idx": self._qt_char_to_word(int(char_pos)),
                    "anchor": anchor,
                    "note": text.strip(),
                    "tags": tags,
                    "cite": "",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
            self._qt_store_annotations(items)
            self._qt_build_annotations()
            if not self._annot_dock.isVisible():
                self._annot_dock.setVisible(True)
                self.settings["qt_show_notes"] = True
            self.statusBar().showMessage(
                f"Note added{(' with tags: ' + ', '.join(tags)) if tags else ''}"
            )

        def _qt_selected_annotation_index(self) -> int:
            """Index (into the saved list) of the selected note, or -1."""
            item = self._annot_list.currentItem()
            if item is None:
                return -1
            data = item.data(_USER_ROLE)
            return int(data) if data is not None else -1

        def _qt_edit_annotation(self) -> None:
            """Edit the text of the selected note."""
            idx = self._qt_selected_annotation_index()
            items = self._qt_load_annotations()
            if idx < 0 or idx >= len(items):
                self.statusBar().showMessage("Select a note to edit")
                return
            text, ok = QInputDialog.getMultiLineText(
                self, "Edit Note", "Note:", str(items[idx].get("note", ""))
            )
            if not ok:
                return
            if not text.strip():
                # Empty text deletes the note.
                del items[idx]
            else:
                items[idx]["note"] = text.strip()
                items[idx]["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._qt_store_annotations(items)
            self._qt_build_annotations()
            self.statusBar().showMessage("Note updated")

        def _qt_delete_annotation(self) -> None:
            """Delete the selected note."""
            idx = self._qt_selected_annotation_index()
            items = self._qt_load_annotations()
            if idx < 0 or idx >= len(items):
                self.statusBar().showMessage("Select a note to delete")
                return
            del items[idx]
            self._qt_store_annotations(items)
            self._qt_build_annotations()
            self.statusBar().showMessage("Note deleted")

        def _qt_annotation_charpos(self, item: QListWidgetItem) -> int:
            """Resolve a Qt character position for a notes-list *item*.

            Prefers the stored Qt char position; falls back to the note's
            word index (how TUI-created notes are anchored) mapped through
            the Qt word map so notes made in either UI navigate correctly.
            """
            data = item.data(_USER_ROLE + 1)
            char_pos = int(data) if data is not None else -1
            if char_pos and char_pos > 0:
                return char_pos
            idx = item.data(_USER_ROLE)
            items = self._qt_load_annotations()
            if idx is not None and 0 <= int(idx) < len(items):
                wi = int(items[int(idx)].get("word_idx", 0) or 0)
                if self._qt_word_map and 0 <= wi < len(self._qt_word_map):
                    return self._qt_word_map[wi]
            return char_pos

        def _qt_annotation_navigate(self, item: QListWidgetItem) -> None:
            """Single-click / Enter: scroll the viewport to the note anchor."""
            char_pos = self._qt_annotation_charpos(item)
            if char_pos < 0:
                return
            doc_len = self.editor.document().characterCount()
            char_pos = max(0, min(char_pos, doc_len - 1))
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(char_pos)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

        def _qt_annotation_play(self, item: QListWidgetItem) -> None:
            """Double-click: start reading from the note anchor."""
            if not self.doc:
                return
            char_pos = self._qt_annotation_charpos(item)
            if char_pos < 0:
                return
            self._tts_play_from_word(self._qt_char_to_word(char_pos))

        def _qt_toggle_annotations(self) -> None:
            """Toggle the visibility of the Notes dock panel."""
            visible = not self._annot_dock.isVisible()
            self._annot_dock.setVisible(visible)
            self.settings["qt_show_notes"] = visible

        def _qt_export_annotations(self) -> None:
            """Export the current document's notes to Markdown / JSON / BibTeX / RIS.

            The format is chosen by the file extension in the save dialog.
            BibTeX and RIS emit a single reference for the source document with
            the notes attached (the standard reference-manager convention).
            """
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            items = self._qt_load_annotations()
            if not items:
                self.statusBar().showMessage("No notes to export")
                return
            p = Path(self.doc.path) if self.doc.path else Path("notes")
            default = str(p.parent / (p.stem + "_notes.md"))
            dest, _flt = QFileDialog.getSaveFileName(
                self,
                "Export Notes",
                default,
                "Markdown (*.md);;JSON (*.json);;BibTeX (*.bib);;RIS (*.ris);;Text (*.txt)",
            )
            if not dest:
                return
            ext = Path(dest).suffix.lower()
            meta = getattr(self.doc, "metadata", {}) or {}
            title = self.doc.title or Path(self.doc.path or "document").stem
            author = (
                meta.get("author") or meta.get("creator") or meta.get("Author") or ""
            )
            try:
                content = _format_annotations(
                    items, ext, title, author, self.doc.path or ""
                )
                Path(dest).write_text(content, encoding="utf-8")
                self.statusBar().showMessage(f"Exported {len(items)} note(s) → {dest}")
            except OSError as exc:
                self.statusBar().showMessage(f"Export error: {exc}")

        def _qt_export_anki(self) -> None:
            """Export the current document's notes as an Anki deck (.apkg).

            Each note becomes a card: the highlighted passage on the front, the
            user's note on the back.  Requires genanki and at least one note.
            """
            if not _GENANKI:
                QMessageBox.information(
                    self,
                    "Anki export unavailable",
                    "Anki flashcard export requires genanki:\n\n"
                    "    pip install genanki",
                )
                return
            if not self.doc:
                self.statusBar().showMessage("No document loaded")
                return
            items = self._qt_load_annotations()
            if not items:
                QMessageBox.information(
                    self,
                    "No notes to export",
                    "Add a note or two first — each note becomes a flashcard.",
                )
                return
            title = self.doc.title or Path(self.doc.path or "document").stem
            p = Path(self.doc.path) if self.doc.path else Path(title)
            default = str(p.parent / (p.stem + ".apkg"))
            dest, _flt = QFileDialog.getSaveFileName(
                self, "Export Anki Flashcards", default, "Anki Deck (*.apkg)"
            )
            if not dest:
                return
            if not dest.lower().endswith(".apkg"):
                dest += ".apkg"
            try:
                export_anki_deck(items, title, dest)
                self.statusBar().showMessage(
                    f"Exported {len(items)} flashcard(s) → {dest}"
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Anki export failed", str(exc))
                self.statusBar().showMessage(f"Anki export error: {exc}")

        # ── Citation manager ──────────────────────────────

        def _qt_load_citations(self) -> List[Dict[str, Any]]:
            return [dict(c) for c in (self.settings.get("citations", []) or [])]

        def _qt_store_citations(self, items: List[Dict[str, Any]]) -> None:
            self.settings.set("citations", items)

        def _qt_import_citations(self) -> None:
            """Import citations from a BibTeX / RIS / CSL-JSON file."""
            src, _flt = QFileDialog.getOpenFileName(
                self,
                "Import Citations",
                "",
                "Citations (*.bib *.ris *.json *.csl);;All Files (*)",
            )
            if not src:
                return
            try:
                imported = _import_citations(src)
            except Exception as exc:  # noqa: BLE001
                self.statusBar().showMessage(f"Import error: {exc}")
                return
            existing = self._qt_load_citations()
            by_id = {c.get("id"): c for c in existing if c.get("id")}
            added = 0
            for c in imported:
                cid = c.get("id")
                if cid and cid in by_id:
                    by_id[cid].update(c)  # refresh existing
                else:
                    existing.append(c)
                    if cid:
                        by_id[cid] = c
                    added += 1
            self._qt_store_citations(existing)
            self.statusBar().showMessage(
                f"Imported {len(imported)} citation(s) ({added} new); "
                f"library now {len(existing)}"
            )

        def _qt_export_citations(self) -> None:
            """Export the citation library to BibTeX / RIS / CSL-JSON."""
            items = self._qt_load_citations()
            if not items:
                self.statusBar().showMessage("Citation library is empty")
                return
            dest, _flt = QFileDialog.getSaveFileName(
                self,
                "Export Citations",
                "citations.bib",
                "BibTeX (*.bib);;RIS (*.ris);;CSL-JSON (*.json)",
            )
            if not dest:
                return
            try:
                Path(dest).write_text(
                    _format_citations(items, Path(dest).suffix.lower()),
                    encoding="utf-8",
                )
                self.statusBar().showMessage(
                    f"Exported {len(items)} citation(s) → {dest}"
                )
            except OSError as exc:
                self.statusBar().showMessage(f"Export error: {exc}")

        def _qt_add_citation(self) -> None:
            """Add a citation to the library by hand (a few quick prompts)."""
            fields = [
                ("id", "Citation key (e.g. smith2020):"),
                ("title", "Title:"),
                ("author", "Author(s) (Last, First and Last, First):"),
                ("year", "Year:"),
                ("journal", "Journal / container (optional):"),
                ("doi", "DOI (optional):"),
            ]
            cite: Dict[str, Any] = {"type": "article"}
            for key, prompt in fields:
                val, ok = QInputDialog.getText(self, "Add Citation", prompt)
                if not ok:
                    return
                cite[key] = val.strip()
            if not (cite.get("title") or cite.get("id")):
                self.statusBar().showMessage("Citation needs at least a title or key")
                return
            if not cite.get("id"):
                cite["id"] = (
                    re.sub(r"\W+", "", cite.get("author", "ref").split(",")[0])
                    + str(cite.get("year", ""))
                ) or "ref"
            items = self._qt_load_citations()
            items.append(cite)
            self._qt_store_citations(items)
            self.statusBar().showMessage(f"Added citation [{cite['id']}]")

        def _qt_add_citation_by_doi(self) -> None:
            """Fetch a citation from a DOI via Crossref and add it (background)."""
            doi, ok = QInputDialog.getText(
                self, "Add Citation by DOI", "DOI (e.g. 10.1038/nature12373):"
            )
            if not ok or not doi.strip():
                return
            self.statusBar().showMessage(f"Looking up {doi.strip()} …")

            def _work() -> None:
                try:
                    cite = _fetch_citation_by_doi(doi)
                    self._doi_signal.emit(json.dumps(cite))
                except Exception as exc:  # noqa: BLE001
                    self._doi_signal.emit(f"ERROR: {exc}")

            threading.Thread(target=_work, daemon=True).start()

        def _qt_on_doi(self, payload: str) -> None:
            """Main-thread handler for a Crossref DOI lookup result."""
            if payload.startswith("ERROR: "):
                self.statusBar().showMessage(f"DOI lookup failed: {payload[7:]}")
                return
            try:
                cite = json.loads(payload)
            except ValueError:
                self.statusBar().showMessage("DOI lookup returned bad data")
                return
            items = self._qt_load_citations()
            if any(c.get("id") == cite.get("id") for c in items):
                self.statusBar().showMessage(f"[{cite.get('id')}] already in library")
                return
            items.append(cite)
            self._qt_store_citations(items)
            self.statusBar().showMessage(
                f"Added [{cite.get('id')}] {str(cite.get('title', ''))[:50]}"
            )

        def _qt_insert_citation(self) -> None:
            """Insert a Pandoc-style `[@key]` marker at the cursor (or copy it).

            In edit mode the marker is inserted inline; otherwise it is copied
            to the clipboard so it can be pasted after entering edit mode.
            """
            items = self._qt_load_citations()
            if not items:
                self.statusBar().showMessage("No citations — import or add one first")
                return
            labels = [_citation_label(c) for c in items]
            choice, ok = QInputDialog.getItem(
                self, "Insert Citation", "Insert which reference?", labels, 0, False
            )
            if not ok or choice not in labels:
                return
            marker = f"[@{items[labels.index(choice)].get('id', '')}]"
            if self._qt_edit_mode:
                self.editor.textCursor().insertText(marker)
                self.statusBar().showMessage(f"Inserted {marker}")
            else:
                QApplication.clipboard().setText(marker)
                self.statusBar().showMessage(
                    f"Copied {marker} — enter edit mode (Ctrl+E) to insert inline"
                )

        def _qt_manage_citations(self) -> None:
            """Browse the citation library; copy a key or delete an entry."""
            items = self._qt_load_citations()
            if not items:
                self.statusBar().showMessage(
                    "No citations yet — use Citations → Import or Add"
                )
                return
            labels = [_citation_label(c) for c in items]
            choice, ok = QInputDialog.getItem(
                self, "Citations", "Library (Cancel to close):", labels, 0, False
            )
            if not ok or choice not in labels:
                return
            c = items[labels.index(choice)]
            action, ok2 = QInputDialog.getItem(
                self,
                _citation_label(c),
                "Action:",
                ["Copy key to clipboard", "Link to selected note", "Delete"],
                0,
                False,
            )
            if not ok2:
                return
            if action.startswith("Copy"):
                QApplication.clipboard().setText(str(c.get("id", "")))
                self.statusBar().showMessage(f"Copied [{c.get('id', '')}]")
            elif action.startswith("Link"):
                self._qt_link_citation(c.get("id", ""))
            elif action == "Delete":
                items.remove(c)
                self._qt_store_citations(items)
                self.statusBar().showMessage("Citation deleted")

        def _qt_link_citation(self, cite_id: str) -> None:
            """Attach a citation key to the currently selected note."""
            idx = self._qt_selected_annotation_index()
            items = self._qt_load_annotations()
            if idx < 0 or idx >= len(items):
                self.statusBar().showMessage(
                    "Select a note first, then link a citation"
                )
                return
            items[idx]["cite"] = cite_id
            self._qt_store_annotations(items)
            self._qt_build_annotations()
            self.statusBar().showMessage(f"Linked note to [{cite_id}]")

        # ── Speech recognition (Whisper) ───────────────────

        def _qt_transcribe_file(self) -> None:
            """Transcribe an audio file with Whisper and open it as a document."""
            if not _WHISPER:
                QMessageBox.information(
                    self,
                    "Speech recognition unavailable",
                    "Transcription requires Whisper:\n\n"
                    "    pip install openai-whisper\n"
                    "or  pip install faster-whisper",
                )
                return
            src, _flt = QFileDialog.getOpenFileName(
                self,
                "Transcribe Audio",
                "",
                "Audio (*.wav *.mp3 *.m4a *.ogg *.flac *.aac *.mp4);;All Files (*)",
            )
            if not src:
                return
            model = str(self.settings.get("whisper_model", "base"))
            ts = bool(self.settings.get("transcribe_timestamps", False))
            self.statusBar().showMessage(
                f"Transcribing with Whisper ({model})… this may take a while"
            )

            def _work() -> None:
                try:
                    text = _transcribe_audio(src, model, timestamps=ts)
                    self._transcribe_signal.emit(text, src)
                except Exception as exc:  # noqa: BLE001
                    self._transcribe_signal.emit("", f"ERROR: {exc}")

            threading.Thread(target=_work, daemon=True).start()

        def _qt_on_transcribed(self, text: str, src: str) -> None:
            """Main-thread handler for a completed transcription."""
            if src.startswith("ERROR: "):
                self.statusBar().showMessage(src[7:])
                return
            if not text:
                self.statusBar().showMessage("Transcription produced no text")
                return
            name = Path(src).stem if src else "transcription"
            md = f"# Transcription — {name}\n\n{text}\n"
            self._pending_doc = Document(
                path="",
                title=f"Transcription — {name}",
                markdown=md,
                plain_text=text,
                format="transcription",
            )
            self._on_doc_loaded()
            self.statusBar().showMessage(f"Transcribed {name} ({len(text)} chars)")

        def _qt_dictate_note(self) -> None:
            """Record a short voice memo and add it as a note (Whisper)."""
            if not self.doc:
                self.statusBar().showMessage("Open a document before dictating a note")
                return
            if not _WHISPER or not _AUDIO_IN:
                QMessageBox.information(
                    self,
                    "Dictation unavailable",
                    "Voice dictation requires Whisper and a microphone library:\n\n"
                    "    pip install openai-whisper sounddevice numpy",
                )
                return
            secs, ok = QInputDialog.getInt(
                self, "Dictate Note", "Record for how many seconds?", 8, 2, 300
            )
            if not ok:
                return
            char_pos, anchor = self._qt_current_anchor()
            model = str(self.settings.get("whisper_model", "base"))
            chunk = max(2, int(self.settings.get("whisper_chunk_seconds", 6)))
            self.statusBar().showMessage(f"Recording {secs}s… speak now")

            def _work() -> None:
                # Live streaming: record in short chunks, transcribing each as
                # it arrives so the user sees text accumulate instead of waiting
                # for one long blocking pass.  Chunks are concatenated into the
                # final note.
                try:
                    remaining = secs
                    parts: List[str] = []
                    while remaining > 0:
                        seg = min(chunk, remaining)
                        remaining -= seg
                        wav = _record_audio_to_wav(seg)
                        try:
                            piece = _transcribe_audio(wav, model)
                        finally:
                            Path(wav).unlink(missing_ok=True)
                        if piece:
                            parts.append(piece)
                            self._dictate_partial_signal.emit(" ".join(parts))
                    self._dictate_signal.emit(
                        " ".join(parts), str(int(char_pos)), anchor
                    )
                except Exception as exc:  # noqa: BLE001
                    self._dictate_signal.emit("", "ERROR", str(exc))

            threading.Thread(target=_work, daemon=True).start()

        def _qt_on_dictate_partial(self, text: str) -> None:
            """Live status update as dictation chunks are transcribed."""
            preview = text[-80:]
            self.statusBar().showMessage(f"🎙 …{preview}")

        def _qt_on_dictated(self, text: str, char_pos_s: str, anchor: str) -> None:
            """Main-thread handler for a completed dictation → save as a note."""
            if char_pos_s == "ERROR":
                self.statusBar().showMessage(f"Dictation error: {anchor}")
                return
            if not text:
                self.statusBar().showMessage("Dictation produced no text")
                return
            items = self._qt_load_annotations()
            items.append(
                {
                    "char_pos": int(char_pos_s or 0),
                    "word_idx": self._qt_char_to_word(int(char_pos_s or 0)),
                    "anchor": anchor,
                    "note": text,
                    "tags": ["dictated"],
                    "cite": "",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
            self._qt_store_annotations(items)
            self._qt_build_annotations()
            if not self._annot_dock.isVisible():
                self._annot_dock.setVisible(True)
                self.settings["qt_show_notes"] = True
            self.statusBar().showMessage(f"Dictated note added ({len(text)} chars)")

        # ── Keyboard cheat sheet ────────────────────────

        def _qt_show_shortcuts(self) -> None:
            """Show the canonical keyboard shortcut cheat sheet in a dialog."""
            dlg = QDialog(self)
            dlg.setWindowTitle("Keyboard Shortcuts")
            dlg.resize(640, 600)
            layout = QVBoxLayout(dlg)
            view = QTextBrowser()
            view.setHtml(self._md_to_html(_shortcuts_text(plain=False)))
            layout.addWidget(view)
            try:
                _ok_btn = QDialogButtonBox.StandardButton.Ok  # PyQt6
            except AttributeError:
                _ok_btn = QDialogButtonBox.Ok  # type: ignore[attr-defined]  # PyQt5
            buttons = QDialogButtonBox(_ok_btn)
            buttons.accepted.connect(dlg.accept)
            layout.addWidget(buttons)
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()

        # ── Remappable keybindings ─────────────────

        def _resolve_shortcut(self, default: str) -> str:
            """Return the user's override for *default* shortcut, or *default*."""
            overrides = self.settings.get("keybindings", {}) or {}
            return str(overrides.get(default, default))

        def _qt_customize_shortcuts(self) -> None:
            """Let the user remap any window/toolbar shortcut; persists overrides."""
            actions = getattr(self, "_shortcut_actions", [])
            if not actions:
                self.statusBar().showMessage("No remappable shortcuts")
                return
            labels = [
                f"{label}   —   {act.shortcut().toString() or '(none)'}"
                for label, act, _default in actions
            ]
            labels.append("→ Reset all to defaults")
            choice, ok = QInputDialog.getItem(
                self, "Customize Shortcuts", "Action to rebind:", labels, 0, False
            )
            if not ok:
                return
            if choice == "→ Reset all to defaults":
                self.settings.set("keybindings", {})
                for _label, act, default in actions:
                    act.setShortcut(default)
                self.statusBar().showMessage("Shortcuts reset to defaults")
                return
            idx = labels.index(choice)
            label, act, default = actions[idx]
            new_key, ok2 = QInputDialog.getText(
                self,
                "Rebind Shortcut",
                f"New shortcut for “{label}”\n"
                f"(e.g. Ctrl+Shift+K; blank = restore default {default}):",
                text=act.shortcut().toString(),
            )
            if not ok2:
                return
            overrides = dict(self.settings.get("keybindings", {}) or {})
            new_key = new_key.strip()
            if not new_key or new_key == default:
                overrides.pop(default, None)
                act.setShortcut(default)
            else:
                overrides[default] = new_key
                act.setShortcut(new_key)
            self.settings.set("keybindings", overrides)
            self.statusBar().showMessage(
                f"“{label}” → {act.shortcut().toString() or default}"
            )

        # ── Command palette ───────────────────────

        def _qt_command_registry(self) -> List[Tuple[str, Callable]]:
            """All commands the palette can search and run."""
            return [
                ("Open File…", self._open_dialog),
                ("Open URL…", self._qt_open_url),
                ("Open Feed…", self._qt_open_feed),
                ("Play / Pause", self._tts_toggle),
                ("Stop", self._tts_stop),
                ("Play from Cursor", self._qt_play_from_cursor),
                ("Faster", lambda: self._rate_change(+20)),
                ("Slower", lambda: self._rate_change(-20)),
                ("Choose TTS Engine…", self._qt_pick_backend),
                ("Choose Voice…", self._voice_picker_qt),
                ("Pronunciation Lexicon…", self._qt_pronunciations),
                ("Save Current Settings as Profile…", self._qt_save_profile),
                ("Load Profile…", self._qt_load_profile),
                ("Delete Profile…", self._qt_delete_profile),
                (
                    "Speech Cursor Mode",
                    lambda: (
                        self._qt_sc_exit() if self._qt_sc_mode else self._qt_sc_enter()
                    ),
                ),
                ("Next Sentence", self._qt_skip_next_sentence),
                ("Previous Sentence", self._qt_skip_prev_sentence),
                ("Replay Sentence", self._qt_replay_sentence),
                ("Next Paragraph", self._qt_skip_next_paragraph),
                ("Previous Paragraph", self._qt_skip_prev_paragraph),
                ("Replay Paragraph", self._qt_replay_paragraph),
                ("Next Heading", self._qt_read_next_heading),
                ("Previous Heading", self._qt_read_prev_heading),
                ("Next Table", self._qt_skip_next_table),
                ("Previous Table", self._qt_skip_prev_table),
                ("Add Note", self._qt_add_annotation),
                ("Toggle Notes Panel", self._qt_toggle_annotations),
                ("Export Notes…", self._qt_export_annotations),
                ("Import Citations…", self._qt_import_citations),
                ("Export Citations…", self._qt_export_citations),
                ("Add Citation…", self._qt_add_citation),
                ("Add Citation by DOI…", self._qt_add_citation_by_doi),
                ("Insert Citation at Cursor…", self._qt_insert_citation),
                ("Browse Citations…", self._qt_manage_citations),
                ("Toggle Contents Panel", self._qt_toggle_toc),
                ("Library / Bookshelf…", self._qt_library),
                ("Reading Statistics…", self._qt_reading_stats),
                ("Summarize Document…", self._qt_summarize),
                ("Translate Document…", self._qt_translate),
                ("Transcribe Audio File…", self._qt_transcribe_file),
                ("Dictate Note…", self._qt_dictate_note),
                ("Copy", self._qt_copy),
                ("Check Spelling", self._qt_check_spelling),
                ("Toggle Edit Mode", self._qt_edit_mode_toggle),
                ("Toggle Live HTML Preview", self._qt_toggle_preview),
                ("Save", self._qt_save),
                ("Export as Markdown…", self._qt_export_markdown),
                ("Export as PDF…", self._qt_export_pdf),
                ("Export as Braille (BRF)…", self._qt_export_brf),
                ("Export as Audio…", self._qt_export_audio),
                ("Export Subtitles (SRT / VTT)…", self._qt_export_subtitles),
                ("Export as Anki Flashcards…", self._qt_export_anki),
                ("Tune Karaoke Highlight…", self._qt_karaoke_dialog),
                ("Highlight Difficult Words", self._qt_toggle_vocab_highlight),
                ("Reading Level", self._qt_reading_level),
                ("Change Font…", self._qt_change_font_dialog),
                ("Next Theme", self._next_theme),
                ("Choose Theme…", self._qt_pick_theme),
                ("Customize Shortcuts…", self._qt_customize_shortcuts),
                ("Keyboard Shortcuts", self._qt_show_shortcuts),
                ("Open README (Help)", self._show_about),
            ]

        def _qt_command_palette(self) -> None:
            """A searchable command palette (F2) — type to filter, Enter to run."""
            cmds = self._qt_command_registry()
            by_label = {label: fn for label, fn in cmds}
            dlg = QDialog(self)
            dlg.setWindowTitle("Command Palette")
            dlg.resize(520, 440)
            lay = QVBoxLayout(dlg)
            box = QLineEdit()
            box.setPlaceholderText(
                "Type to search commands…  (Enter runs, Esc cancels)"
            )
            lst = QListWidget()
            lay.addWidget(box)
            lay.addWidget(lst)

            def _populate(query: str = "") -> None:
                lst.clear()
                terms = query.lower().split()
                for label, _fn in cmds:
                    if all(t in label.lower() for t in terms):
                        lst.addItem(QListWidgetItem(label))
                if lst.count():
                    lst.setCurrentRow(0)

            def _run() -> None:
                it = lst.currentItem() or (lst.item(0) if lst.count() else None)
                if it is None:
                    return
                fn = by_label.get(it.text())
                dlg.accept()
                if fn:
                    fn()

            _populate()
            box.textChanged.connect(_populate)
            box.returnPressed.connect(_run)
            lst.itemActivated.connect(lambda _it: _run())
            # Down-arrow from the search box moves into the results list.
            box.setFocus()
            dlg.exec() if _QT == "PyQt6" else dlg.exec_()

        def _qt_toggle_dyslexia_font(self) -> None:
            """Toggle the dyslexia-friendly display font preference."""
            new = not bool(self.settings.get("qt_dyslexia_font", False))
            self.settings["qt_dyslexia_font"] = new
            if hasattr(self, "_dyslexia_font_act"):
                self._dyslexia_font_act.setChecked(new)
            self.editor.setFont(self._make_editor_font())
            self._apply_qt_theme(str(self.settings.get("theme", "dark")))
            if new:
                fam = self._find_dyslexia_font()
                if fam:
                    self.statusBar().showMessage(f"Dyslexia-friendly font: {fam}")
                else:
                    self.statusBar().showMessage(
                        "No dyslexia-friendly font found — install OpenDyslexic, "
                        "Atkinson Hyperlegible, or Lexend"
                    )
            else:
                self.statusBar().showMessage("Dyslexia-friendly font: OFF")

        def _qt_toggle_bionic(self) -> None:
            """Toggle bionic-reading emphasis and re-render the document."""
            new = not bool(self.settings.get("qt_bionic_reading", False))
            self.settings["qt_bionic_reading"] = new
            if hasattr(self, "_bionic_act"):
                self._bionic_act.setChecked(new)
            self._apply_qt_theme(str(self.settings.get("theme", "dark")))
            self.statusBar().showMessage("Bionic reading: " + ("ON" if new else "OFF"))

        def _qt_toggle_current_line(self) -> None:
            """Toggle the current-line focus band shown while reading."""
            new = not bool(self.settings.get("qt_current_line_highlight", False))
            self.settings["qt_current_line_highlight"] = new
            if hasattr(self, "_current_line_act"):
                self._current_line_act.setChecked(new)
            self.statusBar().showMessage(
                "Current-line highlight: " + ("ON" if new else "OFF")
            )

        def _qt_text_spacing_dialog(self) -> None:
            """Adjust line height, letter spacing, and word spacing.

            Changes preview live; OK keeps them, Cancel reverts.  Spacing is
            a recognized accommodation that reduces crowding for dyslexic and
            low-vision readers (WCAG 1.4.12 Text Spacing).
            """
            keys = ("qt_line_height", "qt_letter_spacing", "qt_word_spacing")
            orig = {k: self.settings.get(k) for k in keys}

            dlg = QDialog(self)
            dlg.setWindowTitle("Text Spacing")
            form = QFormLayout(dlg)
            info = QLabel(
                "Generous spacing reduces crowding (WCAG 1.4.12).\n"
                "Changes preview live — OK to keep, Cancel to revert."
            )
            info.setWordWrap(True)
            form.addRow(info)

            lh = QDoubleSpinBox()
            lh.setRange(1.0, 3.0)
            lh.setSingleStep(0.1)
            lh.setDecimals(2)
            lh.setValue(float(orig["qt_line_height"] or 1.5))
            form.addRow("Line height (×):", lh)

            le = QDoubleSpinBox()
            le.setRange(0.0, 40.0)
            le.setSingleStep(1.0)
            le.setDecimals(1)
            le.setSuffix(" %")
            le.setValue(float(orig["qt_letter_spacing"] or 0.0))
            form.addRow("Extra letter spacing:", le)

            wd = QDoubleSpinBox()
            wd.setRange(0.0, 40.0)
            wd.setSingleStep(1.0)
            wd.setDecimals(1)
            wd.setSuffix(" px")
            wd.setValue(float(orig["qt_word_spacing"] or 0.0))
            form.addRow("Extra word spacing:", wd)

            def _preview() -> None:
                # Mutate in-memory only (no disk write) so Cancel can revert.
                self.settings._data["qt_line_height"] = lh.value()
                self.settings._data["qt_letter_spacing"] = le.value()
                self.settings._data["qt_word_spacing"] = wd.value()
                self._apply_text_spacing()

            lh.valueChanged.connect(lambda _v: _preview())
            le.valueChanged.connect(lambda _v: _preview())
            wd.valueChanged.connect(lambda _v: _preview())

            try:
                _ok = QDialogButtonBox.StandardButton.Ok  # PyQt6
                _cancel = QDialogButtonBox.StandardButton.Cancel
            except AttributeError:
                _ok = QDialogButtonBox.Ok  # type: ignore[attr-defined]
                _cancel = QDialogButtonBox.Cancel  # type: ignore[attr-defined]
            buttons = QDialogButtonBox(_ok | _cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            form.addRow(buttons)

            result = dlg.exec() if _QT == "PyQt6" else dlg.exec_()
            if result:
                _preview()
                self.settings.save()
                self.statusBar().showMessage(
                    f"Spacing — line {lh.value():.2f}×, letter +{le.value():.0f}%, "
                    f"word +{wd.value():.0f}px"
                )
            else:
                for k, v in orig.items():
                    self.settings._data[k] = v
                self._apply_text_spacing()

        def _qt_karaoke_dialog(self) -> None:
            """Tune the per-word karaoke highlight: style, color, speed, lead.

            Different readers track best with different cues — a sharp filled
            highlight, a colored underline, or bold text — and at different
            lead/lag offsets relative to the audio.
            """
            keys = (
                "highlight_style",
                "highlight_color",
                "highlight_speed",
                "highlight_lead_words",
                "highlight_granularity",
            )
            orig = {k: self.settings.get(k) for k in keys}

            dlg = QDialog(self)
            dlg.setWindowTitle("Karaoke Highlight")
            form = QFormLayout(dlg)
            info = QLabel(
                "Tune how the spoken word is marked as it is read.\n"
                "Changes preview live — OK to keep, Cancel to revert."
            )
            info.setWordWrap(True)
            form.addRow(info)

            _GRANS = ["word", "sentence", "both"]
            gran_box = QComboBox()
            gran_box.addItems(_GRANS)
            cur_gran = str(orig["highlight_granularity"] or "word")
            gran_box.setCurrentIndex(
                _GRANS.index(cur_gran) if cur_gran in _GRANS else 0
            )
            gran_box.setToolTip(
                "Highlight the spoken word, the whole sentence (less flicker),\n"
                "or both (sentence band + word)."
            )
            form.addRow("Granularity:", gran_box)

            _STYLES = ["background", "underline", "box", "bold", "color"]
            style_box = QComboBox()
            style_box.addItems(_STYLES)
            cur_style = str(orig["highlight_style"] or "background")
            style_box.setCurrentIndex(
                _STYLES.index(cur_style) if cur_style in _STYLES else 0
            )
            form.addRow("Style:", style_box)

            _COLORS = [
                "cyan",
                "yellow",
                "green",
                "magenta",
                "orange",
                "red",
                "blue",
                "white",
            ]
            color_box = QComboBox()
            color_box.setEditable(True)
            color_box.addItems(_COLORS)
            color_box.setEditText(str(orig["highlight_color"] or "cyan"))
            form.addRow("Color:", color_box)

            speed = QDoubleSpinBox()
            speed.setRange(0.5, 1.5)
            speed.setSingleStep(0.05)
            speed.setDecimals(2)
            speed.setValue(float(orig["highlight_speed"] or 1.0))
            speed.setToolTip(
                "Highlight pacing relative to speech (1.0 = match WPM).\n"
                "Applies on the next play."
            )
            form.addRow("Speed (× WPM):", speed)

            lead = QSpinBox()
            lead.setRange(-5, 5)
            lead.setValue(int(orig["highlight_lead_words"] or 0))
            lead.setToolTip("Words the highlight leads (+) or lags (−) the audio")
            form.addRow("Lead / lag (words):", lead)

            def _preview() -> None:
                self.settings._data["highlight_style"] = style_box.currentText()
                self.settings._data["highlight_color"] = color_box.currentText().strip()
                self.settings._data["highlight_speed"] = speed.value()
                self.settings._data["highlight_lead_words"] = lead.value()
                self.settings._data["highlight_granularity"] = gran_box.currentText()
                self._rebuild_hl_fmt()

            gran_box.currentTextChanged.connect(lambda _v: _preview())
            style_box.currentTextChanged.connect(lambda _v: _preview())
            color_box.editTextChanged.connect(lambda _v: _preview())
            speed.valueChanged.connect(lambda _v: _preview())
            lead.valueChanged.connect(lambda _v: _preview())

            try:
                _ok = QDialogButtonBox.StandardButton.Ok  # PyQt6
                _cancel = QDialogButtonBox.StandardButton.Cancel
            except AttributeError:
                _ok = QDialogButtonBox.Ok  # type: ignore[attr-defined]
                _cancel = QDialogButtonBox.Cancel  # type: ignore[attr-defined]
            buttons = QDialogButtonBox(_ok | _cancel)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            form.addRow(buttons)

            result = dlg.exec() if _QT == "PyQt6" else dlg.exec_()
            if result:
                _preview()
                self.settings.save()
                self.statusBar().showMessage(
                    f"Highlight — {gran_box.currentText()}, "
                    f"{style_box.currentText()}, "
                    f"{color_box.currentText().strip()}, "
                    f"{speed.value():.2f}×, lead {lead.value():+d}"
                )
            else:
                for k, v in orig.items():
                    self.settings._data[k] = v
                self._rebuild_hl_fmt()

        def _qt_change_font_dialog(self) -> None:
            """Open the system font picker to choose family, style, and size.

            Uses Qt's built-in QFontDialog so the user gets the full OS
            font browser with live preview.  Both the chosen family and the
            chosen point size are applied immediately and persisted.
            """
            fam = str(self.settings.get("qt_font_family", "Georgia"))
            fsz = int(self.settings.get("qt_font_size", 14))
            current_font = QFont(fam, fsz)
            font, ok = QFontDialog.getFont(current_font, self, "Choose Display Font")
            if ok:
                self._set_font(family=font.family(), size=max(6, font.pointSize()))

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

    # ────────────────────────────────────────────────────────────────────────
    class _HelpWindow(QDialog):
        """Help window that mirrors the main window\'s TTS controls.

        Opened by StarWindow._show_about().  Uses the parent StarWindow\'s
        TTSManager so rate / volume changes propagate immediately.  On open
        it saves and takes over the manager\'s word-map and highlight
        callback; on close it restores them so the main window can resume
        normal highlighting.
        """

        # Thread-safe word-highlight delivery (same pattern as StarWindow).
        _word_signal = pyqtSignal(int)

        def __init__(self, parent: StarWindow) -> None:  # type: ignore[name-defined]
            super().__init__(parent)
            self._sw = parent
            self._doc_plain: str = ""
            self._word_map: List = []
            self._qt_word_map: List[int] = []
            # Saved parent TTS state — restored when this window closes.
            self._saved_word_map: List = []
            self._saved_hl_cb = None

            self._hl_fmt = QTextCharFormat()
            self._hl_fmt.setBackground(QColor("#06b6d4"))
            self._hl_fmt.setForeground(QColor("#000000"))
            self._hl_fmt.setFontWeight(700)

            self._setup_ui()
            self._word_signal.connect(self._apply_highlight, _QUEUED)
            # Kick off async word-map build so TTS can highlight words.
            self._load_async()

        # ── UI ────────────────────────────────────────────────────────────

        def _setup_ui(self) -> None:
            self.setWindowTitle(f"Help — {APP_TITLE}")
            self.resize(780, 600)

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # ─ Toolbar ─ identical actions to the main window ──────────────
            tb = QToolBar("TTS Controls")
            tb.setMovable(False)

            def _act(label: str, shortcut: str, fn: Any) -> None:
                a = QAction(label, self)
                if shortcut:
                    a.setShortcut(shortcut)
                a.triggered.connect(fn)
                tb.addAction(a)

            _act("Play/Pause ▶⏸", "Space", self._tts_toggle)
            _act("Stop ■", "Escape", self._tts_stop)
            _act("+ Speed", "Ctrl+=", lambda: self._rate_change(+20))
            _act("− Speed", "Ctrl+-", lambda: self._rate_change(-20))
            tb.addSeparator()
            _act("Close", "Ctrl+W", self.close)
            root.addWidget(tb)

            # ─ Editor ────────────────────────────────────────────
            pal = self._sw._PALETTES.get(
                self._sw.settings.get("theme", "dark"),
                self._sw._PALETTES["dark"],
            )
            font_size = int(self._sw.settings.get("font_size", 0)) or 14
            self.editor = QTextEdit()
            self.editor.setReadOnly(True)
            self.editor.setFont(
                QFont(self._sw.settings.get("qt_font_family", "Georgia"), font_size)
            )
            self.editor.setCursorWidth(0)
            self.editor.setStyleSheet(
                "QTextEdit {"
                f" background-color:{pal['bg']}; color:{pal['fg']};"
                f" font-size:{font_size}pt;"
                f" selection-background-color:{pal['sel']};"
                "}"
            )
            root.addWidget(self.editor)

            # ─ Status label ──────────────────────────────────────────
            self._status = QLabel(" ")
            self._status.setContentsMargins(4, 0, 0, 2)
            root.addWidget(self._status)

            # Show HTML immediately; TTS word map loads asynchronously.
            self.editor.setHtml(self._sw._md_to_html(_HELP_TEXT))

        # ── Content / word map ──────────────────────────────────────────

        def _load_async(self) -> None:
            """Build the TTS plain text and word map in a background thread
            so the window appears instantly."""
            qt_text = self.editor.document().toPlainText()

            def _work() -> None:
                plain = _strip_markdown_for_tts(_HELP_TEXT, self._sw.settings)
                flat = qt_text.splitlines()
                wm = _build_word_map(plain, flat)

                # Build Qt character-offset map (same algorithm as StarWindow).
                qt_lower = qt_text.lower()
                tok = re.compile(r"\b\w[\w'-]*")
                result: List[int] = []
                sfrom = 0
                for m in tok.finditer(plain):
                    w = m.group().lower()
                    p = qt_lower.find(w, sfrom)
                    if p >= 0:
                        result.append(p)
                        sfrom = p + 1
                    else:
                        p = qt_lower.find(w, 0)
                        result.append(p if p >= 0 else 0)

                self._doc_plain = plain
                self._word_map = wm
                self._qt_word_map = result

            threading.Thread(target=_work, daemon=True).start()

        # ── TTS ───────────────────────────────────────────────────────────

        def _tts_play(self) -> None:
            if not self._doc_plain:
                self._status.setText("Help text still loading … try again in a moment")
                return
            tm = self._sw.tts_manager
            wm = self._word_map
            text_offset = wm[0].tts_offset if wm else 0
            # Take over the manager\'s word map and highlight callback.
            self._saved_word_map = tm._word_map
            self._saved_hl_cb = tm._on_highlight
            tm.set_word_map(wm)
            tm.set_on_highlight(lambda idx: self._word_signal.emit(idx))
            tm.speak(
                self._doc_plain[text_offset:],
                start_word_idx=0,
                text_offset=text_offset,
            )
            self._status.setText(
                f"Reading at {self._sw.settings['tts_rate']} wpm"
                f"  —  via {tm.backend_name}"
            )

        def _tts_stop(self) -> None:
            self._sw.tts_manager.stop()
            self.editor.setExtraSelections([])
            self._status.setText("Stopped.")

        def _tts_toggle(self) -> None:
            if self._sw.tts_manager.speaking:
                self._tts_stop()
            else:
                self._tts_play()

        def _rate_change(self, delta: int) -> None:
            new_rate = max(50, min(600, int(self._sw.settings["tts_rate"]) + delta))
            self._sw.tts_manager.set_rate(new_rate)
            if self._sw._qt_sc_reader is not None:
                self._sw._qt_sc_reader.update_rate(new_rate)
            self._status.setText(f"Rate: {new_rate} wpm")

        # ── Word highlight ─────────────────────────────────────────────────

        def _apply_highlight(self, word_idx: int) -> None:
            self.editor.setExtraSelections([])
            if word_idx < 0 or not self._qt_word_map:
                return
            if word_idx >= len(self._qt_word_map):
                return
            char_pos = self._qt_word_map[word_idx]
            word_len = 1
            if word_idx < len(self._word_map):
                word_len = max(1, self._word_map[word_idx].tts_len)
            doc_obj = self.editor.document()
            doc_len = doc_obj.characterCount()
            if char_pos >= doc_len:
                return
            word_len = min(word_len, doc_len - char_pos - 1)
            if word_len <= 0:
                return
            cursor = QTextCursor(doc_obj)
            cursor.setPosition(char_pos)
            cursor.setPosition(char_pos + word_len, _KEEP_ANCHOR)
            sel = QTextEdit.ExtraSelection()
            sel.format = self._hl_fmt
            sel.cursor = cursor
            self.editor.setExtraSelections([sel])
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            if word_idx < len(self._word_map):
                word_text = self._word_map[word_idx].word
                pct = int(100 * word_idx / max(1, len(self._word_map)))
                self._status.setText(
                    f"▶  “{word_text}”  —  {pct}%"
                    f"  —  {self._sw.settings['tts_rate']} wpm"
                )

        # ── Close ──────────────────────────────────────────────────────────────

        def closeEvent(self, event: Any) -> None:
            """Stop speech and restore the main window\'s TTS context."""
            tm = self._sw.tts_manager
            tm.stop()
            self.editor.setExtraSelections([])
            # Restore the main window\'s word map.
            restore_wm = self._saved_word_map
            if not restore_wm and self._sw.doc:
                restore_wm = getattr(self._sw.doc, "word_map", []) or []
            tm.set_word_map(restore_wm)
            # Restore highlight callback — rewire to the main window\'s signal.
            if self._saved_hl_cb is not None:
                tm.set_on_highlight(self._saved_hl_cb)
            else:
                tm.set_on_highlight(lambda idx: self._sw._word_signal.emit(idx))
            event.accept()

    # ──────────────────────────────────────────────────────────────────────
    window = StarWindow()
    window.show()
    sys.exit(app.exec() if _QT == "PyQt6" else app.exec_())
