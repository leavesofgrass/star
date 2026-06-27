"""Tests for the private .pyz artifact: the build-side extras gatherer
(build_zipapp.gather_extras) and the runtime bootstrap's native-engine / docs
setup (tools/zipapp_bootstrap.py).  These exercise the new logic without running
the heavy full ``pip install .[all]`` build.
"""
from __future__ import annotations

import importlib.util
import json
import os
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def bootstrap():
    return _load(ROOT / "tools" / "zipapp_bootstrap.py", "star_zipapp_bootstrap_test")


def _make_archive(p: Path, *, manifest=None, vendor=True, docs=True, build_id="test-bid"):
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("__main__.py", "pass\n")
        zf.writestr("_payload/.build_id", build_id)
        zf.writestr("_payload/star/__init__.py", "")  # token payload
        if vendor:
            zf.writestr("_vendor/ffmpeg/ffmpeg.exe", b"FAKE-FFMPEG")
            zf.writestr("_vendor/pandoc/pandoc.exe", b"FAKE-PANDOC")
        if docs:
            zf.writestr("_docs/README.md", "# star")
            zf.writestr("_docs/docs/guide.md", "guide")
        if manifest is not None:
            zf.writestr("_private/manifest.json", json.dumps(manifest))


@pytest.fixture(autouse=True)
def _clean_vendor_env():
    old = os.environ.get("STAR_VENDOR_DIR")
    os.environ.pop("STAR_VENDOR_DIR", None)
    yield
    os.environ.pop("STAR_VENDOR_DIR", None)
    if old is not None:
        os.environ["STAR_VENDOR_DIR"] = old


# ── runtime bootstrap: vendor setup ─────────────────────────────────────────

def test_setup_vendor_bundle_extracts_and_sets_env(tmp_path, monkeypatch, bootstrap):
    arc = tmp_path / "star-private.pyz"
    _make_archive(arc, manifest={"mode": "bundle", "has_vendor": True})
    cfg = tmp_path / "cfg"
    monkeypatch.setattr(bootstrap, "_cfg_root", lambda: cfg)

    bootstrap._setup_vendor(str(arc), "test-bid")

    vroot = cfg / "vendor" / "test-bid"
    assert (vroot / "ffmpeg" / "ffmpeg.exe").read_bytes() == b"FAKE-FFMPEG"
    assert (vroot / "pandoc" / "pandoc.exe").is_file()
    assert os.environ["STAR_VENDOR_DIR"] == str(vroot)
    assert (vroot / ".complete").is_file()


def test_setup_vendor_idempotent(tmp_path, monkeypatch, bootstrap):
    arc = tmp_path / "star-private.pyz"
    _make_archive(arc, manifest={"mode": "bundle", "has_vendor": True})
    cfg = tmp_path / "cfg"
    monkeypatch.setattr(bootstrap, "_cfg_root", lambda: cfg)
    bootstrap._setup_vendor(str(arc), "test-bid")
    # second call short-circuits on the marker and still exports the env var
    os.environ.pop("STAR_VENDOR_DIR", None)
    bootstrap._setup_vendor(str(arc), "test-bid")
    assert os.environ["STAR_VENDOR_DIR"] == str(cfg / "vendor" / "test-bid")


def test_setup_vendor_noop_without_manifest(tmp_path, monkeypatch, bootstrap):
    # The plain dependency-only star.pyz has no manifest → vendor setup is a no-op.
    arc = tmp_path / "star.pyz"
    _make_archive(arc, manifest=None, vendor=False, docs=False)
    monkeypatch.setattr(bootstrap, "_cfg_root", lambda: tmp_path / "cfg")
    bootstrap._setup_vendor(str(arc), "test-bid")
    assert "STAR_VENDOR_DIR" not in os.environ


def test_setup_docs_extracts_tree(tmp_path, monkeypatch, bootstrap):
    arc = tmp_path / "star-private.pyz"
    _make_archive(arc, manifest={"mode": "fetch", "has_vendor": False})
    cfg = tmp_path / "cfg"
    monkeypatch.setattr(bootstrap, "_cfg_root", lambda: cfg)
    bootstrap._setup_docs(str(arc), "test-bid")
    assert (cfg / "docs" / "README.md").read_text(encoding="utf-8") == "# star"
    assert (cfg / "docs" / "docs" / "guide.md").is_file()


# ── build side: gather_extras ───────────────────────────────────────────────

def test_gather_extras_docs_and_fetcher_fetch_mode():
    import build_zipapp as bz

    extras = bz.gather_extras(with_vendor=False, vendor_dir=Path("does-not-exist"))
    arcs = [a for _, a in extras]
    assert "_docs/README.md" in arcs
    assert "_private/build-vendor.py" in arcs
    assert not any(a.startswith("_vendor/") for a in arcs)  # fetch mode bundles no binaries


def test_gather_extras_with_vendor_missing_raises(tmp_path):
    import build_zipapp as bz

    with pytest.raises(FileNotFoundError):
        bz.gather_extras(with_vendor=True, vendor_dir=tmp_path / "nope")


def test_gather_extras_bundles_vendor_tree(tmp_path):
    import build_zipapp as bz

    v = tmp_path / "vendor"
    (v / "ffmpeg").mkdir(parents=True)
    (v / "ffmpeg" / "ffmpeg.exe").write_bytes(b"x")
    arcs = [a for _, a in bz.gather_extras(with_vendor=True, vendor_dir=v)]
    assert "_vendor/ffmpeg/ffmpeg.exe" in arcs
