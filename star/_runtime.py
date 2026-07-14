#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
star — Speaking Terminal Access Reader
=======================================

A fast, keyboard-driven reading and text-to-speech application designed for
students with print disabilities.
Particularly suited for graduate students in Health Sciences,
but usable enough for high school students.

Inspired by Emacspeak, Kurzweil 1000, Natural Reader, and Central Access Reader.

QUICK START
-----------
    star                       # launch Qt GUI (default)
    star document.pdf          # open a file in the Qt GUI
    star https://example.com   # fetch and read a URL
    star --tui                 # force terminal UI mode
    star --plain paper.pdf     # extract text to stdout

    Qt GUI shortcuts
    ----------------
    Space          play / pause speech
    Ctrl+O         open a file
    Ctrl+H / P / T  next heading / paragraph / table
    F5             cycle theme
    F1             open README.md
    Ctrl+Q         quit

    Terminal UI shortcuts
    ---------------------
    Space        play / pause speech
    Ctrl-O       open a file
    F2           command palette
    F1           open README.md
    Ctrl-Q / q   quit

Copyright (C) 2026 Jon Pielaet
License: GNU General Public License v3 (or later)
"""

__version__ = "0.1.26"
__author__ = "Jon Pielaet"
__copyright__ = "Copyright (C) 2026 the star authors"
__license__ = "GPL-3.0-or-later"
__url__ = "https://github.com/leavesofgrass/star"

# =============================================================================
# Standard library
# =============================================================================

import argparse
import csv
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Curses (terminal UI / --tui mode).  curses is in the Python standard library,
# but on Windows the underlying ``_curses`` C extension is not built into
# CPython — it is supplied by the optional ``windows-curses`` package.  Import
# windows_curses first (its mere installation makes stdlib ``curses`` importable
# on Windows), then guard the curses import itself so a machine without it can
# still run the Qt GUI and the command-line modes; only the curses ``--tui``
# interface is unavailable.  ``curses`` is left as ``None`` when absent — every
# curses call lives inside the TUI runtime path, never at import time.
try:
    import windows_curses  # noqa: F401
except ImportError:
    pass

try:
    import curses

    _CURSES = True
except ImportError:
    curses = None  # type: ignore[assignment]
    _CURSES = False

# ----------------------------------------------------------------------------
# Lazy optional-dependency detection.
# ----------------------------------------------------------------------------
# Heavy optional packages (Whisper -> PyTorch, Coqui's ML stack, wordfreq's
# frequency data, sounddevice, …) used to be imported eagerly at module load.
# Because every star module does ``from ._runtime import *``, that meant *every*
# launch paid the multi-second cost of importing them even when the feature was
# never used.  We now detect availability cheaply with importlib.util.find_spec
# (which locates a module WITHOUT executing it) and defer the real import to a
# ``_load_*`` helper called the first time the feature actually runs.  The
# ``_HAS``/string flags keep the same meaning, so star --deps and feature gating
# are unchanged; only the up-front import cost is removed.
from importlib.util import find_spec as _find_spec


def _module_available(name: str) -> bool:
    """True when *name* can be imported, without importing it (keeps startup fast)."""
    try:
        return _find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        # Broken parent package or namespace-package edge case → treat as absent.
        return False


# On Windows, a console-less (windowed) parent that spawns a console child pops
# a black console window that steals focus — in star that means every pandoc
# document open, every ffmpeg mux, and every per-utterance espeak/dectalk call
# flashes a window and yanks screen readers to it.  Every subprocess star
# starts must pass ``creationflags=_SUBPROCESS_FLAGS``.  Harmless where a
# console already exists (TUI/CLI: the child just doesn't get its own), and 0
# on POSIX.
_SUBPROCESS_FLAGS = (
    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
)

# =============================================================================
# Bundled native tools (vendored for the self-contained Windows build)
# =============================================================================
# ffmpeg (audio export), Tesseract (OCR), liblouis (Grade 2 Braille), Pandoc
# (markup conversion), and DECtalk (TTS) are native engines, not Python
# packages.  When present they are shipped under a ``vendor/`` tree next to
# the ``star`` package (source runs) or at the PyInstaller bundle root (frozen runs).  Each
# lookup falls back to a system install when the bundled copy is absent, so
# star still runs from source with zero extras.


def _vendor_dir() -> Path:
    """Directory that holds the vendored native tools (ffmpeg, Tesseract,
    liblouis, Pandoc, DECtalk, libespeak-ng).

    Resolution order:

    1. ``STAR_VENDOR_DIR`` — an explicit directory the user points star at.  This
       is the supported way to supply the native engines to a wheel / pipx /
       source install (the wheel does not bundle them).  Lay the folder out like
       the repo ``vendor/`` tree (``ffmpeg/ffmpeg.exe``, ``tesseract/``,
       ``liblouis/``, ``pandoc/pandoc.exe``, ``dectalk/<arch>/DECtalk.dll``,
       ``espeak-ng/libespeak-ng.dll`` + ``espeak-ng-data``).
    2. ``sys._MEIPASS`` — the PyInstaller onefile extraction dir (frozen builds
       stage the tree at the bundle root).
    3. ``star/vendor`` next to this package, then ``vendor/`` at the project root
       (one level up) — the location ``tools/build-vendor.py`` assembles, so a
       source checkout finds it automatically.
    """
    override = os.environ.get("STAR_VENDOR_DIR")
    if override:
        p = Path(override).expanduser()
        if p.is_dir():
            return p
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller onefile extraction dir
    if base:
        return Path(base)
    # Source / wheel runs: prefer a ``vendor/`` beside the package, then one at
    # the project root (one level up) — the location ``tools/build-vendor.py``
    # assembles, so a source checkout finds it with no env var.
    pkg_vendor = Path(__file__).resolve().parent / "vendor"
    if pkg_vendor.is_dir():
        return pkg_vendor
    repo_vendor = Path(__file__).resolve().parent.parent / "vendor"
    if repo_vendor.is_dir():
        return repo_vendor
    return pkg_vendor


_VENDOR = _vendor_dir()
_FFMPEG_BUNDLED = _VENDOR / "ffmpeg" / "ffmpeg.exe"
_TESSERACT_BUNDLED = _VENDOR / "tesseract" / "tesseract.exe"
_TESSDATA_BUNDLED = _VENDOR / "tesseract" / "tessdata"
_LIBLOUIS_DIR = _VENDOR / "liblouis"
_LIBLOUIS_TABLES = _LIBLOUIS_DIR / "tables"
_PANDOC_BUNDLED = _VENDOR / "pandoc" / "pandoc.exe"
_DECTALK_DIR = _VENDOR / "dectalk"
# eSpeak-NG, driven in-process through libespeak-ng via ctypes.  The library
# delivers per-word events tagged with their audio position, which lets the
# reading highlight follow actual playback instead of a free-running estimate.
_ESPEAK_NG_DIR = _VENDOR / "espeak-ng"
_ESPEAK_NG_DLL = _ESPEAK_NG_DIR / "libespeak-ng.dll"
_ESPEAK_NG_DATA = _ESPEAK_NG_DIR / "espeak-ng-data"


def _find_bundled_dectalk() -> Optional[str]:
    """Locate a bundled DECtalk command-line binary, if one was vendored.

    The backend below drives a ``say``/``dtalk``-style CLI (text on stdin,
    ``-w`` for WAV output), so only those names qualify; the GUI ``speak.exe``
    that ships in the official Windows release is intentionally ignored.
    """
    if not _DECTALK_DIR.is_dir():
        return None
    names = ("say.exe", "dtalk.exe", "dectalk.exe", "say", "dtalk", "dectalk")
    for n in names:
        p = _DECTALK_DIR / n
        if p.is_file():
            return str(p)
    for p in _DECTALK_DIR.rglob("*"):
        if p.is_file() and p.name in names:
            return str(p)
    return None


_DECTALK_BUNDLED = _find_bundled_dectalk()

# DECtalk.dll for the in-process (ctypes) backend.  Vendored per-architecture
# because a 64-bit star.exe cannot load a 32-bit DLL (and vice versa); each
# arch folder also holds the dtalk_us.dic the engine loads from its directory.
_DECTALK_ARCH = "amd64" if sys.maxsize > 2**32 else "ia32"
_DECTALK_DLL = _DECTALK_DIR / _DECTALK_ARCH / "DECtalk.dll"

# Point pypandoc at the bundled Pandoc (it honours $PYPANDOC_PANDOC) so the
# self-contained build converts markup with no separate Pandoc install.
if _PANDOC_BUNDLED.is_file():
    os.environ.setdefault("PYPANDOC_PANDOC", str(_PANDOC_BUNDLED))

# liblouis must be wired up *before* ``import louis`` below: the binding loads
# the DLL at import time, and we point it at the bundled DLL via LIBLOUIS_DLL
# and make the vendored ``louis`` package importable.
if (_LIBLOUIS_DIR / "liblouis.dll").is_file():
    try:
        os.add_dll_directory(str(_LIBLOUIS_DIR))  # Windows / Python 3.8+
    except (AttributeError, OSError):
        pass
    os.environ["LIBLOUIS_DLL"] = str(_LIBLOUIS_DIR / "liblouis.dll")
    os.environ.setdefault("LOUIS_TABLEPATH", str(_LIBLOUIS_TABLES))
    if str(_LIBLOUIS_DIR) not in sys.path:
        sys.path.insert(0, str(_LIBLOUIS_DIR))

# Make the vendored libespeak-ng.dll's directory discoverable so the in-process
# ctypes eSpeak backend (and any co-located dependency DLLs) loads cleanly on
# the self-contained Windows build.
if _ESPEAK_NG_DLL.is_file():
    try:
        os.add_dll_directory(str(_ESPEAK_NG_DIR))
    except (AttributeError, OSError):
        pass

# =============================================================================
# Optional dependencies — all guarded; star runs with zero extras installed
# =============================================================================

# Document loaders are detected cheaply with find_spec and imported lazily by
# the ``_load_*`` helpers below, called from documents.py the first time a file
# of that type is opened.  This keeps PyMuPDF, openpyxl, python-docx/pptx,
# pdfminer, etc. off the startup path entirely.

# --- PDF: pdfminer.six -------------------------------------------------------
# Probe the TOP-LEVEL package only: find_spec on a dotted name (the old
# "pdfminer.layout" probe) imports the parent package to resolve it — ~22 ms
# of exactly the startup cost this probe exists to avoid.  pdfminer.six
# always ships layout + high_level together, so package presence implies the
# "layout" strategy; the legacy "simple" fallback in documents/pdf.py remains
# for exotic installs but is no longer probed for at startup.
_PDF = "layout" if _module_available("pdfminer") else ""


def _load_pdf_text():
    """Return pdfminer's ``extract_text`` (deferred from startup)."""
    from pdfminer.high_level import extract_text

    return extract_text


