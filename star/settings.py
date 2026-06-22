"""Persistent settings store and the default settings table."""
from ._runtime import *  # noqa: F401,F403


# =============================================================================
# Default settings
# =============================================================================

DEFAULTS: Dict[str, Any] = {
    "theme": "dark",
    "tts_backend": "auto",  # "auto"|"pyttsx3"|"espeak"|"festival"|"coqui"|"dectalk"|"none"
    "tts_rate": 265,  # words per minute — intentionally brisk
    "tts_volume": 1.0,  # 0.0 – 1.0
    "tts_voice": "",  # empty = system default (auto-resolved per platform)
    "tts_prefer_voice": "eloquence",  # substring of a preferred default voice
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
    "last_path": "",
    "recent_files": [],  # list of recently opened paths/URLs
    # Reading statistics & progress: per-document time read, furthest word
    # reached, progress %, session count, and last-read time.
    "reading_stats": {},  # {path: {seconds, words_read, words_total, pct, sessions, last_ts}}
    # Library / bookshelf: metadata for every opened document.
    "library": {},  # {path: {title, format, added, last_opened}}
    # Voice & profile presets: named bundles of voice, rate, theme, font,
    # spacing, and highlight settings that can be applied in one step.
    "profiles": {},  # {name: {setting_key: value}}
    # Pronunciation lexicon: spoken-form overrides for specific terms (drug
    # names, anatomy, acronyms) so TTS says them correctly and consistently.
    "pronunciations": {},  # {term: spoken_form}
    "use_pronunciations": True,
    "highlight_current_word": True,
    "highlight_color": "cyan",  # color of the TTS word highlight
    "gui_width": 1000,
    "gui_height": 700,
    "footnote_mode": "inline",  # "inline" | "deferred" | "skip"
    "epub_show_chapters": True,
    "document_cache": True,
    "cache_max_size_mb": 100,
    "qt_show_toc": True,
    "qt_show_notes": False,  # Notes/annotations dock hidden until first used
    "annotations": {},  # {path: [{"char_pos", "word_idx", "anchor", "note", "tags", "cite", "ts"}]}
    "annotation_filter_presets": {},  # {name: filter-query} saved note filters
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
    # ── Dyslexia-friendly reading aids — Qt GUI ───────────────────
    "qt_dyslexia_font": False,  # prefer a bundled/installed dyslexia-friendly font
    "qt_current_line_highlight": False,  # band-highlight the line being read
    "qt_bionic_reading": False,  # embolden the leading part of each word
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
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
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
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)
