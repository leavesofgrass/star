"""Tests for :mod:`star.tts.piper_models` — the Piper voice catalog + cache.

All network access is injected: no test ever hits Hugging Face.  The cache
directory (``CACHE_DIR/piper``) is redirected to a per-test temp path so the
developer's real cache is never touched and detection is deterministic.

The download function is offline-safe by contract (never raises), so a fetcher
that raises must simply return ``None`` and leave no partial file behind — both
of which are asserted here.
"""
from __future__ import annotations

import pytest

from star.tts import piper_models
from star.tts.piper import PiperBackend


@pytest.fixture(autouse=True)
def _isolate_cache(monkeypatch, tmp_path):
    """Point piper_models at a temp cache dir so nothing global is touched."""
    monkeypatch.setattr(piper_models, "CACHE_DIR", tmp_path)
    # Also block the real network path outright as a belt-and-braces guard: any
    # test that forgets to inject a fetcher fails loudly instead of downloading.
    def _no_net(*_a, **_k):
        raise AssertionError("real network fetch attempted in a test")

    monkeypatch.setattr(piper_models, "_default_fetcher", _no_net)
    return tmp_path


# ── catalog ──────────────────────────────────────────────────────────────────


def test_catalog_is_non_empty_and_well_formed():
    cat = piper_models.catalog()
    assert len(cat) >= 5
    keys = [v.key for v in cat]
    assert len(keys) == len(set(keys)), "catalog keys must be unique"
    for v in cat:
        assert v.key and v.name and v.language and v.quality
        assert v.onnx_url.endswith(".onnx")
        assert v.config_url.endswith(".onnx.json")
        assert v.onnx_name == f"{v.key}.onnx"
        assert v.config_name == f"{v.key}.onnx.json"
        # A human label carries name, language, and quality.
        assert v.language in v.label and v.quality in v.label


def test_catalog_spans_the_five_ui_languages():
    langs = {v.language.split("_")[0] for v in piper_models.catalog()}
    for expected in ("en", "es", "fr", "de", "pt"):
        assert expected in langs, f"catalog missing a {expected} voice"


def test_get_returns_known_and_none_for_unknown():
    first = piper_models.catalog()[0]
    assert piper_models.get(first.key) is first
    assert piper_models.get("no-such-voice") is None


def test_urls_point_at_huggingface():
    v = piper_models.catalog()[0]
    assert v.onnx_url.startswith("https://huggingface.co/rhasspy/piper-voices/")


# ── cache detection ────────────────────────────────────────────────────────


def test_nothing_installed_on_fresh_cache():
    assert piper_models.installed_models() == []
    assert piper_models.installed_keys() == []
    assert not piper_models.is_installed(piper_models.catalog()[0])


def test_is_installed_requires_both_files():
    v = piper_models.catalog()[0]
    piper_models.models_dir()  # create the dir
    # Only the .onnx present → still counts as NOT installed (config missing).
    piper_models.model_path(v).write_bytes(b"weights")
    assert piper_models.is_installed(v) is False
    # Now add the config sidecar → installed.
    piper_models.config_path(v).write_bytes(b"{}")
    assert piper_models.is_installed(v) is True
    assert v in piper_models.installed_models()
    assert v.key in piper_models.installed_keys()


# ── injected download ──────────────────────────────────────────────────────


def _fake_fetcher(mapping):
    """Return a fetcher(url, timeout) that serves bytes from *mapping* by URL."""

    def _fetch(url, _timeout):
        return mapping[url]

    return _fetch


def test_fetch_writes_both_files_with_injected_fetcher():
    v = piper_models.catalog()[0]
    fetcher = _fake_fetcher(
        {v.onnx_url: b"ONNX-DATA", v.config_url: b'{"cfg": true}'}
    )
    out = piper_models.fetch(v, fetcher=fetcher)
    assert out == piper_models.model_path(v)
    assert piper_models.model_path(v).read_bytes() == b"ONNX-DATA"
    assert piper_models.config_path(v).read_bytes() == b'{"cfg": true}'
    assert piper_models.is_installed(v)


def test_fetch_is_idempotent_and_skips_when_present():
    v = piper_models.catalog()[0]
    calls = []

    def _count(url, _timeout):
        calls.append(url)
        return b"x"

    piper_models.fetch(v, fetcher=_count)
    assert len(calls) == 2  # onnx + config
    # Second call: already installed → no further fetches.
    piper_models.fetch(v, fetcher=_count)
    assert len(calls) == 2


def test_fetch_offline_safe_returns_none_and_cleans_partial():
    v = piper_models.catalog()[0]

    def _boom(_url, _timeout):
        raise OSError("network down")

    result = piper_models.fetch(v, fetcher=_boom)
    assert result is None
    # No partial .onnx left behind, and the voice is not reported installed.
    assert not piper_models.model_path(v).exists()
    assert not piper_models.is_installed(v)


def test_fetch_unknown_key_via_backend_returns_empty():
    assert PiperBackend.download_model("no-such-key", fetcher=lambda *_a: b"") == ""


# ── backend integration ────────────────────────────────────────────────────


def test_backend_catalog_voices_shape():
    rows = PiperBackend.catalog_voices()
    assert rows and all(
        {"key", "name", "lang", "quality", "label", "path", "installed"} <= set(r)
        for r in rows
    )
    # Fresh cache → nothing installed.
    assert all(r["installed"] == "" and r["path"] == "" for r in rows)


def test_backend_reports_installed_after_download():
    v = piper_models.catalog()[0]
    fetcher = _fake_fetcher({v.onnx_url: b"w", v.config_url: b"{}"})
    path = PiperBackend.download_model(v.key, fetcher=fetcher)
    assert path == str(piper_models.model_path(v))
    assert path in PiperBackend.installed_model_paths()
    rows = {r["key"]: r for r in PiperBackend.catalog_voices()}
    assert rows[v.key]["installed"] == "1"
    assert rows[v.key]["path"] == path


def test_backend_use_model_adopts_downloaded_path(monkeypatch):
    v = piper_models.catalog()[0]
    fetcher = _fake_fetcher({v.onnx_url: b"w", v.config_url: b"{}"})
    path = PiperBackend.download_model(v.key, fetcher=fetcher)
    # Construct a backend without scanning global dirs, then adopt the model.
    monkeypatch.setattr("star.tts.piper._piper_voice_dirs", lambda: [])
    backend = PiperBackend()
    assert backend.use_model(path) is True
    assert backend._model == path
    assert backend.use_model("not-a-model.txt") is False
