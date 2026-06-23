# 📜 Changelog

All notable changes to **star — Speaking Terminal Access Reader** are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

---

## [0.1.7] 2026-06-23

### ✨ Added

- **Document translation.** A new **Tools ▸ Translate Document…**
  (`Ctrl+Shift+X`) translates the open document into any of 15 common languages
  via Google Translate (no API key, no account). A picker dialog chooses the
  target language and shows the result in a read-only pane; the network call
  runs on a background thread so the window stays responsive, and the input is
  capped at 15 000 characters per request to stay within rate limits. Requires
  the optional `deep-translator` package; the menu item prompts to install it
  when absent.
- **RSS / Atom feed reading.** **File ▸ Open Feed…** (`Ctrl+Shift+M`) fetches a
  feed URL, lists its articles, and opens the chosen one in the reader through
  star's normal URL-loading path. Useful for tracking arXiv, PubMed, bioRxiv,
  or journal feeds without leaving star. Requires the optional `feedparser`
  package; the menu item prompts to install it when absent.
- **Difficult-word overlay.** **View ▸ Reading Aids ▸ Highlight Difficult
  Words** (`Ctrl+Alt+O`) tints uncommon / academic vocabulary by word
  frequency, giving a visual pre-scan of dense terminology before reading. The
  overlay is non-destructive (it rides the existing extra-selection pipeline,
  sitting under user highlights and the TTS word highlight), persists across
  sessions (`qt_vocab_highlight`), and recomputes on each document load.
  Requires the optional `wordfreq` package.
- **Dependency status report.** A new `star --deps` flag prints the
  availability of every optional dependency, grouped by area, with a one-line
  description and a copy-paste install hint for anything missing — backed by a
  new `star.diagnostics` module that is the single source of truth for star's
  optional dependencies.
- **New optional-dependency groups.** `translate` (`deep-translator`), `feeds`
  (`feedparser`), and `vocab` (`wordfreq`), all folded into the `all` extra and
  mirrored in `requirements-optional.txt`.

### 🧪 Tests

- **General dependency harness.** `tests/test_dependencies.py` verifies the new
  diagnostics registry against the codebase: a completeness check fails if any
  import guard is ever added without being registered, and a per-dependency
  consistency check asserts that anything reported as available really does
  import. `tests/test_features.py` covers the translation, feed, and
  difficult-word logic, including their graceful-degradation paths.

### 📝 Notes

- The three new commands use `Ctrl+Shift+X`, `Ctrl+Shift+M`, and `Ctrl+Alt+O`
  — the more intuitive `Ctrl+Shift+L/F` and `Ctrl+Alt+W` were already bound
  (live preview, themes folder, text spacing). All three are also reachable
  from the F2 command palette, which now additionally lists Summarize, Anki
  export, and Check Spelling for completeness.

---

## [0.1.6] 2026-06-23

### ✨ Added

- **Document summarization.** A new **Tools ▸ Summarize Document**
  (`Ctrl+Shift+U`) condenses the open document to its key sentences using the
  LexRank algorithm (via the optional `sumy` package) and shows the result in a
  read-only dialog. The number of sentences is configurable through the
  `summary_sentences` setting (default 7). Summarization runs on a background
  thread so the window stays responsive on long documents. Requires
  `pip install sumy`; the menu item prompts to install it when absent. The
  NLTK sentence-tokenizer data it needs is fetched automatically on first use.
- **Anki flashcard export.** **File ▸ Export ▸ Anki Flashcards…**
  (`Ctrl+Alt+H`) turns the current document's notes into an Anki deck
  (`.apkg`): each note becomes one card with the highlighted passage on the
  front and your note on the back. Requires the optional `genanki` package;
  the menu item prompts to install it when absent, and prompts you to add a
  note first if the document has none.
- **Spell checking in edit mode.** While editing a document's Markdown source,
  misspelled words are underlined with a red squiggle, rechecked as you type.
  **Edit ▸ Check Spelling** (`F7`) counts the misspellings and lists them in a
  dialog, in or out of edit mode. Both use the optional `pyspellchecker`
  package and degrade gracefully — edit mode stays fully usable, and the menu
  item prompts to install it — when it is absent.
- **New optional-dependency groups.** `summarize` (`sumy`), `flashcards`
  (`genanki`), and `spellcheck` (`pyspellchecker`), all folded into the `all`
  extra, plus a comment-annotated `requirements-optional.txt` mirroring the
  optional packages for `pip install -r` users.

