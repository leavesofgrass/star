# ⭐ star — Speaking Terminal Access Reader

[![CI](https://github.com/leavesofgrass/star/actions/workflows/ci.yml/badge.svg)](https://github.com/leavesofgrass/star/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/star-reader.svg)](https://pypi.org/project/star-reader/)
[![Python](https://img.shields.io/pypi/pyversions/star-reader.svg)](https://pypi.org/project/star-reader/)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

> **star** is an accessible, **GUI-first** document reader and Markdown
> authoring tool with built-in text-to-speech. It opens PDFs,
> Word/EPUB/PowerPoint, web pages, spreadsheets, and more, reads them aloud, and
> **highlights each word as it is spoken** — with no cloud account and no
> internet required. You can also **write** in it: create documents from
> scratch, format Markdown, and dictate straight into the text.

`star` is built for students with print disabilities — people who work with
dense, heavily formatted documents and need a reading tool that gets out of the
way. The **Qt GUI is the primary interface** (it launches by default and is where
development is focused), with a keyboard shortcut for every command; a
full-featured, keyboard-driven curses **terminal UI** remains available with
`--tui` for headless or text-only environments.

It draws design inspiration from [Emacspeak](https://emacspeak.sourceforge.net/),
[Kurzweil 1000](https://www.kurzweiledu.com/),
[Natural Reader](https://www.naturalreaders.com/), and
[Central Access Reader](https://www.readingmadeeasy.com/).

---

## 🚀 Quick start

**Install** on any platform with **Python 3.11+**:

```bash
pipx install star-reader        # isolated app install (recommended)
# or:  pip install star-reader  # into the current environment
```

star **grows on demand** — it fetches optional features the first time you use
them, so you don't need to pick extras up front. Want everything available
offline right away? `pipx install "star-reader[all]"`.

**Run it:**

```bash
star                 # launch the Qt GUI (the primary interface)
star document.pdf    # open a document
star --tui           # force the terminal UI (headless / text-only)
```

**Your first 60 seconds** (in the GUI):

- Press **`Ctrl+O`** to open a document — or just read the welcome page it opens on.
- Press **`Space`** to hear it read aloud, with **each word highlighted** as it's spoken.
- Put the caret on a word and press **`Ctrl+D`** for an offline definition.
- Press **`Ctrl+N`** to start writing your own document; **`Ctrl+E`** toggles edit mode.

**Where next:**

- Worked examples: **[`docs/examples/`](docs/examples/)** — extract text on the CLI, load
  documents from Python, and read-aloud / authoring walkthroughs.
- Full docs: **[Usage guide](docs/usage_guide.md)** ·
  **[Features](docs/features.md)** · **[Installation](docs/installation.md)**.

### Optional features

**star runs out of the box** on nothing but the Python standard library, and
**grows on demand — no `pip install` step anywhere.** Whenever you reach for a
feature that needs an add-on (OCR, offline dictionary, summarize, translate,
knowledge-graph extras, dictation, …), star offers to **download it in the
background** and the feature then works **in the same session** — no restart. On
first launch the GUI also shows a short **optional-features chooser**: pick the
**Thin** or **All** preset (All means literally everything, download sizes shown
upfront), or tick exactly the capabilities you want. Re-open it any time from
**Tools → Install Optional Features…**.

Prefer the command line or a scripted setup? `star --deps` shows what's
installed; `star --install-optional` fetches the `all` preset, and
`star --install-optional thin` or `star --install-optional ocr,dictionary` a
preset or a comma-separated list (`star --install-optional help` lists every
feature with its size); `star --plugins list` shows the pluggable
backends/formats/exporters; `star --check-update` checks PyPI. Classic extras
still work too — `pip install "star-reader[all]"`, or groups like
`star-reader[translate,vocab]` — but the normal path is one click, in-app.

Full instructions (wheel, single-file `star.pyz`, native engines, per-platform
notes) are in the **[Installation guide](docs/installation.md)**.

---

## ✨ Highlights

### 🗣️ Reading aloud

- **Live word highlighting** in both the Qt GUI and the terminal TUI — and the
  highlight follows the *audio*, not a timer: in-process eSpeak-NG and
  Eloquence report each word's true audio position, and pyttsx3 / Qt speech
  deliver native word-boundary events.
- **Many TTS engines:** pyttsx3 (SAPI5 / NSSpeechSynthesizer), macOS `say`,
  **Eloquence** — the classic screen-reader voice, via open-source OpenEVV on
  Windows, with all eight classic voices (**Reed, Shelley, Bobby, Rod, Glen,
  Sandy, Grandma, Grandpa**) — Qt speech, eSpeak-NG, Festival, **Piper**
  (neural, offline, free), Coqui, and DECtalk.
- **Voice Manager (F4):** browse, filter, preview, and favorite voices, with
  one-click download of offline Piper neural voices. Opt-in **ElevenLabs cloud
  voices** stay private by default: text leaves your machine only after you set
  a key *and* choose the cloud voice, and any failure falls back to a local
  engine.

### 📖 Reading almost anything

- **Every format the Paperback reader opens, on the standard library alone:**
  PDF (incl. OCR), Word/PowerPoint (DOCX/DOCM, PPTX, and the legacy binary
  DOC/PPT), OpenDocument (ODT/ODP and flat XML), RTF and Windows Write, EPUB,
  FictionBook, MOBI/Kindle, CHM and WinHelp help files, DAISY 3 packages and
  DAISY 2.02 books, comic archives, M4B/MP3 audiobook chapters, manual pages,
  HTML, Markdown, spreadsheets, and dozens more.
- **Rich structure survives:** inline LaTeX math rendered as readable Unicode,
  accessible tables that keep their header structure, clickable footnotes
  (with a ↩ backlink), and image captions / alt text.
- **Fast on huge documents:** opt-in pagination renders only a window at a
  time, dropping first paint on a ~500-page file from seconds to well under
  one.

### ✍️ Writing & publishing

- **Write, don't just read:** create a document from scratch (**File ▸ New**,
  **Ctrl+N**), format Markdown from an edit-mode toolbar and a **Format** menu
  with full **Undo/Redo**, and **dictate straight into the text** with
  **Voice Typing** (**Tools ▸ Voice Typing**, **Ctrl+Alt+K**).
- **Export:** Markdown, HTML, EPUB, DOCX, PDF (with highlights), BRF braille,
  TTS audio (WAV/MP3/OGG/MP4), **chaptered M4B audiobooks**, karaoke video
  (MP4), Anki decks, and synchronized SRT/VTT subtitles.
- **Publish (F9):** styled, metadata-complete EPUB / Word / single-file HTML
  with bundled **Large Print**, **Dyslexia-friendly**, and **High Contrast**
  templates — or your own CSS / institution's `.docx` template — plus APA /
  AMA / Vancouver citations with an auto-generated bibliography.

### 🎓 Studying

- **Notes, highlights, and spaced repetition:** annotate anything, turn
  highlights and notes into a review deck (FSRS scheduler), review due cards
  in-app (**Study ▸ Review Due Cards…**), auto-generate cloze cards, and
  optionally two-way sync with Anki.
- **A study toolbelt:** a citation manager, summarization, document
  translation (15 languages, no API key), RSS/Atom feed reading, an offline
  dictionary (**Ctrl+D**), and a difficult-word overlay.
- **Knowledge graph:** link annotations across documents with typed relations
  (`CONFLICTS_WITH`, `SUPPORTS`, `CITES`, …), extract concepts, view the graph
  interactively, and export to SVG/PlantUML/DOT/JSON.
- **Find, bookmark, and search:** incremental find (**Ctrl+F**), named
  bookmarks (**Ctrl+M**) with back/forward history (**Alt+←/→**), and
  full-text search across every document in your library.

### ♿ Accessibility first

- **Screen readers are first-class:** NVDA / JAWS / Orca / VoiceOver
  compatible, with announcements for playback, loads, theme changes, and find
  results.
- **Reading aids for print disabilities:** a **Reading Font chooser**
  (**OpenDyslexic**, **Atkinson Hyperlegible**, **Lexend** — auto-fetched and
  applied across the whole UI), syllable splitting, a caret-tracking reading
  ruler, bionic reading, and adjustable spacing (WCAG 1.4.12).
- **23 themes** including high-contrast (AAA) and four colorblind-friendly
  palettes — every one clears WCAG AA, follows your OS light/dark setting, and
  custom CSS themes are welcome.
- **A translated interface** — terminal UI included — in Spanish, French,
  German, and Portuguese, with a first-run language picker; **right-to-left
  languages mirror the whole app** (Arabic is the first RTL catalog). A
  skippable **Guided Tour** replays any time (Shift+F1).

### 🧰 Sturdy by design

- **Runs on the standard library alone** — every third-party dependency is
  optional and guarded, and add-ons arrive through the one-click
  optional-features flow above.
- **Sync without losing work:** reading progress and annotations from two
  machines *merge* instead of last-write-wins — position resolves by a policy
  you pick, notes union by id.
- **Extensible:** TTS engines, document formats, and export targets are
  discovered through `importlib.metadata` entry points — a third-party plugin
  package adds backends, loaders, or exporters with no changes to star itself.
- **One tabbed Preferences dialog** (**Ctrl+,**) for every setting, an
  all-icon toolbar with descriptive tooltips, a readable welcome page, and
  **F1** opens the bundled README as a document on every install.

See the **[full feature reference](docs/features.md)** for everything.

---

## 📚 Documentation

| Guide | What's in it |
|---|---|
| **[Examples](docs/examples/)** | Runnable, task-focused examples (CLI text extraction, the Python library, read-aloud & authoring walkthroughs) with a catalog mapping every area |
| **[Installation](docs/installation.md)** | PyPI / wheel / zipapp install, optional packages, native engines, platform notes |
| **[Usage Guide](docs/usage_guide.md)** | Running star, the **quick command reference**, full keyboard map, M-x commands, CLI options |
| **[Features](docs/features.md)** | The complete feature reference |
| **[Knowledge Graph](docs/knowledge-graph.md)** | Typed relations between annotations, concept extraction, graph view, and export |
| **[Configuration](docs/configuration.md)** | Every `settings.json` key |
| **[Architecture & Contributing](docs/architecture.md)** | Package layout, distribution artifacts, contributing, tests |
| [Changelog](star/CHANGELOG.md) | Full record of changes |
| [Build guide](star/BUILD.md) | Building the cross-platform wheel and the self-contained Windows `star.exe` / macOS `.app` |

➡️ Browse all docs in the **[`docs/`](docs/)** directory.

---

## 📦 Distribution

The pure-Python **wheel** (`pip install star-reader`) is star's primary, stable
distribution; it works on macOS, Linux, and Windows alike. For anyone who can't
install Python, every GitHub Release also attaches double-click binaries for all
three desktops — a self-contained **Windows `star-<version>-windows-x64.exe`**
(Python, the GUI, and all loaders baked in; DECtalk excluded from the public
exe), a **macOS `star-<version>-macos-arm64.dmg`** (Apple-Silicon; uses the
built-in Apple voices), and a **Linux AppImage**. A single-file
[`star.pyz`](docs/installation.md#single-file-build-starpyz) zipapp is
build-it-yourself. See [Installation](docs/installation.md) and
[`BUILD.md`](star/BUILD.md).

---

## 🤝 Contributing

Contributions are welcome — please open an issue before a PR for anything beyond
small fixes. Keep every third-party dependency optional and guarded, target
Python 3.11, and document new keybindings and `M-x` commands. See
**[Architecture & Contributing](docs/architecture.md#contributing)** for the full
guidelines and how to run the test suite.

---

## 📜 License

`star` — Speaking Terminal Access Reader
Copyright 2026 Jon Pielaet

Free software under the **GNU General Public License version 3 or later**. This
program is distributed in the hope that it will be useful, but **without any
warranty**. See the [LICENSE](LICENSE) file, or run `M-x license` in the app, for
the full text.
