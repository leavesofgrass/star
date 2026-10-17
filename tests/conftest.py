"""Shared pytest fixtures.

Isolation: the suite never writes outside the checkout.  `Settings.set()` /
`Settings[...] = ...` auto-persist to settings.json (see star/settings.py), and
star keeps its cache, themes, publish styles, log and recovery snapshots in the
same profile folder (``star/_runtime.py``: ``%APPDATA%\\star`` on Windows,
``$XDG_CONFIG_HOME/star`` on Linux).  Without isolation a test run would write
into the developer's real profile, on the system drive.  Four layers keep every
write inside the checkout:

* ``pytest_configure`` points the home, profile, cache and temp environment
  variables (HOME, USERPROFILE, APPDATA, LOCALAPPDATA, XDG_*, TMP, TEMP,
  TMPDIR) at a per-process folder under pytest's base temp folder *before* star
  is imported, so star's import-time profile paths land there too.  The base
  temp folder is ``build/pytest-tmp`` in the checkout (``--basetemp`` in
  pyproject.toml's addopts), never the system temp folder.
* ``_isolate_profile`` gives every test its own profile and home: star's
  module-level profile paths (``_CFG_ROOT``, ``SETTINGS_FILE``, ``CACHE_DIR``,
  ``THEMES_DIR`` and every path derived from them) point at
  ``tmp_path / "test-profile"``, and the environment at ``tmp_path / "test-home"``.
* ``_IsolationGuard`` is an audit hook (``sys.addaudithook``): Python announces
  every file open, directory create, rename and delete before it happens, and
  the hook refuses any write outside the checkout, the base temp folder and the
  Python environment, and fails the test that tried it.  It also refuses
  network access from any test not marked ``network`` (see pyproject.toml's
  addopts, which deselect those by default).  Native code and child processes
  are not seen by the hook; the environment above covers them.
* ``tests/test_isolation.py`` proves it: nothing appears under the real profile.

Qt lifecycle: the suite constructs many ``StarWindow`` instances across the GUI
test modules.  Windows own a 1-second stats ``QTimer`` and start background
threads that emit queued signals; if one fires into a window whose C++ object is
being torn down, the interpreter can *segfault* (the flaky exit-139 seen on the
Linux pytest-qt CI legs).  Two guards below make that deterministic:
``STAR_NO_AUTOINSTALL`` stops any test from spawning background install/prefetch
threads, and ``_drain_qt_events`` flushes pending events + deferred C++ deletions
(and forces a GC) after every test, while the shared QApplication is still alive.
"""
import errno
import ipaddress
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePath
from urllib.parse import urlsplit

import pytest

# Must be set before any QApplication is created (i.e. before the GUI fixtures
# run), so import-time is the right place.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Keep every test from kicking off a background pip install / font prefetch,
# whose worker threads are a prime source of teardown races.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

# star itself is imported only after pytest_configure (below) has pointed the
# profile environment at the base temp folder: star computes its profile
# folder at import time.  Nothing in this module may import star at the top.


# ── Isolation: nothing outside the checkout ──────────────────────────────────
# The environment variables that name a home, profile, cache or data folder,
# mapped to the subfolder of an isolated home each one points at.  star's
# profile comes from APPDATA (Windows), XDG_CONFIG_HOME or HOME (Linux) and HOME
# (macOS); the libraries and tools the tests start read the rest.
_HOME_ENV = {
    "HOME": "",
    "USERPROFILE": "",
    "APPDATA": "appdata",
    "LOCALAPPDATA": "localappdata",
    "XDG_CONFIG_HOME": "config",
    "XDG_DATA_HOME": "data",
    "XDG_CACHE_HOME": "cache",
    "XDG_STATE_HOME": "state",
}
_TEMP_ENV = ("TMP", "TEMP", "TMPDIR")
# The real values, saved by the first pytest process before it redirects them
# (xdist workers inherit this variable), so tests can name the real profile.
_REAL_ENV_VAR = "STAR_TEST_REAL_ENV"
# Set to 0 to switch the audit-hook guard off while debugging the guard itself.
_GUARD_ENV_VAR = "STAR_TEST_GUARD"


