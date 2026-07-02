"""Optional-dependency status reporting — the "what's installed?" harness.

star's defining design rule is that *every* third-party dependency is optional
and guarded at import time, so the core runs on the standard library alone.
This module is the single place that knows the full set of those optional
dependencies: it maps each guard flag to what the dependency unlocks and how to
install it, and reports which are currently available.

It powers ``star --deps`` and is exercised by ``tests/test_dependencies.py``,
which uses :data:`OPTIONAL_DEPENDENCIES` as the source of truth and fails if a
guard flag is ever added to the codebase without being registered here — so the
status report can never silently drop a dependency.

Each entry describes one dependency:

``key``       short stable identifier (also the ``--deps`` row id)
``label``     human-readable name
``group``     section heading for the report
``module``    dotted module that defines the guard flag (or ``None`` when the
              dependency is detected purely by probing — e.g. a binary on PATH)
``attr``      the guard-flag attribute on ``module`` (or ``None``)
``kind``      how to read the flag value: ``"bool"`` | ``"string"`` |
              ``"path"`` | ``"binary"`` | ``"probe"``
``probe``     import names that must *all* import for the dependency to count as
              present (used to verify the flag, and as the sole signal for
              ``probe``-kind entries)
``probe_any`` import names where *any* one importing counts as present
``binary``    executable looked up on PATH for ``binary``-kind entries
``enables``   one-line description of what the dependency unlocks
``install``   copy-pasteable install hint shown when the dependency is missing
"""
from ._runtime import *  # noqa: F401,F403

import importlib
import importlib.util


# Convenience: the canonical "install the whole recommended set" hint.
def _extra(name: str) -> str:
    return f'pip install "star-reader[{name}]"'


