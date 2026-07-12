"""On-demand installation of star's optional Python dependencies.

star's core is stdlib + a small base install; every heavier capability is an
*optional* package with a graceful pure-Python (or built-in) fallback, catalogued
in :mod:`star.diagnostics`. This module turns those optional groups into
user-choosable **features** and installs them on request via pip.

Unlike a silent "full-fat" installer, star only fetches what the user asks for —
star is an offline-first accessibility tool and some features are large (Whisper +
PyTorch is ~2 GB). The first-run chooser (:mod:`star.gui.deps_dialog`) presents
these features; this module is the engine behind it and behind ``star
--install-optional`` / *Tools → Install Optional Features…*.

Design points (mirrors abax's autodeps):
- **Best-effort & non-blocking.** Installs run in a daemon thread; the UI never
  waits on pip. If pip is missing, the machine is offline, or a build fails, star
  silently keeps using its fallbacks.
- **Attempted once per machine.** A marker file per package (under the cache dir)
  stops a slow/failing install from retrying every launch. A *forced* install
  (the explicit "install now" action) ignores the markers.
- **Opt-out.** ``settings["auto_install"] = False`` or ``STAR_NO_AUTOINSTALL``
  disables it entirely.

The Qt binding (PyQt6) is **not** offered here — you need it to launch the GUI in
the first place. Native engines (Tesseract, Pandoc, ffmpeg, liblouis, piper, …)
are also out of scope: they are system binaries, not pip packages, and are noted
in each feature's description instead.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading

# Windows: suppress the console-window flash when spawning pip from a windowed
# (console-less) star — see the definition in star/_runtime.py.  Duplicated
# here (not imported from the hub) because autodeps deliberately has no
# star-internal imports.
_SUBPROCESS_FLAGS = (
    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
)

# ── Feature registry: feature key -> [(pip name, import name), …] ────────────
# Grouped to match star's optional extras (see pyproject `[project.optional-
# dependencies]` and diagnostics.OPTIONAL_DEPENDENCIES). Ordered light -> heavy.


FEATURES: dict[str, list[tuple[str, str]]] = {
    "documents": [("odfpy", "odf"), ("openpyxl", "openpyxl")],
    "dictionary": [("nltk", "nltk")],
    "spellcheck": [("pyspellchecker", "spellchecker")],
    "summarize": [("sumy", "sumy")],
    "syllables": [("pyphen", "pyphen")],
    "flashcards": [("genanki", "genanki")],
    "translate": [("deep-translator", "deep_translator")],
    "feeds": [("feedparser", "feedparser")],
    "audio": [("pydub", "pydub")],
    "braille": [("louis", "louis")],
    "watch": [("watchdog", "watchdog")],
    "clipboard": [("pyperclip", "pyperclip")],
    "markup": [("pypandoc", "pypandoc")],
    "vocab": [("wordfreq", "wordfreq")],
    "graph": [("graphviz", "graphviz"), ("plantuml", "plantuml"), ("pyyaml", "yaml")],
    "archive": [("py7zr", "py7zr"), ("rarfile", "rarfile")],
    "ocr": [("pytesseract", "pytesseract"), ("pymupdf", "fitz"), ("Pillow", "PIL")],
    "transcribe": [("faster-whisper", "faster_whisper"), ("sounddevice", "sounddevice"),
                   ("numpy", "numpy")],
    "ner": [("spacy", "spacy"), ("nltk", "nltk")],
}

# Human-facing descriptions for the chooser: feature -> (label, detail, approx MB).
FEATURE_INFO: dict[str, tuple[str, str, int]] = {
    "documents": ("Office documents (ODT, XLSX)",
                  "odfpy + openpyxl — open OpenDocument text and Excel spreadsheets", 10),
    "dictionary": ("Offline dictionary / Define Word",
                   "nltk (WordNet) — offline definitions & synonyms. One-time corpus "
                   "download: python -m nltk.downloader wordnet omw-1.4 cmudict", 12),
    "spellcheck": ("Spell check in edit mode", "pyspellchecker", 5),
    "summarize": ("Summarize documents", "sumy — extractive LexRank summaries", 6),
    "syllables": ("Syllable splitting (decoding aid)",
                  "pyphen — split words into syllables (read·a·bil·i·ty) offline", 2),
    "flashcards": ("Anki flashcard export", "genanki", 2),
    "translate": ("Translate documents",
                  "deep-translator — uses online translation services", 2),
    "feeds": ("RSS / Atom feeds", "feedparser — open an article from a feed", 1),
    "audio": ("Audio format conversion",
              "pydub — MP3/OGG export helpers (also needs ffmpeg on PATH)", 1),
    "braille": ("Grade 2 Braille",
                "louis (liblouis bindings) — contracted Braille; Grade 1 is built in", 3),
    "watch": ("Hot-folder watching",
              "watchdog — real filesystem events for star --watch", 1),
    "clipboard": ("System clipboard copy",
                  "pyperclip — copy the selection / paragraph to the system "
                  "clipboard (an OSC-52 terminal fallback is used otherwise)", 1),
    "markup": ("Extra markup formats",
               "pypandoc — reStructuredText, Textile, MediaWiki and ~20 more "
               "(also needs the pandoc binary on PATH)", 3),
    "vocab": ("Highlight difficult words",
              "wordfreq — flags uncommon / academic vocabulary", 30),
    "graph": ("Knowledge-graph extras",
              "graphviz + plantuml + pyyaml — nicer layouts, PlantUML, richer "
              "front-matter (graphviz also needs its system 'dot' binary)", 6),
    "archive": ("Archive ingestion (.7z, .rar)",
                "py7zr + rarfile — ZIP and TAR are built in", 6),
    "ocr": ("OCR for scanned PDFs & images",
            "pytesseract + PyMuPDF + Pillow (also needs the Tesseract binary on PATH)", 60),
    "transcribe": ("Speech-to-text dictation",
                   "faster-whisper (CTranslate2 — no PyTorch) + sounddevice + "
                   "numpy — offline transcription; downloads roughly 150 MB", 150),
    "ner": ("Named-entity concept extraction (large)",
            "spaCy + a language model — richer knowledge-graph concepts; a regex "
            "fallback is used otherwise", 500),
}

# Presets offered by the chooser. "thin" = the small everyday reading/study aids;
# "all" = literally every optional feature, including the very large ones
# (speech-to-text dictation, named-entity extraction). The chooser labels the
# download size so "All" is an informed, deliberate choice.
PRESETS: dict[str, list[str]] = {
    "thin": ["documents", "dictionary", "spellcheck", "summarize", "syllables",
             "flashcards", "translate", "feeds", "audio", "braille", "watch",
             "clipboard", "markup"],
    "all": list(FEATURES),
}


def preset(name: str) -> list[str]:
    """Feature keys for a named preset (``"thin"`` / ``"all"``)."""
    return list(PRESETS.get(name, []))


def all_packages() -> list[tuple[str, str]]:
    """Every ``(pip, import)`` pair across all features, de-duplicated."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for pkgs in FEATURES.values():
        for pip, mod in pkgs:
            if pip not in seen:
                seen.add(pip)
                out.append((pip, mod))
    return out


