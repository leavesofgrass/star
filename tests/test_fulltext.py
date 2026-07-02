"""Full-text library index + content search (star/fulltext.py, discovery.py).

These tests need no Qt and no optional document loaders: they point a fresh
Settings at a temp library folder full of plain ``.txt`` / ``.md`` files (always
loadable), build the on-demand index, and assert on content search, caching /
incremental refresh, and the discovery.py content-OR-metadata behaviour.
"""
import os

import pytest

os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

from star import fulltext  # noqa: E402
from star import settings as settings_mod  # noqa: E402
from star.discovery import search_library  # noqa: E402
from star.fulltext import FullTextIndex, get_index, build_index_async  # noqa: E402
from star.library import add_library_folder  # noqa: E402
from star.settings import Settings  # noqa: E402


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A Settings pointed at a temp library folder with a few text documents.

    The fulltext on-disk cache and the settings file are redirected into the
    temp dir so tests never touch the user's real cache/settings and stay
    isolated from one another.
    """
    monkeypatch.setattr(fulltext, "_INDEX_CACHE", tmp_path / "ft_cache.json")
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    # Isolate the shared-index registry between tests.
    fulltext._INDEX_CACHE_BY_SETTINGS.clear()

    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "alpha.txt").write_text(
        "The quick brown fox jumps over the lazy dog.", encoding="utf-8"
    )
    (folder / "beta.md").write_text(
        "# Photosynthesis\n\nChloroplasts convert sunlight into energy.",
        encoding="utf-8",
    )
    (folder / "gamma.txt").write_text(
        "Mitochondria are the powerhouse of the cell.", encoding="utf-8"
    )

    settings = Settings()
    settings._data["library"] = {}  # metadata library empty; content only
    settings._data["library_folders"] = []  # drop any real user folders
    add_library_folder(settings, folder)
    return settings, folder


# ── indexing ────────────────────────────────────────────────────────────────


def test_index_builds_and_counts(library):
    settings, _folder = library
    idx = FullTextIndex(settings)
    n = idx.refresh()
    assert n == 3
    assert idx.size == 3


def test_content_search_finds_body_terms(library):
    settings, _folder = library
    idx = FullTextIndex(settings)
    idx.refresh()

    hits = idx.search("chloroplasts")
    assert len(hits) == 1
    assert hits[0]["title"] == "beta"
    assert hits[0]["count"] == 1
    assert "hloroplast" in hits[0]["snippet"].lower() or "energy" in hits[0]["snippet"].lower()

    # Case-insensitive.
    assert idx.search("MITOCHONDRIA")[0]["title"] == "gamma"

    # A term in no document yields nothing.
    assert idx.search("xylophone") == []

    # Empty query is a no-op.
    assert idx.search("") == []
    assert idx.search("   ") == []


def test_search_ranks_by_match_count(library):
    settings, folder = library
    (folder / "repeat.txt").write_text(
        "banana banana banana split", encoding="utf-8"
    )
    (folder / "single.txt").write_text("one banana here", encoding="utf-8")
    idx = FullTextIndex(settings)
    idx.refresh()
    hits = idx.search("banana")
    assert [h["title"] for h in hits[:2]] == ["repeat", "single"]
    assert hits[0]["count"] == 3


def test_matching_paths_returns_absolute_paths(library):
    settings, folder = library
    idx = FullTextIndex(settings)
    idx.refresh()
    paths = idx.matching_paths("dog")
    assert paths == {str(folder / "alpha.txt")}


# ── caching / incremental refresh ────────────────────────────────────────────


def test_refresh_is_incremental_and_persists(library, tmp_path):
    settings, folder = library
    idx = FullTextIndex(settings)
    idx.refresh()
    assert fulltext._INDEX_CACHE.exists(), "index cache file must be written"

    # A brand-new index instance loads from the on-disk cache without re-reading
    # any document (we can search immediately).
    idx2 = FullTextIndex(settings)
    assert idx2.search("fox")[0]["title"] == "alpha"

    # Editing a file changes its (size, mtime); a refresh must pick up the new
    # content while unchanged files stay cached.
    import time as _t

    _t.sleep(0.01)
    (folder / "alpha.txt").write_text(
        "The clever raven solves puzzles.", encoding="utf-8"
    )
    idx2.refresh()
    assert idx2.search("fox") == []
    assert idx2.search("raven")[0]["title"] == "alpha"


def test_refresh_drops_deleted_files(library):
    settings, folder = library
    idx = FullTextIndex(settings)
    idx.refresh()
    assert idx.size == 3
    (folder / "gamma.txt").unlink()
    idx.refresh()
    assert idx.size == 2
    assert idx.search("mitochondria") == []


def test_should_stop_halts_indexing(library):
    settings, _folder = library
    idx = FullTextIndex(settings)
    # Stop before indexing anything.
    n = idx.refresh(should_stop=lambda: True)
    assert n == 0


# ── async builder ────────────────────────────────────────────────────────────


def test_build_index_async_runs_and_calls_back(library):
    settings, _folder = library
    box = {}

    def _done(count):
        box["count"] = count

    t = build_index_async(settings, _done)
    t.join(timeout=10)
    assert not t.is_alive()
    assert box.get("count") == 3
    # The shared index is the same object the async builder populated.
    assert get_index(settings).size == 3


# ── discovery.py content OR metadata ─────────────────────────────────────────


def test_search_library_content_flag(library):
    settings, folder = library
    # Register the docs in the metadata library with unrelated titles so a
    # metadata-only search would miss the body term.
    settings._data["library"] = {
        str(folder / "alpha.txt"): {"title": "Notes One", "path": str(folder / "alpha.txt")},
        str(folder / "beta.md"): {"title": "Notes Two", "path": str(folder / "beta.md")},
        str(folder / "gamma.txt"): {"title": "Notes Three", "path": str(folder / "gamma.txt")},
    }
    get_index(settings).refresh()

    # Without content search, a body-only term matches nothing.
    assert search_library(settings, query="chloroplasts") == []

    # With content search, it finds the document whose body contains it.
    hits = search_library(settings, query="chloroplasts", content=True)
    keys = [k for k, _ in hits]
    assert keys == [str(folder / "beta.md")]

    # Metadata matches still work with the content flag on (OR-combined).
    hits2 = search_library(settings, query="Notes One", content=True)
    assert any("alpha.txt" in k for k, _ in hits2)


def test_search_library_content_respects_other_criteria(library):
    settings, folder = library
    settings._data["library"] = {
        str(folder / "beta.md"): {
            "title": "Bio",
            "path": str(folder / "beta.md"),
            "meta": {"author": "Carol"},
        },
        str(folder / "gamma.txt"): {
            "title": "Cell",
            "path": str(folder / "gamma.txt"),
            "meta": {"author": "Dave"},
        },
    }
    get_index(settings).refresh()
    # "energy" is in beta.md's body; author filter Dave should exclude it even
    # though the content matches, because non-query criteria still AND.
    hits = search_library(settings, query="energy", author="Dave", content=True)
    assert hits == []
    hits2 = search_library(settings, query="energy", author="Carol", content=True)
    assert [k for k, _ in hits2] == [str(folder / "beta.md")]
