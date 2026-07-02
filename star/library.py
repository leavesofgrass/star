"""Folder-as-library: treat any folder as a document library.

A *library folder* is just a directory on disk that star scans for documents it
can open.  Because the library is the filesystem itself — not a list buried in
``settings.json`` — pointing star at a folder synced by Dropbox / OneDrive /
Syncthing / iCloud makes the whole library sync across machines and services for
free.  Add a folder once and every supported document inside it (recursively)
shows up in the Library view.

This module is pure-Python and dependency-free.  Reading progress and time-read
are merged in by the caller from the existing per-path stats, so a synced folder
carries the documents; progress remains per-machine (keyed by absolute path).
"""
from ._runtime import *  # noqa: F401,F403
from .documents import _detect_format, supported_extensions
from .settings import Settings

# Directory names never worth descending into.
_SKIP_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", ".obsidian", ".star",
    "node_modules", ".cache", ".Trash", ".trash", "$RECYCLE.BIN",
    "System Volume Information",
}


def _resolve(folder: "str | Path") -> str:
    """Absolute, user-expanded path string for *folder* (best effort)."""
    try:
        return str(Path(folder).expanduser().resolve())
    except OSError:
        return str(Path(folder).expanduser())


def library_folders(settings: Settings) -> List[str]:
    """The configured library folders (absolute paths), skipping blanks."""
    return [f for f in (settings.get("library_folders") or []) if f]


def add_library_folder(settings: Settings, folder: "str | Path") -> str:
    """Add *folder* to the library folder list (idempotent).  Returns the
    resolved path that was stored."""
    resolved = _resolve(folder)
    folders = list(settings.get("library_folders") or [])
    if resolved not in folders:
        folders.append(resolved)
        settings.set("library_folders", folders)
    return resolved


def remove_library_folder(settings: Settings, folder: "str | Path") -> None:
    """Remove *folder* (matched by resolved path) from the library folder list."""
    target = _resolve(folder)
    folders = [f for f in (settings.get("library_folders") or []) if _resolve(f) != target]
    settings.set("library_folders", folders)


def scan_folder(
    folder: "str | Path", *, recursive: bool = True, max_files: int = 20000
) -> List[Dict[str, Any]]:
    """Return library entries for every supported document under *folder*.

    Hidden files/dirs and well-known junk dirs (``.git``, ``node_modules``, …)
    are skipped.  Each entry is a dict with ``path``, ``rel`` (path relative to
    the folder), ``title`` (the file stem), ``ext``, ``format``, ``size``,
    ``mtime``, and ``folder``.  Stops after *max_files* matches.
    """
    root = Path(folder).expanduser()
    exts = supported_extensions()
    out: List[Dict[str, Any]] = []
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip/hidden directories in place so os.walk never descends them.
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        if not recursive:
            dirnames[:] = []
        for fn in filenames:
            if fn.startswith("."):
                continue
            ext = Path(fn).suffix.lower()
            if ext not in exts:
                continue
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            out.append(
                {
                    "path": str(p),
                    "rel": str(p.relative_to(root)),
                    "title": p.stem,
                    "ext": ext,
                    "format": _detect_format(fn),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "folder": str(root),
                }
            )
            if len(out) >= max_files:
                return out
    return out


def scan_library(settings: Settings, *, recursive: bool = True) -> List[Dict[str, Any]]:
    """Scan every configured library folder, de-duplicate by path, and return
    entries sorted by folder then relative path."""
    seen: set = set()
    entries: List[Dict[str, Any]] = []
    for folder in library_folders(settings):
        for e in scan_folder(folder, recursive=recursive):
            if e["path"] in seen:
                continue
            seen.add(e["path"])
            entries.append(e)
    entries.sort(key=lambda e: (e["folder"].lower(), e["rel"].lower()))
    return entries


# =============================================================================
# Synced reading progress — a .star/progress.json sidecar per library folder
# =============================================================================
#
# Reading progress is keyed by absolute path in settings.json, which is
# machine-specific (a synced folder mounts at different paths on each machine).
# To make progress follow a document across machines, each library folder also
# carries a ``.star/progress.json`` sidecar keyed by the document's path
# *relative* to the folder — so the sidecar syncs with the folder and progress
# travels with the file.  (The ``.star`` dir is in _SKIP_DIRS, so it is never
# itself scanned for documents.)

def _sidecar_file(folder: "str | Path") -> Path:
    return Path(folder) / ".star" / "progress.json"


# Key under which the sidecar carries machine-agnostic per-document metadata
# (reading stats + annotation count), keyed by the same relative path as the
# progress entries.  Kept under a reserved namespace so it can never collide
# with a document whose relative path is literally "_meta" (real relative paths
# always include a file extension, and this key has none).  A leading underscore
# also sorts it away from the document entries in the pretty-printed JSON.
_META_KEY = "_meta"

