"""Shared pytest fixtures.

`Settings.set()` / `Settings[...] = ...` auto-persist to the user's real
settings.json (see star/settings.py).  Without isolation, any test that mutates
a Settings object would clobber the developer's actual configuration and leak
state into later tests.  This autouse fixture redirects the settings file to a
per-test temp path so construction and saves stay sandboxed.

Qt lifecycle: the suite constructs many ``StarWindow`` instances across the GUI
test modules.  Windows own a 1-second stats ``QTimer`` and start background
threads that emit queued signals; if one fires into a window whose C++ object is
being torn down, the interpreter can *segfault* (the flaky exit-139 seen on the
Linux pytest-qt CI legs).  Two guards below make that deterministic:
``STAR_NO_AUTOINSTALL`` stops any test from spawning background install/prefetch
threads, and ``_drain_qt_events`` flushes pending events + deferred C++ deletions
(and forces a GC) after every test, while the shared QApplication is still alive.
"""
import os

import pytest

# Must be set before any QApplication is created (i.e. before the GUI fixtures
# run), so import-time is the right place.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Keep every test from kicking off a background pip install / font prefetch,
# whose worker threads are a prime source of teardown races.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

import star.settings as _settings_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_settings_file(monkeypatch, tmp_path):
    monkeypatch.setattr(_settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")


def _drain(app) -> None:
    """Flush pending Qt events + deferred deletions, then GC, then flush again."""
    import gc

    try:
        from PyQt6.QtCore import QCoreApplication, QEvent
    except Exception:  # pragma: no cover - PyQt5 fallback / no Qt
        try:
            from PyQt5.QtCore import QCoreApplication, QEvent  # type: ignore
        except Exception:
            return
    try:
        deferred = QEvent.Type.DeferredDelete
    except AttributeError:  # PyQt5
        deferred = QEvent.DeferredDelete  # type: ignore[attr-defined]
    try:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, deferred)
        app.processEvents()
        gc.collect()
        QCoreApplication.sendPostedEvents(None, deferred)
        app.processEvents()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _drain_qt_events():
    """After each test, tear down any window it created *while the QApplication is
    still alive* — closed/dereferenced windows are fully deleted here so a late
    stats-timer tick or queued signal can't fire into freed memory later.

    Gated on there being top-level widgets left over, so the ~850 non-GUI tests
    (which never build a window) don't pay for a gc.collect() each."""
    yield
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:
        try:
            from PyQt5.QtWidgets import QApplication  # type: ignore
        except Exception:
            return
    app = QApplication.instance()
    if app is None or not app.topLevelWidgets():
        return
    _drain(app)


@pytest.fixture(scope="session", autouse=True)
def _qt_session_cleanup():
    """A final drain at session end so no widgets are left half-alive when the
    interpreter (and the QApplication) shut down."""
    yield
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:
        try:
            from PyQt5.QtWidgets import QApplication  # type: ignore
        except Exception:
            return
    app = QApplication.instance()
    if app is not None:
        _drain(app)