def _load_pdf_pages():
    """Return ``(extract_pages, LTTextBoxHorizontal)`` from pdfminer (deferred)."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextBoxHorizontal

    return extract_pages, LTTextBoxHorizontal


# --- OCR: pytesseract + PyMuPDF ---------------------------------------------
_OCR = _module_available("pytesseract") and _module_available("PIL")


def _load_ocr():
    """Return ``(pytesseract, PIL.Image)``, wiring the bundled Tesseract if present."""
    import pytesseract
    from PIL import Image

    # Point pytesseract at the bundled Tesseract engine + language data when
    # present, so OCR works with no separate Tesseract install.
    if _TESSERACT_BUNDLED.is_file():
        try:
            pytesseract.pytesseract.tesseract_cmd = str(_TESSERACT_BUNDLED)
            if _TESSDATA_BUNDLED.is_dir():
                os.environ.setdefault("TESSDATA_PREFIX", str(_TESSDATA_BUNDLED))
        except Exception:
            pass
    return pytesseract, Image


# --- PDF rasterizer: PyMuPDF -------------------------------------------------
_PYMUPDF = _module_available("fitz")


def _load_fitz():
    """Return the PyMuPDF (``fitz``) module (deferred from startup)."""
    import fitz

    return fitz


# --- DOCX: python-docx -------------------------------------------------------
_DOCX = _module_available("docx")


def _load_docx():
    """Return the python-docx (``docx``) module (deferred from startup)."""
    import docx

    return docx


# --- ODT: odfpy --------------------------------------------------------------
# Availability only; the ODT loader in documents.py imports odf locally.
_ODT = _module_available("odf")

# --- PowerPoint: python-pptx --------------------------------------------------
_PPTX = _module_available("pptx")


def _load_pptx():
    """Return the python-pptx (``pptx``) module (deferred from startup)."""
    import pptx

    return pptx


# --- XLSX: openpyxl ----------------------------------------------------------
_XLSX = _module_available("openpyxl")


def _load_openpyxl():
    """Return the openpyxl module (deferred from startup)."""
    import openpyxl

    return openpyxl

# --- TTS: pyttsx3 ------------------------------------------------------------
# Detected without importing; the real import is deferred to _load_pyttsx3(),
# called the first time a pyttsx3 engine is built.
_PYTTSX3 = _module_available("pyttsx3")


def _load_pyttsx3():
    """Import and return the pyttsx3 module (deferred from startup)."""
    import pyttsx3

    return pyttsx3


# --- TTS: Coqui TTS (neural) -------------------------------------------------
# Coqui pulls in a large ML stack, so it is detected via find_spec and imported
# lazily by _load_coqui() only when the Coqui backend is actually selected.
_COQUI = _module_available("TTS")


def _load_coqui():
    """Import and return the Coqui ``TTS`` class (deferred from startup)."""
    from TTS.api import TTS  # type: ignore[import]

    return TTS

# --- TTS: Piper (neural, local, offline) -------------------------------------
# Piper ships as a standalone binary that reads text on stdin and writes a WAV
# file.  It needs no Python package — only the `piper` executable on PATH and a
# downloaded voice model (.onnx + .onnx.json).  Detection is just "is the
# binary present"; whether a usable model exists is decided per-backend.
_PIPER_BIN = shutil.which("piper") or shutil.which("piper-tts")

# --- Qt GUI: PyQt6 or PyQt5 --------------------------------------------------
_QT = None
try:
    from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
    from PyQt6.QtGui import (
        QAction,  # PyQt6 moved QAction from QtWidgets to QtGui
        QColor,
        QFont,
        QFontDatabase,
        QTextBlockFormat,
        QTextCharFormat,
        QTextCursor,
        QTextFormat,
    )
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDockWidget,
        QColorDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFontDialog,
        QFormLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QSplitter,
        QStatusBar,
        QTextBrowser,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )

    _QT = "PyQt6"
except ImportError:
    try:
        from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
        from PyQt5.QtGui import (
            QColor,
            QFont,
            QFontDatabase,
            QTextBlockFormat,
            QTextCharFormat,
            QTextCursor,
            QTextFormat,
        )
        from PyQt5.QtWidgets import (
            QAction,
            QApplication,
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDockWidget,
            QColorDialog,
            QDoubleSpinBox,
            QFileDialog,
            QFontDialog,
            QFormLayout,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPushButton,
            QSpinBox,
            QSplitter,
            QStatusBar,
            QTextBrowser,
            QTextEdit,
            QToolBar,
            QVBoxLayout,
            QWidget,
        )

        _QT = "PyQt5"
    except ImportError:
        pass

# --- Braille: louis (liblouis Python binding) --------------------------------
try:
    import louis as _louis

    _LOUIS = True
except ImportError:
    _LOUIS = False

# --- Pandoc: pypandoc (subprocess fallback also available) -------------------
try:
    import pypandoc as _pypandoc

    _PYPANDOC = True
except ImportError:
    _PYPANDOC = False

# Prefer the bundled Pandoc (self-contained build); fall back to PATH.
_PANDOC_BIN = (
    str(_PANDOC_BUNDLED) if _PANDOC_BUNDLED.is_file() else shutil.which("pandoc")
)

# --- Speech recognition: OpenAI Whisper (or faster-whisper) ------------------
# Used for dictation and recording transcription.  Both the model library and
# a microphone capture library are optional; every code path is guarded so the
# program runs identically when they are absent.
# Whisper pulls in PyTorch — a multi-second import — so it is never imported at
# startup.  Detect which backend is installed (cheap), and defer the real import
# to _load_whisper() / _load_faster_whisper(), called only when a transcription
# or dictation actually runs.
# Backend selection.  Auto-detect by default (prefer openai-whisper when both
# are installed, so existing installs are untouched), but honour an explicit
# STAR_WHISPER_BACKEND=openai|faster override — the spike/faster-whisper switch
# that lets a user with both stacks installed force the CTranslate2 path without
# uninstalling Torch.  Unknown/empty value falls through to auto-detect.
_WHISPER_OVERRIDE = os.environ.get("STAR_WHISPER_BACKEND", "").strip().lower()


def _whisper_backend_now() -> str:
    """Pick the speech-to-text backend from what's importable *right now*.

    Prefer openai-whisper when both are installed (so existing Torch installs
    are untouched), but honour ``STAR_WHISPER_BACKEND=openai|faster``.  Returns
    ``""`` when neither is present.  Checked fresh rather than trusting the
    import-time ``_WHISPER`` snapshot so a same-session ``transcribe`` install
    works without a restart — faster-whisper (CTranslate2, no Torch) imports
    cleanly into a running process, so nothing forces a fresh process anymore.
    Mirrors :func:`_audio_in_now` for the microphone half."""
    if _WHISPER_OVERRIDE == "openai" and _module_available("whisper"):
        return "openai"
    if _WHISPER_OVERRIDE == "faster" and _module_available("faster_whisper"):
        return "faster"
    if _module_available("whisper"):
        return "openai"
    if _module_available("faster_whisper"):
        return "faster"
    return ""


# Import-time snapshot (kept for diagnostics + cheap gating); the transcription
# call sites use _whisper_backend_now() so a runtime install needs no restart.
_WHISPER = _whisper_backend_now()


def _load_whisper():
    """Import and return the openai-whisper module (deferred from startup)."""
    import whisper

    return whisper


def _load_faster_whisper():
    """Import and return faster-whisper's WhisperModel class (deferred from startup)."""
    from faster_whisper import WhisperModel  # type: ignore

    return WhisperModel


