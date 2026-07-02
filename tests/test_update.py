"""Tests for :mod:`star.update` — the PyPI auto-update check.

Every test injects a fake fetcher (or an exception-raising one) so **no test
ever touches the real network**.  The on-disk cache is redirected to a per-test
temp path via the ``cache_file=`` argument so the developer's real cache is
never read or written.
"""
from __future__ import annotations

import json
import time
import urllib.error

import pytest

from star import update


def _pypi_payload(latest: str, extra_releases=None, yanked=None):
    """Build a minimal PyPI-JSON-shaped payload string.

    *latest* becomes ``info.version`` and gets a normal (non-yanked) file entry.
    *extra_releases* is an iterable of extra version strings to add as normal
    releases; *yanked* is an iterable of versions whose only file is yanked.
    """
    releases = {latest: [{"filename": f"star_reader-{latest}.whl", "yanked": False}]}
    for ver in extra_releases or []:
        releases[ver] = [{"filename": f"star_reader-{ver}.whl", "yanked": False}]
    for ver in yanked or []:
        releases[ver] = [{"filename": f"star_reader-{ver}.whl", "yanked": True}]
    return json.dumps({"info": {"version": latest}, "releases": releases})


def _fetcher_returning(body: str):
    """A fetcher stub that returns *body* and records the URL/timeout it saw."""
    calls = []

    def _fetch(url, timeout):
        calls.append((url, timeout))
        return body

    _fetch.calls = calls
    return _fetch


def _fetcher_raising(exc: Exception):
    """A fetcher stub that always raises *exc* (simulates offline / HTTP error)."""

    def _fetch(url, timeout):
        raise exc

    return _fetch


# ── version parsing / comparison ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "candidate,current,expected",
    [
        ("0.1.20", "0.1.19", True),
        ("0.2.0", "0.1.19", True),
        ("1.0.0", "0.9.9", True),
        ("0.1.19", "0.1.19", False),  # equal is not newer
        ("0.1.18", "0.1.19", False),  # older
        ("0.1.9", "0.1.10", False),   # numeric, not lexical (9 < 10)
        ("0.1.100", "0.1.99", True),
    ],
)
def test_is_newer_numeric(candidate, current, expected):
    assert update.is_newer(candidate, current) is expected


def test_is_newer_prerelease_orders_before_final():
    # A pre-release of the same release is OLDER than the final.
    assert update.is_newer("0.2.0", "0.2.0rc1") is True
    assert update.is_newer("0.2.0rc1", "0.2.0") is False
    # But a pre-release of a higher release still beats an older final.
    assert update.is_newer("0.2.0rc1", "0.1.19") is True


def test_is_newer_never_raises_on_garbage():
    # Unparseable input must be treated as "not newer", never an exception.
    assert update.is_newer("not-a-version", "0.1.19") is False
    assert update.is_newer("0.1.19", "also-garbage") in (True, False)


# ── latest_version ───────────────────────────────────────────────────────────


def test_latest_version_parses_info_version():
    body = _pypi_payload("0.2.0")
    fetch = _fetcher_returning(body)
    assert update.latest_version(fetcher=fetch) == "0.2.0"
    # Hits the real PyPI JSON URL with the configured timeout.
    url, timeout = fetch.calls[0]
    assert url == update.PYPI_JSON_URL
    assert timeout == update.DEFAULT_TIMEOUT


def test_latest_version_picks_highest_release_not_info():
    # releases contains a higher version than info.version -> pick the highest.
    body = _pypi_payload("0.2.0", extra_releases=["0.3.1", "0.1.5"])
    assert update.latest_version(fetcher=_fetcher_returning(body)) == "0.3.1"


def test_latest_version_skips_yanked_release():
    # 0.9.9 exists but is fully yanked -> the newest usable is 0.2.0.
    body = _pypi_payload("0.2.0", yanked=["0.9.9"])
    assert update.latest_version(fetcher=_fetcher_returning(body)) == "0.2.0"


def test_latest_version_offline_returns_none():
    fetch = _fetcher_raising(urllib.error.URLError("no network"))
    assert update.latest_version(fetcher=fetch) is None


def test_latest_version_timeout_returns_none():
    fetch = _fetcher_raising(TimeoutError("timed out"))
    assert update.latest_version(fetcher=fetch) is None


def test_latest_version_malformed_json_returns_none():
    assert update.latest_version(fetcher=_fetcher_returning("{not json")) is None


def test_latest_version_empty_payload_returns_none():
    assert update.latest_version(fetcher=_fetcher_returning("{}")) is None