# ── configuration / hooks (install fn + marker dir are injectable for tests) ──
_INSTALL_FN = None          # set below; tests may replace it
_MARKER_DIR = None          # None -> CACHE_DIR/autodeps
_enabled_override: bool | None = None
_lock = threading.Lock()
_attempted_session: set[str] = set()


def set_enabled(flag: bool | None) -> None:
    """Force auto-install on/off (``None`` restores the default)."""
    global _enabled_override
    _enabled_override = flag


def enabled() -> bool:
    # A PyInstaller bundle cannot pip-install into itself: sys.executable IS
    # star.exe, so "spawn pip" would relaunch star once per package (a full
    # onefile re-extraction each time) and install nothing.  Every runtime-
    # install surface gates on enabled(), so this one check turns the whole
    # machinery off in frozen builds — the exe must bundle its features
    # instead (see star.spec), and the GUI explains rather than offers.
    if getattr(sys, "frozen", False):
        return False
    if os.environ.get("STAR_NO_AUTOINSTALL"):
        return False
    if _enabled_override is not None:
        return _enabled_override
    return True


def installed(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except Exception:
        return False


def _marker_dir():
    from pathlib import Path
    if _MARKER_DIR is not None:
        return Path(_MARKER_DIR)
    from ._runtime import CACHE_DIR
    return CACHE_DIR / "autodeps"


def _attempted(pip_name: str) -> bool:
    if pip_name in _attempted_session:
        return True
    try:
        return (_marker_dir() / f"{pip_name}.attempted").exists()
    except Exception:
        return False


def _mark(pip_name: str) -> None:
    _attempted_session.add(pip_name)
    try:
        d = _marker_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{pip_name}.attempted").write_text("1", encoding="utf-8")
    except Exception:
        pass


def _pip_install(pip_name: str, timeout: float = 1800) -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
            capture_output=True, timeout=timeout, creationflags=_SUBPROCESS_FLAGS)
        return proc.returncode == 0
    except Exception:
        return False