### 🐛 Fixed

- **Reading highlight no longer runs ahead of eSpeak-NG speech.** In its
  in-process (libespeak-ng) mode, eSpeak synthesizes a whole sentence's audio
  in a burst and reports all of that sentence's word events at once — well
  before the words are actually heard — which made the highlight race up to a
  sentence ahead of the audio. star now paces each word event to the word's
  real audio position (which the engine reports per event) and only advances
  the highlight when that moment arrives, so the highlight follows playback
  instead of synthesis. The highlight timer also tracks these playback-accurate
  events tightly (within a single word) for this backend. A new
  `espeak_highlight_offset_ms` setting (default 120) compensates for audio
  output latency — raise it if highlights still lead the audio, lower it toward
  0 if they lag.

### 📝 Notes

- Summarize Document uses `Ctrl+Shift+U` rather than `Ctrl+Shift+S`, which was
  already bound to Reading Statistics. Every new command has both a menu entry
  and a keyboard shortcut, keeping star fully keyboard-drivable.

---

## [0.1.5] 2026-06-22

### ✨ Added

- **In-process eSpeak-NG via libespeak-ng (ctypes).** A new backend drives
  eSpeak-NG through its C library instead of the `espeak-ng` command line. The
  library reports a per-word event for every spoken word, tagged with the
  word's audio position (milliseconds into the output stream), which `star`
  forwards to the reading highlight. It is preferred automatically when the
  shared library is available — the bundled `libespeak-ng.dll` in the
  self-contained Windows build, or a system `libespeak-ng` on Linux/macOS — and
  falls back to the `espeak-ng` command-line backend otherwise. Speech is
  synthesized in short sentence-sized chunks, so pausing, stopping, or switching
  away silences playback promptly instead of running on in the background.
- **Bundled libespeak-ng in the self-contained Windows build.**
  `tools/build-vendor.py` now fetches eSpeak-NG (1.52.0) and vendors its 64-bit
  `libespeak-ng.dll` plus the `espeak-ng-data` tree, so `star.exe` speaks with
  eSpeak — and the playback-synced highlight — with no separate install.
- **Batch conversion.** Convert many documents — selected files or a whole
  folder — to one output format (Markdown, plain text, or Braille/BRF) in a
  single step, via **File ▸ Batch Convert** (`Ctrl+Shift+C`) in the Qt GUI or
  `M-x batch-convert` in the terminal UI. Each file runs through the existing
  single-file load→export pipeline; a corrupt, password-protected, or
  unsupported file is recorded and skipped instead of aborting the run. Outputs
  reuse the source basename (collisions disambiguated, never overwritten), and a
  timestamped summary — what succeeded, what failed and why, and where outputs
  went — is written alongside the outputs.
- **Hot-folder watching.** Watch a folder and convert files dropped into it,
  unattended: `star --watch <input_dir> --output <output_dir> --format <fmt>`
  for headless use, or **File ▸ Watch Folder** (`Ctrl+Shift+W`, a toggle) from
  the Qt GUI. Built on the batch core (same formats and validation). Files are
  debounced (processed only once their size has stabilised, so a file still
  being copied in is never read half-written); every attempt is logged with a
  timestamp to `<output>/star-watch.log`; successful sources move to
  `<input>/processed/` and failures to `<input>/failed/` (collisions
  disambiguated, never overwritten); and Ctrl+C / SIGTERM shut it down cleanly
  without interrupting a file mid-conversion. Uses `watchdog` when installed
  (the new `[watch]` optional-dependency group) and falls back to directory
  polling otherwise.
- **Every Qt menu item now has a keyboard shortcut**, keeping star fully
  keyboard-drivable.

### 🔧 Changed

- **The Qt GUI is now star's primary interface.** Ongoing development is focused
  on the Qt GUI, so it is the default and the recommended way to run star. The
  curses terminal UI (`--tui`) remains fully supported and keyboard-driven as a
  secondary interface for headless or text-only environments.

### 🐛 Fixed

