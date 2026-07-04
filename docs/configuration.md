# ⚙️ Configuration

`star` stores preferences in `settings.json`, created automatically on first run.

**File location:**

| Platform | Path |
|---|---|
| Linux | `~/.config/star/settings.json` |
| macOS | `~/Library/Application Support/star/settings.json` |
| Windows | `%APPDATA%\star\settings.json` |

Open it from the TUI with `M-x settings`.

> **Optional features install themselves.** Most optional capabilities (neural
> voices, OCR, transcription, richer imports, extra fonts, etc.) fetch what they
> need on demand the first time you use them — no manual `pip install`. This is
> controlled by `auto_install` (see below) and can be turned off globally with
> the `STAR_NO_AUTOINSTALL` environment variable.

---

## All settings keys

| Key | Default | Description |
|---|---|---|
| `theme` | `"obsidian"` | Color theme: `obsidian`, `dark`, `light`, `contrast`, `high-contrast` (AAA low-vision), `phosphor`. See `qt_follow_os_theme` for automatic light/dark/high-contrast switching |
| `qt_follow_os_theme` | `true` | Qt GUI: on startup, follow the OS light/dark/high-contrast appearance and pick a matching built-in theme — unless the user has explicitly chosen one (see `qt_theme_explicit`). Set `false` to always honor the saved `theme` |
| `qt_theme_explicit` | `false` | Set automatically the first time the user deliberately picks a theme (Choose Theme, Next Theme, or a profile that carries a theme). Once set, OS auto-detection never overrides that choice |
| `auto_install` | `true` | Auto-install optional dependencies on demand (neural voices, OCR, imports, fonts, …). Gates the first-run feature chooser and later on-demand fetches. Set `false` — or set the `STAR_NO_AUTOINSTALL` env var — to disable all automatic installs |
| `deps_prompted` | `false` | Set automatically once the first-run optional-feature chooser has been shown, so it never prompts again (populated automatically) |
| `tour_seen` | `false` | Set automatically once the first-run guided tour has been shown or skipped, so it never re-triggers on its own. The tour stays re-runnable from **Help ▸ Guided Tour** |
| `auto_check_updates` | `false` | Opt in to a quiet, best-effort update check shortly after launch (one cached PyPI query; only speaks up if a newer release exists). Off by default for privacy/offline use — **Help ▸ Check for Updates…** always runs a manual check regardless |
| `ui_language` | `"en"` | UI-chrome language (menus, toolbar, docks): `en`, `es`, `fr`, `de`, `pt`. See [Interface language](features.md#interface-language-i18n) |
| `tts_backend` | `"auto"` | TTS engine: `auto`, `pyttsx3`, `espeak`, `festival`, `piper`, `coqui`, `dectalk`, `none` |
| `piper_model` | `""` | Path to a Piper `.onnx` voice model for the `piper` backend (neural, offline). The matching `.onnx.json` must sit beside it. Also honored: `PIPER_MODEL` env var and Piper voice directories. |
| `elevenlabs_api_key` | `""` | API key for the opt-in `elevenlabs` cloud neural voice. Empty = disabled (no network egress); paste a key **and** select the `elevenlabs` engine to enable |
| `tts_rate` | `265` | Reading speed in words per minute |
| `tts_volume` | `1.0` | Volume from `0.0` (silent) to `1.0` (full) |
| `tts_voice` | `""` | Voice ID; empty = system default (auto-resolved via `tts_prefer_voice`) |
| `tts_prefer_voice` | `"eloquence"` | Substring of the voice to auto-select when `tts_voice` is empty (favors US English) |
| `tts_favorite_voices` | `[]` | Voice IDs starred in the Voice Manager; favorites sort to the top and are marked with ★ (populated automatically) |
| `tts_auto_play` | `false` | Start TTS automatically on file open |
| `tts_skip_code` | `true` | Skip fenced code blocks during TTS |
| `tts_auto_resume` | `true` | Restore the reading position automatically on open |
| `wrap_width` | `0` | Text wrap column; `0` = terminal width |
| `tab_width` | `4` | Spaces per tab character |
| `show_line_numbers` | `false` | Show line numbers in the left margin |
| `syntax_highlight` | `true` | Syntax-highlight code blocks |
| `scroll_margin` | `3` | Lines of context above/below current position |
| `font_size` | `0` | Display font size in pt; `0` = default; meaningful in Qt GUI |
| `ocr_lang` | `"eng"` | Tesseract language code(s) |
| `braille_table` | `"en-ueb-g2.ctb"` | liblouis translation table (only used when `braille_grade2` is true) |
| `braille_grade2` | `false` | Opt in to contracted Grade 2 via liblouis; otherwise the built-in Grade 1 translator is used |
| `audio_export_format` | `"wav"` | Default audio export container (WAV needs no external tools) |
| `audiobook_bitrate` | `"64k"` | AAC bitrate for M4B audiobook export (**File ▸ Export ▸ Audiobook**; needs ffmpeg) |
| `subtitle_format` | `"srt"` | Caption format for subtitle export: `srt` or `vtt` |
| `subtitle_word_level` | `false` | Emit one subtitle cue per word instead of sentence-grouped cues |
| `export_subtitles_with_audio` | `false` | Also write an SRT/VTT caption track next to every audio export |
| `highlight_current_word` | `true` | Highlight the spoken word during TTS |
| `highlight_color` | `"cyan"` | TTS word highlight color (any Qt/CSS color name or `#rrggbb`) |
| `sentence_highlight_color` | `""` | Sentence-band color in the `both` highlight granularity; empty = follow the theme's selection color (pickable in **View ▸ Reading Aids ▸ Karaoke Highlight…**) |
| `highlight_style` | `"background"` | Qt karaoke highlight style: `background` (filled), `underline`, `box` (wavy underline), `bold`, `color` (colored text) |
| `highlight_lead_words` | `0` | Qt only: words the visual highlight leads (`+`) or lags (`-`) the audio |
| `highlight_granularity` | `"word"` | Highlight by `word`, whole `sentence` (less flicker), or `both` (sentence band + word) |
| `highlight_speed` | `1.0` | Highlight timer speed as a fraction of `tts_rate`; `1.0` = match speech exactly. The pacing guard caps how far the timer can lead confirmed audio, so values above `1.0` do not cause runaway drift. |
| `recent_files` | `[]` | Recently opened files (populated automatically) |
| `last_path` | `""` | Path/URL of the most recently opened document (populated automatically) |
| `recent_files_limit` | `20` | Maximum entries in the recent files list |
| `gui_width` | `1000` | Qt window width in pixels |
| `gui_height` | `700` | Qt window height in pixels |
| `qt_font_family` | platform sans-serif | Qt display font family (`Helvetica Neue` / `Segoe UI` / `DejaVu Sans`); serif faces are discouraged for accessibility |
| `qt_font_size` | `14` | Qt display font size in pt |
| `qt_hidpi` | `true` | Enable high-DPI scaling in the Qt GUI |
| `qt_ctrl_pause` | `true` | Tap the `Ctrl` key alone to play/pause speech (JAWS habit); chords like `Ctrl+O` never trigger it |
| `qt_edit_preview` | `false` | Show a live-rendered HTML preview beside the editor in edit mode (toggle with `Ctrl+Shift+L`) |
| `qt_caret_browsing` | `true` | Show a movable text caret in the read-only document view for keyboard navigation, passage selection, and Define Word (toggle with `F7` or **View ▸ Caret Browsing**) |
| `qt_autoscroll` | `true` | Auto-scroll the reading view to keep the spoken/highlighted word visible; set `false` to scroll manually |
| `reading_stats` | `{}` | Per-document reading time, progress, and session counts (populated automatically) |
| `library` | `{}` | Library/bookshelf metadata for every opened document (populated automatically) |
| `library_folders` | `[]` | Folders scanned as a folder-as-library (e.g. a Dropbox/OneDrive/Syncthing directory); the filesystem is the library, so it syncs across machines for free |
| `sync_conflict_policy` | `"newest"` | How to resolve a synced `.star/` sidecar that diverges between machines: `newest` (newer timestamp wins — the classic last-write-wins), `highest_progress` (keep the furthest reading position), or `manual` (keep local and surface conflicts). Annotations always union by id |
| `profiles` | `{}` | Named setting bundles (voice, rate, theme, font, spacing, highlight) saved via the Profiles menu |
| `pronunciations` | `{}` | Pronunciation lexicon: `{term: spoken form}` applied before other TTS normalization |
| `use_pronunciations` | `true` | Apply the pronunciation lexicon while reading |
| `dictionary_file` | `""` | Path to a custom JSON dictionary for Define Word (`{term: definition}` or `{term: {pos, definition, pronunciation, examples}}`); checked before WordNet |
| `qt_show_toc` | `true` | Show the Contents panel at startup |
| `qt_show_notes` | `false` | Show the Notes/annotations panel at startup (hidden by default; toggle with `Ctrl+Shift+N`) |
| `qt_line_height` | `1.5` | Qt line-height multiplier (WCAG 1.4.12). Adjust via **View → Reading Aids → Text Spacing…** |
| `qt_letter_spacing` | `0.0` | Qt extra letter spacing, percent of font size (`0` = normal) |
| `qt_word_spacing` | `0.0` | Qt extra word spacing in pixels (`0` = normal) |
| `qt_dyslexia_font` | `false` | Prefer an installed dyslexia-friendly font (OpenDyslexic / Atkinson Hyperlegible / Lexend / Comic Sans) when available |
| `qt_reading_font` | `"default"` | Reading-font override (**View ▸ Reading Aids ▸ Reading Font**): `default` (none), `opendyslexic`, `atkinson` (Atkinson Hyperlegible, for low vision), or `lexend`. Fetched on demand and applied app-wide + in-document |
| `qt_current_line_highlight` | `false` | Tint the line being read with a focus band |
| `qt_bionic_reading` | `false` | Embolden the leading part of each word (bionic reading) |
| `qt_syllable_split` | `false` | Show words split into syllables (`read·a·bil·i·ty`) as a decoding aid (**View ▸ Reading Aids ▸ Syllable Splitting**; needs `pyphen`). Display-only — speech and highlighting are unaffected |
| `qt_syllable_sep` | `"·"` | The visible separator inserted between syllables (U+00B7 middot) |
| `qt_reading_ruler` | `false` | Show a movable, translucent band (typoscope) that follows the caret to help keep your place |
| `qt_ruler_height` | `40` | Reading-ruler band height in pixels (16–160) |
| `qt_ruler_opacity` | `22` | Reading-ruler band opacity, `0`–`100` (percent) |
| `qt_ruler_color` | `""` | Reading-ruler band color; empty = match `highlight_color` (pickable in the Reading Ruler… dialog) |
| `qt_vocab_highlight` | `false` | Highlight uncommon / academic vocabulary (difficult-word overlay; needs `wordfreq`) |
| `qt_rsvp_mode` | `false` | Qt GUI: show the RSVP (Rapid Serial Visual Presentation) overlay — one word at a time at a fixed point |
| `qt_rsvp_position` | `"top-center"` | Qt RSVP overlay placement: `top-left`/`center`/`right`, `center-left`/`right`, `center`, `bottom-left`/`center`/`right` |
| `qt_rsvp_font_size` | `48` | Qt RSVP focused-word point size |
| `qt_rsvp_context` | `true` | Qt RSVP: show the previous/next word above and below the focused word |
| `tui_rsvp_mode` | `false` | TUI mirror of the RSVP toggle |
| `tui_rsvp_position` | `"top-center"` | TUI RSVP placement (same nine-position set as `qt_rsvp_position`) |
| `annotations` | `{}` | Per-document notes: `{path: [{char_pos, word_idx, anchor, note, tags, cite, ts, id, relations}]}`. Reviewable notes (a highlight and/or a note body) also carry an `sr_state` sub-dict — the spaced-repetition scheduler's per-card memory (next review date, interval, stability, difficulty, reps, lapses), so review scheduling persists across sessions. See [`star/sr.py`](../star/sr.py) (FSRS scheduler) and [`star/annotations.py`](../star/annotations.py) |
| `annotation_filter_presets` | `{}` | Saved note-filter queries, `{name: filter-query}` (populated automatically) |
| `citations` | `[]` | Shared citation library (BibTeX/RIS/CSL-JSON import/export) |
| `graph` | *(nested)* | Knowledge-graph options for typed relations between annotations: `auto_rebuild_on_annotation_change` (`true`), `default_layout` (`"spring"`), `node_color_by` (`"doc"`), `show_orphan_nodes` (`false`), `concept_domain` (`"general"`), `last_export_dir` (`""`) |
| `vault` | *(nested)* | Obsidian vault import/export: `last_vault_dir` (`""`) and `default_link_relation` (`"SEE_ALSO"`, the type given to untyped `[[wikilinks]]` on import) |
| `video` | *(nested)* | Video-export options: `resolution` (`"1280x720"`), `theme` (`""` = inherit global), `font_scale` (`1.0`), `subtitles` (`"soft"` — `soft`/`burn`/`none`), `last_export_dir` (`""`) |
| `whisper_model` | `"base"` | Whisper model size for transcription/dictation (`tiny`…`large`) |
| `transcribe_timestamps` | `false` | Prefix each transcript segment with its `[hh:mm:ss]` start time |
| `whisper_chunk_seconds` | `6` | Chunk length in seconds for live streaming dictation |
| `user_highlights` | `{}` | Persistent text highlights per document path |
| `document_cache` | `true` | Cache parsed documents for instant reopening |
| `cache_max_size_mb` | `100` | Maximum cache directory size in MB |
| `qt_paginate_large_docs` | `false` | Qt GUI: opt into windowed pagination so only part of a very large document is laid out at a time (much faster first paint). Off by default; see the caveat below. See [Performance](PERFORMANCE.md) |
| `qt_paginate_threshold_words` | `60000` | Only paginate documents with at least this many words (the size gate) — ordinary books/articles always take the unchanged whole-document path |
| `qt_paginate_words_per_page` | `1200` | Target words per rendered page under pagination |
| `qt_paginate_window_pages` | `2` | Pages of context rendered on each side of the active page (a larger window re-renders less often but lays out more at once) |
| `footnote_mode` | `"inline"` | Footnote handling: `inline`, `deferred`, `skip` |
| `pdf_reading_order` | `"reconstruct"` | PDF layout handling: `reconstruct` rebuilds multi-column reading order and suppresses running headers/footers/page numbers; `raw` keeps pdfminer's native box order |
| `prefer_pandoc` | `true` | When Pandoc is installed, prefer it as a first-class importer for the office/markup formats it handles (and Pandoc-only types like `.rtf`, `.fb2`, `.typst`); falls back to native loaders if Pandoc fails. EPUB always stays native (chapter navigation). Set `false` to always use native loaders |
| `epub_show_chapters` | `true` | Include chapter headings in EPUB rendering |
| `normalize_math` | `true` | Convert math expressions to spoken English |
| `normalize_numbers` | `true` | Convert numbers/dates/times/currency to spoken form |
| `expand_abbreviations` | `true` | Expand common abbreviations before TTS |
| `abbrev_expansions` | `{}` | Custom abbreviation overrides |
| `table_reading_mode` | `"structured"` | Table TTS: `structured`, `flat`, `skip` |
| `use_ssml` | `false` | Wrap TTS text in SSML for prosody (pyttsx3/eSpeak) |
| `ssml_sentence_pause_ms` | `350` | SSML pause after sentence-ending punctuation |
| `ssml_clause_pause_ms` | `150` | SSML pause after clause punctuation |
| `speak_image_alts` | `true` | Read image alt-text aloud |
| `show_reading_level` | `true` | Enable reading-level computation |
| `speed_presets` | *(see below)* | Named speed presets |
| `bookmarks` | `{}` | Named bookmarks per document |
| `reading_positions` | `{}` | Saved reading positions per document |
| `nav_history_size` | `50` | Within-session navigation history depth |
| `regex_search` | `false` | Enable regex mode for search |
| `keybindings` | `{}` | Qt GUI shortcut remaps, `{default_shortcut: custom_shortcut}` |
| `batch_format` | `"markdown"` | Default output format for batch conversion: `markdown`, `text`, or `braille` |
| `watch_format` | `"markdown"` | Default output format for the `--watch` hot-folder: `markdown`, `text`, or `braille` |
| `watch_stable_seconds` | `2.0` | Hot-folder debounce: convert a file only after its size holds steady this long (so files still copying in are never read half-written) |
| `watch_poll_interval` | `0.5` | Hot-folder poll interval in seconds |
| `watch_move_processed` | `true` | Move each source into `<input>/processed/` after a successful hot-folder conversion (failures go to `<input>/failed/`) |

Default speed presets:

```json
"speed_presets": {
  "skim": 350,
  "normal": 265,
  "study": 200,
  "slow": 150
}
```

eSpeak-NG highlight timing offset (advanced): `espeak_highlight_offset_ms`
(default `120`) nudges the in-process eSpeak highlight to compensate for
audio-output latency — raise it if highlights lead the speech, lower it toward
`0` if they lag.

Large-document pagination caveat: to keep highlight and difficult-word placement
exact, a document you have saved highlights on — or have the difficult-word
overlay (`qt_vocab_highlight`) enabled on — is rendered whole rather than
paginated, even when `qt_paginate_large_docs` is on.

---

See also: [Usage Guide](usage_guide.md) · [Features](features.md) ·
[Installation](installation.md) · [Architecture](architecture.md).
