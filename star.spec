# -*- mode: python ; coding: utf-8 -*-
#
# The pure-Python wheel (`python -m build`, published to PyPI: `pipx install
# star-reader`) is the primary, stable distribution artifact.  This PyInstaller
# spec is the SUPPORTED recipe for the self-contained desktop binaries: CI builds
# them from it on every `v*` tag — the `windows-exe` job produces `dist/star.exe`
# and the `macos-app` job (via tools/build-macos.sh) produces `dist/star.app`,
# both attached to the GitHub Release (see .github/workflows/release.yml).  Don't
# invoke it directly — use `tools/build-windows.ps1 -AllowDeprecatedExe` (Windows)
# or `tools/build-macos.sh` (macOS), which set up the environment and stage the
# offline data this spec expects.  See BUILD.md.
#
# PyInstaller build spec for a portable, self-contained binary of star.
#
#   Windows:  pyinstaller --clean star.spec   -> dist/star.exe   (onefile GUI)
#   macOS:    pyinstaller --clean star.spec   -> dist/star.app   (ONEDIR bundle)
#
# The platform is auto-detected (sys.platform); see the EXE/COLLECT/BUNDLE branch
# at the end.  On macOS use tools/build-macos.sh (it stages deps + signs/packages
# the .dmg); on Windows use tools/build-windows.ps1.  See BUILD.md for the full,
# step-by-step instructions (including how to make a console build that also
# supports the --tui terminal interface).
#
# star is packaged as the ``star/`` package; the frozen entry point is the thin
# ``run_star.py`` wrapper, which imports ``star.app.main``.

import os as _os
import sys as _sys

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# Target platform.  The Windows path (the historical purpose of this spec)
# produces a onefile ``star.exe``; on macOS the same Analysis is packaged as a
# ONEDIR ``star.app`` bundle (see the EXE/COLLECT/BUNDLE branch at the end).
_is_mac = _sys.platform == "darwin"

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

# Whether to bundle the offline dictation / transcription stack (faster-whisper /
# CTranslate2 + av + tokenizers + sounddevice + the CTranslate2 model dir).
# Users can't reasonably set this up themselves, so it is bundled BY DEFAULT for
# out-of-the-box voice dictation & transcription.  The stack is now ~140 MB (down
# from multiple GB with the old Torch stack), so it ships on every platform incl.
# the macOS .app; set ``STAR_LEAN=1`` to skip it for a fast, small build (quick
# test builds, CI iteration); see ``tools/build-windows.ps1 -Lean``.  star's code
# guards the faster_whisper/sounddevice imports, so a lean exe simply reports
# dictation as unavailable in ``star --deps`` and every other feature works.
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

# ── Plugin registry metadata — REQUIRED for any speech at all ───────────────
# Since 0.1.21 every TTS engine (SAPI/pyttsx3, eSpeak, DECtalk, …) is
# discovered through importlib.metadata entry points declared in
# pyproject.toml ([project.entry-points."star.backends"]).  A frozen app has
# NO dist-info unless it is copied in: without this block the registry finds
# zero backends, the engine picker shows only "auto"/"none", and star falls
# to the SilentBackend — a reader that cannot speak.  Requires star-reader to
# be pip-installed in the build venv (tools/build-windows.ps1 does this).
datas += copy_metadata("star-reader")
binaries = []

