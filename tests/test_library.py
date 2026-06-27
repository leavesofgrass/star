"""Tests for folder-as-library scanning (star/library.py)."""
from __future__ import annotations

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
    import json
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
