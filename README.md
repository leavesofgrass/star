# ⭐ star — Speaking Terminal Access Reader

[![CI](https://github.com/leavesofgrass/star/actions/workflows/ci.yml/badge.svg)](https://github.com/leavesofgrass/star/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/star-reader.svg)](https://pypi.org/project/star-reader/)
[![Python](https://img.shields.io/pypi/pyversions/star-reader.svg)](https://pypi.org/project/star-reader/)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

> **star** is an accessible, **GUI-first** document reader with built-in
> text-to-speech. It opens PDFs, Word/EPUB/PowerPoint, web pages, spreadsheets,
> and more, reads them aloud, and **highlights each word as it is spoken** — with
> no cloud account and no internet required.

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

## 🚀 Install

On any platform with **Python 3.11+**:

```bash
pipx install star-reader      # isolated app install (recommended)
# or
pip install star-reader       # into the current environment
```

Then run it:

```bash
star                          # launch the Qt GUI
star document.pdf             # open a file
star --tui                    # force the terminal UI
star --deps                   # show which optional features are installed
star --install-optional       # fetch optional features from the command line
star --plugins list           # list registered backends / formats / exporters
star --check-update           # check PyPI for a newer release (offline-safe)
```

### Optional features

**star runs out of the box** on nothing but the Python standard library, and
**grows on demand — no `pip install` step anywhere.** Whenever you reach for a
feature that needs an add-on (OCR, offline dictionary, summarize, translate,
knowledge-graph extras, …), star offers to **download it in the background** and
the feature then works in the same session — only the large speech-to-text pack
asks for a restart. On first launch the GUI also shows a short **optional-features
chooser**: pick the **Thin** or **All** preset, or tick exactly the capabilities
you want. Re-open it any time from **Tools → Install Optional Features…**. **"All"
now means literally everything** (including the large speech-to-text and
named-entity packs); the download size is shown upfront.

Prefer the command line or a scripted setup? `star --install-optional` installs
the `all` preset; `star --install-optional thin` or
`star --install-optional ocr,dictionary` install a preset or a comma-separated
list of features; run it with no value to list every feature with its size.
`star --plugins list` and `star --check-update` round out the CLI. Advanced users
can still install extras the classic way — `pip install "star-reader[all]"`, or
groups like `star-reader[translate,vocab]` — but the normal path is one click,
in-app.

Full instructions (wheel, single-file `star.pyz`, native engines, per-platform
notes) are in the **[Installation guide](docs/installation.md)**.

---

## ✨ Highlights

- **Reads aloud with live word highlighting** in both the Qt GUI and the terminal
  TUI — including in-process eSpeak-NG with true audio-position sync.
- **Many TTS engines + Voice Manager:** **Qt-native system voices** (your OS's
  built-in voices, no key or download, with per-word highlighting), pyttsx3
  (SAPI5 / NSSpeechSynthesizer), macOS `say`, eSpeak-NG, Festival, **Piper**
  (neural, offline, free), Coqui, DECtalk, and opt-in **ElevenLabs cloud neural
  voices** (text leaves your machine only after you set a key *and* choose the
  cloud voice; any failure falls back to a local engine) — browse, filter,
  preview, and favorite voices in the **Voice Manager (F4)**, with one-click
  download of offline Piper neural voices.
- **Opens almost anything:** PDF (incl. OCR), DOCX, PPTX, EPUB, HTML, Markdown,
  spreadsheets, DAISY/DTBook, and dozens more formats.
- **Find, bookmark, and search:** incremental **find in document (Ctrl+F)**, named
  **bookmarks (Ctrl+B)** with back/forward history (**Alt+←/→**), and **full-text
  search inside every document** in your library.
- **Study & spaced repetition:** turn highlights and notes into a review deck
  (FSRS scheduler), review due cards in-app (**Study ▸ Review Due Cards…**,
  Ctrl+Shift+F5), auto-generate cloze cards, and optionally two-way sync with Anki.
- **Study tools:** notes & annotations, a citation manager, summarization, Anki
  flashcard export, document translation (15 languages, no API key), RSS/Atom
  feed reading, and a difficult-word overlay.
- **Richer documents:** inline LaTeX math rendered as readable Unicode, accessible
  tables that keep their header structure, clickable footnotes (with a ↩ backlink),
  and image captions / alt text.
- **Knowledge graph:** link annotations across documents with typed relations
  (`CONFLICTS_WITH`, `SUPPORTS`, `CITES`, …), extract concepts, view the graph
  interactively, and export to SVG/PlantUML/DOT/JSON.
- **Export:** Markdown, HTML, EPUB, PDF (with highlights), BRF braille, TTS
  audio (WAV/MP3/OGG/MP4), **chaptered M4B audiobooks** (chapters from headings;
  needs ffmpeg), karaoke video (MP4), Anki decks, and synchronized SRT/VTT
  subtitles.
- **Extensible:** TTS engines, document formats, and export targets are
  discovered through `importlib.metadata` entry-points — installing a
  third-party plugin package adds backends, loaders, or exporters with no
  changes to star itself.
- **Accessibility-first:** NVDA/JAWS/Orca/VoiceOver compatible, screen-reader
  announcements for playback / load / theme / find results, a **high-contrast
  (AAA) theme** with automatic light / dark / high-contrast following your OS, a
  **Reading Font chooser** (**OpenDyslexic**, **Atkinson Hyperlegible**, **Lexend**
  — auto-fetched and applied across the whole UI), **syllable splitting**
  (display-only decoding aid), a caret-tracking **reading ruler**, four
  colorblind-friendly themes + custom CSS themes, bionic reading, adjustable
  spacing (WCAG 1.4.12), and high-DPI support.
- **Guided tour & translations:** a skippable first-run walkthrough (replay any
  time from **Help ▸ Guided Tour**, Shift+F1), Help ▸ Check for Updates, and a
  translatable TUI with a first-run language picker (Spanish, French, German,
  Portuguese). **Right-to-left interface languages mirror the whole app** —
  Arabic is included as a first catalog.
- **Fast on huge documents:** opt-in pagination renders only a window of a very
  large document at a time, dropping first paint on a ~500-page file from seconds
  to well under one (off by default).
- **Sync without losing work:** reading progress and annotations from two machines
  now *merge* instead of last-write-wins — position resolves by a policy you pick
  (newest / furthest / manual) and notes union by id.
- **Graceful degradation:** every third-party dependency is optional and guarded,
  so the core runs on the Python standard library alone.
- **One-click optional features:** when a capability needs an add-on, star
  downloads it in the background — **no `pip install` step anywhere** — and it
  works right away (only the large speech-to-text pack needs a restart). Driven by
  a first-run chooser or `star --install-optional`.
- **Clear, consistent UI:** an all-icon toolbar with descriptive tooltips (vector
  glyphs drawn programmatically and tinted to your theme — no image files); a
  **readable welcome page** that reads aloud like any document; and **F1** opens
  the bundled README as a document on every install.

See the **[full feature reference](docs/features.md)** for everything.

---

## 📚 Documentation

| Guide | What's in it |
|---|---|
| **[Installation](docs/installation.md)** | PyPI / wheel / zipapp install, optional packages, native engines, platform notes |
| **[Usage Guide](docs/usage_guide.md)** | Running star, the **quick command reference**, full keyboard map, M-x commands, CLI options |
| **[Features](docs/features.md)** | The complete feature reference |
| **[Knowledge Graph](docs/knowledge-graph.md)** | Typed relations between annotations, concept extraction, graph view, and export |
| **[Configuration](docs/configuration.md)** | Every `settings.json` key |
| **[Architecture & Contributing](docs/architecture.md)** | Package layout, distribution artifacts, contributing, tests |
| [Changelog](star/CHANGELOG.md) | Full record of changes |
| [Build guide](star/BUILD.md) | Building the cross-platform wheel (and the deprecated Windows `star.exe`) |

➡️ Browse all docs in the **[`docs/`](docs/)** directory.

---

## 📦 Distribution

The pure-Python **wheel** (`pip install star-reader`) is star's primary, stable
distribution and the only artifact produced by automated releases; it works on
macOS, Linux, and Windows alike. A single-file
[`star.pyz`](docs/installation.md#single-file-build-starpyz) zipapp and the
self-contained Windows `star.exe` (**deprecated**) are **build-it-yourself** —
they are no longer shipped with releases. See
[Installation](docs/installation.md) and [`BUILD.md`](star/BUILD.md).

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