hiddenimports = [
    # pyttsx3 loads its platform driver dynamically at runtime; PyInstaller's
    # static analysis cannot see the driver import, so name both the SAPI5
    # (Windows) and NSSpeechSynthesizer (macOS) drivers.
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "pyttsx3.drivers.nsss",
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

# ── Dictation / transcription stack (faster-whisper / CTranslate2) ──────────
# Offline dictation + audio transcription, bundled by default so it works on a
# clean machine with no pip and no model download.  star migrated OFF
# openai-whisper + Torch (a ~2.5 GB dependency that made the exe ~700 MB and was
# too heavy for the macOS .app) to **faster-whisper** (CTranslate2): the whole
# stack is ~140 MB, so dictation now ships on every platform, macOS included.
# collect_all pulls each package's submodules + data; collect_dynamic_libs
# explicitly grabs the compiled native libs — libctranslate2 + OpenMP, PyAV's
# bundled ffmpeg DLLs, sounddevice's PortAudio — which a frozen transcription
# needs (validated by a standalone PyInstaller probe).  Skipped for a lean build
# (STAR_LEAN=1) — see _bundle_dictation above.
if _bundle_dictation:
    for _pkg in (
        "faster_whisper", "ctranslate2", "av", "tokenizers",
        "onnxruntime", "huggingface_hub", "sounddevice",
    ):
        try:
            _d, _b, _h = collect_all(_pkg)
            datas += _d
            binaries += _b
            hiddenimports += _h
        except Exception:
            pass
    # Native libs are the thing a frozen build most often drops — collect them
    # explicitly for the two packages that carry compiled extensions + DLLs.
    for _pkg in ("ctranslate2", "av"):
        try:
            binaries += collect_dynamic_libs(_pkg)
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
    # NOTE: the IMPORT name, not the PyPI distribution name — collect_all
    # needs the package.  pyspellchecker installs as ``spellchecker``; naming
    # it "pyspellchecker" here collected ZERO files, so edit mode's spell
    # dictionary (resources/en.json.gz) never shipped ("dictionary missing").
    # pyphen ships its Hunspell hyphenation dictionaries as package data, so
    # it too must be collect_all'd or Syllable Splitting is dark in the exe.
    "sumy", "genanki", "spellchecker", "nltk", "pyphen",
    "deep_translator", "feedparser", "wordfreq", "langcodes", "ftfy",
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

# Bundle the CTranslate2 "base" model DIRECTORY (model.bin + config.json +
# tokenizer.json + vocabulary.txt, from Systran/faster-whisper-base, MIT) so
# dictation runs fully offline on first launch — no HF download.  The build
# scripts stage it under build/faster_whisper_model/; it lands at the bundle
# root as faster_whisper_model/, and _runtime._new_faster_model() loads it with
# local_files_only=True (HF_HUB_OFFLINE) when frozen.  (CTranslate2 uses a model
# directory, not openai-whisper's single .pt file.)  Bundled dictation only.
if _bundle_dictation:
    _fw_model_dir = _os.path.join(_here, "build", "faster_whisper_model")
    if _os.path.isdir(_fw_model_dir):
        for _root, _dirs, _files in _os.walk(_fw_model_dir):
            for _f in _files:
                _src = _os.path.join(_root, _f)
                _rel = _os.path.relpath(_root, _fw_model_dir)
                _dest = (
                    "faster_whisper_model/" + _rel.replace("\\", "/")
                    if _rel != "." else "faster_whisper_model"
                )
                datas.append((_src, _dest))

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
# vendor/ holds WINDOWS binaries (fetched by tools/build-vendor.py); never
# bundle them into a macOS .app.  macOS gets speech from the native ``say`` /
# NSSpeechSynthesizer backends, and ffmpeg/pandoc from Homebrew if present.
_vendor_root = _os.path.join(_here, "vendor")
if not _is_mac and _os.path.isdir(_vendor_root):
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
    # star migrated dictation to faster-whisper (CTranslate2), so openai-whisper
    # + Torch are NEVER bundled now — exclude them always so a build venv that
    # happens to have them installed can't drag ~2.5 GB of Torch back into the
    # exe via star's guarded ``import whisper`` fallback.  At runtime the frozen
    # app then sees no ``whisper`` module and selects the faster backend.
    "whisper",
    "torch",
    "numba",
    "llvmlite",
    "tiktoken",
]
if not _bundle_dictation:
    # Lean build (STAR_LEAN=1): also exclude the faster-whisper stack so it is
    # never pulled in transitively; star imports faster_whisper/sounddevice under
    # guarded try/except, and a lean build wants none of it.
    _excludes += [
        "faster_whisper", "ctranslate2", "av", "tokenizers",
        "onnxruntime", "sounddevice",
    ]

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

if _is_mac:
    # macOS: a ONEDIR .app bundle (idiomatic + Gatekeeper-friendly — onefile's
    # temp extraction plays badly with signing/notarization).  Read the version
    # for the Info.plist from pyproject.toml.
    _mac_version = "0.0.0"
    try:
        import tomllib as _tomllib

        with open(_os.path.join(_here, "pyproject.toml"), "rb") as _fp:
            _mac_version = _tomllib.load(_fp)["project"]["version"]
    except Exception:
        pass
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="star",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,          # windowed .app
        disable_windowed_traceback=False,
        target_arch=None,       # native (arm64 on Apple-Silicon runners)
        codesign_identity=None,  # signed later by tools/build-macos.sh
        entitlements_file=None,
        icon=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name="star",
    )
    app = BUNDLE(
        coll,
        name="star.app",
        icon=None,
        bundle_identifier="org.star-reader.star",
        version=_mac_version,
        info_plist={
            "CFBundleName": "star",
            "CFBundleDisplayName": "star",
            "CFBundleShortVersionString": _mac_version,
            "CFBundleVersion": _mac_version,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            # Voice dictation records the microphone; macOS requires a usage
            # string or the app is killed when it first accesses the mic.
            "NSMicrophoneUsageDescription":
                "star uses the microphone for voice dictation.",
        },
    )
else:
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
        # Windowed GUI build by default (no console window flashes on launch).
        # Set STAR_CONSOLE=1 for a console build that also supports the curses
        # --tui mode and prints CLI output (see BUILD.md).
        console=_console,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
