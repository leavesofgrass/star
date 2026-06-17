# -*- mode: python ; coding: utf-8 -*-
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

# ── Bundled data files ──────────────────────────────────────────────────────
# README.md is opened in-app by the Help command (F1), which resolves it via
# Path(__file__).parent.  __file__ now lives inside the star/ package, so the
# help docs ship under the bundle's ``star/`` folder (alongside the frozen
# package modules) rather than at the bundle root.
datas = [
    ("star/README.md", "star"),
    ("star/LICENSE", "star"),
    ("star/CHANGELOG.md", "star"),
]
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

# ── Dictation / transcription stack (Whisper + Torch) ───────────────────────
# Bundle openai-whisper and its full dependency stack so the dictation and
# audio-transcription features work out of the box on a clean Windows machine
# (no pip, no model download).  This is large (Torch alone is multiple GB) but
# is intentional: dictation should not require a separate install.  collect_all
# pulls each package's submodules, data files, and native libraries (e.g. the
# Torch DLLs, the llvmlite LLVM DLL, the sounddevice PortAudio DLL).
for _pkg in ("whisper", "torch", "numba", "llvmlite", "tiktoken", "sounddevice"):
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
_whisper_model = _os.path.join(_here, "build", "whisper_cache", "whisper", "base.pt")
if _os.path.isfile(_whisper_model):
    datas.append((_whisper_model, "whisper_cache/whisper"))

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

a = Analysis(
    ["run_star.py"],
    pathex=[_here],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[_os.path.join("tools", "rthook_star.py")],
    excludes=[
        # Coqui TTS is a heavy, optional neural backend unrelated to dictation;
        # Windows uses the built-in SAPI5 voices via pyttsx3.
        "TTS",
        "tensorflow",
        "tkinter",
        # Only one Qt binding is needed; star prefers PyQt6.  Excluding PyQt5
        # avoids bundling a second, unused Qt.
        "PyQt5",
    ],
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
    name="star",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Windowed GUI build (no console window flashes on launch).  For a build
    # that also supports the curses --tui mode, set console=True (see BUILD.md).
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
