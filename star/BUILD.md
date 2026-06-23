# 🏗️ Building a Portable Windows Binary

This guide produces a **single, self-contained `star.exe`** that runs on Windows
machines with **no Python and no dependencies installed** — ideal for demoing
star as a tool. The binary bundles the Python interpreter, the Qt GUI, the
text-to-speech driver, the document loaders, the study & writing aids (summarize,
Anki export, spell check, translation, feeds, the difficult-word overlay),
**out-of-the-box offline voice dictation & transcription (Whisper + the bundled
`base` model)**, and — when the `vendor/` tree is present — the native engines
for MP3 export (ffmpeg), OCR (Tesseract + English data), Grade 2 Braille
(liblouis), markup conversion (Pandoc), and the classic DECtalk synthesizer.

> Size note: the **full default build is large** (~700+ MB onefile `.exe`). The
> biggest single contributor is the dictation stack — **openai-whisper pulls in
> PyTorch** (multiple hundred MB) plus the ~140 MB Whisper `base` model — on top
> of the bundled `vendor/` engines. Because onefile extracts everything to a temp
> folder on each launch, the **first start takes noticeably longer**. For a fast,
> small build, pass `-Lean` to skip the dictation stack (see
> [Dictation](#out-of-the-box-dictation-whisper)) and/or omit the `vendor/` step.

---

## TL;DR

From a Windows machine with Python 3.11+ and **7-Zip** installed:

```powershell
python tools\build-vendor.py     # download ffmpeg + Tesseract + liblouis into vendor/
powershell -ExecutionPolicy Bypass -File tools\build-windows.ps1
```

The result is **`dist\star.exe`**. Copy it anywhere and double-click to launch
the GUI. (Skip the first line for a lean build without the native engines.)

By default this bundles **offline voice dictation** (PyTorch/Whisper + the `base`
model) so users get it out of the box. For a fast, small build without it, pass
`-Lean`; see [Dictation](#out-of-the-box-dictation-whisper).

---

## What gets built

- **One file:** `dist\star.exe` (PyInstaller *onefile* mode).
- **Windowed GUI:** launches the Qt reader with no console window. This is the
  default demo experience.
- **Bundled runtime:** PyQt6, `pyttsx3` (Windows SAPI5 voices via `comtypes`),
  `pdfminer.six` (PDF text), `python-docx`, `python-pptx`, `openpyxl`, `odfpy`,
  and the `windows-curses` runtime, plus the `star/README.md` / `LICENSE` /
  `CHANGELOG.md` help docs so the in-app **Help (F1)** works.
- **Bundled dictation stack (default; skip with `-Lean`):** `openai-whisper`
  (and its PyTorch backend), `sounddevice` for microphone capture, and the
  Whisper **`base` model**, so **Tools → Dictate Note** and **Transcribe Audio
  File** work offline on a clean machine. This is the largest contributor to the
  binary size — see [Dictation](#out-of-the-box-dictation-whisper).
- **Bundled study & writing aids:** `sumy` (with NLTK's `punkt` tokenizer data
  staged under `build/nltk_data`) for **Tools → Summarize Document**, `genanki`
  for **File → Export → Anki Flashcards**, and `pyspellchecker` for edit-mode
  spell checking (**Edit → Check Spelling**). All three, and the data they
  need, are bundled so the features work offline with no extra install.
- **Bundled native engines** (when `vendor/` is present — see below):
  - **ffmpeg** → MP3 / OGG / MP4 audio export
  - **Tesseract** + English language data → OCR of images and scanned PDFs
  - **liblouis** + translation tables + ctypes binding → Grade 2 Braille
  - **Pandoc** → high-fidelity markup conversion (RST, Org, MediaWiki,
    AsciiDoc, Textile, LaTeX, legacy `.doc`, …)
  - **DECtalk** → `DECtalk.dll` + dictionary for the classic DECtalk voice,
    driven in-process via ctypes (no separate CLI required)

  At runtime `star`'s `_vendor_dir()` finds these under `sys._MEIPASS`; each
  lookup falls back to a system install if the bundled copy is missing, so a
  lean build (no `vendor/`) still runs.

The build is defined by these files:

| File | Purpose |
|---|---|
| [`star.spec`](../star.spec) | PyInstaller build recipe (entry point, hidden imports, bundled data + `vendor/` tree, dictation stack, runtime hook, excludes) |
| [`run_star.py`](../run_star.py) | Frozen entry point — imports `star.app.main` from the generated `star/` package |
| [`tools/rthook_star.py`](../tools/rthook_star.py) | PyInstaller runtime hook: puts the bundled ffmpeg on `PATH`, points Whisper's model cache at the bundled `base` model, and points `NLTK_DATA` at the bundled `punkt` data |
| [`tools/build-windows.ps1`](../tools/build-windows.ps1) | Convenience wrapper: sets up an env, installs deps (study/writing aids + the dictation stack by default; `-Lean` skips dictation), stages the NLTK `punkt` data and the Whisper model, runs PyInstaller |
| [`tools/build-vendor.py`](../tools/build-vendor.py) | Downloads & lays out the native engines (ffmpeg, Tesseract, liblouis, Pandoc, DECtalk) into `vendor/` |

---

## Prerequisites

- **Windows 10/11, 64-bit.**
- **Python 3.11 or newer**, on `PATH` (`python --version` should work).
  - Tip: a regular [python.org](https://www.python.org/downloads/) install is
    the smoothest. The Windows Store build of Python also works.
- For the fully self-contained build: **internet access** (to download the
  engines) and **[7-Zip](https://www.7-zip.org/)** (to unpack the Tesseract
  installer without UAC elevation).

The build script installs everything else (PyInstaller and the runtime
dependencies) into an isolated build virtual environment by default.

---

## Vendoring the native engines (`vendor/`)

MP3 export, OCR, and Grade 2 Braille rely on **native engines that are not
Python packages** (ffmpeg, Tesseract, liblouis). To make the single binary do
*everything*, those engines are placed in a `vendor/` tree that `star.spec`
mirrors into the bundle. The `build-vendor.py` helper downloads and assembles
it for you:

```powershell
python build-vendor.py          # fetch anything missing
python build-vendor.py --force  # re-download everything
```

It produces (~450 MB):

```
vendor/
  ffmpeg/ffmpeg.exe                 # gyan.dev static build (libmp3lame/libvorbis/AAC)
  tesseract/                        # UB-Mannheim 5.4.0: tesseract.exe + DLLs
    tessdata/{eng,osd}.traineddata  #   English + orientation data
  liblouis/
    liblouis.dll                    # liblouis 3.38.0 (win64)
    tables/                         #   *.ctb / *.utb translation tables
    louis/__init__.py               #   ctypes binding (loads $LIBLOUIS_DLL)
  pandoc/pandoc.exe                 # pandoc 3.10 (single self-contained binary)
  dectalk/                          # dectalk 2023-10-30 (vs2022 build)
    amd64/DECtalk.dll + dtalk_us.dic  #   64-bit engine + dictionary
    ia32/DECtalk.dll  + dtalk_us.dic  #   32-bit engine + dictionary
```

> **DECtalk note.** star drives DECtalk **in-process** through `DECtalk.dll`
> via ctypes (the `DECtalkDLLBackend`), so the classic DECtalk voice works from
> the bundled files alone — no separate `say`/`dtalk` CLI is needed. Because a
> 64-bit process can't load a 32-bit DLL (and vice versa), both `amd64/` and
> `ia32/` builds are vendored and star loads the one matching `star.exe`. The
> engine loads `dtalk_us.dic` from the DLL's own folder, so the dictionary is
> kept beside each `DECtalk.dll`. (A `say`/`dtalk` CLI on `PATH` or via
> `DECTALK_BIN` is still honored as a fallback.)
>
> This backend is implemented against the DECtalk C API and the upstream NVDA
> driver, but has **not** been verified against a live build in this
> environment — if the voice doesn't appear, the DLL's startup licensing
> (the shared-memory SMIT blob) may need adjustment for the vs2022 build.

Notes:

- The script prunes Tesseract's training tools/docs to keep the size down,
  keeping only the engine, its DLLs, and the language data.
- Sources & versions are documented at the top of `build-vendor.py`. The
  ffmpeg URL always tracks the current release; Tesseract and liblouis are
  pinned for reproducibility.
- The `vendor/` folder is large — keep it out of version control if you don't
  want a ~300 MB checkout, but keep it locally so rebuilds are instant.
- **Lean build:** skip this step entirely. Without `vendor/`, the build still
  works; MP3/OCR/Grade 2 then require the user's machine to provide ffmpeg /
  Tesseract / liblouis on `PATH`.

---

## Building (step by step)

### Option 1 — the script (recommended)

```powershell
# Creates .venv-build, installs deps, builds dist\star.exe
powershell -ExecutionPolicy Bypass -File build-windows.ps1
```

Useful switches:

| Switch | Effect |
|---|---|
| `-UseCurrentEnv` | Build with the active Python env instead of creating `.venv-build` |
| `-SkipInstall` | Skip `pip install` (assume dependencies are already present) |
| `-Ocr` | Also install OCR deps (`pytesseract`, `PyMuPDF`, `Pillow`) — see caveat below |

Example, when your current environment already has the dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File build-windows.ps1 -UseCurrentEnv -SkipInstall
```

### Option 2 — PyInstaller directly

```powershell
python -m pip install pyinstaller PyQt6 pyttsx3 comtypes pdfminer.six python-docx python-pptx openpyxl odfpy windows-curses
python -m PyInstaller --clean --noconfirm star.spec
```

Either way the output is **`dist\star.exe`**.

---

## Running and distributing

- **Run:** double-click `dist\star.exe`, or from a prompt: `dist\star.exe somefile.pdf`.
- **Distribute:** copy just `star.exe` to the target machine. Nothing else is
  required — no Python, no `pip`, no Qt install.
- **First launch on another PC:** Windows SmartScreen may warn about an
  unrecognized publisher (the binary is unsigned). Choose *More info →
  Run anyway*. For wider distribution, code-sign the exe.
- Settings, themes, and notes are written to `%APPDATA%\star\` on the target
  machine, exactly as for the script version.

---

## Console build (enables the `--tui` terminal mode)

The default build is **windowed**, so the curses terminal UI (`star.exe --tui`)
has no console to draw in. To build a variant that also supports `--tui` and
prints CLI output (`--version`, `--list-themes`, `--plain`, …) to a console, set
the `STAR_CONSOLE` environment variable before running PyInstaller:

```powershell
$env:STAR_CONSOLE = "1"
python -m PyInstaller --noconfirm star.spec
```

This produces **`dist\star-console.exe`** *alongside* the windowed
`dist\star.exe` (it uses a different output name, so the two coexist and you can
keep both). Unset the variable (or open a fresh shell) to go back to the
default windowed build:

```powershell
Remove-Item Env:\STAR_CONSOLE
python -m PyInstaller --noconfirm star.spec
```

Most demos want the clean windowed build, so windowed is the default; the
console variant is handy for verifying the new CLI commands and the `--tui`
terminal mode end to end.

---

## OCR, MP3, and Grade 2 Braille support

These three features depend on native engines (not Python packages):

| Feature | Engine | Self-contained build | Lean build |
|---|---|---|---|
| MP3 / OGG / MP4 export | ffmpeg | **bundled** (works anywhere) | needs `ffmpeg` on the target's `PATH` |
| OCR (images, scanned PDF) | Tesseract + `eng` data | **bundled** (works anywhere) | needs `tesseract.exe` on the target's `PATH` |
| Grade 2 (contracted) Braille | liblouis + tables | **bundled** (works anywhere) | falls back to the built-in Grade 1 translator |
| Markup conversion (RST, Org, LaTeX, …) | Pandoc | **bundled** (works anywhere) | needs `pandoc` on the target's `PATH`; otherwise built-in converters |
| DECtalk voice | `DECtalk.dll` (ctypes) | **bundled** (in-process engine + dictionary) | needs DECtalk on the target's `PATH` / `DECTALK_BIN`, or a system DECtalk |
| Voice dictation / transcription | Whisper + PyTorch + `base` model | **bundled** (works offline) | needs `pip install openai-whisper sounddevice` and a downloaded model |

Run `python tools\build-vendor.py` before building to bundle the native
engines (see [Vendoring the native engines](#vendoring-the-native-engines-vendor)
above). Only **OCR** needs Python wrappers (`pytesseract`, `PyMuPDF`, `Pillow`)
bundled alongside the engine — `build-windows.ps1` installs them automatically
when `vendor\tesseract` is present (or pass `-Ocr`). ffmpeg, liblouis, and
Pandoc are driven directly (subprocess / ctypes), so they need no Python
package.

To add more OCR languages, drop extra `*.traineddata` files into
`vendor/tesseract/tessdata/` before building and rebuild.

---

## Out-of-the-box dictation (Whisper)

star's **Tools → Dictate Note** (record a voice memo) and **Transcribe Audio
File** features use [OpenAI Whisper](https://github.com/openai/whisper). For the
portable binary these are **bundled by default** so they work with **no install
and no network** — Windows users can't reasonably set up the recognition stack
themselves, so it ships in the exe:

- **`openai-whisper` + PyTorch** — the recognition engine. `star` prefers
  `openai-whisper` (falling back to `faster-whisper` if that is what's
  installed); `build-windows.ps1` installs `openai-whisper`, which pulls in
  PyTorch, numba, and tiktoken. `star.spec` bundles the whole stack via
  `collect_all`.
- **`sounddevice`** — microphone capture (ships the PortAudio DLL).
- **The Whisper `base` model** (~140 MB) — staged to
  `build\whisper_cache\whisper\base.pt` by `build-windows.ps1` and bundled by
  `star.spec`. At runtime [`tools/rthook_star.py`](../tools/rthook_star.py)
  points Whisper's cache (`XDG_CACHE_HOME`) at the bundled copy, so
  `load_model("base")` loads it offline instead of downloading.
- **ffmpeg on `PATH`** — Whisper shells out to `ffmpeg` to decode audio. The
  runtime hook prepends the bundled `vendor\ffmpeg` folder to `PATH`, so the
  vendored ffmpeg satisfies both audio export and Whisper.

The Whisper `base` model is a good speed/accuracy balance for dictation. To
bundle a different model, stage it under `build\whisper_cache\whisper\` and set
the default `whisper_model` setting accordingly (read from the `whisper_model`
setting, default `base`).

**The dictation stack is what makes the binary large** (PyTorch is multiple
hundred MB). For a fast, small build that leaves dictation to an optional user
install, pass `-Lean` to `build-windows.ps1` (it sets the `STAR_LEAN`
environment variable that `star.spec` reads) — `star.spec`'s `collect_all` calls
are guarded, so the lean build still succeeds and the feature simply shows its
“requires Whisper” hint at runtime.

---

## Troubleshooting

- **The exe opens then immediately closes.** Run it from a prompt to see if a
  crash log was written to `%APPDATA%\star\star_crash.log`; that file captures
  unhandled GUI exceptions. (A windowed build prints nothing to the terminal.)
- **No speech.** star uses the built-in Windows SAPI5 voices via `pyttsx3`.
  Confirm Windows has at least one voice installed under
  *Settings → Time & Language → Speech*.
- **A document format won't open.** Only the loaders whose libraries were
  bundled are available. The default build covers PDF (text), DOCX, PPTX, XLSX,
  ODT, EPUB, HTML, Markdown, and the markup formats. To add more, install the
  relevant package into the build environment before building and, if needed,
  add it to `collect_data_files` in `star.spec`.
- **Rebuild from scratch.** Delete the `build\` and `dist\` folders (and
  `.venv-build\` if you used it) and run the build again.

---

## Cross-platform install: the wheel (macOS / Linux / Windows)

For distribution that is **not** a frozen single binary, build a normal Python
wheel. Because `star` is pure Python, **one** wheel
(`star_reader-<version>-py3-none-any.whl`, tagged `py3-none-any`) installs on
macOS, Linux, and Windows alike.

```bash
python -m pip install --upgrade build      # one-time: the PEP 517 build frontend
python -m build --wheel                    # writes dist/star_reader-<version>-py3-none-any.whl
```

Install the resulting single file anywhere:

```bash
pip install dist/star_reader-0.1.8-py3-none-any.whl          # recommended deps
pip install "dist/star_reader-0.1.8-py3-none-any.whl[all]"    # every optional feature
```

The wheel provides a `star` console command and `python -m star`. Packaging is
defined by [`pyproject.toml`](pyproject.toml); the package itself is produced
from the monolithic `star.py` by [`tools/split_star.py`](tools/split_star.py),
so regenerate the `star/` package (and bundled help docs) before building if
`star.py` changed.

**Native engines for the wheel.** The wheel covers only the Python side. The
native engines (ffmpeg, Tesseract, liblouis, Pandoc, eSpeak-NG) are not Python
packages; on macOS/Linux install them from the system package manager with
[`tools/install_native.py`](tools/install_native.py):

```bash
python tools/install_native.py             # install whatever is missing
python tools/install_native.py --dry-run   # preview the package-manager commands
python tools/install_native.py ffmpeg pandoc   # only specific engines
```

It detects Homebrew / apt / dnf / pacman / zypper and installs the same engines
`build-vendor.py` bundles on Windows.

---

## Notes for other platforms

`star.py` itself is cross-platform, and `star.spec` is largely portable, but
PyInstaller cannot cross-compile: build the macOS app on macOS and the Linux
binary on Linux. The `console`/windowed and bundled-data choices carry over.
`build-vendor.py` fetches **Windows** engine binaries; for macOS/Linux the
native helpers (`ffmpeg`, `tesseract`, `liblouis`) differ and `star.py`'s
`_vendor_dir()` lookups only know the Windows binary names, so rather than
vendoring them into a frozen bundle the supported path is to install them from
the system package manager via [`tools/install_native.py`](tools/install_native.py)
and distribute the [wheel](#cross-platform-install-the-wheel-macos--linux--windows)
(or run from source).
