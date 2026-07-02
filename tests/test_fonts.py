"""Tests for star.fonts — on-demand OpenDyslexic fetch/cache. No real network."""
from pathlib import Path

from star import fonts


def test_family_name():
    assert fonts.family_name() == "OpenDyslexic"


def test_font_urls_are_otf_and_pinned():
    assert fonts.FONT_URLS, "expected at least one font URL"
    assert all(u.endswith(".otf") for u in fonts.FONT_URLS)
    # Pinned to an immutable ref, not a mutable branch.
    assert "master" not in fonts._FONT_BASE and "/main/" not in fonts._FONT_BASE


def test_is_fetched_and_fetched_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "font_dir", lambda: tmp_path)
    assert fonts.is_fetched() is False
    assert fonts.fetched_paths() == []
    (tmp_path / "OpenDyslexic-Regular.otf").write_bytes(b"font-bytes")
    assert fonts.is_fetched() is True
    assert fonts.fetched_paths() == [tmp_path / "OpenDyslexic-Regular.otf"]


def test_fetch_downloads_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "font_dir", lambda: tmp_path)
    calls = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"FONTDATA"

    def _fake_urlopen(url, timeout=0):
        calls.append(url)
        return _Resp()

    monkeypatch.setattr(fonts.urllib.request, "urlopen", _fake_urlopen)
    paths = fonts.fetch()
    assert len(calls) == len(fonts.FONT_URLS)          # all fetched
    assert (tmp_path / "OpenDyslexic-Regular.otf").read_bytes() == b"FONTDATA"
    assert fonts.is_fetched() is True
    assert all(isinstance(p, Path) for p in paths)


def test_fetch_skips_existing_and_is_offline_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "font_dir", lambda: tmp_path)
    # Regular already present; the rest error out (offline) — fetch must not raise.
    (tmp_path / "OpenDyslexic-Regular.otf").write_bytes(b"already")

    def _boom(url, timeout=0):
        raise OSError("offline")

    monkeypatch.setattr(fonts.urllib.request, "urlopen", _boom)
    paths = fonts.fetch()                               # never raises
    assert (tmp_path / "OpenDyslexic-Regular.otf").read_bytes() == b"already"
    assert (tmp_path / "OpenDyslexic-Regular.otf") in paths


def test_opendyslexic_listed_in_system_tools():
    from star import diagnostics

    keys = {t["key"] for t in diagnostics.system_tools()}
    assert "opendyslexic" in keys
    rec = next(t for t in diagnostics.system_tools() if t["key"] == "opendyslexic")
    assert set(rec) >= {"key", "label", "available", "enables", "install"}
    assert isinstance(rec["available"], bool)
