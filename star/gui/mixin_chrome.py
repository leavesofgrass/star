"""ChromeMixin — toolbar and menu-bar construction for StarWindow.

Extracted verbatim from main_window.py to keep that module focused on window
lifecycle/state. These two builders are large, self-contained, and rebuilt on
UI-language change; they hold no state of their own and operate on the
StarWindow instance via ``self`` (mixed in before QMainWindow in the MRO).

IMPORT SAFETY: references Qt at module scope — imported lazily by main_window.py
(itself imported after the _QT guard), like the other mixin_*.py modules.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import available_languages, get_language, set_language, tr  # noqa: F401
from .icons import make_icon


class ChromeMixin:
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
        # Registry of toolbar QActions keyed by a stable English name, so the
        # guided tour (star/gui/mixin_tour.py) can anchor a popover to the exact
        # button a step describes.  Rebuilt whenever the toolbar is.
        self._toolbar_actions: Dict[str, "QAction"] = {}
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
            # Key on the untranslated label so the tour can find a control by a
            # stable name regardless of the active UI language.
            self._toolbar_actions[label] = a

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
        _act("Font", "font", self._qt_change_font_dialog, "Change display font (Ctrl+Alt+F)")
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
                "",  # menu-only: Ctrl+Alt+V is Tools ▸ Dictate Note
                self._qt_export_video,
                tip="Export as a karaoke MP4 — themed document with highlighted sentence and spoken audio",
            )
        )
        export_menu.addAction(
            _mi(
                "Export Audiobook (M4B)…",
                "",  # menu-only (avoids an ambiguous accelerator)
                self._qt_export_audiobook,
                tip="Export as a chaptered M4B audiobook (chapters from headings; needs ffmpeg)",
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
                tip = row[3] if len(row) > 3 else ""
                menu.addAction(_mi(label, shortcut, fn, tip=tip))
            return menu

        # Speech menu — every playback command reachable without the keyboard.
        _menu(
            "Speech",
            [
                ("Play / Pause", self._tts_toggle, "Space"),
                ("Stop", self._tts_stop, "Escape"),
                ("Play from Cursor", self._qt_play_from_cursor, "Ctrl+Space",
                 "Start reading aloud from the caret position"),
                None,
                ("Faster (+20 wpm)", lambda: self._rate_change(+20), "Ctrl+="),
                ("Slower (−20 wpm)", lambda: self._rate_change(-20), "Ctrl+-"),
                None,
                ("Choose TTS Engine…", self._qt_pick_backend, "Ctrl+Shift+G",
                 "Switch between the installed speech engines"),
                ("Choose Voice…", self._voice_picker_qt, "Ctrl+Shift+V"),
                ("Voice Manager…", self._qt_voice_manager, "F4",
                 "Preview, star, and install voices for the active engine"),
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
                None,
                ("Back", self._qt_history_back, "Alt+Left"),
                ("Forward", self._qt_history_forward, "Alt+Right"),
            ],
        )

        # Bookmarks menu — named positions per document + a jump list.
        # Add Bookmark owns Ctrl+B; the named-add and the list dialog carry no
        # shortcut of their own (they are reachable via the menu and the command
        # palette) so every binding stays owned by exactly one QAction.
        _menu(
            "Bookmarks",
            [
                ("Add Bookmark", self._qt_bookmark_add, "Ctrl+B"),
                ("Add Named Bookmark…", self._qt_bookmark_add_named, ""),
                ("Bookmarks…", self._qt_bookmarks_dialog, ""),
            ],
        )

        # Edit menu.  (Moved next to File in the menu bar below.)
        edit_menu = _menu(
            "Edit",
            [
                ("Find…", self._find_show, "Ctrl+F",
                 "Find in the document — Enter jumps, Ctrl+Enter reads aloud"),
                ("Copy", self._qt_copy, "Ctrl+C"),
                None,
                ("Toggle Edit Mode", self._qt_edit_mode_toggle, "Ctrl+E"),
                ("Save", self._qt_save, "Ctrl+S"),
                # Menu-only: F7 is View ▸ Caret Browsing (an ambiguous shortcut
                # would fire neither).
                ("Check Spelling", self._qt_check_spelling, "",
                 "Spell-check the document and step through suggestions"),
            ],
        )
        # Preferences lives at the foot of Edit (the conventional home for an
        # app's settings), added via _mi so it keeps a tooltip.
        edit_menu.addSeparator()
        edit_menu.addAction(
            _mi(
                "Preferences…",
                "Ctrl+,",
                self._qt_preferences,
                tip="All reader settings in one place (Reading, Voice, Display, General)",
            )
        )

        # Citations menu.
        _menu(
            "Citations",
            [
                ("Import…", self._qt_import_citations, "Ctrl+Alt+I"),
                # Menu-only: Ctrl+Alt+E is View ▸ Reading Aids ▸ RSVP Mode.
                ("Export…", self._qt_export_citations),
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
            _mi(
                "Change Font…",
                "Ctrl+Alt+F",
                self._qt_change_font_dialog,
                tip="Pick any installed font family and size for the reading view",
            )
        )
        # Reading Level is shared with the Tools menu (one Ctrl+L owner).
        level_act = _mi("Reading Level", "Ctrl+L", self._qt_reading_level)
        view_menu.addAction(level_act)
        # Live HTML preview while editing (checkable).  Ctrl+Shift+Z — Ctrl+Shift+L
        # is owned by File ▸ Open Folder as Library (avoids an ambiguous shortcut
        # where Qt would fire neither).
        self._preview_act = _mi(
            "Live HTML Preview (edit mode)",
            "Ctrl+Shift+Z",
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
        aids_menu.addSeparator()
        # ── Reading Font chooser (Default / OpenDyslexic / Atkinson / Lexend) ─
        # Each choice fetches its OFL font from GitHub on demand (no pip) and
        # applies it app-wide + in-document.  A radio-style submenu; the classic
        # Ctrl+Alt+X toggle (below) flips OpenDyslexic on/off for muscle memory.
        font_menu: QMenu = aids_menu.addMenu(tr("Reading Font"))
        try:
            from PyQt6.QtGui import QActionGroup
        except ImportError:
            from PyQt5.QtWidgets import QActionGroup  # type: ignore[no-redef]
        self._reading_font_group = QActionGroup(self)
        self._reading_font_acts: Dict[str, QAction] = {}
        _cur_font = str(self.settings.get("qt_reading_font", "default"))
        if _cur_font == "default" and self.settings.get("qt_dyslexia_font", False):
            _cur_font = "opendyslexic"
        for _label, _key in self._READING_FONT_CHOICES:
            _act = QAction(tr(_label), self)
            _act.setCheckable(True)
            _act.setChecked(_key == _cur_font)
            _act.triggered.connect(lambda _c=False, k=_key: self._qt_set_reading_font(k))
            self._reading_font_group.addAction(_act)
            font_menu.addAction(_act)
            self._reading_font_acts[_key] = _act
        # Hidden accelerator preserving the classic dyslexia-font toggle. Keyed on
        # the same English label so keybinding overrides stay stable.
        self._dyslexia_font_act = _mi(
            "Dyslexia-Friendly Font",
            "Ctrl+Alt+X",
            self._qt_toggle_dyslexia_font,
            tip="Toggle OpenDyslexic on/off (see Reading Font for more choices)",
            checkable=True,
            checked=_cur_font != "default",
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
        self._syllable_act = _mi(
            "Syllable Splitting",
            "",
            self._qt_toggle_syllables,
            tip="Split words into syllables (read·a·bil·i·ty) — a decoding aid "
            "(display-only; speech is unaffected)",
            checkable=True,
            checked=bool(self.settings.get("qt_syllable_split", False)),
        )
        aids_menu.addAction(self._syllable_act)
        self._current_line_act = _mi(
            "Current-Line Highlight",
            "Ctrl+Alt+L",
            self._qt_toggle_current_line,
            tip="Tint the line being read with a focus band",
            checkable=True,
            checked=bool(self.settings.get("qt_current_line_highlight", False)),
        )
        aids_menu.addAction(self._current_line_act)
        self._ruler_act = _mi(
            "Reading Ruler",
            "",
            self._qt_toggle_reading_ruler,
            tip="Show a movable translucent band (typoscope) that tracks the "
            "caret line",
            checkable=True,
            checked=bool(self.settings.get("qt_reading_ruler", False)),
        )
        aids_menu.addAction(self._ruler_act)
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

        # Study menu — spaced-repetition review of notes/highlights.
        # "Review Due Cards…" owns Ctrl+Shift+F5 (Ctrl+Shift+S/R are already
        # taken by Reading Statistics / Reload CSS Themes); the Anki sync item
        # is menu/palette-reachable with no shortcut of its own.
        study_menu: QMenu = mb.addMenu(tr("&Study"))
        study_menu.addAction(
            _mi(
                "Review Due Cards…",
                "Ctrl+Shift+F5",
                self._qt_review_due,
                tip="Study notes and highlights that are due for spaced-repetition review",
            )
        )
        study_menu.addAction(
            _mi(
                "Sync with Anki (AnkiConnect)…",
                "",
                self._qt_anki_sync,
                tip="Push cards to a running Anki and pull back review progress "
                    "(requires the AnkiConnect add-on)",
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
                ("Guided Tour", self._start_tour, "Shift+F1"),
                ("Open README (Help)", self._show_about, "F1"),
                ("Open Documentation", self._open_documentation, ""),
                None,
                ("Check for Updates…", self._qt_check_for_updates, ""),
                None,
                ("About star", self._qt_about, "Ctrl+F1"),
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

        # QMenu hides action tooltips unless told otherwise — without this,
        # every tip= written above is invisible in the menu bar.  Applies to
        # submenus too (findChildren is recursive).
        for m in mb.findChildren(QMenu):
            m.setToolTipsVisible(True)

