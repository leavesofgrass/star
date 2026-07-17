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

# ── Qt test isolation ────────────────────────────────────────────────────────
# The GUI tests build/tear down QWidgets and spawn background daemon threads
# (doc/welcome loads, word-map builds, etc.) that emit *queued* signals.
# One REAL teardown race was proven and fixed 2026-07-16: a worker could
# outlive its window's C++ object (deleted by the drain below) and then run
# its final ``self.<signal>.emit(...)`` on the dead QObject — caught in the
# wild as ``RuntimeError: wrapped C/C++ object of type StarWindow has been
# deleted`` raised from the doc-load worker's emit in a passing run's log.
# Every window worker now goes through ``StarWindow._spawn_worker`` and
# ``closeEvent`` joins them (and bumps the doc-load generation) while the
# C++ object is still alive — pinned by tests/test_bg_thread_lifecycle.py.
# NOTE this is NOT the whole story: the probabilistic teardown segfault
# (heap corruption detonating at an innocent later site, e.g. the
# ``QAction::shortcut`` sweep in test_authoring) reproduces in-process at a
# similar rate before AND after that fix, on Windows and Linux alike — the
# planting write is still being hunted (see ci_gates memory / the segfault
# session).  Serial in-process is NOT inherently crash-free.
#
# The split below stays for speed and containment.  Every
# Qt-touching test gets BOTH:
#   * ``qt`` marker      — lets CI split the suite into two invocations:
#                          ``pytest -m "not qt"`` (parallel under xdist) and
#                          ``pytest -m qt -n0`` (serial, in-process, no execnet
#                          worker — the configuration proven crash-free);
#   * ``xdist_group``    — so a plain ``pytest`` run (everything under xdist)
#                          still keeps Qt tests serial on one worker, which
#                          makes the residual race rare rather than common.
_QT_FIXTURES = frozenset({"qtbot", "qapp", "window"})
_QT_MODULES = frozenset({"test_video"})  # builds a QGuiApplication with no fixture


def pytest_collection_modifyitems(config, items):
    has_xdist = config.pluginmanager.hasplugin("xdist")
    for item in items:
        mod = item.module.__name__.rsplit(".", 1)[-1] if getattr(item, "module", None) else ""
        if (_QT_FIXTURES & set(getattr(item, "fixturenames", ()))) or mod in _QT_MODULES:
            item.add_marker(pytest.mark.qt)
            if has_xdist:
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
    # The deferred deletions above destroyed the marked windows' C++ objects;
    # now clear their (possibly stale) sip object-map entries — see
    # _mark_for_wrapper_cleanup for the use-after-free this prevents.
    _sweep_stale_wrappers()


# Windows awaiting post-destruction wrapper cleanup: (destroyed-flag, wrappers).
_pending_wrapper_cleanup = []


def _mark_for_wrapper_cleanup(w) -> None:
    """Record *w* and every child wrapper so the post-drain sweep can clear
    their sip object-map entries once the C++ side is really destroyed.

    ROOT CAUSE of the long-standing ~25% in-process teardown segfault (2026-07-17,
    proven by core forensics + live instrumentation): when a window dies via
    ``deleteLater``, PyQt sometimes fails to invalidate the Python wrappers of
    its C++-created children (``statusBar()``/``menuBar()``/QActions) — the
    wrapper stays in sip's object map with a dangling pointer, *including* the
    super-class subobject alias at ``base+0x10``.  The next window's
    identically-sized widget is frequently re-carved at that very address, so
    ``self.statusBar()`` on the NEW window returns the STALE wrapper and Qt
    executes against freed memory (observed live: fresh windows handed
    wrappers whose recorded address equals the new widget's — and crashing
    when the reuse lands 16 bytes shifted).  Sweeping ``sip.setdeleted`` over
    the dead window's wrappers clears the poisoned entries deterministically.
    """
    try:
        from PyQt6.QtCore import QObject
    except Exception:
        return
    flag = {"dead": False}
    try:
        w.destroyed.connect(lambda *_a, _f=flag: _f.__setitem__("dead", True))
    except Exception:
        return
    wrappers = [w]
    for getter in ("statusBar", "menuBar"):
        try:
            wrappers.append(getattr(w, getter)())
        except Exception:
            pass
    try:
        # Wrapping every child registers a map entry for it — which is exactly
        # what we want: every entry is then cleared below, leaving the map
        # with NO stale keys for this window's address range.
        wrappers.extend(w.findChildren(QObject))
    except Exception:
        pass
    _pending_wrapper_cleanup.append((flag, wrappers))


def _sweep_stale_wrappers() -> None:
    """After deferred deletions ran: mark the dead windows' wrappers deleted.

    Only touches wrappers whose window's ``destroyed`` signal actually fired —
    a window that somehow survived this drain is retried on the next one (and
    by the session-end drain).
    """
    try:
        import PyQt6.sip as sip
    except Exception:
        return
    remaining = []
    for flag, wrappers in _pending_wrapper_cleanup:
        if not flag["dead"]:
            remaining.append((flag, wrappers))
            continue
        for x in wrappers:
            try:
                if not sip.isdeleted(x):
                    sip.setdeleted(x)
            except Exception:
                pass
    _pending_wrapper_cleanup[:] = remaining


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
        except Exception:
            pass
    # Belt over closeEvent's own 3s worker join: the drain that follows
    # DELETES these windows' C++ objects, so a worker that outlived the
    # in-close join (possible on a saturated box — coverage tracing plus
    # CPU contention can stretch a doc load past the budget) would emit on
    # freed memory.  Tests can afford a fatter budget; deletion is deferred
    # until every registered worker is gone or 10s pass.
    import time as _time

    _deadline = _time.monotonic() + 10.0
    for w in list(app.topLevelWidgets()):
        for _t in list(getattr(w, "_bg_threads", ())):
            try:
                _t.join(timeout=max(0.0, _deadline - _time.monotonic()))
            except Exception:
                pass
    for w in list(app.topLevelWidgets()):
        try:
            _mark_for_wrapper_cleanup(w)
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
