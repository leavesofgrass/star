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
star                 # launch the Qt GUI
star document.pdf    # open a file
star --tui           # force the terminal UI
star --deps          # show which optional features are installed
```

Add optional features with extras — `pip install "star-reader[all]"` for the
full feature set (everything except the multi-GB Whisper/Torch dictation stack,
which is `[transcribe]`), or groups like `star-reader[translate,vocab]`. Full
instructions (wheel, single-file `star.pyz`, native engines, per-platform notes)
are in the **[Installation guide](docs/installation.md)**.

---

## ✨ Highlights

- **Reads aloud with live word highlighting** in both the Qt GUI and the terminal
  TUI — including in-process eSpeak-NG with true audio-position sync.
- **Many TTS engines:** pyttsx3 (SAPI5 / NSSpeechSynthesizer), macOS `say`,
  eSpeak-NG, Festival, **Piper** (neural, offline, free), Coqui, and DECtalk.
- **Opens almost anything:** PDF (incl. OCR), DOCX, PPTX, EPUB, HTML, Markdown,
  spreadsheets, DAISY/DTBook, and dozens more formats.
- **Study tools:** notes & annotations, a citation manager, summarization, Anki
  flashcard export, document translation (15 languages, no API key), RSS/Atom
  feed reading, and a difficult-word overlay.
- **Knowledge graph:** link annotations across documents with typed relations
  (`CONFLICTS_WITH`, `SUPPORTS`, `CITES`, …), extract concepts, view the graph
  interactively, and export to SVG/PlantUML/DOT/JSON.
- **Export:** Markdown, PDF (with highlights), BRF braille, TTS audio
  (WAV/MP3/OGG/MP4), and synchronized SRT/VTT subtitles.
- **Accessibility-first:** NVDA/JAWS/Orca/VoiceOver compatible, four
  colorblind-friendly themes + custom CSS themes, dyslexia-friendly font, bionic
  reading, adjustable spacing (WCAG 1.4.12), and high-DPI support.
- **Graceful degradation:** every third-party dependency is optional and guarded,
  so the core runs on the Python standard library alone.

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
