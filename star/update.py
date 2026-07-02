"""Best-effort auto-update check against the PyPI JSON API.

star is distributed as the ``star-reader`` wheel on PyPI (plus a handful of
build-it-yourself artifacts).  This module lets star tell the user when a newer
release is available, without any third-party dependency: it queries the public
PyPI JSON API with :mod:`urllib` and compares the newest published version
against the running one.

Design contract — the whole module is **offline-safe** and **never raises**:

* :func:`latest_version` returns the newest non-yanked version string, or
  ``None`` on any network / HTTP / parse error (offline, timeout, malformed
  JSON, …).  It is *injectable* (``fetcher=``) so tests never touch the real
  network.
* :func:`check_for_update` wraps that into a small :class:`UpdateResult` and is
  the function GUI/CLI callers should use.  It caches the last successful PyPI
  reply briefly under ``CACHE_DIR`` so repeated launches do not re-hit the
  network, and swallows every error — a failed check is simply "no update
  known", never a crash and never a traceback in the user's face.

Wiring the result into a menu item or a ``--check-update`` CLI flag is a
deliberate follow-up: this module only *exposes* the check (app.py / the GUI are
owned elsewhere).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

from ._runtime import APP_VERSION, CACHE_DIR

_log = logging.getLogger("star.update")

# The canonical distribution name on PyPI (``import star`` but ``pip install
# star-reader``).  The JSON API returns every release for the project.
PACKAGE_NAME = "star-reader"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
PROJECT_URL = f"https://pypi.org/project/{PACKAGE_NAME}/"

# Keep the network request short so a slow/blocked connection never stalls a
# launch — a missed check is harmless.
DEFAULT_TIMEOUT = 5

# How long a successful PyPI reply stays fresh.  Within this window
# check_for_update() answers from the on-disk cache instead of the network, so
# launching star repeatedly does not hammer PyPI.  6 hours is a good balance for
# a desktop app the user may open many times a day.
CACHE_TTL_SECONDS = 6 * 60 * 60

# Where the cached reply lives (a tiny JSON file under the shared cache dir).
_CACHE_FILE = CACHE_DIR / "update_check.json"

# ``fetcher(url, timeout) -> str`` — returns the raw JSON body.  Injected in
# tests so no real request is made.
Fetcher = Callable[[str, int], str]


@dataclass(frozen=True)
class UpdateResult:
    """Outcome of an update check.

    *current* is the running version; *latest* is the newest version PyPI knows
    about (``None`` when the check could not complete — offline, etc.).
    *update_available* is ``True`` only when a strictly-newer release exists.
    *url* points at the PyPI project page so a caller can open it.
    """

    current: str
    latest: Optional[str]
    update_available: bool
    url: str


# ── version comparison ───────────────────────────────────────────────────────


def _parse_version(version: str) -> Tuple[Tuple[int, ...], bool]:
    """Return a sortable key for a PEP 440-ish version string.

    star uses simple ``MAJOR.MINOR.PATCH`` versions with an optional
    pre-release suffix (``-rc1`` / ``rc1`` / ``a1`` / ``b2``).  We only need
    enough ordering to answer "is PyPI newer than me", so we compare the numeric
    release segments and treat any pre-release marker as *older* than the same
    release without one (``1.0.0rc1`` < ``1.0.0``).

    The returned key is ``(release_tuple, is_final)`` where *is_final* is
    ``True`` for a plain release and ``False`` for a pre-release, so ordinary
    tuple comparison orders a pre-release before its final counterpart.
    """
    v = version.strip()
    # Split off a pre/dev/post suffix at the first non [0-9.] run.  Everything
    # before it is the numeric release; its mere presence means "pre-release".
    release = v
    is_final = True
    for i, ch in enumerate(v):
        if not (ch.isdigit() or ch == "."):
            release = v[:i]
            # A trailing ``.postN`` still sorts by release; but a plain
            # rc/a/b/dev suffix marks a pre-release.  Treat post/dev/rc/a/b all
            # via the numeric prefix — good enough for star's scheme.
            is_final = release == v
            break
    parts = []
    for seg in release.split("."):
        if seg.isdigit():
            parts.append(int(seg))
    return (tuple(parts), is_final)


def is_newer(candidate: str, current: str) -> bool:
    """True when *candidate* is a strictly newer version than *current*.

    Never raises on a malformed string — an unparseable candidate is simply
    "not newer" (a conservative default that avoids false update prompts).
    """
    try:
        cand_key = _parse_version(candidate)
        cur_key = _parse_version(current)
    except Exception:  # noqa: BLE001 — comparison must never crash a launch.
        return False
    return cand_key > cur_key


# ── PyPI query ───────────────────────────────────────────────────────────────


def _default_fetcher(url: str, timeout: int) -> str:
    """Fetch *url* and return the response body as text (the real network path).

    Isolated so :func:`latest_version` can accept an injected ``fetcher`` and
    tests never touch the network.
    """
    req = urllib.request.Request(url, headers={"User-Agent": f"star/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def _newest_from_releases(data: dict) -> Optional[str]:
    """Pick the newest non-yanked version from a PyPI JSON payload.

    Prefers ``info.version`` (PyPI's own "latest") but falls back to scanning
    ``releases`` and choosing the highest version whose files are not all
    yanked, so a yanked latest never gets recommended.
    """
    releases = data.get("releases")
    candidates = []
    if isinstance(releases, dict):
        for ver, files in releases.items():
            # ``files`` is a list of upload dicts; a release is usable when at
            # least one file is not yanked (empty file list => skip).
            if not isinstance(files, list) or not files:
                continue
            if all(isinstance(f, dict) and f.get("yanked") for f in files):
                continue
            candidates.append(ver)
    if candidates:
        candidates.sort(key=_parse_version)
        return candidates[-1]
    # Fall back to info.version if releases was missing/empty.
    info = data.get("info")
    if isinstance(info, dict):
        ver = info.get("version")
        if isinstance(ver, str) and ver:
            return ver
    return None


def latest_version(
    timeout: int = DEFAULT_TIMEOUT,
    fetcher: Optional[Fetcher] = None,
) -> Optional[str]:
    """Return the newest ``star-reader`` version on PyPI, or ``None``.

    Best-effort and **offline-safe**: any network error, HTTP error, timeout,
    or malformed/empty JSON yields ``None`` rather than an exception.  Pass a
    *fetcher* (``fetcher(url, timeout) -> str``) to inject a canned response in
    tests.
    """
    if fetcher is None:
        fetcher = _default_fetcher
    try:
        body = fetcher(PYPI_JSON_URL, timeout)
        data = json.loads(body)
    except (urllib.error.URLError, OSError, ValueError, TypeError):
        _log.debug("update check: PyPI query failed", exc_info=True)
        return None
    except Exception:  # noqa: BLE001 — never let an update check crash a launch.
        _log.debug("update check: unexpected error querying PyPI", exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    return _newest_from_releases(data)


# ── cache ────────────────────────────────────────────────────────────────────


def _read_cache(cache_file: Path, ttl: int) -> Optional[str]:
    """Return the cached latest-version string if it is still fresh, else None.

    A missing / stale / unreadable cache returns ``None`` so the caller falls
    through to a live query.  Never raises.
    """
    try:
        raw = cache_file.read_text(encoding="utf-8")
        blob = json.loads(raw)
        fetched_at = float(blob.get("fetched_at", 0))
        latest = blob.get("latest")
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(latest, str) or not latest:
        return None
    if (time.time() - fetched_at) > ttl:
        return None
    return latest


def _write_cache(cache_file: Path, latest: str) -> None:
    """Persist *latest* with a timestamp.  Best-effort; never raises."""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"fetched_at": time.time(), "latest": latest})
        cache_file.write_text(payload, encoding="utf-8")
    except OSError:
        _log.debug("update check: could not write cache", exc_info=True)


# ── public entry point ───────────────────────────────────────────────────────


def check_for_update(
    current: str = APP_VERSION,
    timeout: int = DEFAULT_TIMEOUT,
    use_cache: bool = True,
    fetcher: Optional[Fetcher] = None,
    cache_file: Optional[Path] = None,
    cache_ttl: int = CACHE_TTL_SECONDS,
) -> UpdateResult:
    """Check PyPI for a newer release of star and return an :class:`UpdateResult`.

    This is the function GUI / CLI code should call.  It is **best-effort and
    never raises**: on any failure it returns a result with ``latest=None`` and
    ``update_available=False`` (i.e. "no update known").

    A successful PyPI reply is cached under ``CACHE_DIR`` for *cache_ttl*
    seconds; within that window the network is not hit again.  Pass
    ``use_cache=False`` to force a live query (used by a manual "check now"
    action), *fetcher* to inject a response in tests, and *cache_file* to
    redirect the cache in tests.
    """
    cf = cache_file if cache_file is not None else _CACHE_FILE

    latest: Optional[str] = None
    if use_cache:
        latest = _read_cache(cf, cache_ttl)
    if latest is None:
        latest = latest_version(timeout=timeout, fetcher=fetcher)
        if latest is not None:
            _write_cache(cf, latest)

    available = bool(latest) and is_newer(latest, current)
    return UpdateResult(
        current=current,
        latest=latest,
        update_available=available,
        url=PROJECT_URL,
    )
