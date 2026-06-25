"""Tests for Epic II — metadata & discovery (star.citations + star.discovery)."""
import json
from unittest.mock import patch

import pytest

from star.citations import _fetch_metadata_by_isbn, _valid_isbn
from star.discovery import _norm_doi, _norm_isbn, search_library
from star.settings import Settings


# =============================================================================
# ISBN validation
# =============================================================================


class TestValidISBN:
    def test_valid_isbn13(self):
        assert _valid_isbn("978-3-16-148410-0")
        assert _valid_isbn("9783161484100")  # no hyphens

    def test_valid_isbn10(self):
        assert _valid_isbn("0-306-40615-2")
        assert _valid_isbn("0306406152")

    def test_invalid_isbn10_wrong_check(self):
        assert not _valid_isbn("0306406153")

    def test_invalid_isbn13_wrong_check(self):
        assert not _valid_isbn("9783161484101")

    def test_isbn10_with_x(self):
        assert _valid_isbn("0-8044-2957-X")
        assert _valid_isbn("080442957X")

    def test_too_short(self):
        assert not _valid_isbn("123")

    def test_empty(self):
        assert not _valid_isbn("")

    def test_letters_invalid(self):
        assert not _valid_isbn("978-3-16-14841A-0")

    def test_spaces_stripped(self):
        assert _valid_isbn("978 3 16 148410 0")


# =============================================================================
# Normalisation helpers
# =============================================================================


def test_norm_doi_strips_prefixes():
    assert _norm_doi("https://doi.org/10.1234/foo") == "10.1234/foo"
    assert _norm_doi("doi:10.1234/foo") == "10.1234/foo"
    assert _norm_doi("10.1234/foo") == "10.1234/foo"


def test_norm_isbn_strips_hyphens():
    assert _norm_isbn("978-3-16-148410-0") == "9783161484100"
    assert _norm_isbn("0-306-40615-2") == "0306406152"


# =============================================================================
# Library search
# =============================================================================


def _make_settings(library=None, annotations=None):
    """Build a minimal Settings-like dict-backed object."""

    class _FakeSettings:
        def __init__(self, lib, ann):
            self._lib = lib or {}
            self._ann = ann or {}

        def get(self, key, default=None):
            if key == "library":
                return self._lib
            if key == "annotations":
                return self._ann
            return default

    return _FakeSettings(library, annotations)


def test_search_library_no_criteria():
    settings = _make_settings(
        library={
            "a.pdf": {"title": "Alpha"},
            "b.pdf": {"title": "Beta"},
        }
    )
    results = search_library(settings)
    assert len(results) == 2


def test_search_library_query_title():
    settings = _make_settings(
        library={
            "a.pdf": {"title": "Alpha Document"},
            "b.pdf": {"title": "Beta Paper"},
        }
    )
    results = search_library(settings, query="alpha")
    assert len(results) == 1
    assert results[0][0] == "a.pdf"


def test_search_library_by_doi():
    settings = _make_settings(
        library={
            "a.pdf": {"title": "Alpha", "meta": {"doi": "10.1234/foo"}},
            "b.pdf": {"title": "Beta", "meta": {}},
        }
    )
    results = search_library(settings, doi="https://doi.org/10.1234/foo")
    assert len(results) == 1
    assert results[0][0] == "a.pdf"


def test_search_library_by_isbn():
    settings = _make_settings(
        library={
            "a.pdf": {"title": "Alpha", "meta": {"isbn": "9783161484100"}},
            "b.pdf": {"title": "Beta", "meta": {}},
        }
    )
    results = search_library(settings, isbn="978-3-16-148410-0")
    assert len(results) == 1
    assert results[0][0] == "a.pdf"


def test_search_library_by_author():
    settings = _make_settings(
        library={
            "a.pdf": {"title": "Alpha", "meta": {"author": "Smith, John"}},
            "b.pdf": {"title": "Beta", "meta": {"author": "Jones, Mary"}},
        }
    )
    results = search_library(settings, author="smith")
    assert len(results) == 1
    assert results[0][0] == "a.pdf"


def test_search_library_and_combined():
    settings = _make_settings(
        library={
            "a.pdf": {"title": "Alpha", "meta": {"doi": "10.1/a", "author": "Smith"}},
            "b.pdf": {"title": "Beta", "meta": {"doi": "10.1/a", "author": "Jones"}},
        }
    )
    results = search_library(settings, doi="10.1/a", author="jones")
    assert len(results) == 1
    assert results[0][0] == "b.pdf"


def test_search_library_annotation_fulltext():
    settings = _make_settings(
        library={"a.pdf": {"title": "Alpha"}},
        annotations={"a.pdf": [{"note": "This paper discusses epigenetics"}]},
    )
    results = search_library(settings, query="epigenetics")
    assert len(results) == 1


def test_search_library_empty_library():
    settings = _make_settings(library={})
    assert search_library(settings, query="anything") == []


def test_search_library_offline_doi_mismatch():
    settings = _make_settings(
        library={"a.pdf": {"title": "Alpha", "meta": {"doi": "10.9999/bar"}}}
    )
    results = search_library(settings, doi="10.1/foo")
    assert results == []


# =============================================================================
# OpenLibrary fetch — offline path (network test skipped by default)
# =============================================================================


_OPENLIBRARY_FIXTURE = json.dumps({
    "ISBN:9783161484100": {
        "title": "Sample Book",
        "authors": [{"name": "Author One"}, {"name": "Author Two"}],
        "publish_date": "2021",
        "publishers": [{"name": "Sample Press"}],
    }
}).encode()


def test_fetch_metadata_by_isbn_parse(monkeypatch):
    """Parsing logic tested against a captured fixture (no real network call)."""

    class _FakeResp:
        def read(self):
            return _OPENLIBRARY_FIXTURE

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: _FakeResp()
    )
    meta, msg = _fetch_metadata_by_isbn("978-3-16-148410-0")
    assert msg == ""
    assert meta["title"] == "Sample Book"
    assert "Author One" in meta["author"]
    assert meta["year"] == "2021"
    assert meta["publisher"] == "Sample Press"
    assert meta["isbn"] == "9783161484100"


def test_fetch_metadata_by_isbn_not_found(monkeypatch):
    class _FakeResp:
        def read(self):
            return b"{}"  # empty response → key missing

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: _FakeResp())
    meta, msg = _fetch_metadata_by_isbn("978-3-16-148410-0")
    assert meta == {}
    assert "not found" in msg.lower() or "unavailable" in msg.lower()


def test_fetch_metadata_by_isbn_network_error(monkeypatch):
    import urllib.error

    def _raise(*a, **kw):
        raise urllib.error.URLError("simulated network error")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    meta, msg = _fetch_metadata_by_isbn("978-3-16-148410-0")
    assert meta == {}
    assert "unavailable" in msg.lower() or "failed" in msg.lower()


@pytest.mark.network
def test_fetch_metadata_real_isbn():
    """Real network test — only runs when pytest -m network is given."""
    meta, msg = _fetch_metadata_by_isbn("978-0-345-39180-3")  # Hitchhiker's Guide
    if msg:
        pytest.skip(f"Network unavailable: {msg}")
    assert meta.get("title", "").strip()