def test_latest_version_never_raises_on_unexpected_error():
    fetch = _fetcher_raising(RuntimeError("boom"))
    # Even an unexpected error type is swallowed.
    assert update.latest_version(fetcher=fetch) is None


# ── check_for_update ─────────────────────────────────────────────────────────


def test_check_for_update_reports_available(tmp_path):
    body = _pypi_payload("0.2.0")
    res = update.check_for_update(
        current="0.1.19",
        fetcher=_fetcher_returning(body),
        cache_file=tmp_path / "u.json",
    )
    assert res.current == "0.1.19"
    assert res.latest == "0.2.0"
    assert res.update_available is True
    assert res.url == update.PROJECT_URL


def test_check_for_update_up_to_date(tmp_path):
    body = _pypi_payload("0.1.19")
    res = update.check_for_update(
        current="0.1.19",
        fetcher=_fetcher_returning(body),
        cache_file=tmp_path / "u.json",
    )
    assert res.latest == "0.1.19"
    assert res.update_available is False


def test_check_for_update_offline_is_safe(tmp_path):
    res = update.check_for_update(
        current="0.1.19",
        fetcher=_fetcher_raising(urllib.error.URLError("offline")),
        cache_file=tmp_path / "u.json",
    )
    assert res.latest is None
    assert res.update_available is False
    assert res.current == "0.1.19"
    assert res.url == update.PROJECT_URL


def test_check_for_update_writes_and_reads_cache(tmp_path):
    cache = tmp_path / "u.json"
    body = _pypi_payload("0.2.0")
    live = _fetcher_returning(body)
    # First call performs a live query and writes the cache.
    res1 = update.check_for_update(
        current="0.1.19", fetcher=live, cache_file=cache
    )
    assert res1.latest == "0.2.0"
    assert len(live.calls) == 1
    assert cache.is_file()

    # Second call within TTL uses the cache — the fetcher must NOT be called.
    def _must_not_call(url, timeout):
        raise AssertionError("network hit despite fresh cache")

    res2 = update.check_for_update(
        current="0.1.19", fetcher=_must_not_call, cache_file=cache
    )
    assert res2.latest == "0.2.0"


def test_check_for_update_use_cache_false_bypasses_cache(tmp_path):
    cache = tmp_path / "u.json"
    # Pre-seed a fresh cache with an old version.
    cache.write_text(
        json.dumps({"fetched_at": time.time(), "latest": "0.1.19"}),
        encoding="utf-8",
    )
    body = _pypi_payload("0.3.0")
    res = update.check_for_update(
        current="0.1.19",
        fetcher=_fetcher_returning(body),
        cache_file=cache,
        use_cache=False,
    )
    # Live query wins, and the cache is refreshed to the new value.
    assert res.latest == "0.3.0"
    assert res.update_available is True
    blob = json.loads(cache.read_text(encoding="utf-8"))
    assert blob["latest"] == "0.3.0"


def test_check_for_update_stale_cache_triggers_refetch(tmp_path):
    cache = tmp_path / "u.json"
    # Cache older than the TTL must be ignored.
    cache.write_text(
        json.dumps({"fetched_at": time.time() - 10_000, "latest": "0.1.0"}),
        encoding="utf-8",
    )
    body = _pypi_payload("0.2.0")
    res = update.check_for_update(
        current="0.1.19",
        fetcher=_fetcher_returning(body),
        cache_file=cache,
        cache_ttl=5,  # tiny TTL; the pre-seeded entry is far older
    )
    assert res.latest == "0.2.0"


def test_check_for_update_corrupt_cache_is_ignored(tmp_path):
    cache = tmp_path / "u.json"
    cache.write_text("{ this is not json", encoding="utf-8")
    body = _pypi_payload("0.2.0")
    res = update.check_for_update(
        current="0.1.19",
        fetcher=_fetcher_returning(body),
        cache_file=cache,
    )
    # Corrupt cache is silently discarded and a live query runs.
    assert res.latest == "0.2.0"


def test_check_for_update_offline_with_no_cache_never_raises(tmp_path):
    # Belt-and-braces: offline + no cache + default current must be inert.
    res = update.check_for_update(
        fetcher=_fetcher_raising(OSError("down")),
        cache_file=tmp_path / "nope.json",
    )
    assert res.update_available is False
    assert res.latest is None


def test_default_current_is_app_version(tmp_path):
    # When current is omitted it defaults to the running APP_VERSION.
    from star._runtime import APP_VERSION

    body = _pypi_payload(APP_VERSION)
    res = update.check_for_update(
        fetcher=_fetcher_returning(body),
        cache_file=tmp_path / "u.json",
    )
    assert res.current == APP_VERSION
    assert res.update_available is False
