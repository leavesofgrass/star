"""On-disk document cache."""
from ._runtime import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Document caching
# ---------------------------------------------------------------------------

CACHE_VERSION = 1  # bump to invalidate all on-disk caches


def _cache_key(path: str, settings_fingerprint: str) -> str:
    """Return the cache filename for a given document path + settings."""
    path_hash = hashlib.md5(path.encode()).hexdigest()[:16]
    return f"{path_hash}_{settings_fingerprint}_v{CACHE_VERSION}.json"


def _cache_save(path: str, doc_data: dict, settings_fingerprint: str) -> None:
    """Save parsed document data to the local cache directory."""
    # Skip URLs and very small files (< 1 KB)
    if path.startswith(("http://", "https://")):
        return
    try:
        if Path(path).stat().st_size < 1024:
            return
        mtime = Path(path).stat().st_mtime
    except OSError:
        return

    try:
        cache_dir = Path(CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "path": path,
            "mtime": mtime,
            "settings_fingerprint": settings_fingerprint,
            "data": doc_data,
        }
        (cache_dir / _cache_key(path, settings_fingerprint)).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except (PermissionError, OSError):
        pass


def _cache_load(path: str, settings_fingerprint: str) -> "Optional[dict]":
    """Load cached document data if it is still valid (mtime unchanged).
    Returns None if no valid cache entry exists.
    """
    if path.startswith(("http://", "https://")):
        return None

    try:
        current_mtime = Path(path).stat().st_mtime
    except OSError:
        return None

    try:
        cache_file = Path(CACHE_DIR) / _cache_key(path, settings_fingerprint)
        if not cache_file.exists():
            return None
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        if payload.get("version") != CACHE_VERSION:
            return None
        if abs(payload.get("mtime", 0) - current_mtime) > 1e-3:
            cache_file.unlink(missing_ok=True)
            return None
        return payload.get("data")
    except (PermissionError, json.JSONDecodeError, OSError):
        return None