- **Reading highlight no longer runs ahead of the audio.** The highlight is
  now anchored to the engine's actual word progress rather than a free-running
  words-per-minute estimate:
  - With eSpeak-NG driven through libespeak-ng, the highlight follows each
    word's reported audio position, so it tracks playback across the whole
    document instead of drifting further ahead over time.
  - For backends that report real word events (pyttsx3 and libespeak-ng), the
    highlight now waits for the first event before starting, so it begins when
    audio actually begins rather than when synthesis was requested — removing a
    constant head start.
  - Note: the previous attempt to read `<mark>` events from the `espeak-ng`
    command line could never work (the CLI does not emit them), so the
    command-line backend remains timer-paced; use libespeak-ng for synced
    highlighting.

---

## [0.1.4] — 2026-06-22

### ✨ Added

- **Fat zipapp build (`star.pyz`).** A new `build_zipapp.py` produces a
  single-file `star.pyz` that bundles star together with its Python
  dependencies (the `[all]` extras group). It is self-extracting: on first run
  it unpacks its bundled packages into the per-user config directory (so
  compiled packages such as PyQt6 and PyMuPDF load from real files on disk),
  then starts normally. This removes the `pip install` step — running star this
  way needs only a Python interpreter plus the external engines (ffmpeg,
  Tesseract, liblouis, eSpeak-NG, DECtalk) on `PATH`. Because it carries
  compiled packages, the artifact is **platform-specific** (build one per target
  platform). It is additive and does not replace the self-contained Windows
  `star.exe`, which additionally bundles the external engines.

### 🔧 Changed

- **Minimum supported Python is now 3.11** (previously 3.8). The
  `requires-python` constraint, the installer and build scripts, and the build
  documentation were updated to match.

---

## [0.1.3] — 2026-06-16

A focused round of reading, speech, and study-workflow additions, all built on
the existing single-file architecture — `star.py` still runs with zero extras
installed.

### ✨ Added

- **Sentence-level highlight option.** A new **highlight granularity**
  control lets the spoken text be highlighted by **word** (default), by whole
  **sentence** (much less visual flicker for readers who find rapid word-by-word
  movement distracting), or **both** (a soft sentence band with the current word
  marked on top). Works in **both** the Qt GUI and the curses TUI. Set it from
  **View → Reading Aids → Karaoke Highlight…** (new *Granularity* selector) or
  `M-x highlight-granularity word|sentence|both` in the TUI. New setting:
  `highlight_granularity` (default `word`).
- **Timestamped subtitle export — SRT / VTT.** Audio export can now emit a
  synchronized caption track so the highlight "travels" with the audio into any
  media player. Export captions on their own (**File → Export → Export Subtitles
  (SRT / VTT)…**, or `M-x export-subtitles`), or have them written automatically
  alongside every audio export (`M-x subtitles-with-audio`). Captions are grouped
  into readable sentence-length cues by default, or one cue per word with
  `M-x subtitle-word-level`. Timing is estimated from the synthesized audio's
  duration, so it needs no external tools. New settings: `subtitle_format`
  (`srt`/`vtt`), `subtitle_word_level`, `export_subtitles_with_audio`. New TUI
  commands: `export-subtitles`, `subtitle-format`, `subtitle-word-level`,
  `subtitles-with-audio`.
- **A keyboard shortcut for every GUI menu item.** Every command in the Qt
  menus now has a shortcut shown beside it and listed in **Help → Keyboard
  Shortcuts** (`F3`). Bindings follow a consistent scheme — `Ctrl+letter`
  (forward/primary), `Ctrl+Shift+letter` (backward/secondary), `Alt+punct`
  (sentences), `Ctrl+Alt+letter` (exports, citations, tools, reading aids) —
  and each is owned by exactly one action, eliminating the previous duplicate
  toolbar/window bindings that risked Qt “ambiguous shortcut” conflicts. New:
  highlight colors (`Ctrl+Shift+1`…`5`), export commands (`Ctrl+Alt+M/P/B/A/U`),
  citation commands (`Ctrl+Alt+I/E/C/D/R/G`), reading aids, and more. All
  bindings remain remappable via **Help → Customize Shortcuts…**.
- **Tap `Ctrl` to play/pause (JAWS habit).** Pressing and releasing the `Ctrl`
  key on its own toggles speech, mirroring the JAWS “Ctrl silences speech”
  reflex. Using Ctrl as a modifier in a chord never triggers it. New setting:
  `qt_ctrl_pause` (default `true`).
