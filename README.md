# star — Speaking Terminal Access Reader

A single-file Python application that reads your documents aloud while you follow along — no installation wizard, no cloud account, no internet required.

`star` is an accessible document reader built for students with print disabilities. It opens PDFs, DOCX files, EPUB Books, PowerPoint decks, web pages, spreadsheets, and more, then reads them aloud using your platform's built-in text-to-speech engine while highlighting each spoken word. By default `star` launches a windowed Qt GUI; a full-featured curses terminal interface is also available with `--tui`.

`star` was designed with graduate students in mind — people who work with dense, heavily formatted documents and need a reading tool that gets out of the way. The interface is intentionally simple enough for a high school student to pick up in under five minutes, while the keyboard command set scales to the needs of power users.

`star` draws design inspiration from [Emacspeak](https://emacspeak.sourceforge.net/), [Kurzweil 1000](https://www.kurzweiledu.com/), [Natural Reader](https://www.naturalreaders.com/), and [Central Access Reader](https://www.readingmadeeasy.com/).

---

## Features

| Feature | Detail |
|---|---|
| Qt GUI (default) | Windowed application with menu bar, toolbar, and dock panels; launches automatically when PyQt6/PyQt5 is installed |
| Terminal TUI (fallback) | Full-featured curses interface; force it with `--tui` |
| Built-in TTS | pyttsx3 (SAPI5 / NSSpeechSynthesizer / eSpeak-NG), eSpeak-NG direct, DECtalk, Festival, Coqui |
| eSpeak-NG word callbacks | eSpeak-NG uses SSML `<mark/>` events for accurate per-word highlighting — not just a timer estimate |
| Default reading rate | **265 wpm** — intentionally brisk; adjustable at runtime |
| TTS word highlighting | Spoken word highlighted live; works in both Qt and terminal modes |
| User text highlights | Select any passage and highlight it in yellow, green, cyan, pink, or orange; persists across sessions and exports to PDF |
| Table of Contents panel | Auto-built from document headings in Qt mode; click any entry to jump there |
| EPUB NCX / NAV navigation | Parses EPUB 2 NCX and EPUB 3 NAV documents for chapter-level navigation |
| Async document loading | Documents load in a background thread — the UI never freezes |
| Document caching | Parsed documents are cached in `~/.config/star/cache/`; reopening a large file is instant |
| Markdown rendering | All documents are converted to clean Markdown for display |
| Clean TTS text | Markup is stripped before speech — no symbols read aloud |
| Math normalization | LaTeX and inline math expressions converted to natural spoken English |
| Footnote handling | Markdown / Pandoc footnotes can be read inline, deferred, or skipped |
| Code block skipping | Code fences skipped during TTS by default (configurable) |
| Speed presets | Named presets (skim/normal/study/slow) switchable at runtime |
| Bookmarks | Set named bookmarks and jump back to them; persist in settings |
| History navigation | Alt+Left / Alt+Right navigate the within-session position history |
| Document editing | `Ctrl+E` toggles edit mode (raw Markdown); `Ctrl+S` saves back to the original file |
| Table navigation | `Ctrl+T` / `Ctrl+Shift+T` jump to the next / previous table |
| Screen-reader navigation | `Ctrl+H/P/T` mirror NVDA/JAWS heading/paragraph/table conventions |
| Regex search | Toggle regex mode for pattern-based document search |
| Emacs-style keybindings | Full Emacs navigation plus vi-style `j`/`k`/`gg`/`G` shortcuts (TUI) |
| M-x command palette | Tab-completed command palette with persistent history (TUI) |
| Export | Save as Markdown, PDF (with highlights), BRF braille, or TTS audio from the File menu |
| Braille export | BRF export via liblouis |
| Audio export | Synthesise the document to MP3, OGG, MP4, or WAV using any installed TTS backend |
| Screen reader compatible | AT-SPI2 accessibility metadata; cursor parked at minibuffer (TUI) |
| Four built-in themes | dark (default), light, contrast, phosphor — all colorblind-friendly |
| CSS theme customization | Drop any `.css` file into the themes folder; star picks it up instantly via View → Reload CSS Themes |
| High-DPI display support | Qt GUI scales correctly on 4K and HiDPI screens |
| Font selection | Full OS font picker (family, style, and size) via **View → Change Font…** |
| Reading level | Flesch-Kincaid grade and ease score on demand |
| Persistent settings | User preferences saved to `settings.json` |
| `--plain` mode | Extracts clean text to stdout for piping to other tools |
| Single Python file | `star.py` — zero required dependencies beyond the standard library |

---

## Requirements & Installation

**Minimum Python version: 3.8**

`star` runs with nothing beyond the Python standard library. Every optional package below unlocks additional file formats or features. Install only what you need.

### Optional Packages

| Package | Purpose | Install |
|---|---|---|
| `PyQt6` or `PyQt5` | Qt GUI (default mode; highly recommended) | `pip install PyQt6` |
| `pyttsx3` | TTS via SAPI5 (Windows), NSSpeechSynthesizer (macOS), eSpeak-NG (Linux) | `pip install pyttsx3` |
| `pdfminer.six` | PDF text extraction (text-layer PDFs) | `pip install pdfminer.six` |
| `pytesseract` | OCR for scanned/image PDFs and standalone image files | `pip install pytesseract` |
| `pymupdf` | PDF page rendering required by pytesseract | `pip install pymupdf` |
| `python-docx` | Microsoft Word DOCX support | `pip install python-docx` |
| `python-pptx` | PowerPoint PPTX support | `pip install python-pptx` |
| `odfpy` | OpenDocument ODT support | `pip install odfpy` |
| `openpyxl` | Excel XLSX spreadsheet support | `pip install openpyxl` |
| `pypandoc` | Pandoc conversion for formats without a native loader | `pip install pypandoc` |
| `louis` | Braille BRF export | `pip install louis` |
| `pydub` | Audio format conversion fallback (MP3 / OGG / MP4) when ffmpeg is absent | `pip install pydub` |
| `windows-curses` | Windows terminal (curses) support for `--tui` mode | `pip install windows-curses` |

### External Binary Dependencies

- **Tesseract** — required by `pytesseract`. Download from [github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract/releases) or install via your system package manager.
- **eSpeak-NG** — required for the eSpeak-NG backend and for accurate per-word callbacks. See [TTS Backends](#tts-backends).
- **DECtalk** — set `DECTALK_BIN` to the path of the `dtalk`/`dectalk` binary. Source: [github.com/dectalk/dectalk](https://github.com/dectalk/dectalk).
- **Pandoc** — optional fallback for exotic formats. See [pandoc.org](https://pandoc.org/).
- **ffmpeg** — recommended for audio export (MP3, OGG, MP4). WAV export works without it. Download from [ffmpeg.org](https://ffmpeg.org/download.html) or install via your package manager (`sudo apt install ffmpeg`, `brew install ffmpeg`).

### Platform Notes

| Platform | Notes |
|---|---|
| Linux | `curses` is built into the standard library. No extra terminal package needed. |
| macOS | `curses` is built in. |
| Windows | TUI mode requires `windows-curses` (`pip install windows-curses`). The Qt GUI works without it. |

### Quick Install

```bash
# Recommended: Qt GUI + PDF + DOCX + TTS
pip install PyQt6 pyttsx3 pdfminer.six python-docx python-pptx

# Add OCR support for scanned PDFs and image files
pip install pytesseract pymupdf

# Windows TUI mode
pip install windows-curses

# Everything
pip install PyQt6 pyttsx3 pdfminer.six pytesseract pymupdf python-docx python-pptx odfpy openpyxl pypandoc louis pydub windows-curses
```

---

## Running

```bash
python star.py                        # launch Qt GUI (default when PyQt6/PyQt5 is installed)
python star.py document.pdf          # open a PDF in the Qt GUI
python star.py https://example.com   # fetch and read a URL
python star.py notes.md              # open a Markdown file
python star.py --tui report.docx     # force terminal UI mode
python star.py --plain paper.pdf     # extract clean text to stdout (no UI)
python star.py --rate 200 book.epub  # open with a slower reading speed
python star.py --theme contrast      # start with the high-contrast theme
python star.py --list-themes         # print available theme names and exit
python star.py --list-voices         # list available TTS voices and exit
python star.py --keytest             # open the key-code diagnostic tool (TUI)
```

**Default mode:** When PyQt6 or PyQt5 is installed, `star` opens the Qt GUI automatically. If neither is present, it falls back to the terminal TUI. Use `--tui` to force the terminal interface even when Qt is available.

---

## Screen Layout

### Qt GUI

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ File  Highlight  View                                                         │  ← menu bar
├─────┬──────────────────────────────────────────────────────────────────────  │
│     │ [Open] [Play/Pause ▶⏸] [Stop ■] [+ Speed] [− Speed] [SC ○] [Voice…]   │  ← toolbar
│ ToC │ [Theme] [Help] [Quit] [Copy] [Level] [Highlight]                        │
│     ├────────────────────────────────────────────────────────────────────────│
│ Ch1 │                                                                         │
│ Ch2 │  # Chapter 1: Introduction                                              │  ← document
│ Ch3 │                                                                         │     view
│ ... │  This paragraph is being read aloud. The [current]                      │  ← TTS word
│     │  word is shown with a cyan background highlight.                        │     highlight
│     │                                                                         │
│     │  ════════════════════════════════════════                               │
│     │                                                                         │
├─────┴────────────────────────────────────────────────────────────────────────│
│ ▶  "word"  —  42%  —  265 wpm                                                 │  ← status bar
└──────────────────────────────────────────────────────────────────────────────┘
```

### Terminal TUI

```
┌──────────────────────────────────────────────────────────────────────┐
│ star  │  Document Title                ▶ Speaking  265 wpm  pyttsx3  │  ← title bar
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  # Chapter 1: Introduction                                           │  ← document
│  ══════════════════════                                              │     view
│                                                                      │
│  This paragraph is being read aloud. The [current]                  │  ← word
│  word is shown with a cyan background highlight.                     │     highlight
│                                                                      │
│                                                                  ▼   │  ← scroll
├──────────────────────────────────────────────────────────────────────┤
│ Document Title   Line 42/380   11%                                   │  ← status bar
│   Space:read/pause  ↑↓:scroll  Ctrl-O:open  Ctrl-F:search           │  ← key hints
│   M-x/F2:command   F1:help  q:quit                                   │
│ M-x: open█                                                           │  ← minibuffer
└──────────────────────────────────────────────────────────────────────┘
```

### TUI Regions

**Title bar** — Application name, document title, TTS status (▶ / ‖ / ■), reading rate, and active backend.

**Document view** — Main reading area. Rendered as formatted Markdown. Scrolls automatically to track the spoken word.

**Word highlight** — Currently spoken word highlighted with a distinct background. The cursor does not move here — it stays at the minibuffer so screen readers are not disrupted.

**Status bar** — Document title, current line, total lines, and scroll percentage.

**Key hints** — Two-line quick-reference for the most common keybindings. Always visible.

**Minibuffer** — Input area for file paths, search queries, M-x commands, and all interactive prompts. Terminal cursor always parked here.

---

## Keyboard Shortcuts

Both interfaces share the same navigation philosophy — single-letter or `Ctrl+letter` shortcuts follow **NVDA / JAWS browse-mode conventions** so screen-reader users have the same muscle memory in both modes.

### Playback (both modes)

| Key | Action |
|---|---|
| `Space` | Play / pause TTS |
| `Esc` | Stop TTS |
| `Ctrl+=` / `+` | Speed up (+20 wpm) |
| `Ctrl+-` / `-` | Slow down (−20 wpm) |
| `F8` | Cycle speed preset (skim / normal / study / slow) |

The default reading rate is **265 wpm**. New users should start at 150–180 wpm and increase gradually.

### Structure navigation (both modes)

Keys are shared between the Qt GUI and the TUI. The TUI also accepts the legacy bracket keys as fallbacks.

| Action | Qt GUI | TUI |
|---|---|---|
| Next heading | `Ctrl+H` | `h`   `}` (legacy) |
| Previous heading | `Ctrl+Shift+H` | `{` (legacy) |
| Read next heading aloud | `Ctrl+H` (if playing) | `>` |
| Read previous heading aloud | `Ctrl+Shift+H` (if playing) | `<` |
| Next paragraph | `Ctrl+P` | `p`   `Ctrl+P`   `]` (legacy) |
| Previous paragraph | `Ctrl+Shift+P` | `P`   `[` (legacy) |
| Replay paragraph | `Ctrl+R` | `r`   `Ctrl+R` |
| Next table | `Ctrl+T` | `t` |
| Previous table | `Ctrl+Shift+T` | `T` |
| Next sentence | `Alt+.` | `.` |
| Previous sentence | `Alt+,` | `,` |
| Replay sentence | `Alt+;` | `;` |
| Play from cursor / selection | `Ctrl+Return` | — |

### Scroll navigation (TUI)

| Key | Action |
|---|---|
| `↑` / `k` | Scroll one line up |
| `↓` / `j` | Scroll one line down |
| `PgUp` / `b` | Page up |
| `PgDn` | Page down |
| `Home` | Jump to beginning of document |
| `End` | Jump to end of document |
| `H` | History: go back to previous position |
| `L` | History: go forward |

### File operations

| Action | Qt GUI | TUI |
|---|---|---|
| Open a file | `Ctrl+O` | `Ctrl+O` |
| Open a URL | URL toolbar button | `M-x open-url` |
| Export as Markdown | File → Export | `Ctrl+S` (read mode) |
| Save edited Markdown | `Ctrl+S` (edit mode) | — |
| Reload document | — | `F9` |
| Quit | `Ctrl+Q` | `Ctrl+Q`   `q` |

### Editing (Qt GUI only)

| Key | Action |
|---|---|
| `Ctrl+E` | Toggle edit mode (raw Markdown ↔ rendered view) |
| `Ctrl+S` | Save in edit mode; export as Markdown in read mode |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste |
| `Ctrl+C` | Copy selection or current paragraph (read mode) |

### Search

| Action | Qt GUI | TUI |
|---|---|---|
| Search forward | `Ctrl+F` | `Ctrl+F`   `/` |
| Search backward | — | `Ctrl+R`   `?` |
| Next match | — | `n` |
| Previous match | — | `N` |
| Clear search | `Esc` | `Esc`   `C-g` |

All matches are highlighted: current match in magenta, others in blue.

### View & display

| Action | Qt GUI | TUI |
|---|---|---|
| Cycle color theme | `F5` | `F5` |
| Choose theme by name | View → Choose Theme… | `M-x theme <name>` |
| Toggle Contents panel | `Ctrl+\` | — |
| Show reading level | `Ctrl+L` | `M-x reading-level` |
| Toggle line numbers | — | `F6` |
| Toggle syntax highlight | — | `F7` |
| Open README.md (help) | `F1` | `F1` |

### Voice & mode

| Action | Qt GUI | TUI |
|---|---|---|
| Voice picker | `Ctrl+Shift+V` | `Ctrl+T` |
| Speech Cursor mode | `Tab` | `Tab` |

### Highlighting (Qt GUI)

| Action | How |
|---|---|
| Highlight selection in yellow | `Ctrl+H` toolbar button or Highlight menu |
| Choose highlight color | Highlight menu (yellow / green / cyan / pink / orange) |
| Clear all highlights | Clear Highlights toolbar button or Highlight menu |

### M-x Command Palette (TUI)

| Key | Action |
|---|---|
| `M-x` / `ESC x` / `F2` / `:` | Open the command palette |
| `Tab` | Cycle through completions |
| `↑` / `↓` | Browse command history |
| `Enter` | Execute the current command |
| `C-g` / `Esc` | Cancel |

All standard Emacs line-editing keys work inside the minibuffer (`C-a`, `C-e`, `C-f`, `C-b`, `C-d`, `C-k`, `C-u`, `C-w`, `C-y`, etc.).

---

## M-x Commands

Open the command palette with `M-x`, `F2`, or `:`. Begin typing any part of a command name and press `Tab` to complete.

### Document

| Command | Description |
|---|---|
| `open` | Open a local file |
| `open-url` | Fetch and open a URL |
| `close` | Close the current document |
| `reload` | Reload the current document from disk |
| `export-markdown` | Save the rendered document as a `.md` file |
| `export-braille` | Export a BRF braille file (requires `louis`) |
| `export-audio [fmt]` | Synthesise document to audio; `fmt` is `mp3` (default), `ogg`, `mp4`, or `wav` |
| `recent` | Pick from recently opened files |
| `cache-clear` | Delete the cached version of the current document |

### Speech

| Command | Description |
|---|---|
| `play` | Begin or resume TTS |
| `stop` | Stop TTS |
| `pause` | Pause TTS |
| `speak-line` | Read the current line without advancing |
| `rate-up` | Increase reading rate by 20 wpm |
| `rate-down` | Decrease reading rate by 20 wpm |
| `volume-up` | Increase TTS volume |
| `volume-down` | Decrease TTS volume |
| `tts-backend` | Switch TTS engine at runtime |
| `tts-voice` | Switch TTS voice by ID |
| `ssml-on` / `ssml-off` | Enable/disable SSML prosody markup |
| `speed <name>` | Apply a named speed preset: `skim`, `normal`, `study`, `slow` |
| `speed-add <name> <wpm>` | Define a new speed preset |
| `speed-list` | List all defined speed presets |

### Search & Navigation

| Command | Description |
|---|---|
| `search` | Search forward |
| `search-backward` | Search backward |
| `search-regex` | Search with a regular expression |
| `goto-line` | Jump to a line number |
| `chapter-list` | List document chapters / headings |
| `chapter-next` / `chapter-prev` | Navigate to adjacent chapter |
| `chapter-goto` | Jump to a named chapter |
| `bookmark-set` | Set a named bookmark at the current position |
| `bookmark-goto` | Jump to a named bookmark |
| `bookmark-list` | List all bookmarks for this document |
| `bookmark-delete` | Delete a named bookmark |

### Display

| Command | Description |
|---|---|
| `theme [name]` | Switch color theme |
| `line-numbers` | Toggle line numbers |
| `syntax-highlight` | Toggle code syntax highlighting |
| `wrap-width` | Set text wrap width in columns |
| `font-size-up` / `font-size-down` | Adjust font size (Qt GUI) |
| `font <family>` | Set font family (Qt GUI) |
| `table-mode` | Switch table reading: `structured`, `flat`, or `skip` |
| `footnote-mode` | Switch footnote handling: `inline`, `deferred`, or `skip` |
| `reading-level` | Show Flesch-Kincaid grade and ease score |

### Abbreviations & Numbers

| Command | Description |
|---|---|
| `abbrev-add` | Add a custom abbreviation expansion for TTS |
| `abbrev-list` | List all active abbreviation expansions |

### System

| Command | Description |
|---|---|
| `help` | Open the built-in help manual |
| `about` | Version, author, and license |
| `license` | Full GPL v3 license text |
| `settings` | Open `settings.json` in your system editor |
| `quit` | Exit `star` |

---

## Supported File Formats

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
| Textile | `.textile` | built-in |
| Creole | `.creole` | built-in |
| LaTeX | `.tex`, `.ltx` | built-in (Pandoc for complex files) |
| Org-mode | `.org` | built-in |
| R source | `.r` | built-in |
| R Markdown | `.rmd` | built-in |
| Jupyter Notebook | `.ipynb` | built-in |
| CSV | `.csv` | built-in |
| TSV | `.tsv` | built-in |
| Excel spreadsheet | `.xlsx` | `openpyxl` |
| Images (OCR) | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp` | `pytesseract` |
| Python source | `.py` | built-in |
| URL (HTTP / HTTPS) | `http://…`, `https://…` | built-in |
| Pandoc fallback | any Pandoc-supported format | `pandoc` binary or `pypandoc` |

**PowerPoint:** Slide titles are rendered as headings, body text as paragraphs, and speaker notes are appended after each slide.

**Spreadsheets:** CSV, TSV, and XLSX files are rendered as Markdown tables. Only cell values are spoken — delimiters and pipe characters are never read aloud.

**Code block skipping:** Fenced code blocks are skipped during TTS by default. Set `"tts_skip_code": false` to include them.

---

## TTS Backends

### pyttsx3 (default when installed)

`pyttsx3` wraps the platform's native TTS engine.

- **Windows** — SAPI5 (all Control Panel voices available)
- **macOS** — NSSpeechSynthesizer (all system voices available)
- **Linux** — eSpeak-NG

`pyttsx3` provides word-boundary callbacks for accurate word-by-word highlighting.

```bash
pip install pyttsx3
```

### eSpeak-NG

`star` drives eSpeak-NG directly as a subprocess. When an `on_word` callback is requested, `star` wraps the text in SSML with `<mark name="N"/>` tags between each word and runs eSpeak-NG in SSML mode (`-m`). eSpeak-NG emits `MARK N` lines to stdout as each word is spoken; a background reader thread fires the word-highlight callback with the same accuracy as pyttsx3's native callbacks.

| Platform | Install |
|---|---|
| Linux (Debian/Ubuntu) | `sudo apt install espeak-ng` |
| macOS | `brew install espeak` |
| Windows | Download from [github.com/espeak-ng/espeak-ng/releases](https://github.com/espeak-ng/espeak-ng/releases) |

The `espeak-ng` or `espeak` binary must be on your system PATH.

### Festival

Festival speech synthesis (Linux). The `festival` binary must be on your PATH.

### Coqui TTS

Neural TTS via the Coqui TTS Python library. High quality but requires a GPU-capable machine for real-time synthesis.

```bash
pip install TTS
```

### DECtalk

The legendary "Perfect Paul" synthesizer, now open source.

- Source: [github.com/dectalk/dectalk](https://github.com/dectalk/dectalk)
- Set `DECTALK_BIN` to the full path of `dtalk`/`dectalk`.
- Word highlighting uses a timer-based approximation.

### Silent (fallback)

When no TTS engine is available, `star` falls back to silent mode. All display, navigation, search, and export features continue to work.

### Switching Backends at Runtime

```
M-x tts-backend pyttsx3
M-x tts-backend espeak
M-x tts-backend festival
M-x tts-backend coqui
M-x tts-backend dectalk
M-x tts-backend none
```

---

## Word Highlighting

While TTS is playing, `star` highlights the word currently being spoken and keeps it scrolled into view.

**How it works:**

- **pyttsx3** — Word-boundary callbacks from the native SAPI5 / NSSpeechSynthesizer engine confirm the exact audio position. A background timer advances the highlight at the configured speech rate; callbacks correct the timer's estimate to keep the two in sync.
- **eSpeak-NG (direct)** — Text is wrapped in SSML with `<mark/>` elements before each word. eSpeak-NG outputs `MARK N` to stdout as each word begins; a reader thread fires the highlight callback with accuracy comparable to pyttsx3.
- **DECtalk / Festival / Coqui** — No word-level events are available. `star` uses the current reading rate (wpm) to advance the highlight on a timer.

The document view scrolls automatically to keep the highlighted word visible. In the terminal TUI the cursor tracks the highlighted line; in Qt the word is scrolled into view without stealing keyboard focus.

**Highlight timer and SAPI5 pacing (pyttsx3 backend):**

The highlight is driven by a background timer that fires once per word at the configured rate (`highlight_speed × tts_rate`). When pyttsx3 word callbacks are actively firing, the timer also applies a *pacing guard*: it will not run more than **4 words ahead** of the last callback-confirmed position, keeping the visual close to actual audio during engine startup or sentence transitions.

SAPI5 word callbacks can arrive 1–3 words late and sometimes stop firing entirely mid-utterance. To prevent the highlight from freezing while speech continues, the guard has a **1.5-second timeout**: if no callback has arrived within 1.5 s the guard is bypassed and the timer runs freely until the next callback resumes. This means a highlight that is slightly ahead of audio is always preferred over one that is stuck.

**Word-position map:**

At document load time `star` builds a word-position map that links every TTS word to its display line and column. The map uses a monotonically advancing, column-aware search: when the same word appears multiple times on a single line (`the cat and the dog`) each occurrence is matched in document order rather than all mapping back to the first. The search position never moves backward between words, which prevents common words from cascade-matching several lines before their actual display position and making the highlight appear stuck.

---

## Qt GUI Mode

The Qt GUI is the default mode when PyQt6 or PyQt5 is installed. No special flag is needed:

```bash
python star.py document.pdf
python star.py                   # opens to the welcome screen
```

To force the terminal interface even when Qt is available:

```bash
python star.py --tui document.pdf
```

### Menu Bar

**File menu**

| Item | Action |
|---|---|
| Open… | Open a file via a standard file dialog |
| Export › Export as Markdown… | Save document as `.md` |
| Export › Export as PDF… | Save document as `.pdf` (user highlights included) |
| Export › Export as Braille (BRF)… | Save document as `.brf` (requires `louis`) |
| Export › Export as Audio (MP3 / OGG / MP4)… | Synthesise document to an audio file (WAV always works; MP3/OGG/MP4 require ffmpeg or pydub) |
| Quit | Exit the application |

**Highlight menu**

| Item | Shortcut | Action |
|---|---|---|
| Highlight Yellow | — | Highlight selected text in yellow |
| Highlight Green | — | Highlight selected text in green |
| Highlight Cyan | — | Highlight in cyan |
| Highlight Pink | — | Highlight in pink |
| Highlight Orange | — | Highlight in orange |
| Clear All Highlights | — | Remove all highlights for this document |

> `Ctrl+H` is now the **Next Heading** shortcut (matching NVDA/JAWS convention). Use the toolbar Highlight button or the Highlight menu to apply colors.

**View menu**

| Item | Shortcut | Action |
|---|---|---|
| Toggle Contents Panel | `Ctrl+\` | Show/hide the Table of Contents dock |
| Next Theme | `F5` | Cycle through all themes (built-in + CSS) |
| Choose Theme… | — | Pick any theme by name from a list |
| Reload CSS Themes | — | Rescan the themes folder without restarting |
| Open Themes Folder | — | Open the themes folder in the system file manager |
| Change Font… | — | Open the OS font picker to choose family, style, and size |
| Reading Level | `Ctrl+L` | Show Flesch-Kincaid reading level |

### Toolbar

The toolbar is divided into labelled groups separated by dividers:

| Group | Buttons |
|---|---|
| **File** | Open · URL |
| **Playback** | Play/Pause ▶⏸ · Stop ■ · − Speed · + Speed |
| **Navigate** | ◀ S (prev sentence) · ↺ S (replay sentence) · S ▶ (next sentence) · ◀ ¶ · ↺ ¶ · ¶ ▶ · ◀ H (prev heading, read) · H ▶ (next heading, read) |
| **Voice / Mode** | Voice… · SC ○ |
| **Text** | Copy · Highlight · Clear Highlights |
| **View** | Theme · ToC · Level · Font |
| **Edit** | Edit · Save |
| **App** | Help · Quit |

Every button shows a tooltip describing its action and keyboard shortcut.

### Table of Contents Panel

The left-side dock panel lists all headings found in the current document. It is populated automatically when a file is opened and updates whenever the document changes. Click any entry to scroll the document to that heading and stop at that position. Toggle the panel with `Ctrl+\` or **View → Toggle Contents Panel**; its visibility is saved in settings.

### User Text Highlighting

Select any range of text with the mouse or keyboard, then use the **Highlight toolbar button** (yellow) or choose a color from the **Highlight menu**. `Ctrl+H` is reserved for heading navigation and no longer triggers highlighting.

Highlights are stored in `settings.json` keyed by document path and restored automatically the next time the file is opened. When you export the document as a PDF (**File → Export → Export as PDF…**), the highlights are baked into the output.

To remove all highlights for the current document, use the **Clear Highlights** toolbar button or choose **Highlight → Clear All Highlights**.

### Font Selection

**View → Change Font…** opens the operating system's native font picker. You can choose:

- **Family** — any font installed on your system (scrollable, searchable list)
- **Style** — Regular, Bold, Italic, Bold Italic
- **Size** — numeric point size with live preview

The dialog opens pre-populated with your current family and size. Both selections are applied immediately and persisted in `settings.json` under `qt_font_family` and `qt_font_size`.

Fonts well-suited for readers with dyslexia include **OpenDyslexic**, **Lexie Readable**, and **Atkinson Hyperlegible**. Install the font on your system, then select it here.

### High-DPI Support

`star` applies `HighDpiScaleFactorRoundingPolicy.PassThrough` (PyQt6) or `AA_EnableHighDpiScaling` (PyQt5) before creating the `QApplication`, so the window renders crisp on 4K and HiDPI displays. Set `"qt_hidpi": false` in `settings.json` to disable this if it causes scaling problems.

### AT-SPI2 Accessibility

The document view has `accessibleName` and `accessibleDescription` set so that Orca and other AT-SPI2 consumers can inspect it. On Linux, running `star` alongside Orca in a standard GNOME session should work without special configuration.

---

## User Highlights

User-created highlights are saved per document path in `settings.json` under the `user_highlights` key:

```json
"user_highlights": {
  "/home/user/papers/thesis.pdf": [
    {"start": 1240, "end": 1298, "color": "#ffff00"},
    {"start": 3500, "end": 3612, "color": "#90ee90"}
  ]
}
```

- `start` and `end` are character offsets in the rendered Qt document text.
- `color` is any CSS hex color string.
- Highlights are displayed using `QTextEdit.setExtraSelections()` — they do not modify the document and do not interfere with TTS word highlighting, which is layered on top.
- PDF export temporarily applies the highlight formats to the document before printing, then reverts by reloading the HTML.

---

## Table of Contents

The Contents panel is populated by scanning the document's Markdown for heading lines (`#`, `##`, etc.). Each heading becomes a list entry; heading level is indicated by indentation. Clicking an entry calls `QTextDocument.find()` to locate the heading text and scrolls to it.

For EPUB files, the chapter list is also derived from the NCX or NAV navigation document (see [EPUB Navigation](#epub-navigation)) and made available through `M-x chapter-list` and `M-x chapter-goto` in both TUI and Qt modes.

---

## EPUB Navigation

`star` parses EPUB navigation data to provide chapter-level navigation for long books:

- **EPUB 3 NAV** — Reads the `<nav epub:type="toc">` element from the navigation document listed in the OPF manifest with `properties="nav"`.
- **EPUB 2 NCX** — Falls back to the `.ncx` file referenced by the `<spine toc="…">` attribute or identified by `media-type="application/x-dtbncx+xml"` in the manifest.

Extracted chapters are available via:

```
M-x chapter-list        # list all chapters with their indices
M-x chapter-goto        # jump to a chapter by name or index
M-x chapter-next        # move to the next chapter
M-x chapter-prev        # move to the previous chapter
```

In the Qt GUI the Contents panel shows all headings extracted from the rendered text; for EPUBs this closely mirrors the NCX/NAV structure.

---

## DAISY / DTBook Support

`star` parses DTBook XML natively and supports the DAISY 3 digital talking book format:

- **DTBook XML** (`.xml`, `.daisy`) — parsed directly.
- **Bookshare ZIP downloads** — pass the `.zip` path; `star` unpacks and locates the content automatically.
- **Archive.org DAISY books** — pass the direct URL to an `.xml` or `.zip` file.

Structure navigation follows the DTBook element hierarchy. Reading order follows the `<spine>` or `<book>` element sequence.

---

## Document Caching

`star` caches the parsed text and word map for each document in:

| Platform | Cache path |
|---|---|
| Linux | `~/.config/star/cache/` |
| macOS | `~/Library/Application Support/star/cache/` |
| Windows | `%APPDATA%\star\cache\` |

On subsequent opens `star` checks the file's modification time; if the file hasn't changed and the settings fingerprint matches, the cached result is used immediately — making reopening a large PDF or running Pandoc conversion on startup instant.

Cache files are JSON-formatted and named by a hash of the file path and settings. To force a fresh parse:

```
M-x cache-clear
```

Configure caching in `settings.json`:

```json
"document_cache": true,
"cache_max_size_mb": 100
```

---

## Footnote Handling

Markdown and Pandoc-style footnotes (`[^1]`, `[^label]`) are recognized and handled according to the `footnote_mode` setting:

| Mode | Behavior |
|---|---|
| `inline` (default) | Footnote text is inserted at the reference point: *word (footnote: text)* |
| `deferred` | Footnote references are removed; footnote text is collected and appended as a "## Footnotes" section at the end |
| `skip` | All footnote markers and definitions are silently removed |

Change at runtime:

```
M-x footnote-mode inline
M-x footnote-mode deferred
M-x footnote-mode skip
```

---

## OCR Support

`star` uses [Tesseract](https://github.com/tesseract-ocr/tesseract) via `pytesseract` for image-based PDFs and standalone image files.

```bash
pip install pytesseract pymupdf
```

| Platform | Tesseract install |
|---|---|
| Linux (Debian/Ubuntu) | `sudo apt install tesseract-ocr tesseract-ocr-eng` |
| macOS | `brew install tesseract` |
| Windows | Download from [github.com/tesseract-ocr/tesseract/releases](https://github.com/tesseract-ocr/tesseract/releases) |

Configure the language pack in `settings.json`:

```json
"ocr_lang": "eng+spa"
```

`star` uses PyMuPDF to render each page to a bitmap, then Tesseract to recognize the text. Text-layer PDFs are always preferred; OCR is triggered only when no text layer is detected.

---

## Math Normalization

When `"normalize_math": true` (the default), `star` converts common LaTeX and inline math expressions to natural English before TTS:

- `x^2` → "x squared"
- `\sqrt{x}` → "square root of x"
- `\frac{a}{b}` → "a over b"
- `x_i` → "x sub i"
- Greek letters: `\alpha` → "alpha", `\pi` → "pi", etc.
- Operators: `\times` → "times", `\leq` → "less than or equal to", etc.

This normalization also applies to MathML-embedded math extracted from EPUB and HTML documents.

---

## Braille Support

**Braille display passthrough** — On Linux, BrlTTY intercepts curses output and routes it to a connected braille display automatically. On Windows, NVDA and JAWS handle braille display routing.

**BRF file export** — Export the current document to a Braille Ready Format file:

- TUI: `M-x export-braille`
- Qt GUI: **File → Export → Export as Braille (BRF)…**

Requires the `louis` Python binding:

```bash
pip install louis
```

The braille translation table is configurable:

```json
"braille_table": "en-ueb-g2.ctb"
```

| Table file | Description |
|---|---|
| `en-ueb-g1.ctb` | UEB Grade 1 (uncontracted) |
| `en-ueb-g2.ctb` | UEB Grade 2 (contracted, default) |
| `es-g1.ctb` | Spanish Grade 1 |
| `nemeth.ctb` | Nemeth Code for mathematics |

---

## Audio Export

`star` can synthesise an entire document to an audio file using whatever TTS backend is currently active. This is useful for creating offline listening copies, sharing recordings, or integrating with other tools.

**How to export:**

- **Qt GUI:** **File → Export → Export as Audio (MP3 / OGG / MP4)…** — opens a save dialog; synthesis runs in a background thread so the window stays responsive.
- **TUI:** `M-x export-audio [fmt]` — prompts for a file path; synthesis is synchronous (the TUI is unresponsive until complete). Use a short document or a fast backend (pyttsx3/eSpeak) to minimise wait time.

**Output formats:**

| Format | Extension | Extra requirement |
|---|---|---|
| WAV | `.wav` | None — always works |
| MP3 | `.mp3` | **ffmpeg** (recommended) or `pydub` |
| OGG Vorbis | `.ogg` | **ffmpeg** or `pydub` |
| MP4 (audio-only AAC) | `.mp4` | **ffmpeg** or `pydub` |

The output format is inferred automatically from the file extension you choose.

**Backend support for audio export:**

| Backend | Mechanism |
|---|---|
| pyttsx3 | `engine.save_to_file()` → WAV |
| eSpeak-NG | `-w wav_path` flag |
| Festival | `text2wave` helper (or Festival Scheme fallback) |
| Coqui TTS | Coqui synthesis API → WAV |
| DECtalk | `-w` flag |
| Silent | Not supported (raises an error) |

**Format conversion pipeline:** The backend always produces a WAV file first. If the requested format is not WAV, `star` converts it using:

1. **ffmpeg** (preferred) — install from [ffmpeg.org](https://ffmpeg.org/download.html) or via your package manager.
2. **pydub** (pure-Python fallback) — `pip install pydub`.
3. If neither is available and the format is not WAV, export raises a clear error with installation instructions.

```bash
# Install ffmpeg (Linux)
sudo apt install ffmpeg

# Install ffmpeg (macOS)
brew install ffmpeg

# Pure-Python fallback (all platforms)
pip install pydub
```

**Example workflow:**

```
M-x export-audio          # prompts for path; defaults to <docname>.mp3
M-x export-audio wav      # defaults to <docname>.wav (no extras needed)
M-x export-audio ogg      # defaults to <docname>.ogg
```

In the Qt GUI, the file dialog filter shows `*.mp3 *.ogg *.mp4 *.wav`; you can type any extension and the format will be inferred.

---

## Speed Presets

Named speed presets let you switch reading rate with a single command:

| Preset | Default wpm | Use case |
|---|---|---|
| `skim` | 350 | Quick overview |
| `normal` | 265 | General reading (default) |
| `study` | 200 | Careful study |
| `slow` | 150 | Difficult or unfamiliar material |

```
M-x speed skim          # switch to skim preset
M-x speed normal        # switch to normal preset
M-x speed-add fast 400  # define a new preset named "fast" at 400 wpm
M-x speed-list          # show all presets and their rates
```

Presets are stored in `settings.json` under `speed_presets` and can be freely edited.

---

## Bookmarks

Set named bookmarks at the current reading position and jump back to them later:

```
M-x bookmark-set introduction    # bookmark the current position as "introduction"
M-x bookmark-goto introduction   # jump to the "introduction" bookmark
M-x bookmark-list                # show all bookmarks for this document
M-x bookmark-delete introduction # remove the "introduction" bookmark
```

Bookmarks are stored per document path in `settings.json` under `bookmarks` and survive between sessions.

---

## History Navigation

`star` tracks recently visited positions within a session. Navigate the history with:

| TUI key | Action |
|---|---|
| `Alt+Left` | Go back to the previous position |
| `Alt+Right` | Go forward |

The history depth defaults to 50 entries and is configurable via `"nav_history_size"` in `settings.json`.

---

## Document Editing (Qt GUI)

`star` includes a **Markdown edit mode** that lets you correct OCR errors, add notes, or revise any document in place.

### Entering and leaving edit mode

| Action | Key / button |
|---|---|
| Enter edit mode | `Ctrl+E` or the **Edit** toolbar button |
| Exit edit mode (discard changes) | `Ctrl+E` again |
| Save and return to read mode | `Ctrl+S` or the **Save** toolbar button |

When edit mode is active the status bar shows **✏ EDIT MODE — Markdown source**. The editor switches from rendered HTML to the raw Markdown source so you are editing the actual document text, not an HTML approximation.

### Editing shortcuts (standard text-editor conventions)

| Key | Action |
|---|---|
| `Ctrl+Z` | Undo |
| `Ctrl+Y` (or `Ctrl+Shift+Z`) | Redo |
| `Ctrl+X` | Cut |
| `Ctrl+C` | Copy |
| `Ctrl+V` | Paste |
| `Ctrl+A` | Select all |
| `Delete` / `Backspace` | Delete forward / backward |
| Arrow keys | Move cursor |
| `Shift+Arrow` | Extend selection |
| `Ctrl+Arrow` | Move by word |
| `Home` / `End` | Start / end of line |
| `Ctrl+Home` / `Ctrl+End` | Start / end of document |

### Saving

`Ctrl+S` writes the edited Markdown back to the **original file** when the source has a text-based extension (`.md`, `.markdown`, `.txt`, `.rst`, `.org`, `.adoc`). For PDF, DOCX, EPUB, and other binary formats a **Save As** dialog opens so you can choose a Markdown output path. After saving, `star` re-renders the HTML, rebuilds the Table of Contents, and rebuilds the TTS word maps.

### What “edit mode” edits

The editor works on the Markdown representation of the document (the same text that `M-x export-markdown` would produce). For formats like PDF or DOCX this is a converted approximation — useful for fixing OCR errors or adding annotations, but not a round-trip back to the original binary format.

---

## Screen Reader Compatibility

| Screen Reader | Platform | Notes |
|---|---|---|
| NVDA | Windows | Full compatibility; braille routing via NVDA braille display support |
| JAWS | Windows | Full compatibility; use virtual cursor mode |
| Orca | Linux | Full compatibility; AT-SPI2 metadata exposed on the Qt document view |
| VoiceOver | macOS | Compatible with Terminal.app and iTerm2 |

**Design decisions:**

- **Cursor parking (TUI)** — The terminal cursor stays at the minibuffer. Screen readers tracking the system cursor receive text echoed in one predictable location.
- **AT-SPI2 (Qt)** — The document view widget has `accessibleName="Document View"` and a descriptive `accessibleDescription`, enabling Orca to inspect the reading area.
- **Screen-reader navigation conventions** — Qt GUI navigation shortcuts follow NVDA/JAWS/VoiceOver muscle memory: `Ctrl+H` next heading, `Ctrl+Shift+H` previous heading, `Ctrl+P`/`Ctrl+T` for paragraph/table, and so on.
- **No auto-scrolling interference** — The document scrolls visually, but the cursor does not follow.
- **High-contrast theme** — `--theme contrast` or `M-x theme contrast` for maximum legibility.
- **`--plain` mode** — Extracts clean text to stdout, ideal for piping to other AT tools.

---

## Color Themes

### Built-in themes

| Name | Description |
|---|---|
| `dark` | Modern dark — cyan, blue, and magenta on a dark background (default) |
| `light` | Dark text on white with blue and magenta accents |
| `contrast` | Bold white and cyan on pure black — maximum legibility for low-vision users |
| `phosphor` | Classic green phosphor monochrome |

No built-in theme places red and green as adjacent accent colors, ensuring usability for deuteranopia and protanopia. Luminance contrast ratios meet or exceed WCAG 2.1 AA.

Switch themes:
- **Qt GUI:** `F5` to cycle, or **View → Choose Theme…** to pick by name
- **TUI:** `F5` to cycle, or `M-x theme <name>`
- **Command line:** `python star.py --theme contrast`

---

## CSS Theme Customization (Qt GUI)

The Qt GUI supports fully custom CSS themes. Each theme is a plain `.css` file stored in the **themes folder**. `star` discovers all `.css` files there automatically.

### Themes folder location

| Platform | Path |
|---|---|
| Linux | `~/.config/star/themes/` |
| macOS | `~/Library/Application Support/star/themes/` |
| Windows | `%APPDATA%\star\themes\` |

The folder is created on first launch. The four built-in themes are written there as `.css` files so you have ready-made starting points to copy and edit.

### Creating a custom theme

1. **Open the themes folder** — **View → Open Themes Folder** opens it in your system file manager.
2. **Copy any existing `.css` file** and give it a new name, e.g. `solarized.css`.
3. **Edit it** with any text editor — it is standard CSS.
4. **Reload** — **View → Reload CSS Themes** (or restart `star`) makes the new theme available.
5. **Switch** — press `F5` to cycle to it, or use **View → Choose Theme…** to pick it by name.

### CSS file format

A theme file is a plain `.css` file. The filename (without extension) becomes the theme name. Any valid CSS that Qt’s HTML renderer understands can be used.

`star` parses the following rules to extract the palette values it needs for the editor widget (`background-color`, `color`, `selection-background-color`):

| CSS rule | Palette key extracted |
|---|---|
| `body { background: …; }` | Editor background color |
| `body { color: …; }` | Editor foreground / text color |
| `::selection { background: …; }` | Text selection highlight color |
| `h1 { color: …; }` | Heading level 1 color |
| `h2 { color: …; }` | Heading level 2 color |
| `h3 { color: …; }` | Heading level 3 color |
| `h4 { color: …; }` | Heading level 4 color |
| `code { color: …; }` | Inline code color |

Any rule not present in the file falls back to the built-in `dark` palette value, so a minimal theme file only needs to specify the colors it wants to change.

The **full CSS** in the file is injected verbatim into the `<style>` block of every rendered document, so any additional selectors you write (`blockquote`, `table`, `a`, custom classes, etc.) are applied directly.

### Annotated example: Solarized Dark

```css
/* star CSS theme: Solarized Dark
 * Copy this file, rename it, and edit freely.
 * star picks up any *.css file in this directory automatically.
 * Run  View → Reload CSS Themes  (or restart) to apply changes.
 */

body {
    background: #002b36;   /* base03  — dark background */
    color:      #839496;   /* base0   — body text */
    font-family: Georgia, serif;
    margin: 14px;
    line-height: 1.6;
}

::selection {
    background: #073642;   /* base02  — selection highlight */
}

h1 { color: #268bd2; }    /* blue */
h2 { color: #2aa198; }    /* cyan */
h3 { color: #859900; }    /* green */
h4 { color: #b58900; }    /* yellow */

code {
    color:       #cb4b16;  /* orange */
    font-family: monospace;
}

pre {
    color:       #cb4b16;
    font-family: monospace;
    white-space: pre-wrap;
}

/* Extra styling beyond the built-in palette — fully supported */
blockquote {
    border-left: 3px solid #586e75;
    margin-left: 8px;
    padding-left: 12px;
    color: #657b83;
}

table {
    border-collapse: collapse;
    width: 100%;
}

th, td {
    border: 1px solid #073642;
    padding: 4px 8px;
}

th {
    background: #073642;
    color: #93a1a1;
}
```

### Tips

- **Qt’s HTML renderer** supports a useful subset of CSS 2.1. Most color, font, margin, padding, and border properties work. CSS variables (`var()`) and `:root {}` are **not** supported.
- **Hex colors** (`#rrggbb`, `#rrggbbaa`), **named colors** (`white`, `salmon`), and **`rgb()`/`rgba()`** all work.
- **Any extra selectors** you add (`a`, `blockquote`, `table`, `td`, `th`, `ul`, `ol`, `li`, etc.) are applied directly to the rendered document.
- **The themes folder is never cleared** by `star`. Your custom files are always preserved across updates.
- **Reload without restarting** — **View → Reload CSS Themes** rescans the folder and re-applies the current theme in one click.
- To **share a theme**, give someone your `.css` file; they drop it in their own themes folder.

---

## Settings

`star` stores preferences in `settings.json`, created automatically on first run.

**File location:**

| Platform | Path |
|---|---|
| Linux | `~/.config/star/settings.json` |
| macOS | `~/Library/Application Support/star/settings.json` |
| Windows | `%APPDATA%\star\settings.json` |

**All settings keys:**

| Key | Default | Description |
|---|---|---|
| `theme` | `"dark"` | Color theme: `dark`, `light`, `contrast`, `phosphor` |
| `tts_backend` | `"auto"` | TTS engine: `auto`, `pyttsx3`, `espeak`, `festival`, `coqui`, `dectalk`, `none` |
| `tts_rate` | `265` | Reading speed in words per minute |
| `tts_volume` | `1.0` | Volume from `0.0` (silent) to `1.0` (full) |
| `tts_voice` | `""` | Voice ID; empty = system default |
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
| `braille_table` | `"en-ueb-g2.ctb"` | liblouis translation table |
| `highlight_current_word` | `true` | Highlight the spoken word during TTS |
| `highlight_color` | `"cyan"` | TTS word highlight color |
| `highlight_speed` | `1.0` | Highlight timer speed as a fraction of `tts_rate`; `1.0` = match speech exactly. Values below `1.0` slow the timer (highlight lags audio); values above `1.0` run it faster. The pacing guard caps how far the timer can lead confirmed audio, so raising this above `1.0` does not cause runaway drift. |
| `recent_files` | `[]` | Recently opened files (populated automatically) |
| `recent_files_limit` | `20` | Maximum entries in the recent files list |
| `gui_width` | `1000` | Qt window width in pixels |
| `gui_height` | `700` | Qt window height in pixels |
| `qt_font_family` | `"Georgia"` | Qt display font family |
| `qt_font_size` | `14` | Qt display font size in pt |
| `qt_hidpi` | `true` | Enable high-DPI scaling in the Qt GUI |
| `qt_show_toc` | `true` | Show the Contents panel at startup |
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

---

## Plain-Text Mode

```bash
python star.py --plain document.pdf
```

`--plain` skips all UI and writes clean, stripped plain text to stdout — the same text the TTS engine would receive. Useful for:

- **Piping** — `python star.py --plain paper.pdf | festival --tts`
- **Batch processing** — extract text from many files in a shell script
- **Word counting** — `python star.py --plain thesis.pdf | wc -w`
- **Headless server use** — where no display is available

---

## Command-Line Options

```
python star.py [OPTIONS] [FILE_OR_URL]
```

| Option | Description |
|---|---|
| `FILE_OR_URL` | File path or HTTP/HTTPS URL to open on launch |
| `--gui` | Force Qt GUI mode (errors if PyQt6/PyQt5 not installed) |
| `--tui` | Force terminal UI mode even when Qt is available |
| `--plain` | Extract clean text to stdout; no UI |
| `--rate RATE` | Initial TTS reading rate in wpm |
| `--theme THEME` | Initial color theme: `dark`, `light`, `contrast`, `phosphor` |
| `--backend BACKEND` | TTS backend: `auto`, `pyttsx3`, `espeak`, `festival`, `coqui`, `dectalk`, `none` |
| `--keytest` | Open the key-code diagnostic tool (TUI only) |
| `--list-themes` | Print available theme names and exit |
| `--list-voices` | Print available TTS voice IDs and exit |
| `--version` | Print version number and exit |
| `--help` | Print help summary and exit |

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request for anything beyond small bug fixes.

**The most important rule: keep `star` a single Python file.** All logic must live in `star.py`. Optional dependencies are imported at runtime with graceful fallbacks — this is the existing pattern and must be maintained. Do not split the project into a package, add a `setup.py` build step, or require compilation.

Other guidelines:

- Target Python 3.8 compatibility. Do not use syntax or standard library features introduced after 3.8.
- All new keybindings must be documented in `README.md` (opened by `F1` in the Qt GUI) and in this file.
- New M-x commands must be added to both the command dispatch table and the Tab-completion list.
- New file format handlers should degrade gracefully when the required package is absent.
- Follow the existing code style — no external formatters mandated, but keep lines ≤ 100 characters and write docstrings for all public functions.
- This project is licensed under the GPL v3. By submitting a pull request you agree your contribution will be released under the same license.

---

## License

`star` — Speaking Terminal Access Reader  
Copyright 2026 Jon Pielaet

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License version 3** as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but **without any warranty** — without even the implied warranty of merchantability or fitness for a particular purpose. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

To view the full license text from within `star`, run:

```
M-x license
```
