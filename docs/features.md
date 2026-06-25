# ✨ Features

The complete feature reference for `star`. For how to invoke each feature, see
the [Usage Guide](usage_guide.md); for the settings that tune them, see
[Configuration](configuration.md).

- [Feature overview](#feature-overview)
- [Supported file formats](#supported-file-formats)
- [TTS backends](#tts-backends)
- [Word highlighting](#word-highlighting)
- [Subtitle export (SRT / VTT)](#subtitle-export-srt--vtt)
- [Reading statistics & progress](#reading-statistics--progress)
- [Library / Bookshelf](#library--bookshelf)
- [Live HTML preview](#live-html-preview-edit-mode)
- [Voice & profile presets](#voice--profile-presets)
- [Pronunciation lexicon](#pronunciation-lexicon)
- [User highlights](#user-highlights)
- [Annotations / notes](#annotations--notes)
- [Citation manager](#citation-manager-qt-gui)
- [Knowledge graph](#knowledge-graph)
- [Voice dictation & transcription](#voice-dictation--transcription-optional)
- [Table of contents & EPUB / DAISY navigation](#table-of-contents--epub--daisy-navigation)
- [Document caching](#document-caching)
- [Footnote handling](#footnote-handling)
- [OCR support](#ocr-support)
- [Math normalization](#math-normalization)
- [Braille support](#braille-support)
- [Audio export](#audio-export)
- [Speed presets, bookmarks & history](#speed-presets-bookmarks--history)
- [Document editing](#document-editing-qt-gui)
- [Study & writing aids](#study--writing-aids)
- [Screen reader compatibility](#screen-reader-compatibility)
- [Color themes & CSS customization](#color-themes--css-customization)
- [Batch conversion & hot-folder watching](#batch-conversion--hot-folder-watching)

---

## Feature overview

| Feature | Detail |
|---|---|
| Qt GUI (primary) | Windowed application with menu bar, toolbar, dock panels, and a keyboard shortcut for every command; launches by default when PyQt6/PyQt5 is installed |
| Terminal TUI (secondary) | Full-featured, fully keyboard-driven curses interface for headless / text-only use; force it with `--tui` |
| Built-in TTS | pyttsx3 (SAPI5 / NSSpeechSynthesizer / eSpeak-NG), macOS `say` (native, default on Mac), eSpeak-NG (in-process libespeak-ng, or CLI), DECtalk, Festival, Piper (neural, offline, free), Coqui |
| eSpeak-NG playback sync | Driven in-process via libespeak-ng (ctypes); per-word events carry their audio position, so the highlight follows the actual audio, not a timer estimate |
| Default reading rate | **265 wpm** — intentionally brisk; adjustable at runtime |
| TTS word highlighting | Spoken word highlighted live; works in both Qt and terminal modes |
| Highlight granularity | Highlight by **word** (default), whole **sentence** (less flicker), or **both** |
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
| Markdown rendering | All documents are converted to clean Markdown for display |
| Math normalization | LaTeX and inline math expressions converted to natural spoken English |
| Footnote handling | Markdown / Pandoc footnotes can be read inline, deferred, or skipped |
| Speed presets | Named presets (skim/normal/study/slow) switchable at runtime |
| Bookmarks / history | Named bookmarks and within-session position history |
| Document editing | `Ctrl+E` toggles raw-Markdown edit mode; `Ctrl+S` saves back to the original file |
| Export | Markdown, PDF (with highlights), BRF braille, TTS audio, and SRT/VTT subtitles |
| Reading statistics | Per-document time read, progress %, and session count, with totals and a most-read dashboard |
| Library / bookshelf | Searchable list of every opened document with progress and last-opened time |
| Live HTML preview | Optional split-pane preview that re-renders the Markdown live while you edit |
| Voice & profile presets | Save voice, rate, theme, font, spacing, and highlight settings as named profiles |
| Pronunciation lexicon | User-editable term → spoken-form dictionary |
| Document translation | Translate into 15 common languages (Google backend, no API key); optional via `deep-translator` |
| RSS / journal feeds | Browse a feed and open any article in the reader; optional via `feedparser` |
| Difficult-word overlay | Tints uncommon / academic vocabulary by word frequency; optional via `wordfreq` |
| Dependency status report | `star --deps` lists every optional dependency and how to add the rest |
| Four built-in themes | dark (default), light, contrast, phosphor — all colorblind-friendly |
| CSS theme customization | Drop any `.css` file into the themes folder; star picks it up instantly |
| High-DPI display support | Qt GUI scales correctly on 4K and HiDPI screens |
| Reading level | Flesch-Kincaid grade and ease score on demand |
| `--plain` mode | Extracts clean text to stdout for piping to other tools |
| Batch & hot-folder convert | Convert many files / a folder at once, or auto-convert a watched folder |
| Installable package, graceful degradation | Every third-party dependency is optional and guarded, so the core runs on the standard library alone |

---

## Supported file formats

| Format | Extension(s) | Package(s) Required |
|---|---|---|
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
| Pandoc fallback | any Pandoc-supported format | `pandoc` binary or `pypandoc` |

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
M-x tts-backend dectalk
M-x tts-backend none
```

In the Qt GUI the same engines are reachable from **Speech → Choose TTS Engine…**.

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

**Highlight timer and SAPI5 pacing:** the highlight timer fires once per word at
`highlight_speed × tts_rate`. With pyttsx3 callbacks active, a *pacing guard*
keeps the timer no more than **4 words ahead** of the last confirmed position;
SAPI5 callbacks can arrive 1–3 words late or stop entirely, so the guard has a
**1.5-second timeout** after which the timer runs freely until callbacks resume.

**Word-position map:** at load time star builds a map linking every TTS word to
its display line and column, using a monotonically advancing, column-aware search
so repeated words match in document order and the highlight never appears stuck.

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

## Footnote handling

Markdown/Pandoc footnotes (`[^1]`, `[^label]`) are handled per `footnote_mode`:

| Mode | Behavior |
|---|---|
| `inline` (default) | Footnote text inserted at the reference: *word (footnote: text)* |
| `deferred` | References removed; text collected as a "## Footnotes" section at the end |
| `skip` | All footnote markers and definitions silently removed |

Change at runtime with `M-x footnote-mode inline|deferred|skip`.

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

**Bookmarks** — `M-x bookmark-set <name>`, `bookmark-goto`, `bookmark-list`,
`bookmark-delete`; stored per document under `bookmarks`.

**History** — `Alt+Left` / `Alt+Right` (TUI) navigate within-session positions;
depth is `nav_history_size` (default 50).

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
menu item always appears and tells you what to `pip install` when its package is
missing.

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
- **Read RSS / Atom feeds** — **File ▸ Open Feed…** (`Ctrl+Shift+M`) fetches a
  feed URL, lists its articles, and opens any one in the reader. `pip install
  feedparser`.

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
| `phosphor` | Classic green phosphor monochrome |

No built-in theme places red and green as adjacent accents (deuteranopia /
protanopia safe); contrast ratios meet or exceed WCAG 2.1 AA. Switch with `F5`
(cycle), **View → Choose Theme…**, `M-x theme <name>`, or `star --theme`.

### CSS theme customization (Qt GUI)

The Qt GUI supports fully custom CSS themes — each is a plain `.css` file in the
**themes folder**:

| Platform | Path |
|---|---|
| Linux | `~/.config/star/themes/` |
| macOS | `~/Library/Application Support/star/themes/` |
| Windows | `%APPDATA%\star\themes\` |

The folder is created on first launch with the four built-in themes as editable
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
**Karaoke Highlight…** (granularity, style, color, speed, lead/lag),
**Dyslexia-Friendly Font** (prefers OpenDyslexic / Atkinson Hyperlegible / Lexend
/ Comic Sans), **Bionic Reading**, and **Current-Line Highlight**. star applies
high-DPI scaling by default (`qt_hidpi`), so the window renders crisp on 4K/HiDPI
displays.

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
[Configuration](configuration.md) · [Architecture](architecture.md).