def _home_env(home: Path) -> dict[str, str]:
    """Return the home and profile environment for an isolated *home* folder."""
    return {key: str(home / sub) if sub else str(home) for key, sub in _HOME_ENV.items()}


def _real_env() -> dict:
    """Return the home, profile and temp variables as they were before the run."""
    try:
        return json.loads(os.environ.get(_REAL_ENV_VAR, "{}"))
    except ValueError:
        return {}


def real_profile_dir(env: dict | None = None) -> Path | None:
    """Return the star profile folder the real environment names, or None.

    Computed the way ``star/_runtime.py`` computes ``_CFG_ROOT``, from the
    variables saved before the run redirected them.
    """
    env = _real_env() if env is None else env
    if sys.platform == "win32":
        base = env.get("APPDATA") or env.get("USERPROFILE")
        return Path(base) / "star" if base else None
    home = env.get("HOME")
    if sys.platform == "darwin":
        return Path(home) / "Library" / "Application Support" / "star" if home else None
    base = env.get("XDG_CONFIG_HOME") or (str(Path(home) / ".config") if home else None)
    return Path(base) / "star" if base else None


class NetworkBlocked(OSError):
    """Raised when a test not marked ``network`` reaches for the network."""


class _IsolationGuard:
    """An audit hook that keeps the suite inside the checkout and offline.

    Python raises an audit event before every file open, directory create,
    rename, delete and socket connect (PEP 578).  While active, the hook
    refuses a write outside ``roots`` with ``PermissionError`` and a network
    call to anything but this machine with ``NetworkBlocked`` (unless the
    running test is marked ``network``), and records each refusal so the test
    fails even when the code under test swallows the error.  Bytecode caches
    are refused quietly: the import system skips the cache and carries on.
    """

    # Event name -> the argument positions that hold a path being written.
    WRITE_EVENTS = {
        "open": (0,),  # (path, mode, flags); only when mode or flags write
        "os.mkdir": (0,),
        "os.rename": (0, 1),
        "os.replace": (0, 1),
        "os.remove": (0,),
        "os.rmdir": (0,),
        "os.link": (1,),
        "os.symlink": (1,),
        "os.truncate": (0,),
        "os.chmod": (0,),
        "os.utime": (0,),
        "shutil.copyfile": (1,),
        "shutil.copymode": (1,),
        "shutil.copystat": (1,),
        "shutil.copytree": (1,),
        "shutil.move": (0, 1),
        "shutil.rmtree": (0,),
        "shutil.make_archive": (0,),
        "shutil.unpack_archive": (1,),
        "tempfile.mkstemp": (0,),
        "tempfile.mkdtemp": (0,),
        "sqlite3.connect": (0,),
    }
    # Events whose arguments may carry a directory file descriptor; a relative
    # path with a descriptor cannot be resolved here and is let through (the
    # top-level shutil.rmtree event has already been checked).
    DIR_FD_ARG = {"os.mkdir": 2, "os.remove": 1, "os.rmdir": 1}
    NETWORK_EVENTS = frozenset({
        "socket.connect",
        "socket.sendto",
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyaddr",
        "socket.getnameinfo",
        "urllib.Request",
        "http.client.connect",
        "webbrowser.open",
    })
    WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
    DEVICES = frozenset({"nul", "con", "conin$", "conout$", "/dev/null"})

    def __init__(self) -> None:
        self.active = False
        self.allow_network = False
        self.roots: tuple[str, ...] = ()
        self.hits: list[str] = []
        self._installed = False

    def install(self, roots) -> None:
        """Allow writes under *roots* only, and start refusing the rest."""
        normalized = []
        for root in roots:
            if root:
                normalized.append(os.path.normcase(os.path.abspath(os.fspath(root))))
        self.roots = tuple(dict.fromkeys(normalized))
        if not self._installed:
            sys.addaudithook(self._hook)
            self._installed = True
        self.active = True

    def take_hits(self) -> list[str]:
        """Return and forget the refusals recorded so far."""
        hits, self.hits[:] = list(self.hits), []
        return hits

    @contextmanager
    def expect_refusals(self):
        """Collect the refusals made inside the block instead of failing the test."""
        start = len(self.hits)
        seen: list[str] = []
        try:
            yield seen
        finally:
            seen.extend(self.hits[start:])
            del self.hits[start:]

    # -- decisions -------------------------------------------------------------
    def outside(self, path, dir_fd=None) -> str | None:
        """Return *path*, absolute and normalized, if writing it is refused."""
        if path is None or isinstance(path, int):
            return None
        try:
            text = os.fsdecode(path)
        except (TypeError, ValueError):
            return None
        if not text or text.lower() in self.DEVICES:
            return None
        if os.name == "nt":
            if text.startswith("\\\\?\\UNC\\"):
                text = "\\\\" + text[8:]
            elif text.startswith("\\\\?\\"):
                text = text[4:]
            elif text.startswith("\\\\.\\"):
                return None  # a device or a named pipe, not a file
        elif text.startswith("/dev/"):
            return None
        if dir_fd is not None and not os.path.isabs(text):
            return None
        full = os.path.normcase(os.path.abspath(text))
        for root in self.roots:
            if full == root or full.startswith(root.rstrip(os.sep) + os.sep):
                return None
        return full

    @staticmethod
    def local_host(host) -> bool:
        """Return True if *host* names this machine (or no host at all)."""
        if host is None:
            return True
        if isinstance(host, bytes):
            host = host.decode("ascii", "replace")
        if not isinstance(host, str):
            return True
        name = host.strip("[]").lower()
        if name in ("", "localhost", "localhost.localdomain") or name.endswith(".localhost"):
            return True
        try:
            ip = ipaddress.ip_address(name.split("%", 1)[0])
        except ValueError:
            return False
        return ip.is_loopback or ip.is_unspecified

    def remote_target(self, event: str, args: tuple) -> str | None:
        """Return what a network event would reach, if that is off this machine."""
        if event == "webbrowser.open":
            return str(args[0])  # a browser window is never wanted in a test
        if event == "urllib.Request":
            parts = urlsplit(str(args[0]))
            if parts.scheme in ("file", "data", ""):
                return None
            host = parts.hostname
        elif event in ("socket.connect", "socket.sendto"):
            address = args[1]
            if isinstance(address, (str, bytes)):
                return None  # a Unix socket path
            host = address[0] if isinstance(address, tuple) and address else None
        elif event == "socket.getnameinfo":
            sockaddr = args[0]
            host = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else None
        elif event == "http.client.connect":
            host = args[1]
        else:  # getaddrinfo, gethostbyname, gethostbyaddr
            host = args[0]
        return None if self.local_host(host) else str(host)

    def _write_targets(self, event: str, args: tuple):
        """Yield each path a write event would change outside the roots."""
        if event == "open":
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else 0
            writing = bool((flags or 0) & self.WRITE_FLAGS) or (
                isinstance(mode, str) and any(c in mode for c in "wax+")
            )
            if not writing:
                return
        dir_fd = None
        if event in self.DIR_FD_ARG and len(args) > self.DIR_FD_ARG[event]:
            dir_fd = args[self.DIR_FD_ARG[event]]
        for position in self.WRITE_EVENTS[event]:
            if position >= len(args):
                continue
            path = args[position]
            if event == "sqlite3.connect":
                text = os.fsdecode(path) if isinstance(path, (str, bytes, os.PathLike)) else ""
                if not text or ":memory:" in text or "mode=memory" in text:
                    continue
                if text.startswith("file:"):
                    path = text[5:].split("?", 1)[0]
            full = self.outside(path, dir_fd)
            if full is not None:
                yield full

    def _hook(self, event: str, args: tuple) -> None:
        if not self.active:
            return
        if event in self.WRITE_EVENTS:
            refused = None
            try:
                for full in self._write_targets(event, args):
                    refused = full
                    break
            except Exception:  # noqa: BLE001 - an odd argument is not a refusal
                return
            if refused is None:
                return
            if "__pycache__" not in PurePath(refused).parts:
                self.hits.append(f"{event}: {refused}")
            raise PermissionError(
                errno.EACCES,
                "star's tests write only inside the checkout; refused " + event,
                refused,
            )
        if event in self.NETWORK_EVENTS and not self.allow_network:
            try:
                target = self.remote_target(event, args)
            except Exception:  # noqa: BLE001
                return
            if target is None:
                return
            self.hits.append(f"{event}: {target} (network, test not marked network)")
            raise NetworkBlocked(
                errno.ECONNREFUSED,
                "star's tests stay offline unless marked network; refused " + event,
                target,
            )