# The single source of truth for every optional dependency star can use.
OPTIONAL_DEPENDENCIES: List[Dict[str, Any]] = [
    # ── Documents & formats ────────────────────────────────────────────────
    {
        "key": "pdf", "label": "PDF text extraction", "group": "Documents",
        "module": "star._runtime", "attr": "_PDF", "kind": "string",
        "probe": ["pdfminer"], "enables": "Open and read PDF files",
        "install": "pip install pdfminer.six",
    },
    {
        "key": "docx", "label": "Word (.docx)", "group": "Documents",
        "module": "star._runtime", "attr": "_DOCX", "kind": "bool",
        "probe": ["docx"], "enables": "Open Word documents",
        "install": "pip install python-docx",
    },
    {
        "key": "pptx", "label": "PowerPoint (.pptx)", "group": "Documents",
        "module": "star._runtime", "attr": "_PPTX", "kind": "bool",
        "probe": ["pptx"], "enables": "Open PowerPoint decks",
        "install": "pip install python-pptx",
    },
    {
        "key": "odt", "label": "OpenDocument (.odt)", "group": "Documents",
        "module": "star._runtime", "attr": "_ODT", "kind": "bool",
        "probe": ["odf"], "enables": "Open OpenDocument text files",
        "install": _extra("formats"),
    },
    {
        "key": "xlsx", "label": "Excel (.xlsx)", "group": "Documents",
        "module": "star._runtime", "attr": "_XLSX", "kind": "bool",
        "probe": ["openpyxl"], "enables": "Open Excel spreadsheets",
        "install": _extra("formats"),
    },
    {
        "key": "ocr", "label": "OCR (pytesseract)", "group": "Documents",
        "module": "star._runtime", "attr": "_OCR", "kind": "bool",
        "probe": ["pytesseract", "PIL"],
        "enables": "Read scanned PDFs and images",
        "install": _extra("ocr"),
    },
    {
        "key": "pymupdf", "label": "PyMuPDF (PDF rasterizer)", "group": "Documents",
        "module": "star._runtime", "attr": "_PYMUPDF", "kind": "bool",
        "probe": ["fitz"], "enables": "Rasterize PDF pages for OCR",
        "install": _extra("ocr"),
    },
    {
        "key": "pypandoc", "label": "Pandoc (Python binding)", "group": "Documents",
        "module": "star._runtime", "attr": "_PYPANDOC", "kind": "bool",
        "probe": ["pypandoc"], "enables": "Convert extra markup formats",
        "install": _extra("markup"),
    },
    {
        "key": "pandoc_bin", "label": "Pandoc (binary)", "group": "Documents",
        "module": "star._runtime", "attr": "_PANDOC_BIN", "kind": "path",
        "binary": "pandoc",
        "enables": "Convert markup formats via the pandoc executable",
        "install": "Install pandoc and put it on PATH (https://pandoc.org)",
    },
    # ── Speech / TTS ───────────────────────────────────────────────────────
    {
        "key": "pyttsx3", "label": "pyttsx3 (system TTS)", "group": "Speech",
        "module": "star._runtime", "attr": "_PYTTSX3", "kind": "bool",
        "probe": ["pyttsx3"],
        "enables": "Cross-platform system voices (SAPI5 / NSSpeech / eSpeak)",
        "install": "pip install pyttsx3",
    },
    {
        "key": "coqui", "label": "Coqui TTS (neural)", "group": "Speech",
        "module": "star._runtime", "attr": "_COQUI", "kind": "bool",
        "probe": ["TTS"], "enables": "Coqui neural text-to-speech",
        "install": "pip install TTS",
    },
    {
        "key": "piper", "label": "Piper (neural, offline)", "group": "Speech",
        "module": "star._runtime", "attr": "_PIPER_BIN", "kind": "path",
        "binary": "piper",
        "enables": "Piper neural offline voices",
        "install": "Install the piper binary on PATH and download a voice model",
    },
    {
        "key": "whisper", "label": "Whisper (speech-to-text)", "group": "Speech",
        "module": "star._runtime", "attr": "_WHISPER", "kind": "string",
        "probe_any": ["whisper", "faster_whisper"],
        "enables": "Voice dictation and audio transcription",
        "install": _extra("transcribe"),
    },
    {
        "key": "audio_in", "label": "Microphone capture", "group": "Speech",
        "module": "star._runtime", "attr": "_AUDIO_IN", "kind": "bool",
        "probe": ["numpy", "sounddevice"],
        "enables": "Record audio for dictation",
        "install": _extra("transcribe"),
    },
    # ── Interface ──────────────────────────────────────────────────────────
    {
        "key": "qt", "label": "Qt GUI (PyQt6 / PyQt5)", "group": "Interface",
        "module": "star._runtime", "attr": "_QT", "kind": "string",
        "probe_any": ["PyQt6", "PyQt5"],
        "enables": "The primary windowed interface",
        "install": "pip install PyQt6",
    },
    {
        "key": "curses", "label": "Terminal UI (curses)", "group": "Interface",
        "module": "star._runtime", "attr": "_CURSES", "kind": "bool",
        # The real signal is the _curses C extension: on Windows the stdlib
        # `curses` package directory exists but `_curses` is only present once
        # windows-curses is installed.
        "probe": ["_curses"],
        "enables": "The keyboard-driven --tui terminal interface",
        "install": "pip install windows-curses  (Windows only; built in elsewhere)",
    },
    {
        "key": "clipboard", "label": "Clipboard (pyperclip)", "group": "Interface",
        "module": None, "attr": None, "kind": "probe",
        "probe": ["pyperclip"],
        "enables": "Copy the selection / paragraph to the system clipboard in the "
                   "TUI (an OSC-52 terminal escape is used otherwise)",
        "install": _extra("clipboard"),
    },
    # ── Export & study aids ────────────────────────────────────────────────
    {
        "key": "braille2", "label": "Grade 2 Braille (liblouis)",
        "group": "Export & study",
        "module": "star._runtime", "attr": "_LOUIS", "kind": "bool",
        "probe": ["louis"],
        "enables": "Contracted Grade 2 Braille export (Grade 1 is built in)",
        "install": _extra("braille"),
    },
    {
        "key": "audio_export", "label": "Audio export (pydub)",
        "group": "Export & study",
        "module": None, "attr": None, "kind": "probe",
        "probe": ["pydub"],
        "enables": "MP3 / OGG / MP4 export when ffmpeg muxing is needed",
        "install": _extra("audio"),
    },
    {
        "key": "ffmpeg", "label": "ffmpeg (binary)", "group": "Export & study",
        "module": None, "attr": None, "kind": "binary", "binary": "ffmpeg",
        "enables": "Encode MP3 / OGG / MP4 audio exports",
        "install": "Install ffmpeg and put it on PATH (https://ffmpeg.org)",
    },
    {
        "key": "summarize", "label": "Summarization (sumy)",
        "group": "Export & study",
        "module": "star.summarize", "attr": "_SUMY", "kind": "bool",
        "probe": ["sumy"], "enables": "Tools > Summarize Document",
        "install": _extra("summarize"),
    },
    {
        "key": "flashcards", "label": "Anki export (genanki)",
        "group": "Export & study",
        "module": "star.flashcards", "attr": "_GENANKI", "kind": "bool",
        "probe": ["genanki"], "enables": "File > Export > Anki Flashcards",
        "install": _extra("flashcards"),
    },
    {
        "key": "spellcheck", "label": "Spell check (pyspellchecker)",
        "group": "Export & study",
        "module": "star.spellcheck", "attr": "_SPELL", "kind": "bool",
        "probe": ["spellchecker"], "enables": "Edit > Check Spelling",
        "install": _extra("spellcheck"),
    },
    {
        "key": "translate", "label": "Translation (deep-translator)",
        "group": "Export & study",
        "module": "star.translate", "attr": "_DEEP_TRANSLATOR", "kind": "bool",
        "probe": ["deep_translator"], "enables": "Tools > Translate Document",
        "install": _extra("translate"),
    },
    {
        "key": "feeds", "label": "Feed reading (feedparser)",
        "group": "Export & study",
        "module": "star.feeds", "attr": "_FEEDPARSER", "kind": "bool",
        "probe": ["feedparser"], "enables": "File > Open Feed",
        "install": _extra("feeds"),
    },
    {
        "key": "vocab", "label": "Difficult words (wordfreq)",
        "group": "Export & study",
        "module": "star.vocab", "attr": "_WORDFREQ", "kind": "bool",
        "probe": ["wordfreq"],
        "enables": "View > Reading Aids > Highlight Difficult Words",
        "install": _extra("vocab"),
    },
    {
        "key": "dictionary", "label": "Offline definitions (WordNet)",
        "group": "Export & study",
        "module": "star.dictionary", "attr": "_NLTK", "kind": "bool",
        "probe": ["nltk"],
        "enables": "View > Reading Aids > Define Word (needs: nltk.downloader wordnet omw-1.4 cmudict)",
        "install": _extra("dictionary"),
    },
    # ── Hot-folder watching ────────────────────────────────────────────────
    {
        "key": "watchdog", "label": "Filesystem events (watchdog)",
        "group": "Automation",
        "module": "star.watch", "attr": "_WATCHDOG", "kind": "bool",
        "probe": ["watchdog"],
        "enables": "Instant --watch reaction (polling is the fallback)",
        "install": _extra("watch"),
    },
    # ── Knowledge graph ────────────────────────────────────────────────────
    {
        "key": "spacy", "label": "spaCy (NER)", "group": "Knowledge graph",
        "module": None, "attr": None, "kind": "probe", "probe": ["spacy"],
        "enables": "Named-entity concept extraction for the knowledge graph",
        "install": "pip install spacy && python -m spacy download en_core_web_sm",
    },
    {
        "key": "nltk", "label": "NLTK (NER fallback)", "group": "Knowledge graph",
        "module": None, "attr": None, "kind": "probe", "probe": ["nltk"],
        "enables": "Concept extraction when spaCy is absent",
        "install": "pip install nltk",
    },
    {
        "key": "graphviz", "label": "Graphviz (graph layout)",
        "group": "Knowledge graph",
        "module": None, "attr": None, "kind": "probe", "probe": ["graphviz"],
        "enables": "High-quality graph layout and SVG/DOT export (pure-Python fallback otherwise)",
        "install": "pip install graphviz  (also needs the graphviz binary)",
    },
    {
        "key": "plantuml", "label": "PlantUML (diagram render)",
        "group": "Knowledge graph",
        "module": None, "attr": None, "kind": "probe", "probe": ["plantuml"],
        "enables": "Render PlantUML graph exports to SVG",
        "install": "pip install plantuml",
    },
    {
        "key": "pyyaml", "label": "PyYAML (front matter)",
        "group": "Knowledge graph",
        "module": None, "attr": None, "kind": "probe", "probe": ["yaml"],
        "enables": "Richer YAML front-matter parsing for Obsidian vault import "
        "(a built-in parser is used otherwise)",
        "install": "pip install pyyaml",
    },
    # ── Archive ingestion ──────────────────────────────────────────────────
    {
        "key": "py7zr", "label": "7-Zip archives (py7zr)", "group": "Archive",
        "module": None, "attr": None, "kind": "probe", "probe": ["py7zr"],
        "enables": "Open .7z archive files",
        "install": _extra("archive"),
    },
    {
        "key": "rarfile", "label": "RAR archives (rarfile)", "group": "Archive",
        "module": None, "attr": None, "kind": "probe", "probe": ["rarfile"],
        "enables": "Open .rar archive files",
        "install": _extra("archive"),
    },
    # ── Video export ───────────────────────────────────────────────────────
    {
        "key": "pillow_video", "label": "Pillow (video frame renderer)",
        "group": "Export & study",
        "module": None, "attr": None, "kind": "probe", "probe": ["PIL"],
        "enables": "Render karaoke video frames when Qt is unavailable",
        "install": _extra("video"),
    },
    # ── Live document-camera capture ───────────────────────────────────────
    {
        "key": "opencv", "label": "OpenCV (document camera)", "group": "Capture",
        "module": "star._runtime", "attr": "_OPENCV", "kind": "bool",
        "probe": ["cv2"], "enables": "Live capture from a UVC document camera",
        "install": "pip install opencv-python",
    },
    {
        "key": "pygrabber", "label": "pygrabber (camera names)", "group": "Capture",
        "module": "star._runtime", "attr": "_PYGRABBER", "kind": "bool",
        "probe": ["pygrabber"],
        "enables": "Show camera device names on Windows (DirectShow)",
        "install": "pip install pygrabber",
    },
]


