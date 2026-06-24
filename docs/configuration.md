# ⚙️ Configuration

`star` stores preferences in `settings.json`, created automatically on first run.

**File location:**

| Platform | Path |
|---|---|
| Linux | `~/.config/star/settings.json` |
| macOS | `~/Library/Application Support/star/settings.json` |
| Windows | `%APPDATA%\star\settings.json` |

Open it from the TUI with `M-x settings`.

---

## All settings keys

| Key | Default | Description |
|---|---|---|
| `theme` | `"dark"` | Color theme: `dark`, `light`, `contrast`, `phosphor` |
| `tts_backend` | `"auto"` | TTS engine: `auto`, `pyttsx3`, `espeak`, `festival`, `piper`, `coqui`, `dectalk`, `none` |
| `piper_model` | `""` | Path to a Piper `.onnx` voice model for the `piper` backend (neural, offline). The matching `.onnx.json` must sit beside it. Also honored: `PIPER_MODEL` env var and Piper voice directories. |
| `tts_rate` | `265` | Reading speed in words per minute |
| `tts_volume` | `1.0` | Volume from `0.0` (silent) to `1.0` (full) |
| `tts_voice` | `""` | Voice ID; empty = system default (auto-resolved via `tts_prefer_voice`) |
| `tts_prefer_voice` | `"eloquence"` | Substring of the voice to auto-select when `tts_voice` is empty (favors US English) |
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
| `subtitle_format` | `"srt"` | Caption format for subtitle export: `srt` or `vtt` |
| `subtitle_word_level` | `false` | Emit one subtitle cue per word instead of sentence-grouped cues |
| `export_subtitles_with_audio` | `false` | Also write an SRT/VTT caption track next to every audio export |
| `highlight_current_word` | `true` | Highlight the spoken word during TTS |
| `highlight_color` | `"cyan"` | TTS word highlight color (any Qt/CSS color name or `#rrggbb`) |
| `highlight_style` | `"background"` | Qt karaoke highlight style: `background` (filled), `underline`, `box` (wavy underline), `bold`, `color` (colored text) |
| `highlight_lead_words` | `0` | Qt only: words the visual highlight leads (`+`) or lags (`-`) the audio |
| `highlight_granularity` | `"word"` | Highlight by `word`, whole `sentence` (less flicker), or `both` (sentence band + word) |
| `highlight_speed` | `1.0` | Highlight timer speed as a fraction of `tts_rate`; `1.0` = match speech exactly. The pacing guard caps how far the timer can lead confirmed audio, so values above `1.0` do not cause runaway drift. |
| `recent_files` | `[]` | Recently opened files (populated automatically) |
| `recent_files_limit` | `20` | Maximum entries in the recent files list |
| `gui_width` | `1000` | Qt window width in pixels |
| `gui_height` | `700` | Qt window height in pixels |
| `qt_font_family` | platform sans-serif | Qt display font family (`Helvetica Neue` / `Segoe UI` / `DejaVu Sans`); serif faces are discouraged for accessibility |
| `qt_font_size` | `14` | Qt display font size in pt |
| `qt_hidpi` | `true` | Enable high-DPI scaling in the Qt GUI |
| `qt_ctrl_pause` | `true` | Tap the `Ctrl` key alone to play/pause speech (JAWS habit); chords like `Ctrl+O` never trigger it |
| `qt_edit_preview` | `false` | Show a live-rendered HTML preview beside the editor in edit mode (toggle with `Ctrl+Shift+L`) |
| `reading_stats` | `{}` | Per-document reading time, progress, and session counts (populated automatically) |
| `library` | `{}` | Library/bookshelf metadata for every opened document (populated automatically) |
| `profiles` | `{}` | Named setting bundles (voice, rate, theme, font, spacing, highlight) saved via the Profiles menu |
| `pronunciations` | `{}` | Pronunciation lexicon: `{term: spoken form}` applied before other TTS normalization |
| `use_pronunciations` | `true` | Apply the pronunciation lexicon while reading |
| `qt_show_toc` | `true` | Show the Contents panel at startup |
| `qt_show_notes` | `false` | Show the Notes/annotations panel at startup (hidden by default; toggle with `Ctrl+Shift+N`) |
| `qt_line_height` | `1.5` | Qt line-height multiplier (WCAG 1.4.12). Adjust via **View → Reading Aids → Text Spacing…** |
| `qt_letter_spacing` | `0.0` | Qt extra letter spacing, percent of font size (`0` = normal) |
| `qt_word_spacing` | `0.0` | Qt extra word spacing in pixels (`0` = normal) |
| `qt_dyslexia_font` | `false` | Prefer an installed dyslexia-friendly font (OpenDyslexic / Atkinson Hyperlegible / Lexend / Comic Sans) when available |
| `qt_current_line_highlight` | `false` | Tint the line being read with a focus band |
| `qt_bionic_reading` | `false` | Embolden the leading part of each word (bionic reading) |
| `qt_vocab_highlight` | `false` | Highlight uncommon / academic vocabulary (difficult-word overlay; needs `wordfreq`) |
| `annotations` | `{}` | Per-document notes: `{path: [{char_pos, word_idx, anchor, note, tags, cite, ts}]}` |
| `citations` | `[]` | Shared citation library (BibTeX/RIS/CSL-JSON import/export) |
| `whisper_model` | `"base"` | Whisper model size for transcription/dictation (`tiny`…`large`) |
| `user_highlights` | `{}` | Persistent text highlights per document path |
| `document_cache` | `true` | Cache parsed documents for instant reopening |
| `cache_max_size_mb` | `100` | Maximum cache directory size in MB |
| `footnote_mode` | `"inline"` | Footnote handling: `inline`, `deferred`, `skip` |
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

---

See also: [Usage Guide](usage_guide.md) · [Features](features.md) ·
[Installation](installation.md) · [Architecture](architecture.md).