- **Reading statistics & progress tracking.** STAR now records time read,
  furthest word reached, progress %, and session count per document while
  speech plays, and surfaces them in a dashboard — **Tools → Reading
  Statistics…** (`Ctrl+Shift+S`) in the Qt GUI and `M-x reading-stats` in the
  TUI — with overall totals and a most-read list. New setting: `reading_stats`.
- **Library / bookshelf view.** Every opened document is remembered with
  its title, format, progress, and last-opened time. **File → Library /
  Bookshelf…** (`Ctrl+Shift+B`) opens a searchable list (Enter / double-click
  reopens a document); the TUI offers `M-x library`. New setting: `library`.
- **Live HTML preview while editing.** In edit mode a split pane can show a
  live-rendered HTML preview of the Markdown source beside the editor,
  re-rendering as you type (debounced). Toggle it with **View → Live HTML
  Preview** (`Ctrl+Shift+L`); turning it on outside edit mode enters edit mode.
  New setting: `qt_edit_preview`.
- **Voice & profile presets.** Save the current voice, rate, volume, theme,
  font, spacing, and highlight settings as a named profile (e.g. “Skim”, “Deep
  Study”, “Low-Light”) and switch between them in one step. A new **Profiles**
  menu offers **Save Current Settings as Profile…** (`Ctrl+Shift+K`), **Load
  Profile…** (`Ctrl+Shift+J`), and **Delete Profile…** (`Ctrl+Shift+Y`); the TUI
  adds `M-x profile-save`, `profile-load`, `profile-list`, and `profile-delete`.
  New setting: `profiles`.
- **Pronunciation lexicon editor.** A user-editable dictionary maps domain
  terms — drug names, anatomy, acronyms — to a spoken form so TTS says them
  correctly and consistently across every backend. Edit it from **Speech →
  Pronunciation Lexicon…** (`Ctrl+Shift+I`) in the Qt GUI, or `M-x pron-add`,
  `pron-list`, `pron-remove`, and `pronunciations` (on/off) in the TUI.
  Pronunciation overrides are applied first, before abbreviation and number
  normalization. New settings: `pronunciations`, `use_pronunciations`.