# Serializes the load→merge→write sidecar sequence in record_progress so
# concurrent writers (scrubbing, a sync callback, another thread) cannot
# interleave a read-modify-write and clobber each other's entry.  A single
# process-wide lock is sufficient: sidecar writes are infrequent and cheap, and
# the atomic os.replace already guards against a *different* process on the same
# machine seeing a half-written file.
_sidecar_lock = threading.Lock()

# Debounce/coalesce state, keyed by resolved sidecar path.  Rapid successive
# writes for the same folder (e.g. a scrub that fires record_progress on every
# frame) are coalesced: within _DEBOUNCE_SECONDS of the last flushed write we
# stash the pending data and skip the disk write, then a later call flushes the
# most recent data.  This never *loses* an update — progress_for/load_sidecar
# consult the pending in-memory value first — it only avoids redundant disk I/O.
_DEBOUNCE_SECONDS = 0.5
_pending: Dict[str, Dict[str, Any]] = {}   # {sidecar_path: latest data dict}
_last_write: Dict[str, float] = {}         # {sidecar_path: monotonic ts of last flush}


def _read_sidecar_raw(folder: "str | Path") -> Dict[str, Any]:
    """Read and parse the on-disk sidecar for *folder* ({} on any failure)."""
    try:
        raw = json.loads(_sidecar_file(folder).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _sidecar_state(folder: "str | Path") -> Dict[str, Any]:
    """Return the freshest full sidecar mapping for *folder*.

    Prefers a debounced-but-not-yet-flushed pending value over the on-disk copy
    so a coalesced write is never invisible to a subsequent read.
    """
    key = str(_sidecar_file(folder))
    pending = _pending.get(key)
    if pending is not None:
        return pending
    return _read_sidecar_raw(folder)


def load_sidecar(folder: "str | Path") -> Dict[str, Any]:
    """Return ``{rel_posix: {offset, pct, ts}}`` from *folder*'s sidecar ({} if none).

    The reserved ``_meta`` namespace (cross-device metadata) is filtered out so
    callers that iterate documents see only per-document progress entries, exactly
    as before this key existed — preserving backward-compatible behaviour.
    """
    return {k: v for k, v in _sidecar_state(folder).items() if k != _META_KEY}


def _atomic_write_json(path: Path, data: Any) -> bool:
    """Serialize *data* to JSON and write it to *path* atomically.

    Writes to a uniquely-named temp file in the *same directory* (so the final
    ``os.replace`` is a same-filesystem atomic rename, not a cross-device copy),
    flushes+fsyncs it, then renames it into place.  A mid-write power loss or a
    sync grabbing the file therefore never yields a half-written / corrupt JSON:
    readers see either the old complete file or the new complete file.  Never
    raises — returns ``False`` (best effort) on any OS error.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass  # fsync unsupported on some filesystems — write still lands
            os.replace(tmp, path)  # atomic rename over the destination
            return True
        except OSError:
            # Clean up the temp file so a failed write never litters .star/.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return False
    except OSError:
        return False


def _write_sidecar(folder: "str | Path", data: Dict[str, Any]) -> bool:
    """Atomically persist the full sidecar mapping *data* for *folder*."""
    return _atomic_write_json(_sidecar_file(folder), data)


def folder_for(settings: Settings, path: "str | Path") -> Optional[Tuple[str, str]]:
    """Return ``(folder, rel_posix)`` for the most specific (deepest) library
    folder that contains *path*, or ``None`` if it is not in any library folder."""
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        return None
    best: Optional[Tuple[Path, Path]] = None
    for folder in library_folders(settings):
        try:
            root = Path(folder).expanduser().resolve()
            rel = p.relative_to(root)
        except (ValueError, OSError):
            continue
        if best is None or len(str(root)) > len(str(best[0])):
            best = (root, rel)
    if best is None:
        return None
    return str(best[0]), best[1].as_posix()


# Fields of a reading-stats entry that are machine-agnostic and therefore worth
# carrying in the synced sidecar so they travel with the document across
# machines (unlike settings.json's per-path stats, which are keyed by absolute
# path and stay local).  A superset here is harmless — only present keys are
# copied — but we keep it to the portable subset the roadmap calls for.
_PORTABLE_STAT_FIELDS = ("seconds", "pct", "last_ts")


def _build_meta_entry(
    settings: Settings, abs_path: "str | Path", rel: str
) -> Optional[Dict[str, Any]]:
    """Assemble the machine-agnostic metadata entry for *rel* from *settings*.

    Pulls the portable subset of the per-path reading stats plus a count of the
    document's annotations.  Returns ``None`` when there is nothing to record so
    the ``_meta`` namespace never fills with empty dicts.
    """
    key = str(abs_path)
    stats = (settings.get("reading_stats") or {}).get(key) or {}
    meta: Dict[str, Any] = {}
    for f in _PORTABLE_STAT_FIELDS:
        if f in stats:
            meta[f] = stats[f]
    anns = (settings.get("annotations") or {}).get(key)
    if isinstance(anns, list) and anns:
        meta["annotations"] = len(anns)
    return meta or None


def record_progress(settings: Settings, path: "str | Path", entry: Dict[str, Any]) -> bool:
    """Write *entry* (e.g. ``{offset, pct, ts}``) for *path* into its library
    folder's sidecar, keyed by relative path.  No-op (returns False) when *path*
    is not inside any library folder.

    The whole load→merge→write sequence runs under a lock so concurrent writers
    cannot interleave and clobber one another, and rapid successive writes to the
    same sidecar are coalesced (debounced) to avoid redundant disk I/O during
    scrubbing/sync — the pending value is still returned by ``progress_for`` in
    the meantime, so no update is ever lost.  The sidecar also carries a
    machine-agnostic ``_meta`` entry (portable reading stats + annotation count)
    keyed by the same relative path, so that metadata travels with the document.
    """
    fr = folder_for(settings, path)
    if not fr:
        return False
    folder, rel = fr
    sidecar_path = str(_sidecar_file(folder))
    with _sidecar_lock:
        data = dict(_sidecar_state(folder))
        data[rel] = entry
        meta_entry = _build_meta_entry(settings, path, rel)
        if meta_entry is not None:
            meta = dict(data.get(_META_KEY) or {})
            meta[rel] = meta_entry
            data[_META_KEY] = meta
        # Always keep the freshest data available to readers in-memory…
        _pending[sidecar_path] = data
        now = time.monotonic()
        last = _last_write.get(sidecar_path)
        if last is not None and (now - last) < _DEBOUNCE_SECONDS:
            # …but coalesce this write: within the debounce window we skip the
            # disk hit and let a later flush persist the most recent data.
            return True
        ok = _write_sidecar(folder, data)
        if ok:
            _last_write[sidecar_path] = now
            _pending.pop(sidecar_path, None)
        return ok


def flush_pending(folder: "str | Path") -> bool:
    """Force any debounced-but-unwritten sidecar data for *folder* to disk.

    Returns ``True`` if a pending write was flushed (or there was nothing
    pending), ``False`` only if the disk write failed.  Call on shutdown/close so
    a coalesced final scrub position is not left only in memory.
    """
    sidecar_path = str(_sidecar_file(folder))
    with _sidecar_lock:
        data = _pending.get(sidecar_path)
        if data is None:
            return True
        ok = _write_sidecar(folder, data)
        if ok:
            _last_write[sidecar_path] = time.monotonic()
            _pending.pop(sidecar_path, None)
        return ok


def progress_for(settings: Settings, path: "str | Path") -> Optional[Dict[str, Any]]:
    """Return the synced sidecar progress entry for *path*, or ``None``."""
    fr = folder_for(settings, path)
    if not fr:
        return None
    folder, rel = fr
    return load_sidecar(folder).get(rel)


def metadata_for(settings: Settings, path: "str | Path") -> Optional[Dict[str, Any]]:
    """Return the machine-agnostic ``_meta`` sidecar entry for *path*, or ``None``.

    Surfaces the portable per-document metadata (reading seconds/pct/last_ts and
    annotation count) that ``record_progress`` stashes alongside the raw progress
    offset, keyed by the document's path relative to its library folder.
    """
    fr = folder_for(settings, path)
    if not fr:
        return None
    folder, rel = fr
    meta = _sidecar_state(folder).get(_META_KEY)
    if isinstance(meta, dict):
        return meta.get(rel)
    return None


def metadata_by_folder(settings: Settings) -> Dict[str, Dict[str, Any]]:
    """Pre-load every library folder's ``_meta`` map once: ``{folder: {rel: meta}}``."""
    out: Dict[str, Dict[str, Any]] = {}
    for folder in library_folders(settings):
        meta = _sidecar_state(folder).get(_META_KEY)
        out[folder] = meta if isinstance(meta, dict) else {}
    return out


def sidecars_by_folder(settings: Settings) -> Dict[str, Dict[str, Any]]:
    """Pre-load every library folder's sidecar once: ``{folder: {rel: entry}}``.
    Lets a bulk library listing look up progress without re-reading files."""
    return {folder: load_sidecar(folder) for folder in library_folders(settings)}
