"""Tests for hot-folder watching (``star.watch.HotFolderWatcher``).

These exercise the watcher end to end with short debounce timings:

* a file dropped into the watched folder is converted into the output folder
  and its source is moved to ``processed/``;
* a file written slowly in chunks is *not* converted until it has fully
  stabilised (the debounce / partial-write guard), and the converted output
  then contains the complete content.

The watcher works with or without the optional ``watchdog`` dependency (it
falls back to directory polling), so these tests pass either way.
"""

import time
from pathlib import Path

import pytest

from star.settings import Settings
from star.watch import HotFolderWatcher


@pytest.fixture
def settings():
    s = Settings()
    s._data["document_cache"] = False
    return s


def _wait_for(predicate, timeout=20.0, interval=0.1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_hotfolder_converts_and_moves_source(tmp_path, settings):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    watcher = HotFolderWatcher(
        in_dir,
        out_dir,
        "markdown",
        settings,
        stable_seconds=0.3,
        poll_interval=0.1,
    )
    watcher.start()
    try:
        (in_dir / "note.txt").write_text("Hello hot folder.", encoding="utf-8")
        assert _wait_for(lambda: (out_dir / "note.md").exists()), (
            "converted output never appeared"
        )
        # Source moved into processed/ (and gone from the watched dir).
        assert _wait_for(lambda: (in_dir / "processed" / "note.txt").exists())
        assert not (in_dir / "note.txt").exists()
    finally:
        watcher.stop()


def test_hotfolder_failure_moves_to_failed(tmp_path, settings, monkeypatch):
    import star.convert as convert

    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()

    real_load = convert.load_document

    def fake_load(path, s):
        if Path(path).name == "bad.txt":
            raise RuntimeError("simulated bad file")
        return real_load(path, s)

    monkeypatch.setattr(convert, "load_document", fake_load)

    watcher = HotFolderWatcher(
        in_dir,
        out_dir,
        "text",
        settings,
        stable_seconds=0.3,
        poll_interval=0.1,
    )
    watcher.start()
    try:
        (in_dir / "bad.txt").write_text("whatever", encoding="utf-8")
        # On failure the source goes to failed/, NOT processed/.
        assert _wait_for(lambda: (in_dir / "failed" / "bad.txt").exists())
        assert not (in_dir / "processed" / "bad.txt").exists()
        assert not (out_dir / "bad.txt").exists()
    finally:
        watcher.stop()


def test_hotfolder_debounce_partial_write(tmp_path, settings):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    watcher = HotFolderWatcher(
        in_dir,
        out_dir,
        "text",
        settings,
        stable_seconds=1.0,
        poll_interval=0.2,
    )
    watcher.start()
    target = in_dir / "slow.txt"
    out_file = out_dir / "slow.txt"
    try:
        # Write the file slowly in chunks over ~1.5 s.  While it is still
        # growing it must never be converted (that would mean a partial read).
        with open(target, "w", encoding="utf-8") as f:
            for i in range(5):
                f.write(f"chunk {i} ")
                f.flush()
                time.sleep(0.3)
                if i < 4:
                    assert not out_file.exists(), (
                        "a partially-written file was processed before it stabilised"
                    )
        # After the writer closes and the size stabilises, it converts — with
        # the full content, not a truncated prefix.
        assert _wait_for(lambda: out_file.exists(), timeout=10.0)
        assert "chunk 4" in out_file.read_text(encoding="utf-8")
    finally:
        watcher.stop()
