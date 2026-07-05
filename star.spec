# -*- mode: python ; coding: utf-8 -*-
#
# DEPRECATED — manual fallback only.
# The primary, stable distribution artifact is the pure-Python wheel
# (`python -m build`, published to PyPI: `pipx install star-reader`).  This
# PyInstaller spec is retained only for maintainers who specifically need a
# self-contained .exe; CI no longer builds it on tag pushes.  Do not invoke it
# directly — use `tools/build-windows.ps1 -AllowDeprecatedExe`, which sets up the
# environment and stages the offline data this spec expects.  See BUILD.md.
#
# PyInstaller build spec for a portable, single-file Windows binary of star.
#
#   Build:   pyinstaller --clean star.spec
#   Output:  dist/star.exe   (onefile, windowed GUI)
#
# See BUILD.md for the full, step-by-step instructions (including how to make
# a console build that also supports the --tui terminal interface).
#
# star is now packaged as the ``star/`` package (generated from star-monolith.py
# by tools/split_star.py); the frozen entry point is the thin ``run_star.py``
# wrapper, which imports ``star.app.main``.

import os as _os

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

block_cipher = None

_here = _os.path.dirname(_os.path.abspath(SPEC))

# Console vs. windowed build.  The default is the clean windowed GUI build
# (``star.exe``, no console window).  Set the environment variable
# ``STAR_CONSOLE=1`` to instead produce a console variant that also supports the
# curses ``--tui`` terminal mode and prints CLI output (e.g. ``--list-themes``,
# ``--version``) to a console.  The console variant is named ``star-console.exe``
# so it sits alongside the windowed ``star.exe`` in dist/ instead of replacing
# it.
_console = bool(_os.environ.get("STAR_CONSOLE"))
_exe_name = "star-console" if _console else "star"

# Whether to bundle the offline dictation / transcription stack (openai-whisper
# + Torch + numba/llvmlite/tiktoken/sounddevice + the Whisper model).  Windows
# users can't reasonably set this up themselves, so it is bundled BY DEFAULT for
# out-of-the-box voice dictation & transcription.  The stack is large (multiple
# GB), so set ``STAR_LEAN=1`` to skip it for a fast, small build (quick test
# builds, CI iteration); see ``tools/build-windows.ps1 -Lean``.  star's code
# guards the whisper/sounddevice imports, so a lean exe simply reports dictation
# as unavailable in ``star --deps`` and every other feature works unchanged.
_bundle_dictation = not _os.environ.get("STAR_LEAN")

# ── Bundled data files ──────────────────────────────────────────────────────
# README.md is opened in-app by the Help command (F1), which resolves it via
# Path(__file__).parent.  __file__ now lives inside the star/ package, so the
# help docs ship under the bundle's ``star/`` folder (alongside the frozen
# package modules) rather than at the bundle root.
datas = [
    ("star/README.md", "star"),
    ("star/LICENSE", "star"),
    ("star/CHANGELOG.md", "star"),
    # First-screen welcome page — loads as a real document at startup
    # (0.1.18+); without it the GUI silently falls back to a static splash.
    ("star/welcome.md", "star"),
]
# i18n catalogs (0.1.19+): es/fr/de/pt UI translations + the ar RTL proof.
# Without these, Interface Language silently falls back to English.
if _os.path.isdir(_os.path.join(_here, "star", "locale")):
    datas.append(("star/locale", "star/locale"))
binaries = []

hiddenimports = [
    # pyttsx3 loads its platform driver dynamically at runtime; PyInstaller's
    # static analysis cannot see the SAPI5 (Windows) driver import, so name it.
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    # The SAPI5 driver talks to Windows speech through COM via comtypes.
    "comtypes",
    "comtypes.client",
    "comtypes.stream",
    # sounddevice (microphone capture for dictation) uses a cffi backend.
    "cffi",
    "_cffi_backend",
]

# The whole star package (so indirectly-imported submodules are never dropped).
hiddenimports += collect_submodules("star")

# Packages that ship templates / resource data needed at runtime.  Each collect
# is guarded so the spec still builds if an optional package is not installed.
for _pkg in ("pdfminer", "docx", "pptx", "odf", "openpyxl"):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

# ── Dictation / transcription stack (Whisper + Torch) — bundled by default ──
# Bundle openai-whisper and its full dependency stack so the dictation and
# audio-transcription features work out of the box on a clean Windows machine
# (no pip, no model download).  This is large (Torch alone is multiple GB);
# collect_all pulls each package's submodules, data files, and native libraries
# (the Torch DLLs, the llvmlite LLVM DLL, the sounddevice PortAudio DLL).
# Skipped only for a lean build (STAR_LEAN=1) — see _bundle_dictation above.
if _bundle_dictation:
    for _pkg in ("whisper", "torch", "numba", "llvmlite", "tiktoken", "sounddevice"):
        try:
            _d, _b, _h = collect_all(_pkg)
            datas += _d
            binaries += _b
            hiddenimports += _h
        except Exception:
            pass