def _faster_whisper_model_dir() -> Optional[str]:
    """The bundled CTranslate2 model directory in a frozen build, else None.

    star.spec stages ``Systran/faster-whisper-base`` at
    ``<bundle>/faster_whisper_model`` so dictation runs fully offline with no HF
    download.  A source / pip install returns None and downloads the model by
    name on first use."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        d = os.path.join(base, "faster_whisper_model")
        if os.path.isdir(d):
            return d
    return None


def _new_faster_model(model_name: str = "base"):
    """Construct a faster-whisper (CTranslate2) model for CPU-int8 inference.

    int8 is the quantised CPU path that gives CTranslate2 its speed and memory
    win over Torch fp32; device is pinned to CPU because star's frozen builds
    ship no CUDA.  STAR_WHISPER_COMPUTE overrides the compute type for testing
    (e.g. ``int8_float32`` / ``float32``).

    In a frozen build the bundled ``base`` model directory is loaded with
    ``local_files_only=True`` (+ ``HF_HUB_OFFLINE``) so no network is touched.
    Any *other* size the user picked (the ``whisper_model`` setting) is
    downloaded/cached by faster-whisper as usual — lifting the rthook's
    offline default first, since that default exists only to keep the bundled
    path network-free, never to override an explicit user choice.  A
    user-set ``HF_HUB_OFFLINE`` is left alone (the download then fails with
    hub's own offline error rather than silently ignoring their environment)."""
    compute = os.environ.get("STAR_WHISPER_COMPUTE", "int8").strip() or "int8"
    WhisperModel = _load_faster_whisper()
    bundled = _faster_whisper_model_dir()
    if bundled and model_name in ("", "base"):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        return WhisperModel(
            bundled, device="cpu", compute_type=compute, local_files_only=True
        )
    if bundled:
        for var in os.environ.get("_STAR_HF_OFFLINE_DEFAULT", "").split(","):
            if var:
                os.environ.pop(var, None)
    return WhisperModel(model_name, device="cpu", compute_type=compute)


# Microphone capture (numpy + sounddevice).  Detected without importing; the
# sounddevice module is loaded lazily by _load_sounddevice() at record time.
_AUDIO_IN = _module_available("numpy") and _module_available("sounddevice")


def refresh_whisper_backend() -> bool:
    """Re-detect the dictation stack after a runtime install; no restart needed.

    Refreshes the import-time ``_WHISPER`` / ``_AUDIO_IN`` snapshots (which
    diagnostics and the cheap gates read) so they agree with reality once
    faster-whisper + sounddevice land mid-session.  Returns True when a
    speech-to-text backend is now importable.  The transcription call sites
    already detect fresh via :func:`_whisper_backend_now`, so this is really
    about the GUI reporting "you can use it now" instead of "restart"."""
    global _WHISPER, _AUDIO_IN
    import importlib

    importlib.invalidate_caches()
    _WHISPER = _whisper_backend_now()
    _AUDIO_IN = _module_available("numpy") and _module_available("sounddevice")
    return bool(_WHISPER)


def _load_sounddevice():
    """Import and return the sounddevice module (deferred from startup)."""
    import sounddevice

    return sounddevice

# --- Live document-camera capture: OpenCV (UVC webcam-class devices) ----------
# Used by the live-capture feature (capture.py) to grab frames from a connected
# UVC document camera (e.g. a Czur unit, which presents as a standard webcam).
# Optional and fully guarded: when OpenCV is absent the feature is simply
# unavailable and the rest of star runs unchanged.  On Windows, device *names*
# (OpenCV only exposes indices) come from the optional ``pygrabber`` DirectShow
# helper when present; index probing is the fallback everywhere.
try:
    import cv2 as _cv2

    _OPENCV = True
except ImportError:
    _OPENCV = False
    _cv2 = None  # type: ignore[assignment]

try:
    from pygrabber.dshow_graph import FilterGraph as _DShowFilterGraph

    _PYGRABBER = True
except ImportError:
    _PYGRABBER = False
    _DShowFilterGraph = None  # type: ignore[assignment]

# =============================================================================
# Metadata & paths
# =============================================================================

APP_NAME = "star"
APP_TITLE = "Speaking Terminal Access Reader"
APP_VERSION = __version__

if sys.platform == "win32":
    _CFG_ROOT = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
elif sys.platform == "darwin":
    _CFG_ROOT = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    _CFG_ROOT = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    )

