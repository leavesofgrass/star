"""A window's background workers must never outlive its C++ object.

Every ``StarWindow`` spawns daemon threads — the constructor's async
welcome-doc load, word-map builds, update checks, exports — and each ends by
emitting a pyqtSignal on the window.  If the window's C++ object has already
been deleted, that emit is a use-after-free.  This is not hypothetical: a
full serial suite run's log caught the benign face of the race —
``RuntimeError: wrapped C/C++ object of type StarWindow has been deleted``
raised from ``_work``'s ``self._doc_loaded_signal.emit()``.  (Fixing it did
NOT eliminate the separate probabilistic teardown heap corruption, which
reproduces at a similar rate either way — that hunt continues elsewhere.)

The contract pinned here: window threads go through ``_spawn_worker`` (so
they are registered), and ``closeEvent`` both bumps ``_doc_load_gen`` (an
in-flight load becomes stale and returns without staging or emitting) and
joins every registered worker while the C++ object is still alive.
"""
import importlib.util
import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))
pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


def _make_window():
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    return StarWindow(Settings())


def test_constructor_registers_the_welcome_load_worker(qapp):
    """The async welcome.md load must be a *registered* worker (joinable on
    close), not an anonymous daemon thread."""
    win = _make_window()
    try:
        names = [t.name for t in win._bg_threads]
        assert any(n.startswith("star-doc-load") for n in names), names
    finally:
        win.close()


def test_close_joins_registered_workers(qapp):
    """closeEvent joins a live worker before returning, so no window thread
    can survive into the window's deletion."""
    win = _make_window()
    release = threading.Event()
    worker = win._spawn_worker(lambda: release.wait(timeout=10.0),
                               name="star-test-worker")
    assert worker.is_alive()
    # Let the worker finish shortly after the join in closeEvent begins.
    threading.Timer(0.05, release.set).start()
    win.close()
    worker.join(timeout=5.0)
    assert not worker.is_alive()
    assert win._bg_threads == []  # the registry is drained on close


def test_close_disarms_an_inflight_doc_load(qapp, monkeypatch):
    """A doc load still running when the window closes must neither stage its
    result nor emit — the generation bump in closeEvent makes it stale, and
    the join bounds it to the window's lifetime."""
    import star.gui.mixin_document as mdoc

    gate = threading.Event()
    real_load = mdoc.load_document

    def slow_load(path, settings):
        gate.wait(timeout=10.0)
        return real_load(path, settings)

    monkeypatch.setattr(mdoc, "load_document", slow_load)
    win = _make_window()  # the constructor's welcome load is now gated
    loaders = [t for t in win._bg_threads if t.name.startswith("star-doc-load")]
    assert loaders, "welcome load did not register a star-doc-load worker"

    gen_before = win._doc_load_gen
    threading.Timer(0.05, gate.set).start()
    win.close()

    for t in loaders:
        t.join(timeout=5.0)
    assert not any(t.is_alive() for t in loaders)
    # close() invalidated the load: nothing staged, nothing to emit.
    assert win._doc_load_gen > gen_before
    assert win._pending_doc is None
