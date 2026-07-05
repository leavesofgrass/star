# ⭐ star — Speaking Terminal Access Reader

[![CI](https://github.com/leavesofgrass/star/actions/workflows/ci.yml/badge.svg)](https://github.com/leavesofgrass/star/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/star-reader.svg)](https://pypi.org/project/star-reader/)

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
full feature set (everything except the multi-GB Whisper/Torch dictation stack,
which is `[transcribe]`), or groups like `star-reader[translate,vocab]`. Full
instructions (wheel, single-file `star.pyz`, native engines, per-platform notes)
are in the
[Installation guide](https://github.com/leavesofgrass/star/blob/main/docs/installation.md).

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
- **Export:** Markdown, PDF (with highlights), BRF braille, TTS audio
  (WAV/MP3/OGG/MP4), and synchronized SRT/VTT subtitles.
- **Accessibility-first:** NVDA/JAWS/Orca/VoiceOver compatible, four
  colorblind-friendly themes + custom CSS themes, dyslexia-friendly font, bionic
  reading, adjustable spacing (WCAG 1.4.12), and high-DPI support.
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
| [Build guide](https://github.com/leavesofgrass/star/blob/main/BUILD.md) | Building the cross-platform wheel (and the deprecated Windows `star.exe`) |

---

## 📜 License

`star` — Speaking Terminal Access Reader
Copyright 2026 Jon Pielaet

Free software under the **GNU General Public License version 3 or later**. This
program is distributed in the hope that it will be useful, but **without any
warranty**. Run `M-x license` in the app for the full text.