# Enforced by tests/test_plugins.py — every key must have all listed entry-points
# resolvable after `pip install -e .`.
PLUGIN_ENTRY_POINTS: dict[str, list[str]] = {
    "star.backends": [
        "silent", "pyttsx3", "applesay", "espeak", "espeaklib",
        "festival", "piper", "coqui", "dectalk", "dectalkdll",
    ],
    "star.formats": [
        "pdf", "epub", "docx", "odt", "pptx", "xlsx",
        "html", "markdown", "txt", "rst", "org", "pandoc",
    ],
    "star.exporters": [
        "anki", "markdown", "html", "epub", "wav", "mp4",
    ],
}


def _module_present(name: str) -> bool:
    """True when import name *name* can be imported (without importing it)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        # A namespace-package edge case or a broken parent package.
        return False


def probe_present(dep: Dict[str, Any]) -> Optional[bool]:
    """Independent availability signal for *dep*, ignoring its guard flag.

    Returns True/False from importing the dependency's probe modules (all of
    ``probe`` must import; any of ``probe_any`` suffices) or, for a binary,
    whether the executable is on PATH.  Returns ``None`` when there is nothing
    to probe (so the caller can skip the consistency check).
    """
    binary = dep.get("binary")
    if dep.get("kind") == "binary" or (binary and not dep.get("probe") and not dep.get("probe_any")):
        return shutil.which(binary) is not None if binary else None
    probe = dep.get("probe")
    probe_any = dep.get("probe_any")
    if probe:
        return all(_module_present(m) for m in probe)
    if probe_any:
        return any(_module_present(m) for m in probe_any)
    if binary:
        return shutil.which(binary) is not None
    return None


def _read_flag(dep: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
    """Return ``(raw_value, error)`` for *dep*'s guard flag.

    ``raw_value`` is ``None`` and ``error`` is set when the module cannot be
    imported or the attribute is missing.  Probe-only entries (no module/attr)
    return ``(None, None)``.
    """
    mod_name = dep.get("module")
    attr = dep.get("attr")
    if not mod_name or not attr:
        return None, None
    try:
        mod = importlib.import_module(mod_name)
    except Exception as exc:  # noqa: BLE001
        return None, f"cannot import {mod_name}: {exc}"
    if not hasattr(mod, attr):
        return None, f"{mod_name} has no attribute {attr}"
    return getattr(mod, attr), None


def _is_available(dep: Dict[str, Any], raw_value: Any) -> bool:
    """Interpret a guard flag's raw value as an availability boolean."""
    kind = dep.get("kind")
    if kind in ("string", "path"):
        # "" / None mean absent; any other value (e.g. "PyQt6", a path) present.
        return bool(raw_value)
    if kind in ("binary", "probe"):
        # No guard flag — availability is whatever probing says.
        probed = probe_present(dep)
        return bool(probed)
    return bool(raw_value)


