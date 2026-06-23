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

__version__ = "0.1.8rc2"
__author__ = "Jon Pielaet"
__copyright__ = "Copyright (C) 2026 Jon Pielaet"
__license__ = "GPL-3.0-or-later"

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
    """Directory that holds the vendored native tools."""
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller onefile extraction dir
    if base:
        return Path(base)
    return Path(__file__).resolve().parent / "vendor"


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

# --- PDF: pdfminer.six -------------------------------------------------------
try:
    from pdfminer.high_level import extract_pages as _pdf_pages
    from pdfminer.high_level import extract_text as _pdf_text
    from pdfminer.layout import LTTextBoxHorizontal

    _PDF = "layout"
except ImportError:
    try:
        from pdfminer.high_level import extract_text as _pdf_text  # type: ignore

        _PDF = "simple"
    except ImportError:
        _PDF = ""

# --- OCR: pytesseract + PyMuPDF ---------------------------------------------
try:
    import pytesseract as _tesseract
    from PIL import Image as _PIL_Image

    _OCR = True
    # Point pytesseract at the bundled Tesseract engine + language data when
    # present, so OCR works with no separate Tesseract install.
    if _TESSERACT_BUNDLED.is_file():
        try:
            _tesseract.pytesseract.tesseract_cmd = str(_TESSERACT_BUNDLED)
            if _TESSDATA_BUNDLED.is_dir():
                os.environ.setdefault("TESSDATA_PREFIX", str(_TESSDATA_BUNDLED))
        except Exception:
            pass
except ImportError:
    _OCR = False

try:
    import fitz as _fitz  # PyMuPDF

    _PYMUPDF = True
except ImportError:
    _PYMUPDF = False

# --- DOCX: python-docx -------------------------------------------------------
try:
    import docx as _docx_lib

    _DOCX = True
except ImportError:
    _DOCX = False

# --- ODT: odfpy --------------------------------------------------------------
try:
    from odf.opendocument import load as _odf_load
    from odf.text import H, ListItem, P
    from odf.text import List as OdfList

    _ODT = True
except ImportError:
    _ODT = False

# --- PowerPoint: python-pptx --------------------------------------------------
try:
    import pptx as _pptx_lib

    _PPTX = True
except ImportError:
    _PPTX = False
    _pptx_lib = None


# --- XLSX: openpyxl ----------------------------------------------------------
try:
    import openpyxl as _openpyxl

    _XLSX = True
except ImportError:
    _XLSX = False

# --- TTS: pyttsx3 ------------------------------------------------------------
try:
    import pyttsx3 as _pyttsx3

    _PYTTSX3 = True
except ImportError:
    _PYTTSX3 = False

# --- TTS: Coqui TTS (neural) -------------------------------------------------
try:
    from TTS.api import TTS as _CoquiTTS  # type: ignore[import]

    _COQUI = True
except (ImportError, Exception):  # also catches missing dependencies
    _COQUI = False
    _CoquiTTS = None  # type: ignore[assignment]

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
try:
    import whisper as _whisper  # openai-whisper

    _WHISPER = "openai"
except ImportError:
    try:
        from faster_whisper import WhisperModel as _FasterWhisper  # type: ignore

        _WHISPER = "faster"
    except ImportError:
        _WHISPER = ""

try:
    import numpy as _np
    import sounddevice as _sounddevice  # microphone capture

    _AUDIO_IN = True
except ImportError:
    _AUDIO_IN = False

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
__all__ += ["__version__", "__author__", "__copyright__", "__license__"]
