# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller build spec for a portable, single-file Windows binary of star.
#
#   Build:   pyinstaller --clean star.spec
#   Output:  dist/star.exe   (onefile, windowed GUI)
#
# See BUILD.md for the full, step-by-step instructions (including how to make
# a console build that also supports the --tui terminal interface).

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Bundled data files ──────────────────────────────────────────────────────
# README.md is opened in-app by the Help command (F1), which resolves it via
# Path(__file__).parent.  In a frozen build PyInstaller sets __file__ inside
# the extraction directory, so shipping these at the bundle root keeps Help
# (and the license/changelog) working.
datas = [
    ("README.md", "."),
    ("LICENSE", "."),
    ("CHANGELOG.md", "."),
]

hiddenimports = [
    # pyttsx3 loads its platform driver dynamically at runtime; PyInstaller's
    # static analysis cannot see the SAPS5 (Windows) driver import, so name it.
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    # The SAPI5 driver talks to Windows speech through COM via comtypes.
    "comtypes",
    "comtypes.client",
    "comtypes.stream",
]

# Packages that ship templates / resource data needed at runtime.  Each collect
# is guarded so the spec still builds if an optional package is not installed.
for _pkg in ("pdfminer", "docx", "pptx", "odf", "openpyxl"):
    try:
        datas += collect_data_files(_pkg)
    except Exception:
        pass

# ── Vendored native tools (self-contained build) ────────────────────────────
# Bundle ffmpeg (audio export), Tesseract + English data (OCR), liblouis + its
# tables and Python binding (Grade 2 Braille), Pandoc (markup conversion), and
# DECtalk (DECtalk.dll + dictionary, driven in-process via ctypes).  The whole
# ``vendor/`` tree is mirrored at the
# bundle root so star.py's _vendor_dir() finds each tool under sys._MEIPASS at
# runtime.  Guarded so the spec still builds if a tool has not been downloaded.
import os as _os

_here = _os.path.dirname(_os.path.abspath(SPEC))
_vendor_root = _os.path.join(_here, "vendor")
if _os.path.isdir(_vendor_root):
    for _root, _dirs, _files in _os.walk(_vendor_root):
        # Skip the downloaded installer archive if it lingers.
        for _f in _files:
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
    ["star.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy / neural backends are optional and unnecessary for a Windows
        # demo (Windows uses the built-in SAPI5 voices via pyttsx3).  Excluding
        # them keeps the bundle from ballooning if they happen to be installed.
        "TTS",
        "torch",
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
