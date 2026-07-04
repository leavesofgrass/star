# ✨ Features

The complete feature reference for `star`. For how to invoke each feature, see
the [Usage Guide](usage_guide.md); for the settings that tune them, see
[Configuration](configuration.md).

- [Feature overview](#feature-overview)
- [Supported file formats](#supported-file-formats)
- [TTS backends](#tts-backends)
- [Voice Manager](#voice-manager)
- [Word highlighting](#word-highlighting)
- [Find in document](#find-in-document)
- [Full-text library search](#full-text-library-search)
- [Subtitle export (SRT / VTT)](#subtitle-export-srt--vtt)
- [Reading statistics & progress](#reading-statistics--progress)
- [Library / Bookshelf](#library--bookshelf)
- [Live HTML preview](#live-html-preview-edit-mode)
- [Voice & profile presets](#voice--profile-presets)
- [Pronunciation lexicon](#pronunciation-lexicon)
- [User highlights](#user-highlights)
- [Annotations / notes](#annotations--notes)
- [Study & spaced repetition](#study--spaced-repetition)
- [Citation manager](#citation-manager-qt-gui)
- [Knowledge graph](#knowledge-graph)
- [Voice dictation & transcription](#voice-dictation--transcription-optional)
- [Table of contents & EPUB / DAISY navigation](#table-of-contents--epub--daisy-navigation)
- [Document caching](#document-caching)
- [Large-document pagination](#large-document-pagination)
- [Document fidelity](#document-fidelity)
- [Footnote handling](#footnote-handling)
- [OCR support](#ocr-support)
- [Math normalization](#math-normalization)
- [Braille support](#braille-support)
- [Archive ingestion](#archive-ingestion)
- [Metadata editor & library search](#metadata-editor--library-search)
- [Karaoke video export](#karaoke-video-export)
- [RSVP reading mode](#rsvp-reading-mode)
- [Audio export](#audio-export)
- [Speed presets, bookmarks & history](#speed-presets-bookmarks--history)
- [Document editing](#document-editing-qt-gui)
- [Study & writing aids](#study--writing-aids)
- [Optional features & one-click install](#optional-features--one-click-install)
- [Accessibility](#accessibility)
- [Screen reader compatibility](#screen-reader-compatibility)
- [Color themes & CSS customization](#color-themes--css-customization)
- [Interface language (i18n)](#interface-language-i18n)
- [Plugins](#plugins)
- [Batch conversion & hot-folder watching](#batch-conversion--hot-folder-watching)

---

## Feature overview

| Feature | Detail |
|---|---|
| Qt GUI (primary) | Windowed application with menu bar, toolbar, dock panels, and a keyboard shortcut for every command; launches by default when PyQt6/PyQt5 is installed |
| Terminal TUI (secondary) | Full-featured, fully keyboard-driven curses interface for headless / text-only use; force it with `--tui` |
| Built-in TTS | pyttsx3 (SAPI5 / NSSpeechSynthesizer / eSpeak-NG), macOS `say` (native, default on Mac), eSpeak-NG (in-process libespeak-ng, or CLI), DECtalk, Festival, Piper (neural, offline, free), Coqui, ElevenLabs (opt-in cloud neural) |
| Voice Manager | Browse, filter, preview, and favorite voices across every engine (`F4`); one-click download of offline Piper neural voices |
| eSpeak-NG playback sync | Driven in-process via libespeak-ng (ctypes); per-word events carry their audio position, so the highlight follows the actual audio, not a timer estimate |
| Default reading rate | **265 wpm** — intentionally brisk; adjustable at runtime |
| TTS word highlighting | Spoken word highlighted live; works in both Qt and terminal modes |
| Highlight granularity | Highlight by **word** (default), whole **sentence** (less flicker), or **both** |
| Find in document | Incremental `Ctrl+F` find bar: live match count, case toggle, wrap-around, and highlight-all |
| Full-text library search | Search *inside* every document in the library, not just titles and metadata |
| Study & spaced repetition | Turn notes/highlights into review cards with an FSRS scheduler; in-app review dashboard; auto-cloze cards; optional AnkiConnect two-way sync |
| User text highlights | Highlight passages in yellow, green, cyan, pink, or orange; persists across sessions and exports to PDF |
| Annotations / notes panel | Tagged notes anywhere in a document; full-text + `#tag` search; persists per-document; exports to Markdown, JSON, BibTeX, or RIS |
| Citation manager | Import/export BibTeX, RIS, and CSL-JSON; link citations to notes |
| Knowledge graph | Link annotations across documents with typed relations; extract concepts; interactive graph view; export to SVG / PlantUML / DOT / JSON |
| Obsidian vaults | Import an Obsidian vault (notes + `[[wikilinks]]` + tags) into the knowledge graph, and export the graph back as linked Markdown notes |
| Voice dictation & transcription | Transcribe audio files and dictate notes by voice via Whisper (optional) |
| Table of Contents panel | Auto-built from document headings in Qt mode; click any entry to jump there |
| EPUB NCX / NAV navigation | Parses EPUB 2 NCX and EPUB 3 NAV documents for chapter-level navigation |
| Async document loading | Documents load in a background thread — the UI never freezes |
| Document caching | Parsed documents cached per platform; reopening a large file is instant |
| Large-document pagination | Opt-in: renders only a window of a very large document at a time (~5× faster first paint on huge docs); off by default (`qt_paginate_large_docs`) |
| Markdown rendering | All documents are converted to clean Markdown for display |
| Math normalization | LaTeX and inline math expressions converted to natural spoken English |
| Inline math display | Inline / display LaTeX rendered to Unicode (`x²`, `√2`, `½`, `α`) in the Qt document view |
| Accessible tables | Rendered tables keep header structure (`scope="col"` / `scope="row"`) for screen readers |
| Clickable footnotes | Footnote markers link to the note and a `↩` backlink jumps back |
| Footnote handling | Markdown / Pandoc footnotes can be read inline, deferred, or skipped |
| PDF reading order | Multi-column PDFs read column-by-column, top-to-bottom; running headers/footers and page numbers suppressed (toggle: `pdf_reading_order`) |
| Speed presets | Named presets (skim/normal/study/slow) switchable at runtime |
| Bookmarks / history | Named per-document bookmarks (`Ctrl+B`) and back/forward navigation history (`Alt+←/→`), in both the Qt GUI and the TUI |
| Document editing | `Ctrl+E` toggles raw-Markdown edit mode; `Ctrl+S` saves back to the original file |
| Archive ingestion | Open ZIP, TAR, .7z, and .rar archives; browse members; load any member by format; archive refs persisted in library and annotations |
| Metadata editor | Edit title, author, year, DOI, ISBN, publisher per document; one-click DOI / ISBN lookup (CrossRef / OpenLibrary) |
| Library search | AND-combined search over title, author, DOI, ISBN, and annotation full-text |
| Karaoke video export | Sentence-synchronized MP4: TTS audio + rendered page frames with highlight advancing sentence by sentence; soft SRT subtitle track |
| Audiobook export (M4B) | Export a document as a chaptered `.m4b` audiobook — chapters come from its headings — for listening on the go (needs ffmpeg) |
| RSVP reading mode | One-word-at-a-time display at a fixed on-screen point; 9 placement positions for limited-visual-field accessibility; prev/next context words; syncs with TTS |
| Interface language | Localize the menus, toolbar, and docks — **and now the terminal UI** — (English, Spanish, French, German, Portuguese, plus a first Arabic catalog); first-run language picker; switch live from View ▸ Interface Language; TTS prefers a voice matching the interface language |
| Right-to-left interface | Choosing a right-to-left interface language mirrors the whole app and reading view; Arabic is included as a first catalog |
| Export | Markdown, PDF (with highlights), BRF braille, TTS audio, SRT/VTT subtitles, and karaoke MP4 video |
| Reading statistics | Per-document time read, progress %, and session count, with totals and a most-read dashboard |
| Library / bookshelf | Searchable list of every opened document with progress and last-opened time |
| Live HTML preview | Optional split-pane preview that re-renders the Markdown live while you edit |
| Voice & profile presets | Save voice, rate, theme, font, spacing, and highlight settings as named profiles |
| Pronunciation lexicon | User-editable term → spoken-form dictionary |
| Document translation | Translate into 15 common languages (Google backend, no API key); optional via `deep-translator` |
| RSS / journal feeds | Browse a feed and open any article in the reader; optional via `feedparser` |
| Difficult-word overlay | Tints uncommon / academic vocabulary by word frequency; optional via `wordfreq` |
| Define word (offline) | Selected word → definition, senses, synonyms, pronunciation; WordNet via `nltk`, or a custom JSON glossary |
| Screen-reader announcements | Playback, document load, theme change, and find results are spoken to NVDA / JAWS / Orca without moving focus |
| High-contrast AAA theme | WCAG 2.1 AAA (§1.4.6) low-vision theme; theming can also follow the OS light / dark / high-contrast preference |
| Reading Font chooser | Pick OpenDyslexic, Atkinson Hyperlegible, or Lexend from View ▸ Reading Aids ▸ Reading Font; auto-fetched on first use and applied across the whole UI — document, menus, toolbar, and panels |
| Syllable splitting | Show words split into syllables (`read·a·bil·i·ty`) as a decoding aid; display-only, so speech and highlighting are unaffected |
| Reading ruler | A movable, translucent band (typoscope) that follows the caret line to help keep your place; adjustable height, opacity, and band color (or "Use highlight color" to match the highlight) |
| One-click optional features | Missing add-ons are offered for background download — no `pip` required; the feature works in the same session |
| Plugin system | Third parties add TTS engines, document formats, or exporters via entry-point plugins; introspect with `star --plugins` |
| Dependency status report | `star --deps` lists every optional dependency and how to add the rest |
| Built-in themes | dark (default), light, contrast, high-contrast (WCAG AAA), phosphor — all colorblind-friendly; can also follow the OS light / dark / high-contrast preference |
| CSS theme customization | Drop any `.css` file into the themes folder; star picks it up instantly |
| High-DPI display support | Qt GUI scales correctly on 4K and HiDPI screens; toolbar icons render crisply on high-DPI displays |
| Reading level | Flesch-Kincaid grade and ease score on demand |
| `--plain` mode | Extracts clean text to stdout for piping to other tools |
| Batch & hot-folder convert | Convert many files / a folder at once, or auto-convert a watched folder |
| Installable package, graceful degradation | Every third-party dependency is optional and guarded, so the core runs on the standard library alone; when a feature needs an add-on, star offers to fetch it for you (no `pip` instructions) |

---

## Supported file formats

| Format | Extension(s) | Package(s) Required |
|---|---|---|
| ZIP archive | `.zip` | built-in (stdlib) |
| TAR archive | `.tar`, `.tar.gz`, `.tgz`, `.tar.xz`, `.tar.bz2` | built-in (stdlib) |
| 7-Zip archive | `.7z` | `py7zr` (`[archive]` extra) |
| RAR archive | `.rar` | `rarfile` (`[archive]` extra) |
| PDF (text layer) | `.pdf` | `pdfminer.six` |
| PDF (scanned / image) | `.pdf` | `pytesseract`, `pymupdf` |
| Microsoft Word | `.docx` | `python-docx` |
| Microsoft Word (legacy) | `.doc` | `python-docx` or `antiword` |
| PowerPoint | `.pptx` | `python-pptx` |
| OpenDocument Text | `.odt` | `odfpy` (or Pandoc fallback) |
| EPUB 2 / 3 | `.epub` | built-in |
| HTML / XHTML | `.html`, `.htm` | built-in |
| DAISY / DTBook | `.xml`, `.daisy` | built-in |
| DAISY ZIP | `.zip` | built-in |
| Markdown | `.md`, `.markdown` | built-in |
| Plain text | `.txt` | built-in |
| reStructuredText | `.rst`, `.rest` | built-in |
| AsciiDoc | `.adoc`, `.asciidoc`, `.asc` | built-in (or Pandoc) |
| MediaWiki markup | `.wiki`, `.mediawiki` | built-in |
| Textile / Creole | `.textile`, `.creole` | built-in |
| LaTeX | `.tex`, `.ltx` | built-in (Pandoc for complex files) |
| Org-mode | `.org` | built-in |
| R / R Markdown | `.r`, `.rmd` | built-in |
| Jupyter Notebook | `.ipynb` | built-in |
| CSV / TSV | `.csv`, `.tsv` | built-in |
| Excel spreadsheet | `.xlsx` | `openpyxl` |
| Images (OCR) | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp` | `pytesseract` |
| Python source | `.py` | built-in |
| URL (HTTP / HTTPS) | `http://…`, `https://…` | built-in |
| Pandoc import | any of Pandoc's **50+** input formats (RTF, FB2, Typst, …) | `pandoc` binary or `pypandoc` |

**Pandoc as a first-class importer.** When Pandoc is installed, star prefers it
for the formats it handles well — the office and markup formats above (DOCX,
ODT, PPTX, HTML, RST, LaTeX, MediaWiki, Textile, Creole, Org, Jupyter,
CSV/TSV/XLSX) **plus Pandoc-only types** with no native loader: `.rtf`, `.fb2`,
`.docbook`, `.jats`, `.ris`, `.bib`/`.bibtex` (BibTeX/BibLaTeX), `.opml`,
`.t2t`, `.muse`, `.typst`, `.dokuwiki`, `.twiki`, `.tikiwiki`, `.vimwiki`,
`.jira`, `.man`/`.mdoc`, `.pod`, and more. Pandoc reads **50+ input formats**
(51 as of Pandoc 3.9; the exact set is `pandoc --list-input-formats`). star
falls back to its native loader if a Pandoc conversion fails.

Three things are **always read natively**: **EPUB** (so its NCX/NAV chapter
navigation is preserved), the formats Pandoc can't open (PDF, images/OCR, plain
code, DAISY/DTBook, archives, URLs), and Markdown/plain text (no conversion
needed). Controlled by the **`prefer_pandoc`** setting (default `true`); set it
`false` to always use the native loaders.

**PowerPoint:** Slide titles render as headings, body text as paragraphs, and
speaker notes are appended after each slide. **Spreadsheets:** CSV, TSV, and XLSX
files render as Markdown tables; only cell values are spoken. **Code block
skipping:** Fenced code blocks are skipped during TTS by default
(`tts_skip_code`).

---

## TTS backends

In `auto` mode (the default), `star` chooses the first available backend in this
order: **pyttsx3 → macOS `say` → eSpeak-NG → Festival → DECtalk → silent**. On a
Mac this guarantees a native Apple voice even without any Python packages.

Switch engines any time with **Speech → Choose TTS Engine…** (`Ctrl+Shift+G`) or
`M-x tts-backend`.

- **pyttsx3 (preferred when installed)** — wraps the platform's native engine
  (Windows SAPI5, macOS NSSpeechSynthesizer (needs `pyobjc`), Linux eSpeak-NG)
  and provides word-boundary callbacks for the most accurate highlighting.
- **macOS `say` (native, default on Mac)** — drives `/usr/bin/say`, giving
  Apple's high-quality voices with no extra dependencies. When no voice is set,
  star auto-selects a voice matching `tts_prefer_voice` (default `"eloquence"`),
  favoring a US-English variant.
- **eSpeak-NG** — preferentially driven **in process through libespeak-ng** (via
  `ctypes`); each per-word event carries the word's audio position, so the
  highlight follows actual playback. Falls back to the `espeak-ng` CLI
  (timer-paced) when the shared library is absent.
  | Platform | Install |
  |---|---|
  | Linux (Debian/Ubuntu) | `sudo apt install espeak-ng` |
  | macOS | `brew install espeak` |
  | Windows | `winget install eSpeak-NG.eSpeak-NG`, or the [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases) installer (puts `libespeak-ng.dll` + `espeak-ng.exe` on PATH) |

- **Festival** — Linux Festival synthesis; the `festival` binary must be on PATH.
- **Piper (neural, offline, free)** — [Piper](https://github.com/rhasspy/piper)
  gives natural neural-quality speech entirely offline. Install the `piper`
  binary, download a voice model (`.onnx` + `.onnx.json`), and point star at it
  via `piper_model`, the `PIPER_MODEL` env var, or a Piper voice directory. Piper
  is **opt-in** and never chosen in `auto` mode.
- **Coqui TTS** — neural TTS via the Coqui library (`pip install TTS`); high
  quality but needs a GPU-capable machine for real-time synthesis. Opt-in.
- **ElevenLabs (cloud neural, opt-in)** — premium neural voices from the
  ElevenLabs cloud API. It is **strictly opt-in and privacy-preserving**: nothing
  ever leaves your machine unless you paste a key (`elevenlabs_api_key`) **and**
  choose the cloud voice, and on any failure (no key, offline, quota) star
  silently falls back to a local engine. Never chosen in `auto` mode.
- **DECtalk** — the legendary "Perfect Paul" synthesizer; all nine classic
  speakers appear in the voice picker. Set `DECTALK_BIN` to a `dtalk`/`dectalk`
  CLI, or install system DECtalk. Source:
  [github.com/dectalk/dectalk](https://github.com/dectalk/dectalk).
- **Silent (fallback)** — when no TTS engine is available, star falls back to
  silent mode; all display, navigation, search, and export features keep working.

### Switching backends at runtime

```
M-x tts-backend pyttsx3
M-x tts-backend applesay     # macOS native `say`
M-x tts-backend espeak
M-x tts-backend festival
M-x tts-backend piper        # neural, offline, free (needs a .onnx model)
M-x tts-backend coqui
M-x tts-backend elevenlabs   # opt-in cloud neural (needs an API key)
M-x tts-backend dectalk
M-x tts-backend none
```

In the Qt GUI the same engines are reachable from **Speech → Choose TTS Engine…**.

---

## Voice Manager

The classic voice picker lists only the *active* backend's voices. The **Voice
Manager** (Qt GUI: **Speech ▸ Voice Manager…**, `F4`) is a fuller dialog that
gathers **every** voice — from the active engine *and* the downloadable Piper
neural-voice catalog — into one searchable list.

- **Filter** the list live by language or name, or show **Favorites only**.
- **Preview** a voice — it speaks a short sample without committing to it.
- **Set as Current** applies the voice for speech (double-click or Enter also
  sets it, for keyboard parity).
- **Toggle Favorite** pins a voice with a ★; favorites persist in
  `tts_favorite_voices` and survive across sessions.
- **Download** a catalog Piper voice — see below.

Every control carries an accessible name/description, and the list is fully
keyboard-drivable.

### One-click Piper neural voices

Piper gives natural, offline neural speech, but its voice *models* (a `.onnx`
weights file plus its `.onnx.json` config) are large and are **not** bundled.
The Voice Manager ships a curated catalog of **nine** voices spanning star's five
interface languages plus a couple of extra widely-used English voices:

| Voice | Language | Quality |
|---|---|---|
| Lessac | English (US) | medium |
| Amy | English (US) | medium |
| Ryan | English (US) | high |
| Alan | English (GB) | medium |
| Davefx | Español (ES) | medium |
| Claude | Español (MX) | high |
| Siwis | Français (FR) | medium |
| Thorsten | Deutsch (DE) | medium |
| Faber | Português (BR) | medium |

Selecting a not-yet-downloaded catalog voice (marked ⬇ with its size) and
pressing **Download** fetches both files into `CACHE_DIR/piper` — the directory
Piper already scans — and switches star to the Piper backend with the new model
selected. The download is best-effort and **offline-safe**: any network error is
reported ("Could not download … (offline?)") instead of raising. A half-download
(one file present) is treated as *not installed* and removed so a retry starts
clean.

---

## Word highlighting

While TTS is playing, `star` highlights the word currently being spoken and keeps
it scrolled into view.

- **pyttsx3** — word-boundary callbacks from the native engine confirm the exact
  audio position; a background timer advances the highlight at the configured
  rate and callbacks correct its estimate.
- **eSpeak-NG** — when libespeak-ng is available, star paces each word to the
  audio position the engine reports for it, so the highlight follows what is
  actually heard. The `espeak_highlight_offset_ms` setting (default 120) nudges
  that timing.
- **DECtalk / Festival / Piper / Coqui** — no word-level events; star uses the
  reading rate (wpm) to advance the highlight on a timer.

**Granularity (word / sentence / both):** by default the single spoken word is
highlighted. Switch to **sentence** highlighting (the whole current sentence is
banded) or **both** (a soft sentence band with the current word on top) in **View
→ Reading Aids → Karaoke Highlight…** or with `M-x highlight-granularity`.

**Highlight colors:** the same **Karaoke Highlight…** dialog has two color
pickers. **Word color** sets the spoken-word highlight (opens a system color
dialog); **Sentence color** sets the sentence band shown in **Both** granularity,
and can either **follow the theme** (a "Use theme" button matches the theme's
selection color) or use a color you pick — so the word and the band can be set to
clearly distinct colors.

**Follow-scroll:** as playback advances, the reading view keeps the spoken word
in a steady middle reading band (~40% down the viewport) rather than letting it
drift to the bottom edge, so there is always already-read context above and
upcoming text below. Controlled by the `qt_autoscroll` setting (on by default).

**Highlight timer and SAPI5 pacing:** the highlight timer fires once per word at
`highlight_speed × tts_rate`. With pyttsx3 callbacks active, a *pacing guard*
keeps the timer no more than **4 words ahead** of the last confirmed position;
SAPI5 callbacks can arrive 1–3 words late or stop entirely, so the guard has a
**1.5-second timeout** after which the timer runs freely until callbacks resume.

**Word-position map:** at load time star builds a map linking every TTS word to
its display line and column, using a monotonically advancing, column-aware search
so repeated words match in document order and the highlight never appears stuck.

---

## Find in document

A slim **find bar** docks at the bottom of the Qt window, over the document. Open
it with **`Ctrl+F`** (it seeds itself from the current single-word selection);
close it with **Escape**.

- **Incremental** — matches recompute as you type, and the first match at or
  after the cursor is revealed, so the search feels anchored where you are
  reading.
- **Live count** — a "**N of M**" label shows your position among all matches.
- **Next / Previous** — Enter or `F3` for next, Shift+Enter or Shift+`F3` for
  previous; navigation **wraps around** the document.
- **Case toggle** — a **Match case** checkbox switches between case-insensitive
  (default) and exact matching.
- **Highlight-all** — every match is banded in dim amber while the active match
  is emphasised in bright orange. The find highlights are painted *on top* of any
  user or difficult-word highlights, so neither wipes the other.
- **Spoken results** — the match count is announced to screen readers ("3 of 12"
  / "No matches") and mirrored to the status bar, so a blind user hears their
  search progress without leaving the input.

Matching reuses the plain-text substring scan of `star.search.SearchEngine`,
run over the editor's text so offsets map straight onto the on-screen selection.

---

## Full-text library search

The [metadata search](#metadata-editor--library-search) matches only titles,
authors, paths, and annotations. **Full-text library search** goes further: it
searches the actual **contents** of every document in your library.

- **On-demand & lazy** — nothing is indexed at start-up or at document-open time;
  the content index is built the first time a search runs, so the reading UI
  never pays for indexing it does not use.
- **Cached & incremental** — each document's extracted text is cached on disk
  (`fulltext_index.json` in the cache dir) keyed by the file's `(size, mtime)`
  fingerprint, so a later refresh only re-reads files that changed.
- **Off the UI thread** — a large library is indexed on a background worker so the
  event loop never blocks.
- **Best-effort** — a file that fails to load is simply skipped; one bad document
  never breaks the index.

Each result carries the document's path, title, the number of matches, and a
short snippet around the first hit; results are ranked by match count. Matching is
a case-insensitive substring scan. Per document, up to ~2 MB of text is indexed,
so a giant file can't bloat the cache or a query.

---

## Subtitle export (SRT / VTT)

When you export a document as audio, star can also produce a synchronized caption
track so the highlight "travels" with the audio into any media player.

- **On their own:** **File → Export → Export Subtitles (SRT / VTT)…** or `M-x
  export-subtitles`. The format follows the file extension (`.srt` or `.vtt`).
- **Alongside audio:** enable `M-x subtitles-with-audio` (or
  `export_subtitles_with_audio`) and every audio export drops a matching caption
  file next to it.
- **Cue size:** sentence-length lines by default; `M-x subtitle-word-level`
  switches to one cue per word.
- **Default format:** `M-x subtitle-format srt|vtt` (setting `subtitle_format`).

Timing is **estimated** from the synthesized audio's total duration (apportioned
across spoken tokens by length); no external tools are required.

---

## Reading statistics & progress

- **Tracked per document:** total **time read** (only while speech plays), the
  **furthest word** reached, **progress %**, and number of **sessions**.
- **Dashboard:** **Tools → Reading Statistics…** (`Ctrl+Shift+S`) or `M-x
  reading-stats` — overall totals, current document progress, and a **most-read**
  list.
- **Storage:** `settings.json` under `reading_stats`, flushed periodically and on
  exit.

### Sync without losing work (conflict merge)

When the same document is read on two machines through a synced folder (Dropbox,
iCloud, Syncthing, …), star now **merges** the per-document `.star/` sidecars
instead of last-write-wins. Reading position resolves by a policy you choose,
`sync_conflict_policy`:

| Policy | Behaviour |
|---|---|
| `newest` (default) | Newer timestamp wins — the classic last-write-wins |
| `highest_progress` | Keep the furthest reading position |
| `manual` | Keep the local position and surface the conflict |

**Annotations always union by id**, so an edit made on either machine is never
dropped. Corruption-hardened: a malformed sidecar value no longer discards valid
reading progress or crashes resume — the bad value is ignored and the good state
is kept.

---

## Library / Bookshelf

Every document you open is remembered in a central library.

- **Open it:** **File → Library / Bookshelf…** (`Ctrl+Shift+B`) or `M-x library`.
- **Shows:** each document's title, format, progress %, time read, and
  last-opened date, newest first; filter by title or path.
- **Reopen:** Enter / double-click (Qt) or pick its number (TUI); resumes at your
  saved position.
- **Storage:** the `library` setting, merged with `reading_positions` and
  `reading_stats`.

---

## Live HTML preview (edit mode)

While editing Markdown source you can show a **live HTML preview** beside the
editor that re-renders as you type.

- **Toggle:** **View → Live HTML Preview** or `Ctrl+Shift+L` (enters edit mode if
  needed; editor and preview sit in a draggable split pane).
- **Live updates:** re-renders ~300 ms after your last keystroke (debounced) and
  follows the current theme.
- **Preference:** `qt_edit_preview` remembers whether the preview is shown next
  time you enter edit mode.

---

## Voice & profile presets

Profiles bundle your most important settings so you can adapt star to a task in
one step.

- **Captured:** TTS backend, voice, rate, volume, SSML toggle, theme, font
  family/size, letter/word/line spacing, the dyslexia-friendly font, bionic
  reading, current-line highlight, and all karaoke-highlight settings.
- **Qt GUI:** the **Profiles** menu — Save (`Ctrl+Shift+K`), Load
  (`Ctrl+Shift+J`), Delete (`Ctrl+Shift+Y`).
- **TUI:** `M-x profile-save <name>`, `profile-load <name>`, `profile-list`,
  `profile-delete <name>`.
- **Storage:** `settings.json` under `profiles`.

---

## Pronunciation lexicon

Map any term to a spoken form so it is read correctly on **every** backend.

- **Editor (Qt GUI):** **Speech → Pronunciation Lexicon…** (`Ctrl+Shift+I`).
- **TUI:** `M-x pron-add <term> <spoken form>`, `pron-list`, `pron-remove
  <term>`, and `pronunciations` to toggle.
- **How it works:** whole-word, case-insensitive matching; longer terms win;
  overrides are applied **first**, before abbreviation expansion and number
  normalization. Example: `CHF → congestive heart failure`.
- **Storage:** `settings.json` under `pronunciations`; `use_pronunciations`
  toggles the feature.

---

## User highlights

Select any passage and highlight it in yellow, green, cyan, pink, or orange via
the **Highlight toolbar button** or the **Highlight menu** (`Ctrl+Shift+1` …
`Ctrl+Shift+5`; clear all with `Ctrl+Shift+0`).

Highlights are saved per document path in `settings.json` under `user_highlights`
and restored when the file is reopened. They are rendered with
`QTextEdit.setExtraSelections()` so they do not modify the document or interfere
with the TTS word highlight; PDF export bakes them into the output.

---

## Annotations / notes

Attach notes anywhere in a document, available in **both** interfaces and sharing
the same per-document store (anchored by reading position so they survive
re-rendering).

- **Qt GUI:** add with `Ctrl+Shift+A` / **Notes → Add Note at Cursor…** /
  toolbar; a text selection becomes the note's anchor and a second prompt accepts
  comma-separated tags. Single-click to scroll to a note; double-click to read
  aloud from there. Filter via the panel's box (plain terms or `#tag`). Toggle
  the panel with `Ctrl+Shift+N`.
- **TUI:** `a` to add, `A` / `M-x annotations-list` to browse, `M-x
  annotations-search`, `annotation-goto <n>`, `annotation-delete <n>`,
  `annotations-export`.

Notes persist per-document in `settings.json` under `annotations` (each carries
both a Qt `char_pos` and a `word_idx`, so a note created in one interface
navigates correctly in the other).

### Exporting notes (bibliographic formats)

**Notes → Export Notes…** writes the current document's notes; the format is
chosen by extension:

| Extension | Format | Notes |
|---|---|---|
| `.md` | Markdown | Human-readable list with a citation header — the default |
| `.json` | JSON | Full structured data including document metadata |
| `.bib` | BibTeX | A single `@misc` reference with all notes in the `annote` field |
| `.ris` | RIS | A reference-manager entry with each note as an `N1` line |
| `.txt` | Plain text | Simple numbered list |

The BibTeX/RIS output draws title and author from the document's metadata so
exported notes drop cleanly into Zotero, Mendeley, or a `.bib` bibliography.

---

## Study & spaced repetition

Your highlights and notes double as flashcards: the highlighted passage is the
**front** (the prompt) and your note is the **back** (the answer). star schedules
them for review with a modern spaced-repetition engine so you re-see material just
before you would forget it.

### The scheduler (FSRS)

Scheduling uses **FSRS** (Free Spaced Repetition Scheduler) — the open memory
model that replaced SM-2 in Anki 23.10. Each card carries a *stability* (days
until recall probability falls to the target) and a *difficulty* (1–10); each
review updates both and sets the next interval so retrievability decays back to a
target retention (default 90%). The scheduler is pure, deterministic, and stored
as plain JSON in settings, so a card's state round-trips through `settings.json`
and the `.star/` sidecars. A documented SM-2 fallback is available for reference.

### Reviewing in the app

Open the review dashboard from **Study ▸ Review Due Cards…** (`Ctrl+Shift+F5`).
It walks you through the cards due today, one at a time:

- **Reveal** the answer with **Enter** (recall is tested before the answer shows).
- **Grade** your recall with four buttons or the keys **1** (Again), **2** (Hard),
  **3** (Good), **4** (Easy); focus lands on **Good**, the most common grade, for
  one-key grading.
- The header shows your position in the deck, the due count, and a running
  **retention** estimate; each grade is written to the card's state immediately,
  so closing mid-session loses nothing.

Every control is keyboard-reachable and carries an accessible name/description,
and the header announces progress and retention to screen readers.

### Auto-generated cloze cards

star can turn passages into **cloze** (fill-in-the-blank) cards automatically, so
you get study material without hand-authoring every card.

### Optional AnkiConnect sync

If you also use Anki, star can two-way sync with a **locally running** Anki that
has the community **AnkiConnect** add-on installed (it exposes a small JSON-RPC
API on `localhost:8765`). The sync **pushes** star's reviewable notes into a
`star` deck (front = highlight, back = note, tagged with a stable id so a re-push
updates rather than duplicates) and **pulls** back each note's scheduling info
(interval, due, reps, lapses, ease) so the in-app dashboard reflects reviews you
did inside Anki.

It uses only the standard library, so importing star never requires Anki. It is
fully **offline-safe**: if Anki is closed, the add-on is absent, or the port is
blocked, you get a friendly hint instead of an error, and star's own note store
remains the source of truth.

---

## Citation manager (Qt GUI)

A lightweight citation library lives in the **Citations** menu, shared across all
documents (stored under `citations` in `settings.json`).

- **Import…** — read references from BibTeX (`.bib`), RIS (`.ris`), or CSL-JSON
  (`.json`).
- **Export…** — write the whole library to BibTeX, RIS, or CSL-JSON.
- **Add Citation…** — enter a reference by hand; **Add by DOI…** fetches it.
- **Manage / Browse…** — copy a citation's key, link it to the selected note, or
  delete it.

Linking a citation to a note records its key in the note's `cite` field (shown as
`@key`), so exported study notes carry proper attribution.

---

## Knowledge graph

Link annotations **across documents** into a typed, directed graph — turning a
flat notes list into a navigable web of how ideas relate. Each annotation becomes
a node (it gains a stable `id` and an optional `relations` list, assigned lazily
so existing notes keep working); edges carry a relation type and an optional
label.

- **Relation types:** `CONFLICTS_WITH`, `SUPPORTS`, `IS_EXAMPLE_OF`, `CITES`,
  `CONTRADICTS`, `DEFINES`, `EXTENDS`, `SEE_ALSO`, `PRECEDES`, `FOLLOWS`.
- **Add / edit relations:** select a note, then **Graph → Add Relation…** /
  **Edit Relations…** (Qt), or `M-x graph-add-relation` (TUI).
- **Graph view:** **Graph → Show Graph View** (`Ctrl+Shift+Q`) opens an
  interactive dock rendering the graph colour-coded by relation type;
  double-click a node to jump to that annotation. The TUI shows the DOT source
  via `M-x graph-show`.
- **Concept extraction:** **Graph → Extract Concepts…** finds candidate concepts
  (spaCy → NLTK → a domain-aware regex fallback: `general` / `legal` / `medical`
  / `sociological`); **Auto-Suggest Relations…** lists concepts that already
  appear in your notes.
- **Export:** SVG, PlantUML, DOT, and JSON (**Graph → Export Graph**). SVG works
  with no external packages via a built-in spring layout; `graphviz` is used for
  nicer layout when installed.
- **Optional dependencies:** `spacy`, `nltk`, `graphviz`, `plantuml` — all
  guarded; the feature works fully without them.

See the dedicated **[Knowledge Graph guide](knowledge-graph.md)** for the
complete walkthrough, every relation type's meaning, and the full
shortcut/command table.

---

## Voice dictation & transcription (optional)

With **Whisper** installed, `star` can turn speech into text.

- **Tools → Transcribe Audio File…** — pick an audio file; the transcription
  opens as a new readable document (runs in a background thread).
- **Tools → Dictate Note (record)…** — record a short voice memo; the
  transcribed text is saved as a note (tagged `dictated`) at the current
  position.

```bash
pip install openai-whisper          # transcription of audio files
pip install sounddevice numpy       # plus this for microphone dictation
```

`faster-whisper` is also supported. The model size is configurable with
`whisper_model` (`tiny`, `base`, `small`, `medium`, `large`). When Whisper is not
installed, these menu items simply explain how to enable them.

---

## Table of contents & EPUB / DAISY navigation

The **Contents panel** is populated by scanning the document's Markdown for
heading lines; clicking an entry scrolls to it. For EPUBs the chapter list is
also derived from navigation data:

- **EPUB 3 NAV** — the `<nav epub:type="toc">` element from the navigation
  document.
- **EPUB 2 NCX** — falls back to the `.ncx` file referenced by the spine.

Chapters are available via `M-x chapter-list`, `chapter-goto`, `chapter-next`,
and `chapter-prev` in both modes.

`star` also parses **DTBook XML** natively (DAISY 3): `.xml`/`.daisy` files
directly, Bookshare `.zip` downloads (unpacked automatically), and Archive.org
DAISY URLs. Reading order follows the `<spine>`/`<book>` sequence.

---

## Document caching

`star` caches the parsed text and word map for each document:

| Platform | Cache path |
|---|---|
| Linux | `~/.config/star/cache/` |
| macOS | `~/Library/Application Support/star/cache/` |
| Windows | `%APPDATA%\star\cache\` |

On reopen, star checks the file's modification time and the settings fingerprint;
if both match, the cached result is used immediately. Cache files are JSON named
by a hash of the path and settings. Force a fresh parse with `M-x cache-clear`.
Configure via `document_cache` and `cache_max_size_mb`.

---

## Large-document pagination

Very large documents (a full textbook, a scanned book, a giant merged PDF) are
slow to lay out all at once in the Qt view. **Opt-in pagination** renders only a
window of the document at a time, so the first page paints almost immediately —
on a ~500-page document first paint drops from several seconds to well under one
(roughly 5× faster). Reading, word highlighting, Find, and Define-Word all stay
correct across page boundaries.

- **Off by default.** Enable it with `qt_paginate_large_docs`; a document then
  paginates only once it exceeds `qt_paginate_threshold_words` (default 60 000
  words), so ordinary documents keep the whole-document path.
- **Tunable window.** `qt_paginate_words_per_page` (default 1 200) and
  `qt_paginate_window_pages` (default 2) size the rendered window.
- **Correctness first.** To keep highlight and difficult-word placement exact, a
  document you have highlighted — or have the difficult-word overlay enabled on —
  renders in full rather than paginating; highlighting a very large document turns
  pagination off for that session (with a status note), the same way opening Find
  does.

---

## Document fidelity

Beyond plain reading order, the Qt document view preserves the structure that
makes a document navigable and accessible.

- **Inline LaTeX math → Unicode.** Inline and display math (`$…$`, `$$…$$`,
  `\(…\)`, `\[…\]`) is rendered to real Unicode for the on-screen view — `x^2` →
  `x²`, `\sqrt{2}` → `√2`, `\frac{1}{2}` → `½`, `\alpha` → `α`, Greek letters,
  operators, roots, accents, and super/subscripts. This is purely a *display*
  transform (best-effort, no external deps): the **speech** path still receives
  the raw LaTeX and normalizes it to spoken English separately (see
  [Math normalization](#math-normalization)), so the two never interfere.
- **Accessible tables.** Markdown tables render with real header structure — a
  `<thead>` header row marked `scope="col"`, and the first cell of each body row
  marked `scope="row"` — so a screen reader can announce the row/column headers
  for any cell instead of reading a flat grid. Column alignment is preserved.
- **Clickable footnotes with backlinks.** Footnote *markers* become links that
  jump to the note at the bottom of the document, and each note carries a `↩`
  backlink that jumps back to where you were reading. (This is independent of the
  spoken [footnote handling](#footnote-handling) modes below.)
- **Image captions & alt text.** Image references render as a visible label from
  their alt text (falling back to the file name when alt is missing), styled as an
  italic caption so figures are distinguishable from body prose.

---

## Footnote handling

Markdown/Pandoc footnotes (`[^1]`, `[^label]`) are handled per `footnote_mode`:

| Mode | Behavior |
|---|---|
| `inline` (default) | Footnote text inserted at the reference: *word (footnote: text)* |
| `deferred` | References removed; text collected as a "## Footnotes" section at the end |
| `skip` | All footnote markers and definitions silently removed |

Change at runtime with `M-x footnote-mode inline|deferred|skip`.

This controls how footnotes are *spoken*. For the on-screen document, footnote
markers are also rendered as **clickable anchors** with a `↩` backlink — see
[Document fidelity](#document-fidelity).

---

## PDF reading order

Academic PDFs are the worst case for a screen reader: two-column layouts,
running headers/footers, and page numbers. In pdfminer's native order a
two-column page reads *across* the columns — "line 1 of column A, line 1 of
column B, …" — which is gibberish aloud. `star` reconstructs the reading order
from the page geometry:

- **Column detection** — a vertical projection of text-box extents finds the
  column gutters; the page is read **column by column, top-to-bottom**. Pages
  with no gutter are treated as a single column.
- **Full-width elements** — titles, author blocks, and figures that span the
  columns act as dividers: the flow reads the columns *above* them, then the
  spanning element, then the columns below it.
- **Running heads/feet** — text that recurs in the top/bottom margin across
  pages, and bare page numbers (`12`, `Page 12`, `12 of 340`, `iv`), are
  dropped from the spoken stream.

Controlled by the **`pdf_reading_order`** setting: `"reconstruct"` (default) or
`"raw"` to fall back to pdfminer's native box order when the heuristics misfire
on an unusual layout. Single-column PDFs are unaffected by the column logic and
still gain header/footer suppression. The feature uses the existing
`pdfminer.six` text layer — no extra dependency.

---

## OCR support

`star` uses [Tesseract](https://github.com/tesseract-ocr/tesseract) via
`pytesseract` for image-based PDFs and standalone image files.

```bash
pip install pytesseract pymupdf
```

| Platform | Tesseract install |
|---|---|
| Linux (Debian/Ubuntu) | `sudo apt install tesseract-ocr tesseract-ocr-eng` |
| macOS | `brew install tesseract` |
| Windows | [tesseract releases](https://github.com/tesseract-ocr/tesseract/releases) |

Configure the language pack with `ocr_lang` (e.g. `"eng+spa"`). star renders each
page to a bitmap with PyMuPDF, then runs Tesseract; text-layer PDFs are always
preferred and OCR triggers only when no text layer is detected.

---

## Math normalization

When `normalize_math` is true (the default), star converts common LaTeX and
inline math to natural English before TTS: `x^2` → "x squared", `\sqrt{x}` →
"square root of x", `\frac{a}{b}` → "a over b", `x_i` → "x sub i", Greek letters,
and operators (`\times` → "times", `\leq` → "less than or equal to"). Also applies
to MathML-embedded math from EPUB and HTML.

---

## Braille support

**Display passthrough** — On Linux, BrlTTY routes curses output to a connected
braille display; on Windows, NVDA and JAWS handle routing.

**BRF export** — Export the current document to a Braille Ready Format file (TUI:
`M-x export-braille`; Qt: **File → Export → Export as Braille (BRF)…**).

### Reliable out-of-the-box (Grade 1)

BRF export works **with no dependencies** via a pure-Python uncontracted **Grade
1** translator using the NABCC character set, with number/capital signs,
punctuation, and standard **40-cell × 25-line** page geometry.

> Earlier versions relied solely on liblouis, where a missing translation table
> could make liblouis call `exit()` at the C level — closing the whole window.
> The built-in translator is now the default and can never crash the process.

### Optional contracted Grade 2 (liblouis)

```bash
pip install louis
```

```json
"braille_grade2": true,
"braille_table": "en-ueb-g2.ctb"
```

When `braille_grade2` is enabled and the table resolves, star uses liblouis; any
failure falls back automatically to the built-in Grade 1 translator. Useful
tables: `en-ueb-g1.ctb`, `en-ueb-g2.ctb`, `es-g1.ctb`, `nemeth.ctb`.

---

## Archive ingestion

`star` can open archive files as containers and read their members directly —
no manual extraction required.

**Supported archive formats:**

| Format | Extension(s) | Notes |
|---|---|---|
| ZIP | `.zip` | stdlib; always available (DAISY ZIPs use the DAISY handler, not this one) |
| TAR | `.tar`, `.tar.gz`, `.tgz`, `.tar.xz`, `.tar.bz2` | stdlib; always available |
| 7-Zip | `.7z` | requires `py7zr` (`pip install "star-reader[archive]"`) |
| RAR | `.rar` | requires `rarfile` (`pip install "star-reader[archive]"`) |

**Opening an archive directly** produces a Markdown index listing its readable
members. Each member is registered in the library so you can reopen it later.
Click any entry or type its ref directly.

**Opening an archive member** uses the ref form
`/path/to/archive.zip!inner/paper.pdf`. The member is extracted to a temp file,
loaded in its native format (PDF, EPUB, Markdown, …), and keyed in the library
and annotations by the ref — so notes survive across sessions.

- **Qt GUI:** **File ▸ Open Archive…** — pick the archive from a dialog, then
  select a member from the list that appears.
- **TUI:** `M-x open-archive [path]` — same workflow from the command palette.
- **CLI / open directly:** `star /path/to/book.zip!chapter1.pdf`

**Filtering:** only readable members are shown: documents (`.pdf`, `.epub`,
`.docx`, `.md`, `.txt`, etc.). System junk (`__MACOSX/`, `.DS_Store`, dotfiles)
and directory entries are filtered out automatically.

---

## Metadata editor & library search

Each document in the library can carry structured metadata: **title**, **author**,
**year**, **DOI**, **ISBN**, and **publisher**. Metadata is stored in the
`"meta"` sub-dict of the library entry and persists in `settings.json`.

### Editing metadata

- **Qt GUI:** **File ▸ Edit Document Metadata…** — a dialog with one field per
  attribute. The **Look up DOI** button fetches the citation from CrossRef (requires
  a network connection and the DOI in the `doi` field). The **Look up ISBN** button
  fetches title, author, year, and publisher from the
  [OpenLibrary Books API](https://openlibrary.org/developers/api) (keyless, no
  account needed).
- **TUI:** `M-x metadata-edit` — field-by-field editing with DOI/ISBN lookup from
  the command palette.

ISBN entry accepts any notation: `978-3-16-148410-0`, `9783161484100`, or
`0-306-40615-2`. star validates the checksum (ISBN-10 mod-11 and ISBN-13 mod-10)
before sending a lookup request.

### Cross-library search

`M-x library-search` (TUI) opens a multi-criteria search over the entire
document library:

| Criterion | Matches |
|---|---|
| `query` | Title, author, path, and annotation text (all notes for the document) |
| `doi` | Exact DOI match (normalized — `https://doi.org/`, `doi:` prefix stripped) |
| `isbn` | Exact ISBN match (normalized — hyphens and spaces stripped) |
| `author` | Case-insensitive substring in the stored author field |

All criteria are AND-combined: only documents satisfying every non-empty
criterion are returned. With no criteria the entire library is returned in
last-opened order.

---

## Karaoke video export

`star` can produce a sentence-synchronized karaoke MP4 video from any document:
a rendered page image where the current sentence is highlighted while the TTS
voice reads it aloud — useful for study, accessibility demonstrations, or
sharing content as video.

See the dedicated **[Karaoke Video Export guide](video-export.md)** for the full
walkthrough, settings reference, and troubleshooting.

**Quick start:**

- **Qt GUI:** **File ▸ Export ▸ Video (MP4)…** (`Ctrl+Alt+V`) — choose an output
  path; the export runs in the background and the status bar confirms the file.
- **TUI:** `M-x export-video [path]` — same pipeline from the command palette.

**Requirements:** a TTS engine (any backend), **ffmpeg** on PATH, and Qt or Pillow
for frame rendering. `pip install "star-reader[video]"` adds Pillow as a fallback
renderer.

---

## RSVP reading mode

RSVP (Rapid Serial Visual Presentation) shows one word at a time at a fixed
point on screen, synchronized with TTS playback.  This eliminates the need to
track moving text across a line — a recognized aid for many dyslexic readers and
readers with limited visual field. The one-word display works as intended and no
longer crashes on activation.

**Activation**

| Interface | Action |
|---|---|
| Qt GUI | **View ▸ Reading Aids ▸ RSVP Mode** (`Ctrl+Alt+E`) |
| TUI | `M-x rsvp-mode` |

**Placement** — 9 positions let you choose where the word panel appears so it
falls within your comfortable field of view:

| | Left | Center | Right |
|---|---|---|---|
| **Top** | `top-left` | `top-center` *(default)* | `top-right` |
| **Middle** | `center-left` | `center` | `center-right` |
| **Bottom** | `bottom-left` | `bottom-center` | `bottom-right` |

- **Qt GUI:** **View ▸ Reading Aids ▸ RSVP Position…** opens a 3×3 button grid;
  click any cell to move the panel instantly.
- **TUI:** `M-x rsvp-position` cycles through or lets you select a position.

**Display** — the Qt overlay shows the current word in large type (default 48 pt)
with optional previous/next context words in a smaller face so you can orient
yourself without losing the focal point.  The TUI overlay uses a background-filled
row that spans the word and its context.

**Settings**

| Key | Default | Description |
|---|---|---|
| `qt_rsvp_mode` | `false` | Enable RSVP overlay at startup |
| `qt_rsvp_position` | `"top-center"` | Initial panel position |
| `qt_rsvp_font_size` | `48` | Current-word font size in pt |
| `qt_rsvp_context` | `true` | Show prev/next context words |
| `tui_rsvp_mode` | `false` | Enable RSVP overlay in TUI at startup |
| `tui_rsvp_position` | `"top-center"` | Initial panel position in TUI |

---

## Audio export

`star` can synthesize an entire document to an audio file using the active TTS
backend.

- **Qt GUI:** **File → Export → Export as Audio…** (background thread).
- **TUI:** `M-x export-audio [fmt]` (synchronous).

**Defaults to WAV** (no external tools). MP3/OGG/MP4 require **ffmpeg** (or
`pydub` as a pure-Python fallback):

| Format | Extension | Extra requirement |
|---|---|---|
| WAV | `.wav` | None — always works (**default**) |
| MP3 | `.mp3` | **ffmpeg** (recommended) or `pydub` |
| OGG Vorbis | `.ogg` | **ffmpeg** or `pydub` |
| MP4 (audio-only AAC) | `.mp4` | **ffmpeg** or `pydub` |

The backend always produces a WAV first; non-WAV formats are converted via ffmpeg
(preferred) or pydub, and a clear error with install instructions is raised if
neither is available. Audio export can also emit a synchronized SRT/VTT track —
see [Subtitle export](#subtitle-export-srt--vtt).

### Audiobook export (M4B)

For listening on the go, star can export a whole document as a chaptered `.m4b`
audiobook — the format audiobook players and Apple Books expect.

- **Qt GUI:** **File ▸ Export ▸ Export Audiobook (M4B)…** (background thread).

**Chapters come from the document's headings**, so an audiobook player can jump
straight to a section. The document is synthesized with the active TTS backend
(any engine) and muxed into an `.m4b` container with embedded chapter markers.
Because the container is built with ffmpeg, **ffmpeg must be on PATH**; without
it you get a clear message rather than a broken file.

---

## Speed presets, bookmarks & history

**Speed presets** switch reading rate with one command:

| Preset | Default wpm | Use case |
|---|---|---|
| `skim` | 350 | Quick overview |
| `normal` | 265 | General reading (default) |
| `study` | 200 | Careful study |
| `slow` | 150 | Difficult or unfamiliar material |

```
M-x speed skim
M-x speed-add fast 400  # define a new preset
M-x speed-list
```

**Bookmarks** — named, one set per document, and now available in **both**
interfaces from a shared store (`settings['bookmarks']`, keyed by document path,
so a bookmark set in one UI shows up in the other).

- **Qt GUI:** **`Ctrl+B`** (**Bookmarks ▸ Add Bookmark**) sets a bookmark at the
  current reading position (auto-named `mark1`, `mark2`, …); **Add Named
  Bookmark…** prompts for a name; the **Bookmarks…** dialog lists them (ordered by
  position) to jump to or delete.
- **TUI:** `M-x bookmark-set <name>`, `bookmark-goto`, `bookmark-list`,
  `bookmark-delete`.

Each bookmark records the position's character offset, a percentage, and a
timestamp.

**Navigation history (back / forward)** — every jump (a bookmark, a list pick, a
back/forward target) first records where you were, so you can walk your reading
path with **`Alt+←`** (back) and **`Alt+→`** (forward) in **both** the Qt GUI and
the TUI. Jumping mid-history branches (discarding the forward entries), and the
stack depth is `nav_history_size` (default 50).

---

## Document editing (Qt GUI)

A **Markdown edit mode** lets you correct OCR errors, add notes, or revise any
document in place.

| Action | Key / button |
|---|---|
| Enter edit mode | `Ctrl+E` or the **Edit** toolbar button |
| Exit edit mode (discard) | `Ctrl+E` again |
| Save and return to read mode | `Ctrl+S` or the **Save** toolbar button |

The editor switches from rendered HTML to the raw Markdown source. Standard
text-editor keys apply (`Ctrl+Z/Y`, `Ctrl+X/C/V`, `Ctrl+A`, word/line motion,
etc.). `Ctrl+S` writes back to the **original file** for text-based extensions
(`.md`, `.markdown`, `.txt`, `.rst`, `.org`, `.adoc`); for PDF/DOCX/EPUB a **Save
As** dialog opens. The editor works on the Markdown representation — for binary
formats this is a converted approximation, not a round-trip.

---

## Study & writing aids

Each helper is gated behind an optional package and degrades gracefully — the
menu item always appears, and when its package is missing star **offers to
install it for you** in the background (no `pip` command to run — see
[Optional features & one-click install](#optional-features--one-click-install)).
The `pip install` lines below are shown for reference; you normally never need to
type them.

- **Summarize a document** — **Tools ▸ Summarize Document** (`Ctrl+Shift+U`)
  condenses the document to its most important sentences via the extractive
  **LexRank** algorithm (`summary_sentences`, default 7). `pip install sumy`.
- **Anki flashcards** — **File ▸ Export ▸ Anki Flashcards…** (`Ctrl+Alt+H`) turns
  notes into an `.apkg` deck (highlighted passage on the front, your note on the
  back). `pip install genanki`.
- **Spell check** — in edit mode (`Ctrl+E`) misspellings get a red squiggle;
  **Edit ▸ Check Spelling** (`F7`) lists them. `pip install pyspellchecker`.
- **Translate** — **Tools ▸ Translate Document** (`Ctrl+Shift+X`) translates into
  15 languages via Google Translate (no API key; input capped at 15,000 chars per
  request). The one study aid that needs a network connection. `pip install
  deep-translator`.
- **Highlight difficult words** — **View ▸ Reading Aids ▸ Highlight Difficult
  Words** (`Ctrl+Alt+O`) tints uncommon/academic vocabulary by frequency
  (non-destructive; persists via `qt_vocab_highlight`). `pip install wordfreq`.
- **Define word (offline)** — **View ▸ Reading Aids ▸ Define Word** (`Ctrl+D`,
  also `M-x define` / the `d` key in the TUI) looks up the selected word (or the
  word under the cursor) and shows its part of speech, senses, synonyms, and
  pronunciation — entirely offline. Backed by WordNet
  (`pip install "star-reader[dictionary]"`, then `python -m nltk.downloader
  wordnet omw-1.4 cmudict`); point `dictionary_file` at a custom JSON glossary to
  layer your own domain terms on top (checked first).
- **Read RSS / Atom feeds** — **File ▸ Open Feed…** (`Ctrl+Shift+M`) fetches a
  feed URL, lists its articles, and opens any one in the reader. `pip install
  feedparser`.

---

## Optional features & one-click install

star runs fully out of the box on the Python standard library alone. Every
heavier capability is an *optional* package with a graceful fallback — but you no
longer have to run `pip` to get one. When a feature needs an add-on that isn't
installed, star offers to **download it for you in the background**, and the
feature becomes usable **in the same session** (only the very large speech-to-text
pack asks for a restart).

### First-run chooser

On first launch star shows a short **Optional Features** menu instead of silently
fetching everything. Pick a preset — **Thin** (the lightweight everyday reading
and study aids, ~40 MB) or **All** (everything star can use) — or tick individual
features. Each entry shows its purpose, approximate download size, and whether it
is already installed. The very large packs (speech-to-text dictation ≈ 2 GB,
named-entity extraction ≈ 500 MB) are opt-in and listed with their size upfront,
so choosing **All** is an informed, deliberate choice. A read-only **System
tools** list also reports native (non-pip) engines — Tesseract, Pandoc, ffmpeg,
liblouis, Piper — that star can use but cannot install for you.

The chooser also carries the **first-run interface-language picker** (see
[Interface language](#interface-language-i18n)). Re-open it any time from
**Tools → Install Optional Features…**.

### The feature groups

The chooser groups optional packages into features such as: office documents
(ODT/XLSX), offline dictionary, spell check, summarize, Anki flashcard export,
translate, RSS feeds, audio conversion, Grade 2 braille, hot-folder watching,
system clipboard, extra markup formats, difficult-word highlighting, knowledge-
graph extras, archive ingestion (`.7z`/`.rar`), OCR, speech-to-text dictation,
and named-entity concept extraction.

### Headless install (`star --install-optional`)

The scriptable counterpart to the GUI chooser installs features from the command
line:

```bash
star --install-optional                 # the "all" preset
star --install-optional thin            # the lightweight everyday set
star --install-optional ocr,dictionary  # a comma-separated feature list
```

Run it with no value (or an unknown one) to list every feature with its size and
install status. The fetch runs in the foreground with plain progress output.

### How it works

- **Best-effort & non-blocking.** GUI installs run on a daemon thread; the UI
  never waits on pip. If pip is missing, the machine is offline, or a build fails,
  star silently keeps using its fallbacks.
- **Attempted once per machine.** A marker file per package stops a slow or
  failing install from retrying on every launch; an explicit "install now" ignores
  the markers, so a prior failed attempt never makes the button silently no-op.
- **Usable in-session.** After a runtime install star flips the stale
  module-level "is it available?" flags for the affected feature, so it works
  immediately without a restart.
- **Opt-out.** `settings["auto_install"] = false` or the `STAR_NO_AUTOINSTALL`
  environment variable disables the chooser and background fetching entirely; once
  the chooser has been shown, `deps_prompted` keeps it from reappearing on its
  own.

The Qt binding itself is never installed here (you need it to launch the GUI in
the first place), and native binaries (Tesseract, Pandoc, ffmpeg, liblouis, Piper)
are out of scope — they are system tools, noted in each feature's description
rather than pip-installed.

---

## Accessibility

star is accessibility-first; several capabilities exist specifically for blind,
low-vision, and dyslexic readers. (See also [Screen reader
compatibility](#screen-reader-compatibility), [RSVP reading
mode](#rsvp-reading-mode), and the reading aids under [Color themes & CSS
customization](#color-themes--css-customization).)

### Screen-reader announcements

State changes are **spoken without moving focus**, using Qt's live-region
mechanism (`QAccessible` `Announcement` events — the Qt equivalent of an ARIA
live region). A blind user driving the app with NVDA / JAWS / Orca hears:

- **playback** transitions — "Playing", "Paused", "Stopped";
- **document load** — "Loaded ⟨title⟩";
- **theme changes** — "Theme: ⟨name⟩";
- **find results** — the live "N of M" / "No matches" count as you search;
- guided-tour steps.

Each announcement is paired with the matching status-bar message, so the same
information is both seen and heard. The helper is defensive: it is a silent no-op
when the accessibility bridge is unavailable (e.g. a headless test run) and never
raises, so an announcement failing can't break playback or a load.

### High-contrast AAA theme & OS theme follow

A dedicated **high-contrast** theme is engineered for **WCAG 2.1 AAA** (§1.4.6):
every text, heading, link, and code colour clears 7:1 contrast on pure black by a
wide margin (lowest pair ≈ 11:1), with six distinct hues so information is never
carried by colour alone — links are additionally underlined, headings by weight
and size. star can also **follow the operating system** appearance, mapping the
OS's light / dark / high-contrast preference to the matching built-in theme
(via `QGuiApplication.styleHints().colorScheme()` on Qt 6.5+); detection is
best-effort and falls back to your saved theme when the OS preference is unknown.

### Reading fonts across the whole UI

A **Reading Font** chooser (View ▸ Reading Aids ▸ Reading Font) offers three
low-vision / dyslexia-friendly faces beyond the default: **OpenDyslexic**,
**Atkinson Hyperlegible** (the Braille Institute's typeface, designed for low
vision), and **Lexend**. Each OFL font is fetched on demand the first time it is
picked and applied to the **entire interface** — not just the document, but the
menus, toolbar, dialogs, and dock panels — so nothing is left in the default face.
star snapshots the real default application font before overriding, so switching
back to **Default** restores the original chrome cleanly. (The classic
`Ctrl+Alt+X` toggle still flips OpenDyslexic on and off for muscle memory.)

---

## Screen reader compatibility

| Screen Reader | Platform | Notes |
|---|---|---|
| NVDA | Windows | Full compatibility; braille routing via NVDA |
| JAWS | Windows | Full compatibility; use virtual cursor mode |
| Orca | Linux | Full compatibility; AT-SPI2 metadata on the Qt document view |
| VoiceOver | macOS | Compatible with Terminal.app and iTerm2 |

**Design decisions:** cursor parking in the TUI (the terminal cursor stays at the
minibuffer); AT-SPI2 `accessibleName`/`accessibleDescription` on the Qt document
view; navigation shortcuts that follow NVDA/JAWS/VoiceOver muscle memory; no
auto-scroll cursor interference; a high-contrast theme; and `--plain` mode for
piping to other AT tools.

---

## Color themes & CSS customization

### Built-in themes

| Name | Description |
|---|---|
| `dark` | Polished neutral-dark (Zed/Ghostty-inspired) with blue/cyan/purple/teal accents (default) |
| `light` | Dark text on white with blue and magenta accents |
| `contrast` | Bold white and cyan on pure black — maximum legibility |
| `high-contrast` | **WCAG 2.1 AAA** (§1.4.6) low-vision theme — six distinct, slightly-desaturated hues on pure black, all clearing 7:1 contrast by a wide margin (lowest pair ≈ 11:1); links are also underlined and headings distinguished by weight/size, so meaning never rides on colour alone |
| `phosphor` | Classic green phosphor monochrome |

No built-in theme places red and green as adjacent accents (deuteranopia /
protanopia safe); contrast ratios meet or exceed WCAG 2.1 AA (and, for
`high-contrast`, AAA). Switch with `F5` (cycle), **View → Choose Theme…**, `M-x
theme <name>`, or `star --theme`.

### Follow the OS appearance

star can track the operating system's appearance and pick the matching built-in
theme automatically: the OS **dark**, **light**, and **high-contrast** preferences
map to the dark, light, and AAA themes respectively. Detection uses
`QGuiApplication.styleHints().colorScheme()` (Qt 6.5+) and is best-effort — when
the OS preference is unavailable or unknown, star leaves your saved theme
untouched. See also [Accessibility](#accessibility).

### CSS theme customization (Qt GUI)

The Qt GUI supports fully custom CSS themes — each is a plain `.css` file in the
**themes folder**:

| Platform | Path |
|---|---|
| Linux | `~/.config/star/themes/` |
| macOS | `~/Library/Application Support/star/themes/` |
| Windows | `%APPDATA%\star\themes\` |

The folder is created on first launch with the built-in themes as editable
starting points. To create one: **View → Open Themes Folder**, copy a `.css`
file, edit it, then **View → Reload CSS Themes** (or `F5` to cycle to it).

`star` extracts palette values from `body { background / color }`, `::selection
{ background }`, and `h1`–`h4`/`code` `{ color }`; any rule not present falls back
to the built-in `dark` palette. The full CSS is injected verbatim into every
rendered document, so extra selectors (`blockquote`, `table`, `a`, etc.) apply
directly. Qt's HTML renderer supports a subset of CSS 2.1 — most color/font/
margin/border properties work, but CSS variables (`var()`) and `:root {}` do not.

### Reading aids & High-DPI

**View → Reading Aids** collects accommodations for dyslexic and low-vision
readers: **Text Spacing…** (line height / letter / word spacing — WCAG 1.4.12),
**Karaoke Highlight…** (granularity, style, color, speed, lead/lag), the
**Reading Font** chooser (**Default**, **OpenDyslexic**, **Atkinson Hyperlegible**,
or **Lexend** — each OFL font fetched on demand the first time it is picked and
applied app-wide; the classic `Ctrl+Alt+X` still toggles OpenDyslexic on/off for
muscle memory), **Bionic Reading**, **Syllable Splitting**, **Current-Line
Highlight**, the **Reading Ruler**, and **RSVP Mode** (one word at a time at a
chosen screen position — see [RSVP reading mode](#rsvp-reading-mode)). star
applies high-DPI scaling by default (`qt_hidpi`), so the window renders crisp on
4K/HiDPI displays.

- **Syllable splitting** shows words broken into syllables (`read·a·bil·i·ty`) as
  an offline decoding aid. It is purely a *display* transform — the speech and
  word-highlighting paths receive the unsplit text, so playback is unaffected —
  and it works the moment it installs, no restart. Persists via
  `qt_syllable_split`.
- **Reading ruler** overlays a movable, translucent band (a typoscope) that
  follows the caret line so your eye can keep its place; its height and opacity
  are adjustable from **Reading Ruler…**. Persists via `qt_reading_ruler`.

---

## Interface language (i18n)

star can localize its own **chrome** — the menu bar, toolbar button labels, and
dock titles in the Qt GUI, **and now the terminal UI as well** — independently of
the document being read. (Document *content* is handled separately by **Tools ▸
Translate Document…**.)

**Shipped languages:** English (source), **Español**, **Français**, **Deutsch**,
**Português**, and a first **العربية** (Arabic) catalog. The non-English catalogs
are kept complete by a CI gate, so no string is left untranslated.

**Right-to-left (RTL) support** — choosing a right-to-left interface language
mirrors the whole app: the layout direction flips and the reading view renders
with `dir="rtl"`. Arabic is the first RTL catalog; the machinery also covers
Hebrew, Persian/Farsi, and Urdu (`star.i18n.is_rtl`) so a future RTL catalog
needs no code changes.

**First-run language picker** — the interface language is offered right at the
top of the first-launch [Optional Features](#optional-features--one-click-install)
chooser (first launch is the earliest natural point to pick a language). Choosing
one applies it immediately and re-localizes the surrounding app without a restart.

**Locale-aware TTS** — when speech is auto-selecting a voice, star **biases the
default toward a voice that speaks your interface language**, so a Spanish UI
tends to read aloud in a Spanish voice. If no installed voice matches, it keeps
the English default. (The [Voice Manager](#voice-manager)'s Piper catalog covers
all five interface languages so a matching neural voice is one click away.)

**Switching** — Qt GUI: **View ▸ Interface Language**, then pick a language. The
menu bar and toolbar are rebuilt immediately (no restart) and the choice is
saved to `ui_language` in settings. Native language names are shown
untranslated so you can always find your own. The TUI activates the persisted
`ui_language` at start-up.

**How it works** — each language is a flat JSON catalog of
`{english_source: translation}` in `star/locale/<code>.json`, loaded at runtime
by `star/i18n.py`. There is **no build step** (unlike Qt's native `.ts`/`.qm`
workflow). Any string without a catalog entry falls back to its English source,
so a partial catalog degrades gracefully rather than showing blanks.

**Adding a language** — no code changes to the GUI are required:

1. Copy `star/locale/es.json` to `star/locale/<code>.json` and translate the
   values (leave the English keys untouched).
2. Add a `(native name, code)` row to `LANGUAGES` in `star/i18n.py`.
3. The language appears in **View ▸ Interface Language** on next launch.

See [`star/locale/README.md`](../star/locale/README.md) for the full
contributor guide.

| Setting | Default | Description |
|---|---|---|
| `ui_language` | `"en"` | ISO-639-1 code of the UI-chrome language |

---

## Plugins

`star` is extensible through **entry-point plugins**: a separate pip package can
add a new capability with no fork and no change to star itself. star discovers
plugins at runtime via Python's standard `importlib.metadata` entry-points — the
same mechanism its own built-ins use.

There are **three plugin groups**:

| Entry-point group | Base class (ABC) | What it adds |
|---|---|---|
| `star.formats` | `star.formats.FormatHandler` | A document loader for one or more file extensions |
| `star.backends` | `star.tts.base.TTSBackend` | A text-to-speech engine |
| `star.exporters` | `star.formats.Exporter` | A new export target |

Each plugin is a class subclassing the matching ABC and registered in one table
in your package's `pyproject.toml`.

**Introspecting the plugin system** — the `star --plugins` CLI reports what is
registered without launching the GUI or TUI:

```bash
star --plugins list                 # every registered plugin, by group
star --plugins info <group> <name>  # details for one plugin
star --plugins api                  # the ABC contracts a plugin must implement
```

There is a complete, working, copy-me example in
[`examples/plugin-template/`](../examples/plugin-template/) — a ~40-line package
that adds a toy `.demo` format. For the full walkthrough — the API contract, all
three groups, packaging, and local testing — see the dedicated
**[Developing star plugins](plugins-developing.md)** guide.

---

## Batch conversion & hot-folder watching

Both features drive the **same** single-file load → export pipeline over the
headless export formats: **markdown** (`.md`), **text** (`.txt`), and **braille**
(`.brf`).

### Batch conversion

Convert many documents — selected files or a whole folder — to one format:

- **Qt GUI:** **File ▸ Batch Convert** (`Ctrl+Shift+C`).
- **TUI:** `M-x batch-convert`.

Each file is converted independently: a corrupt/password-protected/unsupported
file is **recorded and skipped**, never aborting the run. Outputs reuse the
source basename (collisions disambiguated, never overwritten), and a timestamped
`star-batch-<timestamp>.log` summary is saved in the output directory.

### Hot-folder watching

```bash
# Headless: convert every file added to ./inbox into ./out as Markdown
star --watch ./inbox --output ./out --format markdown
```

`--format` accepts `markdown`, `text`, `braille` (default `markdown`). Start/stop
from the **Qt GUI** with **File ▸ Watch Folder** (`Ctrl+Shift+W`).

Behavior: **partial-write safe** (waits for steady file size); on success the
source moves to `<input>/processed/`, on failure to `<input>/failed/`; every
attempt is logged to `<output>/star-watch.log`; Ctrl+C / SIGTERM shut down
cleanly without interrupting an in-progress conversion. Uses
[`watchdog`](https://pypi.org/project/watchdog/) for real filesystem events when
installed (the `[watch]` extra); otherwise falls back to directory polling.

---

See also: [Usage Guide](usage_guide.md) · [Installation](installation.md) ·
[Configuration](configuration.md) · [Architecture](architecture.md) ·
[Karaoke Video Export](video-export.md) ·
[Developing star plugins](plugins-developing.md).
