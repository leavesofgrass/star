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

import inspect
import logging
import threading
from contextlib import contextmanager
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Generator, TypeVar

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


# ── introspection (powers `star --plugins`) ─────────────────────────────────────
#
# These helpers walk the installed entry-points directly (not the cached
# singleton) so the CLI can report every declared plugin — including ones whose
# optional dependencies are missing — without a heavy import of the whole stack.

#: The three entry-point groups, in report order, with the human label used by
#: the CLI and the dotted path to the ABC each plugin in the group implements.
PLUGIN_GROUPS: dict[str, dict[str, str]] = {
    BACKEND_GROUP: {"label": "TTS backends", "base": "star.tts.base.TTSBackend"},
    FORMAT_GROUP: {"label": "Document format handlers", "base": "star.formats.FormatHandler"},
    EXPORTER_GROUP: {"label": "Exporters", "base": "star.formats.Exporter"},
}


def _availability(cls: type) -> bool | None:
    """Best-effort ``available()`` for a plugin class.

    ``available`` is a ``classmethod`` on FormatHandler/Exporter but an instance
    method on TTSBackend.  Returns the boolean when it can be evaluated cheaply,
    or ``None`` when availability cannot be determined without instantiating a
    backend (or the check itself raised).
    """
    checker = getattr(cls, "available", None)
    if checker is None:
        return None
    # classmethod → bound to the class; call it directly.
    if inspect.ismethod(checker) and checker.__self__ is cls:
        try:
            return bool(checker())
        except Exception:  # noqa: BLE001
            return None
    # Plain instance method (TTSBackend): instantiating a backend can be
    # expensive/side-effectful, so don't — report "unknown".
    return None


def describe_plugin(group: str, name: str) -> dict[str, Any] | None:
    """Return a structured description of one registered plugin, or ``None``.

    Loads only the single named entry-point (not the whole group).  The returned
    dict has: ``group``, ``name``, ``target`` (``module:attr`` the entry-point
    points at), ``distribution`` (installing package, or ``None``), plus, when the
    class loads: ``class`` (dotted class name), ``priority`` (or ``None`` if the
    ABC has none), ``extensions`` (sorted list, ``[]`` when not applicable),
    ``available`` (bool or ``None``), and ``doc`` (first docstring line).  A
    ``load_error`` key is set instead of the class fields when the plugin fails
    to import.
    """
    for ep in entry_points(group=group):
        if ep.name != name:
            continue
        info: dict[str, Any] = {
            "group": group,
            "name": ep.name,
            "target": ep.value,
            "distribution": _ep_distribution(ep),
        }
        try:
            cls = ep.load()
        except Exception as exc:  # noqa: BLE001
            info["load_error"] = f"{type(exc).__name__}: {exc}"
            return info
        info["class"] = f"{cls.__module__}.{cls.__qualname__}"
        info["priority"] = getattr(cls, "priority", None)
        exts = getattr(cls, "extensions", None)
        if exts is not None:
            try:
                info["extensions"] = sorted(exts())
            except Exception:  # noqa: BLE001
                info["extensions"] = []
        else:
            info["extensions"] = []
        info["available"] = _availability(cls)
        doc = inspect.getdoc(cls) or ""
        info["doc"] = doc.strip().splitlines()[0] if doc.strip() else ""
        return info
    return None


def list_plugins() -> dict[str, list[dict[str, Any]]]:
    """Enumerate every registered plugin, grouped by entry-point group.

    Returns ``{group: [plugin-info, …]}`` for each group in
    :data:`PLUGIN_GROUPS`, each list sorted by ``(priority, name)``.  Each
    plugin-info dict is what :func:`describe_plugin` returns.  Loading a plugin
    can fail (missing optional deps); those entries carry a ``load_error`` key
    rather than being dropped, so the report is complete.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for group in PLUGIN_GROUPS:
        entries = []
        for ep in entry_points(group=group):
            desc = describe_plugin(group, ep.name)
            if desc is not None:
                entries.append(desc)
        entries.sort(key=lambda d: (d.get("priority") if d.get("priority") is not None else 1_000_000, d["name"]))
        out[group] = entries
    return out


def _ep_distribution(ep: Any) -> str | None:
    """Return the installing distribution name for an entry-point, if known."""
    dist = getattr(ep, "dist", None)
    if dist is None:
        return None
    name = getattr(dist, "name", None)
    version = getattr(dist, "version", None)
    if name and version:
        return f"{name} {version}"
    return name


def describe_api() -> list[dict[str, Any]]:
    """Describe the plugin ABC contracts (``star --plugins api``).

    Returns one dict per ABC with: ``name`` (dotted class), ``group`` (the
    entry-point group implementers register in), ``doc`` (first docstring line),
    ``api_version``, and ``methods`` — a list of ``{name, signature, doc,
    abstract, classmethod}`` for every public method/abstract method on the ABC.
    Imports the ABC modules (cheap, stdlib-only) but nothing heavy.
    """
    from . import formats as _formats
    from .tts.base import TTSBackend

    api_version = getattr(_formats, "__api_version__", "?")
    specs = [
        (TTSBackend, BACKEND_GROUP),
        (_formats.FormatHandler, FORMAT_GROUP),
        (_formats.Exporter, EXPORTER_GROUP),
    ]
    out: list[dict[str, Any]] = []
    for cls, group in specs:
        methods: list[dict[str, Any]] = []
        for mname, member in _public_members(cls):
            raw = inspect.getattr_static(cls, mname)
            is_classmethod = isinstance(raw, classmethod)
            is_abstract = mname in getattr(cls, "__abstractmethods__", frozenset())
            try:
                sig = str(inspect.signature(member))
            except (TypeError, ValueError):
                sig = "(…)"
            mdoc = inspect.getdoc(member) or ""
            methods.append(
                {
                    "name": mname,
                    "signature": f"{mname}{sig}",
                    "doc": mdoc.strip().splitlines()[0] if mdoc.strip() else "",
                    "abstract": is_abstract,
                    "classmethod": is_classmethod,
                }
            )
        cdoc = inspect.getdoc(cls) or ""
        out.append(
            {
                "name": f"{cls.__module__}.{cls.__qualname__}",
                "group": group,
                "doc": cdoc.strip().splitlines()[0] if cdoc.strip() else "",
                "api_version": api_version,
                "methods": methods,
            }
        )
    return out


def _public_members(cls: type) -> list[tuple[str, Any]]:
    """Public callables (methods/properties) declared on the ABC hierarchy.

    Skips dunders and private names; includes inherited abstract/def members but
    not ``object``'s.  Ordered by name for a stable report.
    """
    out: list[tuple[str, Any]] = []
    for mname in sorted(dir(cls)):
        if mname.startswith("_"):
            continue
        member = inspect.getattr_static(cls, mname)
        # Unwrap classmethod/staticmethod/property to the underlying function.
        target = member
        if isinstance(member, (classmethod, staticmethod)):
            target = member.__func__
        elif isinstance(member, property):
            target = member.fget
        if not callable(target):
            continue
        out.append((mname, target))
    return out
