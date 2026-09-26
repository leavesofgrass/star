# ⭐ star — Speaking Terminal Access Reader

[![CI](https://github.com/leavesofgrass/star/actions/workflows/ci.yml/badge.svg)](https://github.com/leavesofgrass/star/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/star-reader.svg)](https://pypi.org/project/star-reader/)

> **star** is an accessible, **GUI-first** document reader and Markdown
> authoring tool with built-in text-to-speech. It opens PDFs,
> Word/EPUB/PowerPoint, web pages, spreadsheets,
> and more, reads them aloud, and **highlights each word as it is spoken** — with
> no cloud account and no internet required.

`star` is built for students with print disabilities — people who work with
dense, heavily formatted documents and need a reading tool that gets out of the
way. The **Qt GUI is the primary interface** (it launches by default and is where
development is focused), with a keyboard shortcut for every command; a
full-featured, keyboard-driven curses **terminal UI** remains available with
`--tui` for headless or text-only environments.

> 📖 **This is the in-app help summary.** The full documentation lives online:
> browse it at <https://github.com/leavesofgrass/star/tree/main/docs>.

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
full feature set (everything except the speech-to-text dictation stack, which is
`[transcribe]` — faster-whisper, ~140 MB), or groups like
`star-reader[translate,vocab]`. Full
instructions (wheel, single-file `star.pyz`, native engines, per-platform notes)
are in the
[Installation guide](https://github.com/leavesofgrass/star/blob/main/docs/installation.md).

---

## ✨ Highlights

- **Reads aloud with live word highlighting** in both the Qt GUI and the terminal
  TUI — the highlight follows the *audio*, not a timer.
- **Many TTS engines:** pyttsx3 (SAPI5 / NSSpeechSynthesizer), macOS `say`,
  **Eloquence** (the classic screen-reader voice via open-source OpenEVV on
  Windows, with exact word timing and all eight classic voices — Reed,
  Shelley, Bobby, Rod, Glen, Sandy, Grandma, Grandpa), Qt speech, eSpeak-NG,
  Festival, **Piper** (neural, offline, free), Coqui, and DECtalk — browse and
  preview them in the **Voice Manager** (**F4**).
- **Opens almost anything:** PDF (incl. OCR), Word/PowerPoint (DOCX/DOCM, PPTX,
  and the legacy binary DOC/PPT), OpenDocument (ODT/ODP and flat XML), RTF and
  Windows Write, EPUB, FictionBook, MOBI/Kindle, CHM and WinHelp help files,
  DAISY 3 packages and DAISY 2.02 books, comic archives, M4B/MP3 audiobook
  chapters, manual pages, HTML, Markdown, spreadsheets, and dozens more —
  every format the Paperback reader opens, on the standard library alone.
- **Write, don't just read:** create a document from scratch (**File ▸ New**,
  **Ctrl+N**), format Markdown from an edit-mode toolbar and a **Format** menu
  with full **Undo/Redo**, and **dictate straight into the text** with
  **Voice Typing** (**Tools ▸ Voice Typing**, **Ctrl+Alt+K**).
- **Study tools:** notes & annotations with spaced repetition (FSRS, optional
  Anki two-way sync), a citation manager, summarization, document translation
  (15 languages, no API key), RSS/Atom feed reading, an offline dictionary
  (**Ctrl+D**), a knowledge graph, and a difficult-word overlay.
- **Export & publish:** Markdown, HTML, EPUB, DOCX, PDF (with highlights), BRF
  braille, TTS audio (WAV/MP3/OGG/MP4), chaptered M4B audiobooks, karaoke
  video, Anki decks, and SRT/VTT subtitles — plus **Publish (F9)** for styled,
  metadata-complete EPUB / Word / HTML with accessibility templates and
  APA / AMA / Vancouver citations.
- **Accessibility-first:** NVDA/JAWS/Orca/VoiceOver compatible, 23 themes
  (high-contrast AAA and colorblind-friendly palettes included), a Reading
  Font chooser (OpenDyslexic, Atkinson Hyperlegible, Lexend), syllable
  splitting, a reading ruler, bionic reading, adjustable spacing
  (WCAG 1.4.12), and a translated, RTL-capable interface.
- **Graceful degradation:** every third-party dependency is optional and guarded,
  so the core runs on the Python standard library alone.

Press `F3` (Qt) or `?` (TUI) for the keyboard cheat sheet, and `F2` for the
command palette.

---

## 📚 Documentation

The complete documentation is online at
<https://github.com/leavesofgrass/star/tree/main/docs>:

| Guide | What's in it |
|---|---|
| [Installation](https://github.com/leavesofgrass/star/blob/main/docs/installation.md) | Install, optional packages, native engines, platform notes |
| [Usage Guide](https://github.com/leavesofgrass/star/blob/main/docs/usage_guide.md) | Running star, the quick command reference, full keyboard map, M-x commands |
| [Features](https://github.com/leavesofgrass/star/blob/main/docs/features.md) | The complete feature reference |
| [Configuration](https://github.com/leavesofgrass/star/blob/main/docs/configuration.md) | Every `settings.json` key |
| [Architecture & Contributing](https://github.com/leavesofgrass/star/blob/main/docs/architecture.md) | Package layout, distribution, contributing, tests |
| [Changelog](CHANGELOG.md) | Full record of changes |
| [Build guide](https://github.com/leavesofgrass/star/blob/main/BUILD.md) | Building the cross-platform wheel and the self-contained Windows `star.exe` |

---

## 📜 License

`star` — Speaking Terminal Access Reader
Copyright 2026 Jon Pielaet

Free software under the **GNU General Public License version 3 or later**. This
program is distributed in the hope that it will be useful, but **without any
warranty**. Run `M-x license` in the app for the full text.
