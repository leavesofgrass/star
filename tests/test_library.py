"""Tests for folder-as-library scanning (star/library.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from star import library, settings as settings_mod
from star.settings import Settings


def _make_tree(root):
    (root / "a.md").write_text("# A", encoding="utf-8")
    (root / "b.txt").write_text("b", encoding="utf-8")
    (root / "paper.pdf").write_bytes(b"%PDF-1.4")
    (root / "pic.png").write_bytes(b"\x89PNG")
    (root / "ignore.bin").write_bytes(b"x")        # unsupported extension
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.epub").write_bytes(b"PK\x03\x04")
    hidden_dir = root / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "d.md").write_text("hidden", encoding="utf-8")
    (root / ".secret.md").write_text("x", encoding="utf-8")
    gitdir = root / ".git"
    gitdir.mkdir()
    (gitdir / "config.md").write_text("g", encoding="utf-8")


def _rels(entries):
    return sorted(e["rel"].replace("\\", "/") for e in entries)


def test_scan_folder_finds_supported_recursively(tmp_path):
    _make_tree(tmp_path)
    rels = _rels(library.scan_folder(tmp_path))
    assert "a.md" in rels and "b.txt" in rels and "paper.pdf" in rels and "pic.png" in rels
    assert "sub/c.epub" in rels


def test_scan_folder_excludes_junk(tmp_path):
    _make_tree(tmp_path)
    rels = _rels(library.scan_folder(tmp_path))
    # unsupported extension, hidden file, hidden dir, and .git are all skipped
    assert not any("ignore.bin" in r for r in rels)
    assert not any(r.startswith(".") or "/." in r or ".hidden" in r or ".git" in r for r in rels)
    assert ".secret.md" not in rels


def test_scan_folder_non_recursive(tmp_path):
    _make_tree(tmp_path)
    rels = _rels(library.scan_folder(tmp_path, recursive=False))
    assert "a.md" in rels
    assert "sub/c.epub" not in rels


def test_scan_folder_missing_dir_returns_empty(tmp_path):
    assert library.scan_folder(tmp_path / "does-not-exist") == []


def test_entry_fields(tmp_path):
    (tmp_path / "doc.md").write_text("# T", encoding="utf-8")
    (e,) = library.scan_folder(tmp_path)
    assert e["title"] == "doc"
    assert e["ext"] == ".md"
    assert e["format"] == "markdown"
    assert e["path"].endswith("doc.md")
    assert e["rel"].replace("\\", "/") == "doc.md"
    assert e["size"] >= 0 and e["mtime"] > 0


def test_max_files_cap(tmp_path):
    for i in range(10):
        (tmp_path / f"f{i}.md").write_text("x", encoding="utf-8")
    assert len(library.scan_folder(tmp_path, max_files=4)) == 4


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """A Settings backed by a throwaway file so set()/save() never touch the
    real user settings.json."""
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    return Settings()


def test_add_remove_and_scan_library(tmp_path, isolated_settings):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "x.md").write_text("x", encoding="utf-8")
    s = isolated_settings

    resolved = library.add_library_folder(s, lib)
    assert resolved in library.library_folders(s)
    # idempotent
    library.add_library_folder(s, lib)
    assert len(library.library_folders(s)) == 1

    entries = library.scan_library(s)
    assert any(e["title"] == "x" for e in entries)

    library.remove_library_folder(s, lib)
    assert library.library_folders(s) == []


def test_record_and_read_progress_sidecar(tmp_path, isolated_settings):
    lib = tmp_path / "lib"
    (lib / "sub").mkdir(parents=True)
    doc = lib / "sub" / "book.epub"
    doc.write_bytes(b"PK")
    s = isolated_settings
    library.add_library_folder(s, lib)

    assert library.progress_for(s, doc) is None
    library.record_progress(s, doc, {"offset": 1200, "pct": 42, "ts": "2026-06-27T10:00:00"})

    # sidecar lives in the folder, keyed by POSIX relative path
    sidecar = lib / ".star" / "progress.json"
    assert sidecar.is_file()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "sub/book.epub" in data and data["sub/book.epub"]["pct"] == 42

    got = library.progress_for(s, doc)
    assert got and got["pct"] == 42 and got["offset"] == 1200


def test_progress_syncs_by_relative_path_across_machines(tmp_path, isolated_settings):
    # Machine A writes the sidecar; machine B mounts the SAME folder at a
    # different absolute path (a copy) and reads progress by relative path.
    a = tmp_path / "machineA" / "Reading"
    a.mkdir(parents=True)
    (a / "paper.pdf").write_bytes(b"%PDF")
    s = isolated_settings
    library.add_library_folder(s, a)
    library.record_progress(s, a / "paper.pdf", {"offset": 5, "pct": 77, "ts": "t"})

    # Simulate the synced folder appearing at a different path on machine B.
    import shutil
    b = tmp_path / "machineB" / "Reading"
    b.parent.mkdir(parents=True)
    shutil.copytree(a, b)
    s._data["library_folders"] = [str(b)]
    got = library.progress_for(s, b / "paper.pdf")
    assert got and got["pct"] == 77  # progress traveled with the folder


def test_record_progress_noop_outside_library(tmp_path, isolated_settings):
    outside = tmp_path / "loose.md"
    outside.write_text("x", encoding="utf-8")
    s = isolated_settings  # no library folders configured
    assert library.record_progress(s, outside, {"pct": 1}) is False
    assert library.progress_for(s, outside) is None


def test_folder_for_picks_deepest(tmp_path, isolated_settings):
    parent = tmp_path / "p"
    child = parent / "c"
    child.mkdir(parents=True)
    doc = child / "d.md"
    doc.write_text("x", encoding="utf-8")
    s = isolated_settings
    library.add_library_folder(s, parent)
    library.add_library_folder(s, child)
    folder, rel = library.folder_for(s, doc)
    assert Path(folder) == child.resolve() and rel == "d.md"


def test_scan_library_dedupes_overlapping_folders(tmp_path, isolated_settings):
    # A child folder whose file is also reachable from the parent folder.
    child = tmp_path / "child"
    child.mkdir()
    (child / "one.md").write_text("1", encoding="utf-8")
    s = isolated_settings
    library.add_library_folder(s, tmp_path)   # parent (finds child/one.md)
    library.add_library_folder(s, child)      # child   (finds one.md, same path)
    paths = [e["path"] for e in library.scan_library(s)]
    assert len(paths) == len(set(paths)) == 1  # one.md counted once


# =============================================================================
# Reliability & sync: atomic sidecar writes, locking/debounce, cross-device meta
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_debounce_state():
    """Clear the module-level debounce/pending state before each test so a
    coalesced write from one test can never leak into another (the state is keyed
    by resolved sidecar path, but tmp_path reuse across runs could still alias)."""
    library._pending.clear()
    library._last_write.clear()
    yield
    library._pending.clear()
    library._last_write.clear()


def _leftover_tmps(sidecar_dir: Path):
    return [p for p in sidecar_dir.iterdir() if p.name != "progress.json"] if sidecar_dir.is_dir() else []


def test_sidecar_write_is_atomic_no_temp_left_behind(tmp_path, isolated_settings):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "a.md").write_text("x", encoding="utf-8")
    s = isolated_settings
    library.add_library_folder(s, lib)

    assert library.record_progress(s, lib / "a.md", {"offset": 3, "pct": 10, "ts": "t"})
    sidecar = lib / ".star" / "progress.json"
    assert sidecar.is_file()
    # No .tmp scratch file was left behind in the .star dir.
    assert _leftover_tmps(sidecar.parent) == []
    # And the content is complete, valid JSON (never a truncated middle).
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["a.md"]["pct"] == 10


def test_sidecar_write_preserves_previous_on_replace(tmp_path, isolated_settings):
    """os.replace never yields a partial file: after a second write the file is
    always fully-formed JSON containing both entries."""
    lib = tmp_path / "lib"
    (lib / "sub").mkdir(parents=True)
    (lib / "one.md").write_text("1", encoding="utf-8")
    (lib / "sub" / "two.md").write_text("2", encoding="utf-8")
    s = isolated_settings
    library.add_library_folder(s, lib)

    library.record_progress(s, lib / "one.md", {"pct": 1, "ts": "t1"})
    # Advance past the debounce window so the second write actually hits disk.
    library._last_write.clear()
    library.record_progress(s, lib / "sub" / "two.md", {"pct": 2, "ts": "t2"})

    sidecar = lib / ".star" / "progress.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))  # parses => not corrupt
    assert data["one.md"]["pct"] == 1
    assert data["sub/two.md"]["pct"] == 2
    assert _leftover_tmps(sidecar.parent) == []


def test_write_never_raises_on_bad_target(tmp_path, monkeypatch):
    """A failed atomic write degrades to False, never an exception."""
    # Point the sidecar at a path whose parent cannot be created (a file, not a dir).
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / ".star" / "progress.json"  # parent is a file → mkdir fails
    assert library._atomic_write_json(target, {"k": "v"}) is False


def test_debounce_coalesces_rapid_writes(tmp_path, isolated_settings):
    """Rapid successive record_progress calls to the same sidecar coalesce: the
    disk is written once, but every intermediate value is still readable."""
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "a.md").write_text("x", encoding="utf-8")
    s = isolated_settings
    library.add_library_folder(s, lib)
    doc = lib / "a.md"

    write_calls = {"n": 0}
    real_write = library._write_sidecar

    def _counting_write(folder, data):
        write_calls["n"] += 1
        return real_write(folder, data)

    import star.library as _lib
    orig = _lib._write_sidecar
    _lib._write_sidecar = _counting_write
    try:
        # First write flushes to disk (n=1); the rapid follow-ups within the
        # debounce window are coalesced (no additional disk writes).
        for pct in (10, 20, 30, 40):
            library.record_progress(s, doc, {"pct": pct, "ts": "t"})
    finally:
        _lib._write_sidecar = orig

    assert write_calls["n"] == 1  # coalesced: only the first hit disk
    # …but the latest value is still surfaced (from the pending in-memory copy).
    assert library.progress_for(s, doc)["pct"] == 40
    # flush_pending forces the coalesced tail to disk.
    assert library.flush_pending(lib) is True
    on_disk = json.loads((lib / ".star" / "progress.json").read_text(encoding="utf-8"))
    assert on_disk["a.md"]["pct"] == 40


def test_record_progress_lock_serializes_concurrent_writers(tmp_path, isolated_settings):
    """Many threads scrubbing at once never lose or corrupt an entry: after they
    all finish, every document key is present with a valid value."""
    import threading

    lib = tmp_path / "lib"
    lib.mkdir()
    s = isolated_settings
    library.add_library_folder(s, lib)
    docs = []
    for i in range(12):
        d = lib / f"doc{i}.md"
        d.write_text("x", encoding="utf-8")
        docs.append(d)

    barrier = threading.Barrier(len(docs))

    def _writer(doc, idx):
        barrier.wait()  # maximize contention
        for rep in range(5):
            # Bypass the debounce so every writer forces a disk flush and we
            # exercise the load→merge→write critical section under contention.
            library._last_write.clear()
            library.record_progress(s, doc, {"pct": idx * 10 + rep, "ts": "t"})

    threads = [threading.Thread(target=_writer, args=(d, i)) for i, d in enumerate(docs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    library.flush_pending(lib)
    data = json.loads((lib / ".star" / "progress.json").read_text(encoding="utf-8"))
    # Every document survived — no writer's key was lost to an interleaved
    # read-modify-write (which is exactly what the lock prevents).
    for i in range(len(docs)):
        assert f"doc{i}.md" in data


def test_metadata_round_trip(tmp_path, isolated_settings):
    """Portable per-document metadata (stats subset + annotation count) is
    written to the sidecar's _meta namespace and read back by metadata_for."""
    lib = tmp_path / "lib"
    (lib / "sub").mkdir(parents=True)
    doc = lib / "sub" / "book.epub"
    doc.write_bytes(b"PK")
    s = isolated_settings
    library.add_library_folder(s, lib)

    key = str(Path(doc).expanduser().resolve())
    s._data["reading_stats"] = {
        key: {"seconds": 1234, "pct": 55, "last_ts": "2026-06-30T12:00:00",
              "words_read": 999}  # words_read is machine-specific → must NOT travel
    }
    s._data["annotations"] = {key: [{"note": "a"}, {"note": "b"}, {"note": "c"}]}

    library.record_progress(s, doc, {"offset": 7, "pct": 55, "ts": "t"})

    meta = library.metadata_for(s, doc)
    assert meta is not None
    assert meta["seconds"] == 1234
    assert meta["pct"] == 55
    assert meta["last_ts"] == "2026-06-30T12:00:00"
    assert meta["annotations"] == 3
    assert "words_read" not in meta  # non-portable field excluded

    # metadata_by_folder surfaces the same, keyed by relative path.
    by_folder = library.metadata_by_folder(s)
    assert by_folder[library.folder_for(s, doc)[0]]["sub/book.epub"]["annotations"] == 3


