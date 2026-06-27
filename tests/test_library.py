"""Tests for folder-as-library scanning (star/library.py)."""
from __future__ import annotations

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