- **Piper neural TTS backend.** A new optional **`piper`** backend brings
  free, offline, neural-quality voices via the standalone
  [Piper](https://github.com/rhasspy/piper) binary — no Python package, no
  subscription, no network. Point STAR at a `.onnx` voice model with the new
  `piper_model` setting (or the `PIPER_MODEL` env var, or by dropping models in
  a Piper voice directory) and select it from **Speech → Choose TTS Engine…**
  (new GUI engine picker) or `M-x tts-backend piper`. Like Coqui, it is opt-in
  and never chosen in `auto` mode. New setting: `piper_model`.
- **Fully self-contained Windows binary.** The portable `star.exe` can now
  bundle the native engines that previously had to be installed separately, so
  a single file does *everything* on a clean PC:
  - **ffmpeg** → MP3 / OGG / MP4 audio export
  - **Tesseract** + English language data → OCR of images and scanned PDFs
  - **liblouis** + translation tables → Grade 2 (contracted) Braille
  - **Pandoc** → high-fidelity markup conversion (RST, Org, MediaWiki,
    AsciiDoc, Textile, LaTeX, legacy `.doc`, …)
  - **DECtalk** → the classic “Perfect Paul” voice, via the bundled
    `DECtalk.dll` + dictionary driven **in-process through ctypes** (no
    separate CLI required); the architecture-matched 64-/32-bit engine is
    selected automatically. On the self-contained Windows build DECtalk is now
    the **default engine** and **Perfect Paul the default voice**, and all
    nine classic speakers — Perfect Paul, Beautiful Betty, Huge Harry, Frail
    Frank, Doctor Dennis, Kit the Kid, Uppity Ursula, Rough Rita, Whispering
    Wendy — appear in the voice picker (**Speech → Choose Voice…**,
    `Ctrl+Shift+V`). DECtalk is only chosen automatically when the engine
    actually starts (a real startup is probed once), so machines without a
    working DECtalk fall back to pyttsx3/SAPI as before

  `star.py` locates each bundled engine via a new `_vendor_dir()` resolver
  (`sys._MEIPASS` when frozen) and falls back to a system install when a tool
  is absent, so running from source still needs nothing extra. For Pandoc the
  bundled binary is also exposed to `pypandoc` via `$PYPANDOC_PANDOC`; for
  DECtalk a `say`/`dtalk` CLI (on `PATH` or via `DECTALK_BIN`) still works as a
  fallback. A new `build-vendor.py` helper downloads and assembles the engines
  into `vendor/`, which `star.spec` packs into the bundle (see `BUILD.md`). The
  fully self-contained build is ~300+ MB (Pandoc alone adds ~150 MB); a lean
  build without `vendor/` remains ~90–100 MB.

### 🏗️ Packaging & architecture

- **`star.py` can now be split into an importable `star/` package.** A new
  [`tools/split_star.py`](tools/split_star.py) refactors the monolithic
  `star.py` into logical submodules (`tts`, `tui`, `gui`, `documents`,
  `markup`, `render`, `braille`, `citations`, …) under a `star/` package,
  with shared foundational state (stdlib imports, vendored-tool wiring,
  optional-dependency flags, paths, metadata) in `star/_runtime.py` and
  re-exported via `from ._runtime import *`. The tool moves exact source by
  top-level AST node — **nothing is re-typed** — and computes the
  cross-module imports automatically, so the package stays byte-for-byte
  faithful to `star.py`. `star.py` remains the canonical single-file source
  and still runs with zero extras; the generated `star/` package is what the
  wheel ships and what `python -m star` / the `star` console command import.
- **Pure-Python wheel for macOS / Linux / Windows.** A new
  [`pyproject.toml`](pyproject.toml) builds a single `py3-none-any` wheel
  (`star_reader-<version>-py3-none-any.whl`) that installs `star` and its
  `star` command into any environment. Recommended dependencies (Qt GUI, TTS,
  common document loaders) install by default; the optional features are
  available as extras — `[ocr]`, `[formats]`, `[markup]`, `[braille]`,
  `[audio]`, `[transcribe]`, and `[all]`. Build it with `python -m build
  --wheel` (see `BUILD.md`).
- **macOS / Linux native-engine bootstrap.** A new
  [`tools/install_native.py`](tools/install_native.py) is the cross-platform
  counterpart of `build-vendor.py`: it installs the native engines (ffmpeg,
  Tesseract + English data, liblouis, Pandoc, and eSpeak-NG on Linux) through
  the system package manager (Homebrew / apt / dnf / pacman / zypper),
  installing only what is missing. Supports `--dry-run` and per-engine
  selection.
- **Voice dictation & transcription now bundled in the Windows binary.** The
  self-contained `star.exe` ships the full Whisper stack — `openai-whisper`
  with its PyTorch backend, `sounddevice` for microphone capture, and the
  Whisper **`base` model** — so **Tools → Dictate Note** and **Transcribe
  Audio File** work **offline, with no install and no first-run download** on a
  clean machine. A PyInstaller runtime hook
  ([`tools/rthook_star.py`](tools/rthook_star.py)) puts the bundled ffmpeg on
  `PATH` (Whisper decodes audio through it) and points Whisper's model cache at
  the bundled `base` model; `tools/build-windows.ps1` installs the dictation
  dependencies and stages the model automatically. PyTorch makes this the
  largest single addition to the bundle (the binary grows to ~600+ MB); the
  dependencies are guarded, so a build without them still succeeds and the
  feature falls back to its “requires Whisper” hint. The frozen entry point is
  now [`run_star.py`](run_star.py), which imports `star.app.main` from the
  generated package.

### 📝 Notes for upgrading users

- All new settings have safe defaults, so existing `settings.json` files keep
  working unchanged; the new keys are added on next save.
- Subtitle timing is *estimated* (proportional to spoken-token length) because
  file-based TTS synthesis exposes no per-word callbacks. It is accurate enough
  for review and study recordings.

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
- **Portable Windows binary build.** A PyInstaller recipe (`star.spec`) and a
  one-command wrapper (`build-windows.ps1`) produce a single, self-contained
  `dist\star.exe` that runs on Windows machines with no Python or dependencies
  installed — ideal for demos. Bundles the Qt GUI, SAPI5 speech, and the core
  document loaders. Documented in `BUILD.md`.
- New documentation: `CHANGELOG.md` and `BUILD.md` (portable Windows binary).

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

[0.1.3]: #013--2026-06-16
[0.1.2]: #012--2026-06-14
[0.1.1]: #011--earlier