_GUARD = _IsolationGuard()


class _ProfilePaths:
    """star's module-level profile paths, moved per test to the test's folder.

    star copies ``_CFG_ROOT``, ``SETTINGS_FILE``, ``CACHE_DIR`` and friends into
    every module through ``from ._runtime import *``, and derives more from them
    (``ELOQUENCE_DIR``, the full-text index, the update-check cache).  Rather
    than list them, every ``star`` module's path attributes that sit under the
    session profile or the session home are found, and moved under the test's
    own folder for the duration of each test.  A module first imported during a
    test is found at the end of that test and moved back to the session folder,
    so between tests every path names the session folder.
    """

    def __init__(self) -> None:
        self.session_home: Path | None = None  # set by pytest_configure
        self.session: tuple[Path, ...] | None = None
        self.entries: list[tuple[object, str, int, PurePath]] = []
        self.seen: set[str] = set()

    def _start(self) -> None:
        import star._runtime as runtime  # imported here, after pytest_configure

        self.session = (Path(runtime._CFG_ROOT), self.session_home)

    def _scan(self, roots) -> list:
        """Index path attributes, under *roots*, of star modules not yet seen."""
        found = []
        for name, module in list(sys.modules.items()):
            if name in self.seen or not (name == "star" or name.startswith("star.")):
                continue
            self.seen.add(name)
            if module is None:
                continue
            for attr, value in list(vars(module).items()):
                if not isinstance(value, PurePath):
                    continue
                for index, root in enumerate(roots):
                    try:
                        rel = PurePath(value).relative_to(root)
                    except ValueError:
                        continue
                    found.append((module, attr, index, rel))
                    break
        self.entries.extend(found)
        return found

    def move_to(self, profile: Path, home: Path) -> None:
        """Point every indexed path at *profile* (star's folder) or *home*."""
        if self.session is None:
            self._start()
        self._scan(self.session)
        roots = (profile, home)
        for module, attr, index, rel in self.entries:
            setattr(module, attr, roots[index] / rel)

    def move_back(self, profile: Path, home: Path) -> None:
        """Point every indexed path at the session folder again."""
        self._scan((profile, home))  # modules first imported during the test
        for module, attr, index, rel in self.entries:
            setattr(module, attr, self.session[index] / rel)


