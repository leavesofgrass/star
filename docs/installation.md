# 📦 Installation

**Minimum Python version: 3.11**

`star` runs with nothing beyond the Python standard library. Every optional
package below unlocks additional file formats or features. Install only what you
need.

- [No Python? Download-and-run builds](#no-python-download-and-run-builds)
- [Easiest: install from PyPI](#easiest-install-from-pypi)
- [From a source checkout: the installer scripts](#from-a-source-checkout-the-installer-scripts)
- [Install from the wheel](#install-from-the-wheel-macos--linux--windows)
- [Single-file build: star.pyz](#single-file-build-starpyz)
- [Optional packages](#optional-packages)
- [External binary dependencies](#external-binary-dependencies)
- [Platform notes](#platform-notes)

---

## No Python? Download-and-run builds

Don't have Python, or find installing it and its dependencies a hassle? Every
release ships **self-contained binaries** on the
[GitHub Releases page](https://github.com/leavesofgrass/star/releases/latest) —
download one file and run it, nothing else to install:

| Platform | File | How to run |
|---|---|---|
| **Windows** | `star-<version>-windows-x64.exe` | Double-click it. |
| **macOS** (Apple Silicon) | `star-<version>-macos-arm64.dmg` | Open the `.dmg`, drag **star** to Applications, then **right-click ▸ Open** the first time. |
| **Linux** | `star-<version>-x86_64.AppImage` | `chmod +x` it, then run it. |

All three bundle Python, the GUI, and every document loader, so reading and
note-taking work out of the box. **Offline voice dictation (faster-whisper) is
now bundled on Windows and macOS alike** — the switch from Whisper+PyTorch to
faster-whisper (CTranslate2) made the dictation stack small enough (~140 MB) to
ship everywhere. What still differs:

- The **Windows `star.exe`** is the fully-loaded one — it also bakes in the
  native helper tools (ffmpeg for audio export, Tesseract for OCR, liblouis for
  braille, eSpeak-NG for extra voices), so it's the largest (~580 MB, most of
  which is those vendored engines).
- The **macOS `.app`** uses the built-in Apple voices for speech and **bundles
  offline dictation**, but relies on Homebrew for ffmpeg / Pandoc / Tesseract
  rather than vendoring native engines.
- The **Linux AppImage** carries the pure-Python feature set; OCR, audio export,
  and braille use your distro's `tesseract` / `ffmpeg` / `liblouis` when present.

If you already have Python, `pip install star-reader` is much smaller than any of
them.

> On Windows, SmartScreen may warn about an unrecognized publisher the first
> time (the binary isn't code-signed yet) — choose **More info → Run anyway**.
>
> On macOS, the `.app` isn't notarized yet, so the first launch needs a
> **right-click ▸ Open** (or `xattr -dr com.apple.quarantine /Applications/star.app`)
> to get past Gatekeeper. This is a one-time step. The build is Apple-Silicon
> only for now; on an Intel Mac, install from PyPI instead.

---

## Easiest: install from PyPI

star is published on PyPI, so on any platform with Python 3.11+:

```bash
pipx install star-reader      # isolated app install (recommended)
# or
pip install star-reader       # into the current environment
```

Then run `star` (or `python -m star`). This pulls the GUI, TTS, and common
document loaders — and from there **star grows on demand with no further `pip`
step.** The first time you reach for a capability that needs an add-on (OCR,
offline dictionary, summarize, translate, knowledge-graph extras, …), star offers
to **download it in the background**, and the feature works in the same session
— including voice dictation now that it's faster-whisper (no restart needed since
0.1.25). A first-run chooser lets
you pick a **Thin** or **All** preset up front, and you can re-open it any time
from **Tools → Install Optional Features…**. **"All" now means literally
everything** — including the large speech-to-text and named-entity packs — with
the download size shown upfront.

Prefer the command line? These CLIs cover the same ground and then exit:

```bash
star --deps                        # what's installed and what each missing piece unlocks
star --install-optional            # install the 'all' preset (everything)
star --install-optional thin       # or a preset: thin | all
star --install-optional ocr,dictionary   # or a comma-separated list of feature keys
star --plugins list                # registered backends / format handlers / exporters
star --check-update                # check PyPI for a newer release (offline-safe)
```

Worked examples: [`docs/examples/cli/check-dependencies`](examples/cli/check-dependencies) ·
[`docs/examples/cli/list-plugins`](examples/cli/list-plugins).

**Advanced users can still install extras the classic way** — `pip install
"star-reader[all]"` for the full feature set, or individual groups such as
`star-reader[translate,vocab]`. Since 0.1.27 `[all]` **includes** the
speech-to-text dictation stack (`[transcribe]` — faster-whisper, ~150 MB; the
old exclusion dated from the PyTorch era, when it was over 2 GB). Only Coqui
TTS and the spaCy NER backend (`[ner]`, which also needs a language model)
remain separate installs — but the normal path is one click, in-app.

The **pure-Python wheel** behind this install is star's primary, stable
distribution artifact.

## From a source checkout: the installer scripts

The installer creates an isolated virtual environment (`.venv`) and pulls in the
GUI, TTS, and common document-format packages for your platform. It never
modifies your system Python unless you pass `--no-venv`.

```bash
# Linux / macOS
chmod +x tools/install.sh
tools/install.sh            # recommended: GUI + TTS + common formats
tools/install.sh --all      # every optional package
tools/install.sh --minimal  # GUI + TTS only
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1
powershell -ExecutionPolicy Bypass -File .\tools\install.ps1 -Profile all
```

The scripts also add the platform-specific pieces automatically — `pyobjc` on
macOS (so pyttsx3 can drive Apple voices) and `windows-curses` on Windows (for
`--tui` mode) — and tell you which optional external tools (ffmpeg, tesseract)
are missing and what they're for.

## Install from the wheel (macOS / Linux / Windows)

A single pure-Python wheel (`star_reader-<version>-py3-none-any.whl`) installs
`star` and its `star` command into any environment — no per-platform build
required. Build it once with `python -m build --wheel` (output lands in `dist/`),
then copy that one file anywhere and:

```bash
# Recommended dependencies (Qt GUI + TTS + common formats) come with the wheel
pip install star_reader-0.1.27-py3-none-any.whl

# Or pull in the optional Python features (OCR, ODT/XLSX, Pandoc, Braille,
# audio conversion, study aids, feeds, vocab, watch):
pip install "star_reader-0.1.27-py3-none-any.whl[all]"
```

> **`[all]` includes voice dictation/transcription** (`[transcribe]` —
> faster-whisper, ~150 MB, no PyTorch) since 0.1.27; the old exclusion dated
> from the openai-whisper/PyTorch era, when the stack was over 2 GB. Only
> Coqui neural TTS stays a separate, explicit install:
>
> ```bash
> pip install TTS                          # Coqui neural TTS
> ```

The wheel then exposes a `star` console command and `python -m star`:

```bash
star                 # launch the Qt GUI
star document.pdf    # open a file
star --tui           # force the terminal UI
```

Extras let you install exactly what you need: `[ocr]`, `[formats]`, `[markup]`,
`[braille]`, `[audio]`, `[syllables]` (syllable-splitting decoding aid),
`[transcribe]`, `[watch]`, `[graph]` (knowledge-graph / Obsidian helpers),
`[ner]` (spaCy/NLTK concept extraction), or `[all]`.

> The wheel covers the **Python** side. The native engines below (ffmpeg,
> Tesseract, liblouis, Pandoc, eSpeak-NG) are not Python packages; on
> macOS/Linux install them from your system package manager — `python
> tools/install_native.py` does this for you (see
> [External Binary Dependencies](#external-binary-dependencies)).

## Single-file build: star.pyz

> **Build-it-yourself.** The `star.pyz` is **not** produced by automated releases
> and is not attached to GitHub Releases — the wheel (above) is the only shipped
> artifact. If you want a `.pyz`, build your own with the one command below. It is
> platform-specific, so build it on the OS you intend to run it on.

For a build that needs no `pip install` step at all, `star` can be packaged as a
"fat" zipapp: one file, `star.pyz`, that bundles `star` together with its Python
dependencies (the `[all]` extras group). Build it on the same platform you intend
to run it on:

```bash
python build_zipapp.py        # output: dist/star.pyz
```

Run it with any Python interpreter:

```bash
starz                 # launch the Qt GUI
starz document.pdf    # open a file
starz --tui           # force the terminal UI
```

On first run, `star.pyz` extracts its bundled packages into your per-user config
directory (the same place `star` keeps its settings and document cache) and then
starts normally; later runs reuse that extracted copy.

What the fat zipapp does and does not remove:

- It removes the dependency-install step — you do not need to `pip install`
  `star` or its Python packages separately.
- It does **not** bundle the external engines (ffmpeg, Tesseract, liblouis,
  eSpeak-NG, DECtalk). Those still have to be on your `PATH` for the features
  that use them (see [External Binary Dependencies](#external-binary-dependencies)).
- Because it bundles compiled packages (PyQt6, PyMuPDF), `star.pyz` is
  **platform-specific**: a file built on Linux runs only on Linux, one built on
  Windows only on Windows, and so on. Build a separate `star.pyz` for each
  platform you target.

> Prefer a no-Python-install binary? The self-contained Windows `star.exe`, the
> macOS `star.app`/DMG, and the Linux AppImage are attached to every release —
> see [No Python? Download-and-run builds](#no-python-download-and-run-builds) above.

> **Native installers (opt-in).** The release workflow can additionally build a
> Windows NSIS installer — off-by-default and produced only when a maintainer
> enables it. Maintainers: see [`PACKAGING.md`](PACKAGING.md) for the full
> channel matrix, the optional CI jobs, and which signing certificates/secrets
> each one needs.

## Optional Packages

> **You rarely need this table.** star installs each of these **automatically, on
> demand** — the first time you use a feature that needs one, it fetches the
> package in the background (or run `star --install-optional`). The `pip` commands
> below are the manual / advanced route for scripted or offline setups.

| Package | Purpose | Install |
|---|---|---|
| `PyQt6` or `PyQt5` | Qt GUI (default mode; highly recommended) | `pip install PyQt6` |
| `pyttsx3` | TTS via SAPI5 (Windows), NSSpeechSynthesizer (macOS), eSpeak-NG (Linux); gives accurate word-boundary highlighting | `pip install pyttsx3` |
| `pyobjc` | **macOS only** — required for `pyttsx3` to drive Apple voices (not needed for the built-in `say` backend) | `pip install pyobjc` |
| `pdfminer.six` | PDF text extraction (text-layer PDFs) | `pip install pdfminer.six` |
| `pytesseract` | OCR for scanned/image PDFs and standalone image files | `pip install pytesseract` |
| `pymupdf` | PDF page rendering required by pytesseract | `pip install pymupdf` |
| `python-docx` | Microsoft Word DOCX support | `pip install python-docx` |
| `python-pptx` | PowerPoint PPTX support | `pip install python-pptx` |
| `odfpy` | OpenDocument ODT support | `pip install odfpy` |
| `openpyxl` | Excel XLSX spreadsheet support | `pip install openpyxl` |
| `pypandoc` | Pandoc conversion for formats without a native loader | `pip install pypandoc` |
| `louis` | **Optional** contracted Grade 2 Braille (Grade 1 BRF export is built in and needs nothing) | `pip install louis` |
| `pydub` | Audio format conversion fallback (MP3 / OGG / MP4) when ffmpeg is absent | `pip install pydub` |
| `faster-whisper` | Speech recognition for audio transcription and voice dictation of notes (the legacy `openai-whisper` backend still works but is **deprecated** — scheduled for removal in 0.2.0) | `pip install faster-whisper` |
| `sounddevice` + `numpy` | Microphone capture for voice dictation (transcription of files needs only Whisper) | `pip install sounddevice numpy` |
| `windows-curses` | Windows terminal (curses) support for `--tui` mode | `pip install windows-curses` |
| `watchdog` | Hot-folder watching (`--watch` / GUI Watch Folder); falls back to directory polling if absent | `pip install watchdog` |
| `sumy` | Extractive document summarization (**Tools ▸ Summarize Document**) | `pip install sumy` |
| `genanki` | Anki flashcard (`.apkg`) export (**File ▸ Export ▸ Anki Flashcards**) | `pip install genanki` |
| `pyspellchecker` | Spell checking in edit mode (**Edit ▸ Check Spelling**) | `pip install pyspellchecker` |
| `deep-translator` | Document translation (**Tools ▸ Translate Document**) | `pip install deep-translator` |
| `feedparser` | RSS / Atom feed reading (**File ▸ Open Feed**) | `pip install feedparser` |
| `wordfreq` | Difficult-word overlay (**View ▸ Reading Aids ▸ Highlight Difficult Words**) | `pip install wordfreq` |
| `pyphen` | Syllable splitting (**View ▸ Reading Aids ▸ Syllable Splitting**); pure-Python, offline | `pip install pyphen` |

> **The cloud engine needs no extra at all.** The `elevenlabs` cloud engine uses
> only the standard library (paste a key to enable) — it has no optional-
> dependency group.

## External Binary Dependencies

These are native engines (not Python packages), each unlocking one optional
feature. **star's core does not need any of them** — it opens documents, reads
aloud, and exports text with nothing but the wheel. star detects each engine
automatically when it is installed and on your `PATH`; `star --deps` shows which
are currently found.

> **Offline dictation ships on Windows + macOS; the native engines are
> Windows-only.** The download-and-run Windows `star.exe` (see [No Python?
> Download-and-run builds](#no-python-download-and-run-builds)) *ships the native
> engines inside* (ffmpeg, Tesseract, liblouis, Pandoc, eSpeak-NG), so it "just
> works" with nothing else installed. **Only DECtalk is excluded from that public
> exe.** **Offline voice dictation** (faster-whisper) is bundled in **both** the
> Windows exe and the **macOS `.app`** now. The **Linux AppImage** and the macOS
> `.app` do **not** bundle the *native* engines: the AppImage carries the
> pure-Python feature set and uses your distro's `ffmpeg` / `tesseract` /
> `liblouis` when present; the `.app` uses the built-in Apple voices and picks up
> ffmpeg / Pandoc / Tesseract from Homebrew if you have them. The **wheel / pipx**
> install does **not** bundle any of them — install
> only the ones you want, as below. On Windows, the **SAPI5** voices star uses by
> default (via `pyttsx3`, included with the wheel) need none of this, so most
> Windows users never have to install a native engine at all.

### macOS / Linux

These engines come from your system package manager. Run **`python
tools/install_native.py`** to install whatever is missing (ffmpeg, Tesseract +
English data, liblouis, Pandoc, and eSpeak-NG on Linux) via Homebrew / apt / dnf
/ pacman / zypper. Add `--dry-run` to preview the commands or name specific
engines (e.g. `python tools/install_native.py ffmpeg pandoc`).

### Windows

`tools/install_native.py` does not cover Windows; install each engine yourself
and make sure it is on your `PATH`. The easiest route is
[winget](https://learn.microsoft.com/windows/package-manager/) (built into
Windows 10/11; [scoop](https://scoop.sh/) or [Chocolatey](https://chocolatey.org/)
work too):

| Engine | Unlocks | Windows install |
|---|---|---|
| **eSpeak-NG** | The eSpeak voice (and audio-synced word highlighting) | `winget install eSpeak-NG.eSpeak-NG`, or the installer from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases). It puts `libespeak-ng.dll` and `espeak-ng.exe` on `PATH`, which is all star needs. |
| **ffmpeg** | MP3 / OGG / MP4 audio export (WAV always works) | `winget install Gyan.FFmpeg` |
| **Tesseract** | OCR of scanned PDFs / images (also needs `pip install "star-reader[ocr]"`) | `winget install UB-Mannheim.TesseractOCR` |
| **Pandoc** | Conversion of exotic markup formats | `winget install JohnMacFarlane.Pandoc` |
| **liblouis** | Contracted **Grade 2** Braille (Grade 1 BRF is built in) | `pip install louis` (ships the binding + library), or install liblouis and set `LOUIS_TABLEPATH` |
| **DECtalk** | The classic "Perfect Paul" voice | Niche on Windows: point `DECTALK_BIN` at a `dtalk`/`dectalk` CLI. The in-process DECtalk engine is deliberately **excluded from the public `star.exe`** (it's a commercial synthesizer); **SAPI5 is the recommended Windows voice.** |

After installing, **restart your terminal** (so the updated `PATH` takes effect)
and run `star --deps` to confirm star sees the new engine.

> **How star finds eSpeak-NG:** it loads `libespeak-ng.dll` in-process (giving
> audio-position-accurate word highlighting) when the DLL is discoverable on
> `PATH`, and otherwise drives the `espeak-ng` CLI as a subprocess (timer-paced
> highlighting). A standard eSpeak-NG install provides both. See
> [TTS backends](features.md#tts-backends).

### Bundling the engines yourself: `STAR_VENDOR_DIR`

A few engines have no plain "install + PATH" route on Windows — most notably the
**in-process DECtalk** voice, which needs the per-architecture `DECtalk.dll` that
the self-contained `star.exe` deliberately excludes (DECtalk is a commercial
synthesizer). For these, point star at a *vendor tree* with the
`STAR_VENDOR_DIR` environment variable:

```powershell
# Persist it for your user account, then open a new terminal:
setx STAR_VENDOR_DIR "C:\Users\you\star-vendor"
```

star looks there (ahead of its built-in locations) for native tools laid out
exactly like the repo's `vendor/` tree:

```
<STAR_VENDOR_DIR>/
  ffmpeg/ffmpeg.exe
  tesseract/tesseract.exe   tesseract/tessdata/
  liblouis/                 (liblouis.dll + tables/)
  pandoc/pandoc.exe
  dectalk/<amd64|ia32>/DECtalk.dll
  espeak-ng/libespeak-ng.dll   espeak-ng/espeak-ng-data/
```

From a **source checkout**, `python tools/build-vendor.py` (needs
[7-Zip](https://www.7-zip.org/) on PATH) downloads and assembles that whole tree
at the project root (`vendor/`), where star finds it **automatically** when you
run from that checkout — no env var needed. For a **wheel / pipx** install, copy
that `vendor/` folder anywhere and set `STAR_VENDOR_DIR` to it. You only need the
subfolders for the engines you actually want. Run `star --deps` (and try
**Speech → Choose TTS Engine…**) to confirm star picks them up.

### Per-engine reference

- **Tesseract** — required by `pytesseract` for OCR. Download from
  [github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract/releases)
  or install via your system package manager.
- **liblouis** — only for contracted **Grade 2** Braille; Grade 1 BRF export is
  built in and needs nothing.
- **eSpeak-NG** — the eSpeak voice. star loads the system `libespeak-ng`
  in-process when present, or falls back to the `espeak-ng` CLI. See
  [TTS backends](features.md#tts-backends).
- **DECtalk** — set `DECTALK_BIN` to the path of a `dtalk`/`dectalk` CLI, or
  install system DECtalk. Source: [github.com/dectalk/dectalk](https://github.com/dectalk/dectalk).
- **Pandoc** — optional fallback for exotic formats. See [pandoc.org](https://pandoc.org/).
- **ffmpeg** — needed for audio export (MP3, OGG, MP4). WAV export works without
  it. Download from [ffmpeg.org](https://ffmpeg.org/download.html) or install via
  your package manager (`sudo apt install ffmpeg`, `brew install ffmpeg`,
  `winget install Gyan.FFmpeg`).

## Platform Notes

| Platform | Notes |
|---|---|
| Linux | `curses` is built into the standard library. No extra terminal package needed. |
| macOS | `curses` is built in. Native speech works out of the box via the `say` command (Apple voices incl. Eloquence). For `pyttsx3` word-callback highlighting, also `pip install pyobjc pyttsx3`. |
| Windows | TUI mode requires `windows-curses` (`pip install windows-curses`). The Qt GUI works without it. |

### Quick install (manual extras)

```bash
# Recommended: Qt GUI + PDF + DOCX + TTS
pip install PyQt6 pyttsx3 pdfminer.six python-docx python-pptx

# Add OCR support for scanned PDFs and image files
pip install pytesseract pymupdf

# Windows TUI mode
pip install windows-curses

# Everything
pip install PyQt6 pyttsx3 pdfminer.six pytesseract pymupdf python-docx python-pptx odfpy openpyxl pypandoc louis pydub pyphen windows-curses
```

---

See also: [Usage Guide](usage_guide.md) · [Features](features.md) ·
[Configuration](configuration.md) · [Architecture](architecture.md).
