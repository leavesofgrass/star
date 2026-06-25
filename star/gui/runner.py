"""The Qt GUI core: _run_qt_gui() and the StarWindow main window.

WHY THIS MODULE EXISTS: this is the bulk of the former monolithic star/gui.py,
which packed its entire ~5,600-line implementation into a single _run_qt_gui()
function (a StarWindow(QMainWindow) plus a _HelpWindow(QDialog), both nested in
that closure).  As of 0.1.9 the GUI is a package (star/gui/) so it can be split
into focused modules; this file keeps _run_qt_gui and StarWindow, while the
self-contained help dialog moved to star/gui/help_window.py.  The behavior is
unchanged — the extraction passes the closure-captured values (the StarWindow
class and the Qt enum-compat constants) into a class factory instead of relying
on lexical scope.  Public imports are preserved by star/gui/__init__.py
(`from star.gui import _run_qt_gui`).  See docs/architecture.md.
"""
from .._runtime import *  # noqa: F401,F403
from ..annotations import _annotation_matches, _format_annotations, _parse_tags
from ..braille import _export_braille
from ..citations import (
    _citation_label,
    _fetch_citation_by_doi,
    _format_citations,
    _import_citations,
)
from ..convert import resolve_format, run_batch, supported_formats
from ..documents import Document, _build_word_map, load_document
from ..feeds import _FEEDPARSER, fetch_feed
from ..flashcards import _GENANKI, export_anki_deck
from ..i18n import available_languages, get_language, set_language, tr
from ..settings import Settings
from ..spellcheck import _SPELL, SpellHighlighter, misspelled_words
from ..stats import (
    ReadingStats,
    _apply_profile_values,
    _delete_profile,
    _fmt_duration,
    _format_reading_stats,
    _library_entries,
    _record_library,
    _save_profile,
)
from ..summarize import _SUMY, summarize_document
from ..themes import _load_css_themes, _seed_default_css_themes
from ..transcribe import _record_audio_to_wav, _transcribe_audio
from ..translate import _DEEP_TRANSLATOR, COMMON_LANGUAGES, translate_text
from ..tts import Pyttsx3Backend, TTSManager, _SCReader
from ..ttstext import _preprocess_tts_text, _strip_markdown_for_tts
from ..tui import _HELP_TEXT, THEME_NAMES, _shortcuts_text
from ..vocab import _WORDFREQ, DEFAULT_THRESHOLD, find_difficult_words
from ..watch import HotFolderWatcher, _make_logger

# =============================================================================
# Optional Qt GUI
# =============================================================================


def _run_qt_gui(settings: Settings, initial_path: str = "") -> None:
    """Launch the optional Qt-based GUI mode."""
    if not _QT:
        print(
            "Qt GUI requires PyQt6 or PyQt5:\n"
            "  pip install PyQt6\nor\n  pip install PyQt5",
            file=sys.stderr,
        )
        sys.exit(1)

    # PyQt5/PyQt6 enum-compat constants live in star/gui/_qtcompat.py (shared by
    # StarWindow and the mixin modules).  _run_qt_gui itself only needs the two
    # the help-window factory takes; imported lazily — after the `_QT` guard —
    # so `import star.gui` stays safe when PyQt is absent.
    from ._qtcompat import _KEEP_ANCHOR, _QUEUED

    # High DPI support — must be set before QApplication().
    # Use the module-level Qt object so PyQt6's C-extension type checks
    # receive the exact enum type they were compiled against.
    if settings.get("qt_hidpi", True):
        try:
            # PyQt6: HighDpiScaleFactorRoundingPolicy is the recommended knob.
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough  # type: ignore[attr-defined]
            )
        except (AttributeError, TypeError):
            # PyQt5 (or an older PyQt6 build): fall back to the AA_* attributes.
            try:
                QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore[attr-defined]
                QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore[attr-defined]
            except AttributeError:
                pass  # Qt version has no HiDPI API — safe to ignore

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)

    # ── Global exception hook ─────────────────────────────────────────
    # In PyQt6, an unhandled Python exception inside a connected slot is
    # re-raised in the GUI thread and can escape app.exec(), causing the
    # process to print a traceback to a briefly-visible console window on
    # Windows and then exit.  This hook catches anything that slips through
    # and writes it to star_crash.log next to the settings file so the user
    # can read it after the window closes.
    _log_path = SETTINGS_FILE.parent / "star_crash.log"

    def _excepthook(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
        import traceback as _tb

        msg = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
        # Write to log file first (always succeeds).
        try:
            _log_path.write_text(msg, encoding="utf-8")
        except Exception:
            pass
        # Try to show a Qt message box.
        try:
            QMessageBox.critical(
                None,
                f"{APP_NAME} — Unexpected Error",
                f"An unexpected error occurred.\n\n"
                f"{msg[:1200]}\n\n"
                f"Full details saved to:\n{_log_path}",
            )
        except Exception:
            pass  # if Qt itself is broken, silently give up

    sys.excepthook = _excepthook

    # StarWindow (with the RSVP overlay) now lives in star/gui/main_window.py —
    # a Qt-heavy module imported lazily here, after the _QT guard above, so
    # `import star.gui` stays safe when PyQt is absent.
    from .main_window import StarWindow

    # _HelpWindow was extracted to star/gui/help_window.py.  Build it here so
    # it still closes over StarWindow and the Qt enum-compat constants
    # (_QUEUED, _KEEP_ANCHOR) exactly as it did when it was nested inline.
    from .help_window import build_help_window_class

    _HelpWindow = build_help_window_class(StarWindow, _QUEUED, _KEEP_ANCHOR)

    # ──────────────────────────────────────────────────────────────────────
    window = StarWindow(settings, initial_path)
    window.show()
    sys.exit(app.exec() if _QT == "PyQt6" else app.exec_())
