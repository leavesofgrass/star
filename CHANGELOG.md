# 📜 Changelog

All notable changes to **star — Speaking Terminal Access Reader** are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

---

## [0.1.2] — 2026-06-14

A substantial revision focused on **reliable, accessible defaults out of the
box**: native speech on every platform, dependency-free Braille export, smoother
word-highlight tracking, a more professional default look, and a new set of
reading-accessibility aids. The single-file architecture is unchanged —
`star.py` still runs with zero extras installed.

### ✨ Added

- **Reading accessibility aids (Qt GUI).** A new **View → Reading Aids** submenu
  collects low-friction, high-impact accommodations:
  - **Adjustable text spacing** (WCAG 1.4.12) — independently tune line height,
    letter spacing, and word spacing from a live-preview dialog. New settings:
    `qt_line_height` (default `1.5`), `qt_letter_spacing`, `qt_word_spacing`.
  - **Dyslexia-friendly font preference** — opt in to an installed
    OpenDyslexic / Atkinson Hyperlegible / Lexend / Comic Sans face, with a
    graceful fallback and prompt when none is installed. New setting:
    `qt_dyslexia_font`.
  - **Bionic reading** — embolden the leading part of each word to pull the
    eye forward. New setting: `qt_bionic_reading`.
  - **Current-line focus band** — tint the line being read. New setting:
    `qt_current_line_highlight`.
  - **Karaoke highlight tuning** — choose the spoken-word highlight style
    (`background`, `underline`, `box`, `bold`, `color`), color, pacing
    (`highlight_speed`), and a lead/lag offset. New settings: `highlight_style`,
    `highlight_lead_words`.
- **Notes dock stays hidden by default.** The Qt **Notes** panel is hidden on
  launch (`qt_show_notes` defaults to `false`) to maximize the reading area; it
  opens on demand via **Ctrl+Shift+N**, **View → Toggle Notes Panel**, or when a
  note is added.
- **Annotations / notes — now in both interfaces, with tags & search.** The Qt
  **Notes** dock and a new curses TUI notes pager share one per-document store.
  Add at the cursor/selection (`Ctrl+Shift+A` in Qt, `a` in the TUI), attach
  **tags**, and **filter with full-text or `#tag` search** (filter box in Qt;
  `M-x annotations-search` / `annotations-list` in the TUI). Notes carry both a
  Qt char offset and a `word_idx`, so a note made in one interface navigates
  correctly in the other. Export to Markdown, JSON, BibTeX, or RIS. New TUI
  commands: `annotate`, `annotations-list`, `annotations-search`,
  `annotation-goto`, `annotation-delete`, `annotations-export`.
- **Citation manager (Qt GUI).** A shared citation library with **import and
  export of BibTeX, RIS, and CSL-JSON** (`Citations` menu). Add references by
  hand, browse/copy/delete them, and **link a citation to a note** so exported
  study notes carry attribution. New setting: `citations`.
- **Whisper voice dictation & transcription (optional).** `Tools → Transcribe
  Audio File…` opens a transcription as a new document; `Tools → Dictate Note…`
  records from the microphone and saves the transcription as a note. Backed by
  `openai-whisper` or `faster-whisper` (+ `sounddevice`/`numpy` for the mic);
  fully guarded when absent. New setting: `whisper_model`.
- **Keyboard cheat sheet & GUI/TUI parity.** A canonical shortcut scheme is now
  documented in one place and shown in-app (`Help → Keyboard Shortcuts` in Qt,
  `?` / `M-x shortcuts` in the TUI).
- **Full menu coverage (Qt GUI).** New **Speech**, **Navigate**, **Edit**,
  **Citations**, **Tools**, and **Help** menus put every command within reach
  of the mouse — important for users who don't drive the app by keyboard.
- **macOS native speech backend (`applesay`).** A new TTS backend drives the
  built-in `/usr/bin/say` command, giving Mac users Apple's high-quality system
  voices with **no extra dependencies** (no `pyobjc`, no Homebrew, no eSpeak).
  In `auto` mode it is ranked **above eSpeak** so a Mac never silently falls
  back to the robotic eSpeak voice.
- **Preferred default voice resolution.** When no voice is explicitly set,
  star now auto-selects a voice matching the new `tts_prefer_voice` setting
  (default `"eloquence"`), favoring a US-English variant. This makes the
  **Eloquence (US English)** voices bundled with recent macOS the default when
  present. A user's explicit voice choice is never overridden.
