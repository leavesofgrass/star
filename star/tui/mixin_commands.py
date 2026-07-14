"""Minibuffer + M-x command palette and its key handlers.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from .text import MX_COMMANDS
from ..search import LineEditor


class CommandsMixin:

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
        # The raw remainder of the line, whitespace intact — for commands whose
        # argument is a path or phrase (" ".join(args) would collapse a path
        # like "week  3.mp3" into a nonexistent file).
        rest = cmd_line.split(None, 1)[1].strip() if len(parts) > 1 else ""

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
            "batch-convert": self._batch_convert,
            "edit": self._edit_cmd,
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
            "graph-show": self._graph_show,
            "graph-rebuild": self._graph_rebuild,
            "graph-add-relation": self._graph_add_relation,
            "graph-extract-concepts": self._graph_extract_concepts,
            "graph-suggest-relations": self._graph_suggest,
            "graph-export-svg": lambda: self._graph_export("svg"),
            "graph-export-dot": lambda: self._graph_export("dot"),
            "graph-export-plantuml": lambda: self._graph_export("puml"),
            "graph-export-json": lambda: self._graph_export("json"),
            "import-vault": self._obsidian_import,
            "export-vault": self._obsidian_export,
            # Study tools — results open as live, speakable documents.
            # Both take the REST of the line ("translate chinese (simplified)",
            # "transcribe-file C:\lectures\week 3.mp3" — paths have spaces).
            "translate": lambda: self._translate_cmd(rest),
            "summarize": self._summarize_cmd,
            "dictate-note": self._dictate_note_cmd,
            "transcribe-file": lambda: self._transcribe_file_cmd(rest),
            "whisper-model": lambda: self._whisper_model_cmd(arg),
            "play": self._tts_play,
            "stop": self._tts_stop,
            "pause": self._tts_toggle,
            "speak-line": self._tts_speak_current_line,
            "search": lambda: self._enter_minibuffer(
                tr("Search: "),
                mode="search",
                on_commit=lambda q: self._do_search(q, "forward"),
            ),
            "search-backward": lambda: self._enter_minibuffer(
                tr("Search ↑: "),
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
            "define": lambda: self._define_cmd(arg),
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
            # Epic I — Archive ingestion
            "open-archive": lambda: self._open_archive_prompt(arg or ""),
            # Epic II — Metadata & discovery
            "metadata-edit": self._metadata_edit_cmd,
            "library-search": lambda: self._library_search_cmd(arg or ""),
            # Epic III — Video export
            "export-video": lambda: self._export_video_cmd(arg or ""),
            # RSVP reading mode
            "rsvp-mode": self._rsvp_mode_cmd,
            "rsvp-position": lambda: self._rsvp_position_cmd(arg or ""),
        }

        fn = cmd_map.get(cmd)
        if fn:
            try:
                fn()
            except Exception as e:
                self.notify(f"Command error: {e}", error=True)
        else:
            self.notify(f"Unknown command '{cmd}'.  Press F1 for help.", error=True)

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
