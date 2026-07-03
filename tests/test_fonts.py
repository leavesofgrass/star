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


# ── Multi-font reading-aid registry (OpenDyslexic + Atkinson + Lexend) ────────


def test_font_registry_has_three_families():
    assert set(fonts.FONTS) == {"opendyslexic", "atkinson", "lexend"}
    assert fonts.font_family("opendyslexic") == "OpenDyslexic"
    assert fonts.font_family("atkinson") == "Atkinson Hyperlegible"
    assert fonts.font_family("lexend") == "Lexend"
    assert fonts.font_family("nope") == ""


def test_every_font_url_is_pinned_and_correct_ext():
    for key, spec in fonts.FONTS.items():
        assert spec.urls, f"{key} has no URLs"
        # Pinned to an immutable ref, never a mutable branch.
        for url in spec.urls:
            assert "/master/" not in url and "/main/" not in url, url
            assert url.endswith((".otf", ".ttf")), url
        # The probe file is one of the fetched basenames.
        names = {u.rsplit("/", 1)[-1] for u in spec.urls}
        assert spec.probe in names


def test_is_font_fetched_per_key(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "font_dir", lambda: tmp_path)
    assert fonts.is_font_fetched("atkinson") is False
    assert fonts.is_font_fetched("lexend") is False
    (tmp_path / fonts.FONTS["atkinson"].probe).write_bytes(b"ttf")
    assert fonts.is_font_fetched("atkinson") is True
    # is_fetched() (back-compat) still keys on OpenDyslexic only.
    assert fonts.is_fetched() is False
    assert fonts.is_font_fetched("nope") is False


def test_fetch_font_downloads_selected_family(tmp_path, monkeypatch):
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
    paths = fonts.fetch_font("lexend")
    # Only Lexend's URLs were fetched, and its files landed in the cache.
    assert set(calls) == set(fonts.FONTS["lexend"].urls)
    assert fonts.is_font_fetched("lexend") is True
    assert any(p.suffix in (".ttf", ".otf") for p in paths)


def test_fetch_font_unknown_key_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "font_dir", lambda: tmp_path)

    def _boom(url, timeout=0):  # would fire if an unknown key hit the network
        raise AssertionError("unknown key must not fetch")

    monkeypatch.setattr(fonts.urllib.request, "urlopen", _boom)
    assert fonts.fetch_font("nope") == []


def test_fetched_paths_includes_ttf(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "font_dir", lambda: tmp_path)
    (tmp_path / "Lexend-Regular.ttf").write_bytes(b"a")
    (tmp_path / "OpenDyslexic-Regular.otf").write_bytes(b"b")
    names = {p.name for p in fonts.fetched_paths()}
    assert names == {"Lexend-Regular.ttf", "OpenDyslexic-Regular.otf"}
