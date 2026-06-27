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


def load_sidecar(folder: "str | Path") -> Dict[str, Any]:
    """Return ``{rel_posix: {offset, pct, ts}}`` from *folder*'s sidecar ({} if none)."""
    try:
        raw = json.loads(_sidecar_file(folder).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _write_sidecar(folder: "str | Path", data: Dict[str, Any]) -> bool:
    try:
        f = _sidecar_file(folder)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False


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


def record_progress(settings: Settings, path: "str | Path", entry: Dict[str, Any]) -> bool:
    """Write *entry* (e.g. ``{offset, pct, ts}``) for *path* into its library
    folder's sidecar, keyed by relative path.  No-op (returns False) when *path*
    is not inside any library folder."""
    fr = folder_for(settings, path)
    if not fr:
        return False
    folder, rel = fr
    data = load_sidecar(folder)
    data[rel] = entry
    return _write_sidecar(folder, data)


def progress_for(settings: Settings, path: "str | Path") -> Optional[Dict[str, Any]]:
    """Return the synced sidecar progress entry for *path*, or ``None``."""
    fr = folder_for(settings, path)
    if not fr:
        return None
    folder, rel = fr
    return load_sidecar(folder).get(rel)


def sidecars_by_folder(settings: Settings) -> Dict[str, Dict[str, Any]]:
    """Pre-load every library folder's sidecar once: ``{folder: {rel: entry}}``.
    Lets a bulk library listing look up progress without re-reading files."""
    return {folder: load_sidecar(folder) for folder in library_folders(settings)}