_PROFILE_PATHS = _ProfilePaths()


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Point home, profile and temp folders into the base temp folder, then guard.

    Runs after pytest's own tmp_path plugin has set up its factory, so the base
    temp folder is known; and before collection, so before star is imported.
    """
    root = config.rootpath
    if config.option.basetemp is None:
        # Someone overrode addopts: still never use the system temp folder.
        fallback = root / "build" / "pytest-tmp-root"
        fallback.mkdir(parents=True, exist_ok=True)
        os.environ["PYTEST_DEBUG_TEMPROOT"] = str(fallback)
    elif not os.path.isabs(str(config.option.basetemp)):
        resolved = os.path.abspath(str(config.option.basetemp))
        inside = os.path.normcase(resolved).startswith(os.path.normcase(str(root)) + os.sep)
        if not inside:
            pytest.exit(
                f"The base temp folder {resolved} is outside the checkout {root}. "
                "Run pytest from the checkout, or pass an absolute --basetemp.",
                returncode=4,
            )
    factory = getattr(config, "_tmp_path_factory", None)
    if factory is not None:
        base = factory.getbasetemp()  # created (and emptied) by pytest here
    else:  # pragma: no cover - pytest without its tmp_path plugin
        base = root / "build" / "pytest-tmp"
        base.mkdir(parents=True, exist_ok=True)
    session = Path(base) / "session"
    home = session / "home"
    temp = session / "tmp"
    keys = (*_HOME_ENV, *_TEMP_ENV)
    if _REAL_ENV_VAR not in os.environ:
        os.environ[_REAL_ENV_VAR] = json.dumps({key: os.environ.get(key) for key in keys})
    for path in (home, temp):
        path.mkdir(parents=True, exist_ok=True)
    for key, value in _home_env(home).items():
        os.environ[key] = value
    for key in _TEMP_ENV:
        os.environ[key] = str(temp)
    tempfile.tempdir = str(temp)
    _PROFILE_PATHS.session_home = home
    if os.environ.get(_GUARD_ENV_VAR, "1") != "0":
        _GUARD.install([root, base, sys.prefix, getattr(sys, "pycache_prefix", None)])


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    # Reports (--junitxml, coverage) may go wherever the developer asked.
    _GUARD.active = False


@pytest.fixture
def isolation_guard():
    """The audit-hook guard, for tests of the guard itself."""
    return _GUARD


@pytest.fixture
def real_star_profile():
    """The real star profile folder (which no test may touch), or None."""
    return real_profile_dir()


@pytest.fixture
def real_env():
    """The home, profile and temp variables as they were before the run."""
    return _real_env()


@pytest.fixture(autouse=True)
def _guard_check(request):
    """Fail a test that wrote outside the checkout or reached for the network.

    Defined first among the autouse fixtures so it wraps the others: refusals
    in their setup and teardown count too.  Refusals recorded before the test
    started (at import or collection, or by an earlier test's thread) fail
    this one, so none goes unreported.
    """
    earlier = _GUARD.take_hits()
    _GUARD.allow_network = request.node.get_closest_marker("network") is not None
    yield
    _GUARD.allow_network = False
    during = _GUARD.take_hits()
    lines = [f"  before this test started: {hit}" for hit in earlier]
    lines += [f"  during this test: {hit}" for hit in during]
    if lines:
        pytest.fail(
            "Test isolation: refused a write outside the checkout or a network "
            "call from a test not marked network:\n" + "\n".join(lines),
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def _isolate_profile(monkeypatch, tmp_path):
    """Give the test its own star profile and home, inside its tmp_path.

    star's profile paths (settings.json, cache, themes, publish styles, log,
    recovery snapshots, Eloquence downloads) point at
    ``tmp_path / "test-profile"``; HOME, APPDATA and the XDG folders at
    ``tmp_path / "test-home"``.  So construction and saves stay sandboxed, and
    no state leaks from one test into the next.  The recovery folder matters
    for more than tidiness: a StarWindow schedules
    ``_autosave_check_on_startup`` on a ``singleShot(0)`` that can fire for a
    window built in an earlier test, and a stray snapshot there would pop a
    blocking QMessageBox and hang the suite.
    """
    profile = tmp_path / "test-profile"
    home = tmp_path / "test-home"
    home.mkdir()
    for key, value in _home_env(home).items():
        monkeypatch.setenv(key, value)
    _PROFILE_PATHS.move_to(profile, home)
    try:
        yield profile
    finally:
        _PROFILE_PATHS.move_back(profile, home)


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