def test_meta_key_hidden_from_progress_listing(tmp_path, isolated_settings):
    """load_sidecar / sidecars_by_folder never expose the reserved _meta key as
    if it were a document, and progress_for still works alongside metadata."""
    lib = tmp_path / "lib"
    lib.mkdir()
    doc = lib / "a.md"
    doc.write_text("x", encoding="utf-8")
    s = isolated_settings
    library.add_library_folder(s, lib)
    key = str(Path(doc).expanduser().resolve())
    s._data["reading_stats"] = {key: {"seconds": 5, "pct": 9, "last_ts": "t"}}

    library.record_progress(s, doc, {"pct": 9, "ts": "t"})

    assert "_meta" not in library.load_sidecar(lib)
    folder = library.folder_for(s, doc)[0]
    assert "_meta" not in library.sidecars_by_folder(s)[folder]
    assert library.progress_for(s, doc)["pct"] == 9


def test_backward_compatible_with_legacy_sidecar(tmp_path, isolated_settings):
    """An old progress.json with no _meta namespace still loads, and its entries
    are preserved when a new write adds the metadata namespace."""
    lib = tmp_path / "lib"
    star_dir = lib / ".star"
    star_dir.mkdir(parents=True)
    doc = lib / "old.md"
    doc.write_text("x", encoding="utf-8")
    # Legacy sidecar: bare progress entries, no _meta key.
    (star_dir / "progress.json").write_text(
        json.dumps({"old.md": {"offset": 100, "pct": 33, "ts": "legacy"}}),
        encoding="utf-8",
    )
    s = isolated_settings
    library.add_library_folder(s, lib)

    # Old file loads unchanged.
    assert library.progress_for(s, doc)["pct"] == 33
    assert library.metadata_for(s, doc) is None  # no meta yet

    # A new write (with stats present) adds _meta additively, keeps the old entry.
    key = str(Path(doc).expanduser().resolve())
    s._data["reading_stats"] = {key: {"seconds": 42, "pct": 33, "last_ts": "now"}}
    library.record_progress(s, doc, {"offset": 200, "pct": 40, "ts": "new"})

    data = json.loads((star_dir / "progress.json").read_text(encoding="utf-8"))
    assert data["old.md"]["pct"] == 40           # progress updated
    assert data["_meta"]["old.md"]["seconds"] == 42  # meta added
    assert library.metadata_for(s, doc)["seconds"] == 42