- **Built-in, dependency-free Braille (Grade 1) translator.** BRF export now
  works out of the box with a pure-Python North-American Braille-ASCII (NABCC)
  translator — letters, capital signs, number signs, common punctuation, and
  standard 40-cell / 25-line page geometry with form feeds.
- **Settings migration.** Settings files written by earlier versions are
  upgraded on load: the deprecated serif `Georgia` font and the lagging `0.85`
  highlight speed are replaced with the new defaults (only when they exactly
  match the old default, so deliberate choices are preserved).
- New settings keys: `tts_prefer_voice`, `braille_grade2`,
  `audio_export_format`.
- **Cross-platform installers**: `install.sh` (Linux/macOS) and `install.ps1`
  (Windows) with `minimal` / `recommended` / `all` profiles, virtual-env by
  default, and platform-aware dependency hints (incl. `pyobjc` on macOS,
  `windows-curses` on Windows).

### 🔧 Changed

- **Word-highlight tracking is smooth and continuous.** The highlight timer no
  longer freezes mid-document when SAPI5 word callbacks arrive late or stop
  firing. The pacing guard now allows the highlight to run up to **4 words**
  ahead of the last confirmed audio position and is **bypassed after 1.5 s**
  of callback silence, so the cursor keeps following speech instead of getting
  stuck. (Builds on the timer-generation race fixes already in place.)
- **Word-position map is monotonic and column-aware.** Repeated common words
  (`the`, `a`, `and`) on a single line are matched in document order instead of
  always snapping back to the first occurrence, and the search position never
  moves backward — eliminating the "highlight stuck several lines back" effect.
- **Audio export now defaults to WAV** (`audio_export_format`). WAV needs no
  external tools; MP3/OGG/MP4 still work when `ffmpeg` or `pydub` is present.
- **Default display font is now sans-serif** (`Helvetica Neue` on macOS,
  `Segoe UI` on Windows, `DejaVu Sans` on Linux). Serif faces are discouraged
  for on-screen reading accessibility.
- **Polished default dark theme** with a modern, professional neutral-dark
  palette (Zed/Ghostty-inspired) for the Qt GUI editor, HTML rendering, and the
  seeded `dark.css` theme.
- **`highlight_speed` default is now `1.0`** (match speech rate exactly); the
  pacing guard is the real throttle, so the highlight stays tight to the audio.
- BRF export gained a `braille_grade2` opt-in for contracted Grade 2 via
  liblouis (when installed and the table resolves).

### 🐛 Fixed

- **Qt GUI now runs on PyQt6.** `QAction` was imported from `QtWidgets`, but
  PyQt6 moved it to `QtGui`; the bad import made the whole PyQt6 branch fail, so
  star silently fell back to PyQt5 (and could not start the GUI at all on a
  PyQt6-only machine). `QAction` is now imported from `QtGui` under PyQt6, and a
  couple of PyQt6 enum-to-int conversions (`line height`, full-width selection)
  were hardened. This also makes the frozen Windows binary work.
- **BRF export no longer crashes the app.** Previously, exporting Braille with
  `louis` installed but a translation table missing could make liblouis call
  `exit()` at the C level, abruptly closing the window. liblouis is now opt-in
  and fully guarded; the built-in Grade 1 translator is the reliable default and
  can never terminate the process.
- **macOS no longer defaults to eSpeak.** With the new `applesay` backend ranked
  above eSpeak, Macs speak with a native Apple voice by default.
- Highlighting that previously got "stuck" and stopped advancing down the page
  while speech continued now tracks reading position reliably.

### 📝 Notes for upgrading users

- Existing `settings.json` files are migrated automatically (see above). To
  adopt the new dark palette, delete `themes/dark.css` in your config directory
  (a fresh, updated copy is regenerated) or pick it from **View → Theme**.
- macOS users who want pyttsx3's word-boundary callbacks (rather than the
  timer-based highlight used by `say`) can `pip install pyobjc pyttsx3`.

---

## [0.1.1] — earlier

Initial public lineage of star prior to the 0.1.2 revision: single-file Qt GUI
and curses TUI, multi-format document loading (PDF, EPUB, DAISY/DTBook, DOCX,
PPTX, ODT, HTML, Markdown, LaTeX, RST and many markup formats, CSV/XLSX, images
via OCR, notebooks, source code), multiple TTS backends, themes, search,
bookmarks, reading-position memory, speed presets, Speech Cursor mode,
table-of-contents navigation, user highlights, audio export, document caching,
and screen-reader compatibility.

[0.1.2]: #012--2026-06-14
[0.1.1]: #011--earlier
