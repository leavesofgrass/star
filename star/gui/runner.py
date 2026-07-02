"""The Qt GUI core: _run_qt_gui() and the StarWindow main window.

WHY THIS MODULE EXISTS: this is the bulk of the former monolithic star/gui.py,
which packed its entire ~5,600-line implementation into a single _run_qt_gui()
function (a StarWindow(QMainWindow), nested in that closure).  As of 0.1.9 the
GUI is a package (star/gui/) so it can be split into focused modules.  As of the
StarWindow split this file keeps only _run_qt_gui() — Qt application setup, the
crash-log excepthook, and launch.  StarWindow and the _RSVPOverlay widget live
in star/gui/main_window.py (itself composed of the responsibility mixins in
star/gui/mixin_*.py); it is Qt-heavy and imported lazily, after the _QT guard,
so `import star.gui` stays safe when PyQt is absent.
Public imports are preserved by star/gui/__init__.py
(`from star.gui import _run_qt_gui`).  See docs/architecture.md.
"""
from .._runtime import *  # noqa: F401,F403
from ..settings import Settings

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

    window = StarWindow(settings, initial_path)
    window.show()

    # First launch only: offer the optional-feature chooser (Thin / All / custom).
    # Honors the auto_install setting and STAR_NO_AUTOINSTALL; marks itself shown so
    # it never nags again. Best-effort — a failure here must not block the app.
    try:
        from .deps_dialog import maybe_prompt

        maybe_prompt(window)
    except Exception:
        pass

    sys.exit(app.exec() if _QT == "PyQt6" else app.exec_())
