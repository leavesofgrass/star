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

# ── Qt test isolation under pytest-xdist ────────────────────────────────────
# The GUI tests build/tear down QWidgets and spawn background daemon threads
# (word-map build, etc.) that emit *queued* signals.  Run in parallel, the
# heavy CPU contention shifts those threads' timing so one can fire into a
# window whose C++ object is already gone — the exit-139 segfault flake.  The
# tests are race-free when run SERIALLY (the whole suite passes serial), so we
# pin every Qt test to a single xdist worker via one shared group: the ~840
# non-GUI tests still parallelize across the other workers (the speed win),
# while the Qt tests run in their crash-free serial order on one worker.
_QT_FIXTURES = frozenset({"qtbot", "qapp", "window"})
_QT_MODULES = frozenset({"test_video"})  # builds a QGuiApplication with no fixture


def pytest_collection_modifyitems(config, items):
    # Only meaningful under xdist + --dist loadgroup; a harmless no-op otherwise.
    if not config.pluginmanager.hasplugin("xdist"):
        return
    for item in items:
        mod = item.module.__name__.rsplit(".", 1)[-1] if getattr(item, "module", None) else ""
        if (_QT_FIXTURES & set(getattr(item, "fixturenames", ()))) or mod in _QT_MODULES:
            item.add_marker(pytest.mark.xdist_group("qt"))


@pytest.fixture(autouse=True)
def _isolate_settings_file(monkeypatch, tmp_path):
    monkeypatch.setattr(_settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")


@pytest.fixture(autouse=True)
def _isolate_recovery_dir(monkeypatch, tmp_path):
    """Point the autosave recovery dir at a per-test temp path.

    A StarWindow schedules ``_autosave_check_on_startup`` on a ``singleShot(0)``;
    pytest-qt processes events between tests, so that callback can fire for a
    window built in an earlier test.  If it scanned the developer's real
    ``<config>/recovery/`` and found a stray snapshot it would pop a **blocking**
    QMessageBox and hang the suite.  Redirecting the dir keeps every test reading
    an empty temp folder (importing the GUI mixin needs Qt, so this is a no-op
    when Qt is absent for the pure-logic legs)."""
    try:
        import star.gui.mixin_autosave as _autosave_mod
    except Exception:  # noqa: BLE001 — no Qt on the non-GUI matrix legs
        return
    monkeypatch.setattr(_autosave_mod, "_CFG_ROOT", tmp_path, raising=False)


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


def _close_leftover_windows(app) -> None:
    """Actively close + schedule deletion of every leftover top-level widget.

    A test that builds a window but does not call ``win.close()`` (or holds it
    only in a local that outlives the assertion) leaves the window ALIVE: its
    1-second stats ``QTimer`` keeps ticking and its C++ object lingers into the
    next test.  Merely draining events (below) does not stop that — the window
    was never closed.  Closing it fires ``closeEvent`` (which stops the stats /
    preview timers) and ``deleteLater`` marks the C++ object for deletion in the
    drain that follows, so nothing accumulates across tests within a process.
    This is what keeps a long-lived (serial or xdist-worker) run from building
    up the ~dozens of half-alive windows that segfault Qt on teardown.
    """
    for w in list(app.topLevelWidgets()):
        try:
            w.close()
            w.hide()
            w.deleteLater()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _drain_qt_events():
    """After each test, tear down any window it created *while the QApplication is
    still alive* — leftover windows are closed and fully deleted here so a late
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
    # A test that builds only a QGuiApplication (e.g. video export renders Qt
    # without widgets) has no topLevelWidgets() — guard so the drain fixture
    # never errors when it runs first in a fresh xdist worker.
    if app is None or not hasattr(app, "topLevelWidgets") or not app.topLevelWidgets():
        return
    _close_leftover_windows(app)
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
