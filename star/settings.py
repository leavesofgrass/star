"""Persistent settings store and the default settings table."""
import logging as _logging

from ._runtime import *  # noqa: F401,F403

_log = _logging.getLogger("star.settings")

# =============================================================================
# Default settings
# =============================================================================

DEFAULTS: Dict[str, Any] = {
    "theme": "obsidian",
    # ── OS colour-scheme / contrast following (Qt GUI) ────────────────────
    # When True, star queries the OS appearance on startup (Qt 6.5+
    # QStyleHints.colorScheme) and, if the user prefers Dark or Light, picks a
    # matching built-in theme — UNLESS the user has explicitly chosen one, in
    # which case their choice always wins (see qt_theme_explicit).  Set False to
    # always honour the saved ``theme`` regardless of the OS appearance.
    "qt_follow_os_theme": True,
    # Set to True the first time the user *deliberately* picks a theme (Choose
    # Theme, Next Theme, or a profile that carries a theme).  Once set, OS
    # auto-detection never overrides the choice.  This is how "do not override
    # an explicit user theme choice" is enforced across launches.
    "qt_theme_explicit": False,
    # Optional-dependency auto-install (star/autodeps.py). auto_install gates the
    # first-run chooser and on-demand fetches; deps_prompted flips true once the
    # chooser has been shown so it never nags again. STAR_NO_AUTOINSTALL overrides.
    "auto_install": True,
    "deps_prompted": False,
    # ── Onboarding & discoverability (Qt GUI) ─────────────────────────────
    # First-run guided tour (star/gui/mixin_tour.py). tour_seen flips true once
    # the tour has been shown (or explicitly skipped) so it never re-triggers on
    # its own; it stays re-runnable from Help ▸ Guided Tour.
    "tour_seen": False,
    # Quiet startup update check (star/update.py). OFF by default to respect
    # privacy and offline use — star never phones home unless the user opts in.
    # When True, star does one best-effort, cached PyPI check shortly after
    # launch and only speaks up if a newer release exists. Help ▸ Check for
    # Updates… always runs a manual check regardless of this setting.
    "auto_check_updates": False,
    # UI chrome language (menus, toolbar, docks).  ISO-639-1 code of a catalog
    # in star/locale/ ("en" = English source, no catalog needed).  See star/i18n.py.
    "ui_language": "en",
    "tts_backend": "auto",  # "auto"|"pyttsx3"|"espeak"|"festival"|"coqui"|"dectalk"|"none"
    "tts_rate": 265,  # words per minute — intentionally brisk
    "tts_volume": 1.0,  # 0.0 – 1.0
    "tts_voice": "",  # empty = system default (auto-resolved per platform)
    "tts_prefer_voice": "eloquence",  # substring of a preferred default voice
    # Opt-in ElevenLabs cloud neural voice.  Empty = disabled (no network egress);
    # paste a key AND select the "elevenlabs" engine to enable.  See star/tts/cloud.
    "elevenlabs_api_key": "",
    "tts_auto_play": False,  # start reading on file open
    "tts_skip_code": True,  # don't read code blocks aloud
    "wrap_width": 0,  # 0 = terminal width
    "tab_width": 4,
    "show_line_numbers": False,
    "syntax_highlight": True,
    "scroll_margin": 3,
    "font_size": 0,  # 0 = terminal default; meaningful in Qt GUI only
    "ocr_lang": "eng",  # Tesseract language(s), e.g. "eng+spa"
    "braille_table": "en-ueb-g2.ctb",
    "braille_grade2": False,  # opt-in liblouis Grade 2; built-in Grade 1 is default
    "audio_export_format": "wav",  # default audio export container (no ffmpeg needed)
    "audiobook_bitrate": "64k",  # AAC bitrate for M4B audiobook export (needs ffmpeg)
    "last_path": "",
    "recent_files": [],  # list of recently opened paths/URLs
    # Reading statistics & progress: per-document time read, furthest word
    # reached, progress %, session count, and last-read time.
    "reading_stats": {},  # {path: {seconds, words_read, words_total, pct, sessions, last_ts}}
    # Library / bookshelf: metadata for every opened document.
    "library": {},  # {path: {title, format, added, last_opened}}
    # Folder-as-library: directories scanned for documents (e.g. a Dropbox /
    # OneDrive / Syncthing folder).  The library is the filesystem itself, so it
    # syncs across machines for free.  See star/library.py.
    "library_folders": [],  # [absolute folder paths]
    # Conflict-resolution policy when a synced .star/ sidecar diverges between
    # machines: "newest" (newer timestamp wins — the historical last-write-wins
    # behaviour), "highest_progress" (keep the furthest reading position), or
    # "manual" (keep local and surface conflicts).  See star/sync.py.
    "sync_conflict_policy": "newest",
    # Voice & profile presets: named bundles of voice, rate, theme, font,
    # spacing, and highlight settings that can be applied in one step.
    "profiles": {},  # {name: {setting_key: value}}
    # Pronunciation lexicon: spoken-form overrides for specific terms (drug
    # names, anatomy, acronyms) so TTS says them correctly and consistently.
    "pronunciations": {},  # {term: spoken_form}
    "use_pronunciations": True,
    # Optional custom dictionary for Define Word: a JSON file mapping term ->
    # definition (string) or {pos, definition, pronunciation, examples}.  Checked
    # before WordNet, so a reader can layer their own domain glossary on top.
    "dictionary_file": "",
    "highlight_current_word": True,
    "highlight_color": "cyan",  # color of the TTS word highlight
    # Sentence-band color used in "both" highlight granularity.  Empty = follow
    # the theme's selection color (previous behaviour); set a hex like "#3b3f52"
    # for a fixed band that clearly contrasts with the word color.  Both are
    # pickable from View ▸ Reading Aids ▸ Karaoke Highlight….
    "sentence_highlight_color": "",
    "gui_width": 1000,
    "gui_height": 700,
    "footnote_mode": "inline",  # "inline" | "deferred" | "skip"
    "epub_show_chapters": True,
    "document_cache": True,
    "cache_max_size_mb": 100,
    "qt_show_toc": True,
    "qt_show_notes": False,  # Notes/annotations dock hidden until first used
    "annotations": {},  # {path: [{"char_pos", "word_idx", "anchor", "note", "tags", "cite", "ts", "id", "relations"}]}
    "annotation_filter_presets": {},  # {name: filter-query} saved note filters
    # Knowledge graph: typed relations between annotations across documents.
    "graph": {
        "auto_rebuild_on_annotation_change": True,
        "default_layout": "spring",  # "spring" | "dot" | "neato" | "fdp"
        "node_color_by": "doc",  # "doc" | "tag" | "rel_type"
        "show_orphan_nodes": False,  # include nodes that have no edges
        "concept_domain": "general",  # "general" | "legal" | "medical" | "sociological"
        "last_export_dir": "",
    },
    # Obsidian vault import/export.
    "vault": {
        "last_vault_dir": "",
        "default_link_relation": "SEE_ALSO",  # type for untyped [[wikilinks]] on import
    },
    # ── Video export ─────────────────────────────────────────────────────────
    "video": {
        "resolution": "1280x720",  # WxH for rendered frames
        "theme": "",               # "" = inherit global theme
        "font_scale": 1.0,         # scale factor applied to the render font size
        "subtitles": "soft",       # "soft" | "burn" | "none"
        "last_export_dir": "",
    },
    "citations": [],  # citation library: list of CSL-ish dicts (see _citation_label)
    "whisper_model": "base",  # Whisper model size for dictation/transcription
    "transcribe_timestamps": False,  # prefix [hh:mm:ss] segment times in transcripts
    "whisper_chunk_seconds": 6,  # chunk length for live streaming dictation
    "keybindings": {},  # {default_shortcut: custom_shortcut} GUI remap overrides
    "bookmarks": {},
    "nav_history_size": 50,
    "regex_search": False,
    "qt_hidpi": True,
    "qt_font_family": _default_sans_font(),  # sans-serif for reading accessibility
    "qt_font_size": 14,
    # ── Text spacing (WCAG 1.4.12) — Qt GUI ─────────────────────────────
    # Generous, independently adjustable spacing reduces crowding effects
    # for dyslexic and low-vision readers.
    "qt_line_height": 1.5,  # line-height multiplier (1.0 = single)
    "qt_letter_spacing": 0.0,  # extra letter spacing, % of font size (0 = normal)
    "qt_word_spacing": 0.0,  # extra word spacing in px (0 = normal)
    # ── Caret browsing (Qt GUI) ──────────────────────────────────────
    # Show a visible, freely-movable text caret in the read-only document view
    # so the user can navigate by keyboard (arrows / Ctrl+arrows / Home-End),
    # select passages for highlighting, and look up the word under the caret
    # (Define Word). On by default for accessibility; toggle with F7 or
    # View ▸ Caret Browsing. False restores the clean caret-free reader view.
    "qt_caret_browsing": True,
    # ── JAWS-style bare-Ctrl tap to play/pause (Qt GUI) ──────────────
    # Tapping (pressing and releasing) the Ctrl key on its own toggles speech,
    # mirroring the JAWS "Ctrl silences speech" habit.  Using Ctrl as a
    # modifier in a chord (Ctrl+O, etc.) never triggers it.  Set False to
    # disable if it ever misfires.
    "qt_ctrl_pause": True,
    # ── Live HTML preview while editing (Qt GUI) ──────────────────
    # When True, edit mode shows a split pane with a live-rendered HTML
    # preview of the Markdown source beside the editor (debounced).
    "qt_edit_preview": False,
    # ── Large-document pagination (Qt GUI) — see docs/PERFORMANCE.md ───────
    # QTextEdit lays out a whole document's HTML at once; for very large
    # documents that one-shot layout (and every later scroll/repaint) is slow.
    # When this is on AND a document exceeds qt_paginate_threshold_words, star
    # renders only a *window* of pages into the editor at a time, advancing the
    # window as reading / navigation / Find crosses a page boundary.  The full
    # plain text and word map stay in memory so speech, highlighting, caret
    # navigation, and Define-Word remain correct; the word→char map is rebuilt
    # per window (out-of-window words carry a sentinel).  OFF by default: normal
    # documents (and all existing behavior) are completely unaffected, and even
    # opted-in it engages only past the threshold.  See docs/PERFORMANCE.md for
    # the design, the size gate, and the features that degrade under paging.
    "qt_paginate_large_docs": False,
    # Only paginate documents with at least this many words (the size gate).
    # Chosen high so ordinary books/articles always take the unchanged
    # whole-document path; pagination is for the pathologically large outliers.
    "qt_paginate_threshold_words": 60000,
    # Target words per rendered page and how many pages flank the active one in
    # the rendered window (a larger window re-renders less often but lays out
    # more at once).  See star/pagination.py.
    "qt_paginate_words_per_page": 1200,
    "qt_paginate_window_pages": 2,
    # ── Dyslexia-friendly reading aids — Qt GUI ───────────────────
    "qt_dyslexia_font": False,  # prefer a bundled/installed dyslexia-friendly font
    # Reading-font chooser (View ▸ Reading Aids ▸ Reading Font): "default" (no
    # override), "opendyslexic", "atkinson" (Atkinson Hyperlegible), or "lexend".
    # Fetched on demand from GitHub (OFL) and applied app-wide + in-document.
    "qt_reading_font": "default",
    "qt_current_line_highlight": False,  # band-highlight the line being read
    "qt_bionic_reading": False,  # embolden the leading part of each word
    # ── Syllable splitting (offline decoding aid, needs pyphen) ────
    # Display-only: inserts a middot between syllables (read·a·bil·i·ty) in the
    # rendered document; never alters the TTS text or the highlight word map.
    "qt_syllable_split": False,      # whether syllable separators are shown
    "qt_syllable_sep": "·",          # the visible separator (U+00B7 middot)
    # ── Reading ruler / typoscope (Qt GUI) ────────────────────────
    # A wide translucent band tracking the caret line — a movable typoscope,
    # distinct from the thin current-line focus tint above.
    "qt_reading_ruler": False,       # whether the ruler overlay is shown
    "qt_ruler_height": 40,           # band height in pixels (16–160)
    "qt_ruler_opacity": 22,          # band opacity, 0–100 (percent)
    # ── RSVP (Rapid Serial Visual Presentation) ───────────────────
    # One word at a time displayed at a fixed point — an aid for some dyslexic
    # readers and users with restricted visual fields.
    "qt_rsvp_mode": False,          # whether the floating overlay is shown
    "qt_rsvp_position": "top-center",  # top-left/center/right, center-left/right,
                                     # center, bottom-left/center/right
    "qt_rsvp_font_size": 48,        # point size of the focused word
    "qt_rsvp_context": True,        # show the prev/next word above/below
    "tui_rsvp_mode": False,         # TUI mirror of the toggle
    "tui_rsvp_position": "top-center",  # same 9-key set, TUI placement
    # ── Karaoke word-highlight tuning — Qt GUI (highlight_speed is shared) ─
    "highlight_style": "background",  # background|underline|box|bold|color
    "highlight_lead_words": 0,  # advance the visual highlight N words (lead/lag)
    # ── Highlight granularity — TUI + Qt GUI ─────────────
    # "word"     — highlight the single word being spoken (default).
    # "sentence" — highlight the whole sentence being spoken (less flicker).
    # "both"     — tint the sentence and mark the word within it.
    "highlight_granularity": "word",  # word|sentence|both
    # ── Piper neural TTS ───────────────────────────────
    # Path to a Piper voice model (.onnx).  Required for the "piper" backend;
    # the matching .onnx.json config must sit beside it.  Free, offline,
    # neural-quality voices: https://github.com/rhasspy/piper
    "piper_model": "",
    # ── Timestamped subtitle export ────────────────────
    "subtitle_format": "srt",  # srt|vtt — format used when emitting captions
    "subtitle_word_level": False,  # one cue per word instead of per sentence
    "export_subtitles_with_audio": False,  # also write captions on audio export
    "speak_image_alts": True,
    "show_reading_level": True,
    "normalize_math": True,
    "recent_files_limit": 20,
    # Abbreviation expansion
    "expand_abbreviations": True,
    "abbrev_expansions": {},  # user overrides: {"abbrev.": "expansion"}
    # Number normalization
    "normalize_numbers": True,
    # Table reading mode
    "table_reading_mode": "structured",  # "structured" | "flat" | "skip"
    # PDF reading order: "reconstruct" rebuilds multi-column reading order and
    # suppresses running headers/footers; "raw" keeps pdfminer's native order.
    "pdf_reading_order": "reconstruct",  # "reconstruct" | "raw"
    # Prefer Pandoc as a first-class importer when it is installed: it handles
    # the office/markup formats it supports (and Pandoc-only types like .rtf,
    # .fb2, .typst, …) in preference to the native loaders. EPUB always stays
    # native (for chapter navigation). Set false to always use native loaders.
    "prefer_pandoc": True,
    # User text highlights (persistent per-document colored annotations)
    "user_highlights": {},  # {path: [{"start": int, "end": int, "color": str}]}
    # Reading position memory
    "tts_auto_resume": True,  # restore position automatically on open
    "reading_positions": {},  # {path: {"offset": int, "pct": int, "ts": str}}
    # Speed presets
    "speed_presets": {
        "skim": 350,
        "normal": 265,
        "study": 200,
        "slow": 150,
    },
    # SSML prosody
    # Off by default: plain-text mode enables pyttsx3 word-boundary callbacks
    # which give accurate word highlighting.  SSML disables those callbacks
    # (character offsets point into the XML string, not the plain text) so the
    # timer runs blind and races ahead of speech.  Enable SSML with the
    # 'ssml-on' command or by setting use_ssml=true in the settings file.
    "use_ssml": False,  # wrap TTS text in SSML for better pausing (opt-in)
    "ssml_sentence_pause_ms": 350,  # pause after . ! ?
    "ssml_clause_pause_ms": 150,  # pause after , ; :
    # Highlight timing (fraction of speech rate the cursor advances at).
    # 1.0 = match speech WPM exactly.  The pacing guard in the highlight timer
    # (capped at _MAX_AHEAD words past the last callback-confirmed position)
    # is the true throttle, so running the timer at full speed keeps the
    # highlight tight to the audio instead of lagging behind it.
    "highlight_speed": 1.0,
    # In-process eSpeak-NG (libespeak-ng) highlight latency compensation, in
    # milliseconds.  That backend paces each word highlight to the word's actual
    # audio position reported by the engine; this offset is added to that target
    # so the highlight is not painted slightly *before* the word is heard (which
    # is unavoidable otherwise, because audio reaches the speakers a little after
    # the engine queues it).  Increase it if highlights still run ahead of the
    # audio; lower it toward 0 if they lag behind.
    "espeak_highlight_offset_ms": 120,
    # ── Batch conversion & hot-folder watching ───────────
    # Default output format for batch conversion and the --watch hot-folder
    # (any of: markdown | text | braille; see convert.supported_formats()).
    "batch_format": "markdown",
    "watch_format": "markdown",
    # Hot-folder debounce: a file is only converted once its size has held
    # steady for watch_stable_seconds (polled every watch_poll_interval),
    # so files still being copied in are never read half-written.
    "watch_stable_seconds": 2.0,
    "watch_poll_interval": 0.5,
    # Move each source into <input>/processed/ after a successful conversion
    # (failures always go to <input>/failed/).
    "watch_move_processed": True,
}