# ── Study & writing aids (summarize / flashcards / spell check / translate /
#    feeds / difficult-word overlay) ──────────────────────────────────────────
# Each of these optional packages ships data files inside its package that
# PyInstaller's import analysis would otherwise miss:
#   sumy            – stopword lists (+ pulls in nltk)
#   genanki         – Anki deck templates
#   pyspellchecker  – compressed frequency dictionaries
#   wordfreq        – the compressed word-frequency tables the difficult-word
#                     overlay reads (essential; the feature fails without them)
#   langcodes/ftfy  – language-data and text-cleanup tables wordfreq depends on
#   deep_translator – translation backend (lazy imports collect_all pins down)
#   feedparser      – RSS / Atom parser (pure code, bundled for completeness)
# collect_all bundles every package's submodules + data so the features work in
# the frozen build with no extra install.  Guarded so the spec still builds when
# one of these optional packages is absent.
for _pkg in (
    "sumy", "genanki", "pyspellchecker", "nltk",
    "deep_translator", "feedparser", "wordfreq", "langcodes", "ftfy",
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

# Bundle the Whisper "base" model so transcription/dictation runs offline on
# first launch.  tools/build-windows.ps1 (or build-vendor flow) stages it under
# build/whisper_cache/whisper/base.pt; the runtime hook points Whisper's cache
# (XDG_CACHE_HOME) at <bundle>/whisper_cache so load_model("base") finds it.
# Only meaningful when the dictation stack is bundled (opt-in).
if _bundle_dictation:
    _whisper_model = _os.path.join(_here, "build", "whisper_cache", "whisper", "base.pt")
    if _os.path.isfile(_whisper_model):
        datas.append((_whisper_model, "whisper_cache/whisper"))

# Bundle NLTK's punkt sentence-tokenizer data so document summarization works
# offline (sumy's Tokenizer needs it, and otherwise downloads it on first use).
# tools/build-windows.ps1 stages it under build/nltk_data; the runtime hook
# points NLTK_DATA at <bundle>/nltk_data so the frozen app finds it.
_nltk_data = _os.path.join(_here, "build", "nltk_data")
if _os.path.isdir(_nltk_data):
    for _root, _dirs, _files in _os.walk(_nltk_data):
        for _f in _files:
            _src = _os.path.join(_root, _f)
            _rel = _os.path.relpath(_root, _nltk_data)
            _dest = (
                "nltk_data/" + _rel.replace("\\", "/") if _rel != "." else "nltk_data"
            )
            datas.append((_src, _dest))

# ── Vendored native tools (self-contained build) ────────────────────────────
# Bundle ffmpeg (audio export + Whisper audio decoding), Tesseract + English
# data (OCR), liblouis + its tables and Python binding (Grade 2 Braille),
# Pandoc (markup conversion), and DECtalk (DECtalk.dll + dictionary, driven
# in-process via ctypes).  The whole ``vendor/`` tree is mirrored at the bundle
# root so star's _vendor_dir() finds each tool under sys._MEIPASS at runtime.
# Guarded so the spec still builds if a tool has not been downloaded.
_vendor_root = _os.path.join(_here, "vendor")
if _os.path.isdir(_vendor_root):
    for _root, _dirs, _files in _os.walk(_vendor_root):
        for _f in _files:
            # Skip the downloaded installer archive if it lingers.
            if _f.endswith("setup.exe"):
                continue
            _src = _os.path.join(_root, _f)
            _rel = _os.path.relpath(_root, _vendor_root)  # e.g. "tesseract/tessdata"
            _dest = _rel.replace("\\", "/") if _rel != "." else "."
            datas.append((_src, _dest))

# comtypes generates COM wrappers from submodules; pull them all in to be safe.
try:
    hiddenimports += collect_submodules("comtypes")
except Exception:
    pass

_excludes = [
    # Coqui TTS is a heavy, optional neural backend unrelated to dictation;
    # Windows uses the built-in SAPI5 voices via pyttsx3.
    "TTS",
    "tensorflow",
    "tkinter",
    # Only one Qt binding is needed; star prefers PyQt6.  Excluding PyQt5
    # avoids bundling a second, unused Qt.
    "PyQt5",
]
if not _bundle_dictation:
    # Lean build (STAR_LEAN=1): explicitly exclude the dictation stack so it is
    # never pulled in transitively — star imports whisper/sounddevice under
    # guarded try/except, and PyInstaller would otherwise follow those imports
    # and bundle multi-GB Torch if it happened to be installed in the build env.
    _excludes += ["whisper", "torch", "numba", "llvmlite", "tiktoken", "sounddevice"]

a = Analysis(
    ["run_star.py"],
    pathex=[_here],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[_os.path.join("tools", "rthook_star.py")],
    excludes=_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=_exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Windowed GUI build by default (no console window flashes on launch).  Set
    # STAR_CONSOLE=1 for a console build that also supports the curses --tui mode
    # and prints CLI output (see BUILD.md).
    console=_console,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