SETTINGS_FILE = _CFG_ROOT / "settings.json"
CACHE_DIR = _CFG_ROOT / "cache"
THEMES_DIR = _CFG_ROOT / "themes"  # user CSS theme files live here
LOG_FILE = _CFG_ROOT / "star.log"


def _default_sans_font() -> str:
    """Return a high-quality sans-serif display font for the current platform.

    Sans-serif faces are preferred over serif for on-screen reading
    accessibility (lower visual crowding, clearer letterforms for readers
    with low vision or dyslexia).  Each value is a face that ships with the
    OS, so it resolves without the user installing anything; Qt falls back
    to its generic sans-serif if the named family is somehow missing.
    """
    if sys.platform == "darwin":
        return "Helvetica Neue"
    if sys.platform == "win32":
        return "Segoe UI"
    return "DejaVu Sans"

# Sentence boundary detector.
# Matches the gap between sentences: terminal punctuation followed by
# whitespace + an uppercase letter / opening quote, or a blank line.
# Intentionally simple — some abbreviations (Dr., Mr.) will cause false
# splits, which is acceptable for a reading application.
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?\u2026])\s+(?=[A-Z\"\u201c\u2018(])"
    r"|(?<=[.!?\u2026])\s*\n"
    r"|\n{2,}"
)

# Re-export every module-level name (so `from ._runtime import *`
# rehydrates the shared namespace the rest of the package was written
# against).  Optional names are only present when their import succeeded.  The metadata dunders are
# re-exported explicitly because `import *` skips underscored names
# unless they are named in __all__.
__all__ = [n for n in dict(globals()) if not n.startswith("__")]
__all__ += ["__version__", "__author__", "__copyright__", "__license__", "__url__"]