# =============================================================================
# Settings manager
# =============================================================================


class Settings:
    """Persistent JSON settings with dot-notation access."""

    def __init__(self):
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            # Accept all known keys, plus nested dicts that may have grown.
            for k, v in raw.items():
                if k in DEFAULTS:
                    # Merge nested dicts (speed_presets, reading_positions)
                    if isinstance(DEFAULTS[k], dict) and isinstance(v, dict):
                        merged = dict(DEFAULTS[k])
                        merged.update(v)
                        self._data[k] = merged
                    else:
                        self._data[k] = v
        except FileNotFoundError:
            pass  # first launch — defaults are correct, not an error
        except (json.JSONDecodeError, OSError) as exc:
            # A corrupt or unreadable settings file silently resets every
            # preference to default; surface it so the reset is diagnosable.
            _log.warning("Could not read settings from %s: %s", SETTINGS_FILE, exc)
        self._migrate()

    def _migrate(self) -> None:
        """Upgrade settings files written by earlier versions.

        Older versions persisted every default into settings.json, which means
        deprecated defaults (the serif ``Georgia`` display font and the
        lagging ``0.85`` highlight speed) would otherwise be pinned forever.
        We only replace values that exactly match the old default, so a user's
        deliberate choice is never overridden.
        """
        if self._data.get("qt_font_family") == "Georgia":
            # Serif default deprecated for reading-accessibility reasons.
            self._data["qt_font_family"] = _default_sans_font()
        if self._data.get("highlight_speed") == 0.85:
            self._data["highlight_speed"] = 1.0

    def save(self) -> None:
        # Write atomically: serialize to a temp file in the same directory,
        # fsync it, then os.replace() it over settings.json.  A mid-write power
        # loss or a cloud-sync client grabbing the file therefore never leaves a
        # half-written / corrupt settings.json — the next launch reads either the
        # complete old file or the complete new one, never a truncated middle.
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(self._data, indent=2, ensure_ascii=False)
            fd, tmp = tempfile.mkstemp(
                prefix=SETTINGS_FILE.name + ".", suffix=".tmp",
                dir=str(SETTINGS_FILE.parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(text)
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except OSError:
                        pass  # fsync unsupported on some filesystems — write still lands
                os.replace(tmp, SETTINGS_FILE)  # atomic rename over the destination
            except OSError:
                # Never leave the temp file behind on a failed write.
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError as exc:
            # Persistence failure would otherwise be fully silent: the user's
            # preferences, presets, annotations, highlights, and reading
            # positions would appear to save but be lost on next launch.
            # Keep degrading gracefully (never raise), but make it diagnosable.
            _log.warning("Could not save settings to %s: %s", SETTINGS_FILE, exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)