def dependency_status() -> List[Dict[str, Any]]:
    """Report the current availability of every optional dependency.

    Each result dict has: ``key``, ``label``, ``group``, ``available`` (bool),
    ``value`` (the raw guard-flag value, or ``None`` for probe-only entries),
    ``enables``, ``install``, and ``error`` (``None`` unless the guard module
    could not be read).
    """
    out: List[Dict[str, Any]] = []
    for dep in OPTIONAL_DEPENDENCIES:
        raw_value, error = _read_flag(dep)
        available = False if error else _is_available(dep, raw_value)
        out.append(
            {
                "key": dep["key"],
                "label": dep["label"],
                "group": dep["group"],
                "available": available,
                "value": raw_value,
                "enables": dep["enables"],
                "install": dep["install"],
                "error": error,
            }
        )
    return out


def format_dependency_report(statuses: Optional[List[Dict[str, Any]]] = None) -> str:
    """Render :func:`dependency_status` as a grouped, human-readable report."""
    if statuses is None:
        statuses = dependency_status()
    present = sum(1 for s in statuses if s["available"])
    lines: List[str] = [
        f"star {APP_VERSION} - optional dependency status "
        f"({present}/{len(statuses)} available)",
        "",
    ]
    # Preserve the registry's group ordering.
    seen_groups: List[str] = []
    for s in statuses:
        if s["group"] not in seen_groups:
            seen_groups.append(s["group"])
    for group in seen_groups:
        lines.append(f"{group}:")
        for s in statuses:
            if s["group"] != group:
                continue
            mark = "+" if s["available"] else "-"
            line = f"  [{mark}] {s['label']} - {s['enables']}"
            if not s["available"]:
                line += f"\n        install: {s['install']}"
                if s["error"]:
                    line += f"\n        note: {s['error']}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
