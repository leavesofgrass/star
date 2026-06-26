"""
Central plugin registry for star.

All plugin types (TTS backends, format handlers, exporters) are discovered via
``importlib.metadata.entry_points`` and cached in a process-lifetime singleton.
Built-in implementations register themselves in star's ``pyproject.toml``;
third-party packages add entry-points in the same groups.

Test helpers
------------
``PluginRegistry.reset()``        — discard the singleton (next get() starts fresh)
``override_plugins(backends=[…])`` — context manager; swaps in fake plugins
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from importlib.metadata import entry_points
from pathlib import Path
from typing import Generator, TypeVar

_log = logging.getLogger(__name__)
T = TypeVar("T")

# ── entry-point group names ────────────────────────────────────────────────────

BACKEND_GROUP = "star.backends"
FORMAT_GROUP = "star.formats"
EXPORTER_GROUP = "star.exporters"


# ── low-level loader ──────────────────────────────────────────────────────────

def _load_group(group: str, base_class: type[T]) -> list[type[T]]:
    """Return all entry-points in *group* that are valid subclasses of *base_class*."""
    result: list[type[T]] = []
    for ep in entry_points(group=group):
        try:
            cls = ep.load()
        except Exception as exc:  # noqa: BLE001
            _log.warning("Plugin load failed [%s] %s: %s", group, ep.name, exc)
            continue
        if not (isinstance(cls, type) and issubclass(cls, base_class)):
            _log.warning(
                "Plugin [%s] %s is not a subclass of %s — skipped",
                group, ep.name, base_class.__name__,
            )
            continue
        result.append(cls)
    return result


# ── singleton registry ────────────────────────────────────────────────────────

class PluginRegistry:
    """Process-lifetime cache of all registered plugin classes.

    Usage (normal code)::

        reg = PluginRegistry.get()
        backend = reg.backends[0]()       # instantiate first available backend
        handler = reg.handler_for(path)   # returns a FormatHandler instance or None

    Usage (tests)::

        PluginRegistry.reset()            # force re-discovery on next get()

        with override_plugins(backends=[FakeBackend]):
            mgr = TTSManager()
            assert mgr._select_backend().name == "fake"
    """

    _instance: PluginRegistry | None = None
    _instance_lock: threading.Lock = threading.Lock()

    # ── singleton access ───────────────────────────────────────────────────────

    @classmethod
    def get(cls) -> "PluginRegistry":
        """Return the singleton, creating and populating it on first call."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:       # double-checked locking
                    inst = cls.__new__(cls)
                    inst._init()
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Discard the singleton.  **Tests only** — not safe during normal operation."""
        with cls._instance_lock:
            cls._instance = None

    # ── internal init (called once by get()) ──────────────────────────────────

    def _init(self) -> None:
        from .tts import TTSBackend
        from .formats import FormatHandler, Exporter

        self._backends: list[type[TTSBackend]] = sorted(
            _load_group(BACKEND_GROUP, TTSBackend),
            key=lambda c: c.priority,
        )
        raw_formats: list[type[FormatHandler]] = _load_group(FORMAT_GROUP, FormatHandler)
        # Build ext → [handler classes] map, sorted by priority per extension
        self._ext_map: dict[str, list[type[FormatHandler]]] = {}
        for cls in raw_formats:
            for ext in cls.extensions():
                self._ext_map.setdefault(ext, []).append(cls)
        for ext in self._ext_map:
            self._ext_map[ext].sort(key=lambda c: c.priority)

        self._exporters: list[type[Exporter]] = _load_group(EXPORTER_GROUP, Exporter)

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def backends(self) -> list:
        """All registered TTSBackend *classes*, sorted by priority (lowest first)."""
        return list(self._backends)

    def handler_for(self, path: Path) -> object | None:
        """Return an instantiated FormatHandler for *path*, or None if unsupported.

        Walks handlers registered for ``path.suffix`` in priority order and
        returns the first one whose ``available()`` returns True.
        """
        ext = path.suffix.lower()
        for cls in self._ext_map.get(ext, []):
            if cls.available():
                return cls()
        return None

    @property
    def exporters(self) -> list:
        """All registered Exporter *classes*."""
        return list(self._exporters)


# ── test helper ───────────────────────────────────────────────────────────────

@contextmanager
def override_plugins(
    *,
    backends: list | None = None,
    formats: list | None = None,
    exporters: list | None = None,
) -> Generator[PluginRegistry, None, None]:
    """Swap in fake plugins for the duration of a ``with`` block.

    Does **not** consult entry-points; the supplied lists are used as-is.
    Restores the previous singleton on exit (including on exception).

    Example::

        with override_plugins(backends=[SilentBackend]) as reg:
            assert reg.backends == [SilentBackend]
    """
    prev = PluginRegistry._instance

    fake = PluginRegistry.__new__(PluginRegistry)
    # Match _init()/the `backends` property contract: priority-sorted, lowest first.
    fake._backends = sorted(backends or [], key=lambda c: c.priority)
    fake._exporters = list(exporters or [])
    fake._ext_map = {}
    for cls in (formats or []):
        for ext in cls.extensions():
            fake._ext_map.setdefault(ext, []).append(cls)

    with PluginRegistry._instance_lock:
        PluginRegistry._instance = fake
    try:
        yield fake
    finally:
        with PluginRegistry._instance_lock:
            PluginRegistry._instance = prev
