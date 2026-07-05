"""CommandsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(CommandsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from .a11y import announce

# NOTE: star.tui.text is imported lazily inside _qt_show_shortcuts, NOT here:
# a module-scope import pulls the whole TUI/curses stack into the GUI's import
# chain, and on a machine without windows-curses (pipx, --no-deps, conda) that
# crashed the Qt GUI before a window ever appeared — the 0.1.15 failure class,
# invisible to CI because CI always has curses.


class CommandsMixin:
    # ── Optional features ───────────────────────────

    def _qt_install_optional_features(self) -> None:
        """Open the optional-feature chooser (Thin / All / custom).

        The same dialog shown once on first launch — re-openable any time to add
        capabilities (OCR, dictionary, knowledge graph, speech-to-text, …)."""
        from .deps_dialog import DependencyChooser

        DependencyChooser(self).exec()

    # ── Keyboard cheat sheet ────────────────────────

    def _qt_show_shortcuts(self) -> None:
        """Show the canonical keyboard shortcut cheat sheet in a dialog."""
        from ..tui.text import _shortcuts_text  # lazy — see module docstring note

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
            # The Reading Ruler / RSVP Position tuning dialogs left the menu bar
            # when Preferences… centralized their settings; the palette keeps
            # their richer live-preview UX reachable (ruler follows the sliders,
            # RSVP offers a spatial 3×3 grid).
            ("Tune Reading Ruler…", self._qt_reading_ruler_dialog),
            ("Tune RSVP Position…", self._qt_rsvp_position_dialog),
            ("Highlight Difficult Words", self._qt_toggle_vocab_highlight),
            ("Define Word", self._qt_define_word),
            ("Reading Level", self._qt_reading_level),
            ("Change Font…", self._qt_change_font_dialog),
            ("Next Theme", self._next_theme),
            ("Choose Theme…", self._qt_pick_theme),
            ("Customize Shortcuts…", self._qt_customize_shortcuts),
            ("Keyboard Shortcuts", self._qt_show_shortcuts),
            ("Open README (Help)", self._show_about),
            ("Show Graph View", self._graph_toggle),
            ("Rebuild Knowledge Graph", self._graph_rebuild),
            ("Add Relation…", self._graph_add_relation),
            ("Edit Relations…", self._graph_edit_relations),
            ("Extract Concepts…", self._graph_extract_concepts),
            ("Auto-Suggest Relations…", self._graph_auto_suggest),
            ("Export Graph as SVG…", self._graph_export_svg),
            ("Export Graph as PlantUML…", self._graph_export_plantuml),
            ("Export Graph as DOT…", self._graph_export_dot),
            ("Export Graph as JSON…", self._graph_export_json),
            ("Open SVG File…", self._graph_open_svg),
            ("Open DOT File…", self._graph_open_dot),
            ("Open PlantUML File…", self._graph_open_plantuml),
            ("Import Obsidian Vault…", self._obsidian_import),
            ("Export Obsidian Vault…", self._obsidian_export),
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
        box.setAccessibleName(tr("Search commands"))
        lst = QListWidget()
        lst.setAccessibleName(tr("Matching commands"))
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
        """Toggle the dyslexia-friendly display font (OpenDyslexic) across the UI.

        Retained for the classic Ctrl+Alt+X accelerator and any code/profiles
        that referenced it; routed through the unified reading-font chooser so the
        submenu, the legacy boolean, and the applied font stay in sync.  On first
        enable OpenDyslexic is fetched on demand (best-effort, offline-safe)."""
        self._qt_toggle_dyslexia_font_shortcut()

    # Reading-font chooser labels (menu order) → the qt_reading_font key.
    _READING_FONT_CHOICES = (
        ("Default", "default"),
        ("OpenDyslexic", "opendyslexic"),
        ("Atkinson Hyperlegible", "atkinson"),
        ("Lexend", "lexend"),
    )

    def _qt_set_reading_font(self, key: str) -> None:
        """Select a reading font (Default / OpenDyslexic / Atkinson / Lexend).

        Applies app-wide + in-document exactly like the dyslexia toggle: the
        chosen family is fetched from GitHub on demand if needed (no pip), then
        applied to the QApplication and the reading pane.  "default" restores the
        user's chosen font.  Persisted via ``qt_reading_font``.
        """
        valid = {k for _lbl, k in self._READING_FONT_CHOICES}
        if key not in valid:
            key = "default"
        self.settings["qt_reading_font"] = key
        # Keep the legacy boolean coherent so old profiles / the classic toggle
        # and the new chooser never disagree.
        self.settings["qt_dyslexia_font"] = key != "default"
        self._sync_reading_font_menu()
        if hasattr(self, "_dyslexia_font_act"):
            self._dyslexia_font_act.setChecked(key != "default")
        # Each outcome is announced as well as shown: the status bar is not
        # spoken by Qt's a11y bridge, and reading fonts are first and foremost
        # an accessibility feature — the failure case matters most.
        if key == "default":
            self._apply_dyslexia_font(False)
            msg = tr("Reading font: Default")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return
        label = next((lbl for lbl, k in self._READING_FONT_CHOICES if k == key), key)
        self.statusBar().showMessage(
            tr("Enabling reading font ({name}) — fetching if needed…").format(name=label)
        )
        QApplication.processEvents()
        fam = self._apply_dyslexia_font(True, fetch=True)
        if fam:
            msg = tr("Reading font: {name} — applied across the UI").format(name=fam)
        else:
            msg = tr("{name} unavailable (offline?) — install it or try again").format(
                name=label
            )
        self.statusBar().showMessage(msg)
        announce(self.editor, msg)

    def _sync_reading_font_menu(self) -> None:
        """Tick the reading-font submenu radio item matching the current key."""
        acts = getattr(self, "_reading_font_acts", {})
        cur = str(self.settings.get("qt_reading_font", "default"))
        if cur == "default" and self.settings.get("qt_dyslexia_font", False):
            cur = "opendyslexic"
        for k, act in acts.items():
            act.setChecked(k == cur)

    def _qt_toggle_dyslexia_font_shortcut(self) -> None:
        """Classic Ctrl+Alt+X toggle: flip OpenDyslexic on/off via the chooser.

        Preserves the original accelerator's behavior — a single keypress turns a
        dyslexia-friendly font on (OpenDyslexic) or back to Default — now routed
        through the unified reading-font machinery."""
        on = self._reading_font_key() != "default"
        self._qt_set_reading_font("default" if on else "opendyslexic")

    def _qt_toggle_bionic(self) -> None:
        """Toggle bionic-reading emphasis and re-render the document."""
        new = not bool(self.settings.get("qt_bionic_reading", False))
        self.settings["qt_bionic_reading"] = new
        if hasattr(self, "_bionic_act"):
            self._bionic_act.setChecked(new)
        self._apply_qt_theme(str(self.settings.get("theme", "dark")))
        self.statusBar().showMessage("Bionic reading: " + ("ON" if new else "OFF"))

    def _qt_toggle_syllables(self) -> None:
        """Toggle offline syllable splitting (read·a·bil·i·ty) and re-render.

        Needs the optional ``pyphen`` package.  When it's missing, offer the
        one-click background download (no pip) via the shared feature-install
        flow; the toggle only turns on once Pyphen is importable.  Display-only:
        the TTS text and highlight word map are unaffected."""
        new = not bool(self.settings.get("qt_syllable_split", False))
        if new and not self._qt_require_optional_feature("syllables", tr("Syllable splitting")):
            # Not installed yet — the install was offered; leave the aid off and
            # the menu unchecked until pyphen is present.
            if hasattr(self, "_syllable_act"):
                self._syllable_act.setChecked(False)
            return
        self.settings["qt_syllable_split"] = new
        if hasattr(self, "_syllable_act"):
            self._syllable_act.setChecked(new)
        self._apply_qt_theme(str(self.settings.get("theme", "dark")))
        self.statusBar().showMessage("Syllable splitting: " + ("ON" if new else "OFF"))

    def _qt_toggle_current_line(self) -> None:
        """Toggle the current-line focus band shown while reading."""
        new = not bool(self.settings.get("qt_current_line_highlight", False))
        self.settings["qt_current_line_highlight"] = new
        if hasattr(self, "_current_line_act"):
            self._current_line_act.setChecked(new)
        self.statusBar().showMessage(
            "Current-line highlight: " + ("ON" if new else "OFF")
        )

    def _qt_toggle_reading_ruler(self) -> None:
        """Toggle the reading ruler / typoscope overlay (a movable focus band)."""
        new = not bool(self.settings.get("qt_reading_ruler", False))
        self.settings["qt_reading_ruler"] = new
        if hasattr(self, "_ruler_act"):
            self._ruler_act.setChecked(new)
        self._apply_reading_ruler(new)
        self.statusBar().showMessage("Reading ruler: " + ("ON" if new else "OFF"))