_INSTALL_FN = _pip_install


def missing(packages) -> list[tuple[str, str]]:
    """The subset of ``(pip, module)`` pairs whose module isn't importable."""
    return [(pip, mod) for pip, mod in packages if not installed(mod)]


def feature_installed(key: str) -> bool:
    """True when every package backing *key* is importable."""
    pkgs = FEATURES.get(key, [])
    return bool(pkgs) and all(installed(mod) for _pip, mod in pkgs)


def ensure(packages, *, background: bool = True, force: bool = False) -> list[str]:
    """Install any missing packages, best-effort and once.

    ``packages`` is a list of ``(pip_name, import_name)`` pairs. Returns the pip
    names it will attempt (empty if disabled, all present, or already attempted).
    With ``force`` it ignores the once-per-machine markers (still skips packages
    already importable).
    """
    if not enabled():
        return []
    todo: list[str] = []
    with _lock:
        for pip, mod in packages:
            if installed(mod):
                continue
            if not force and _attempted(pip):
                continue
            _mark(pip)                     # claim now so concurrent calls don't race
            todo.append(pip)
    if not todo:
        return []

    def work() -> None:
        for pip in todo:
            _INSTALL_FN(pip)

    if background:
        threading.Thread(target=work, name="star-autodeps", daemon=True).start()
    else:
        work()
    return todo


def ensure_feature(key: str, *, background: bool = True, force: bool = False) -> list[str]:
    """Ensure the packages backing one feature (e.g. ``"ocr"``/``"dictionary"``)."""
    return ensure(FEATURES.get(key, []), background=background, force=force)


def install_now(packages) -> bool:
    """Synchronously install any missing packages and report overall success.

    For **explicit, user-initiated** installs (the first-run chooser's "Install"
    button, a feature's "install it now?" prompt). Unlike :func:`ensure`, it
    ignores the once-per-machine markers — the user asked for it, so a previous
    failed attempt must not silently no-op — and returns True only when every
    missing package installed. Blocks, so call it from a worker thread.
    """
    # Explicit installs ignore the markers and the auto_install setting — but
    # not physics: a frozen bundle has no pip and sys.executable is star
    # itself (see enabled()), so even a user-initiated install cannot work.
    if getattr(sys, "frozen", False):
        return False
    ok = True
    for pip, mod in packages:
        if installed(mod):
            continue
        _mark(pip)
        if not _INSTALL_FN(pip):
            ok = False
    return ok


def install_feature_now(key: str) -> bool:
    """Synchronously install one feature's missing packages (see install_now)."""
    return install_now(FEATURES.get(key, []))


# A feature's optional packages are detected once at import into a module-level
# flag (e.g. star.summarize._SUMY).  After a *runtime* install those flags are
# stale-False, so the feature still refuses to run ("pip install …") even though
# the package is now present.  This maps each feature to the flags to flip so it
# works immediately, no restart.  transcribe is handled specially in
# refresh_feature() (its snapshot lives in _runtime): since 0.1.25 the stack is
# faster-whisper (CTranslate2, no Torch), which imports cleanly into a running
# process, so it too works in-session with no restart.
_FEATURE_FLAGS: dict[str, list[tuple[str, str]]] = {
    "summarize": [("star.summarize", "_SUMY")],
    "syllables": [("star.syllables", "_PYPHEN")],
    "translate": [("star.translate", "_DEEP_TRANSLATOR")],
    "feeds": [("star.feeds", "_FEEDPARSER")],
    "vocab": [("star.vocab", "_WORDFREQ")],
    "spellcheck": [("star.spellcheck", "_SPELL")],
    "flashcards": [("star.flashcards", "_GENANKI")],
}


def refresh_feature(key: str) -> bool:
    """After a runtime install, make *key* usable without a restart.

    Clears import caches and flips the stale module-level availability flags so
    the gate and the feature code agree and the deferred ``import`` succeeds.
    Returns True when the feature is ready to use in-session; False when a
    restart is needed."""
    import importlib
    import sys

    importlib.invalidate_caches()
    # transcribe's availability snapshot lives in _runtime, not a feature module.
    # faster-whisper imports cleanly mid-session, so re-detecting is enough.
    if key == "transcribe":
        from . import _runtime
        return _runtime.refresh_whisper_backend()
    flags = _FEATURE_FLAGS.get(key)
    if not flags:
        return False
    ready = True
    for mod_name, flag in flags:
        mod = sys.modules.get(mod_name)
        if mod is None or not hasattr(mod, flag):
            ready = False
            continue
        try:
            setattr(mod, flag, True)
        except Exception:
            ready = False
    return ready
