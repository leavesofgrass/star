"""faster-whisper (CTranslate2) backend selection + offline model loading.

These test the pure logic added when star migrated dictation off
openai-whisper + Torch: bundled-model resolution and how ``_new_faster_model``
loads it.  faster-whisper itself is mocked, so the tests run with or without it
installed.
"""
import os
import sys

import star._runtime as r


def test_faster_whisper_model_dir_none_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert r._faster_whisper_model_dir() is None


def test_faster_whisper_model_dir_resolves_bundled(monkeypatch, tmp_path):
    (tmp_path / "faster_whisper_model").mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert r._faster_whisper_model_dir() == str(tmp_path / "faster_whisper_model")


def test_faster_whisper_model_dir_none_when_bundle_lacks_model(monkeypatch, tmp_path):
    # Frozen but lean (no model staged) → None → download-by-name path.
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert r._faster_whisper_model_dir() is None


def test_new_faster_model_uses_bundled_dir_offline(monkeypatch, tmp_path):
    """Frozen with a bundled model dir: load it with local_files_only + force
    HF offline, so no network is touched."""
    md = tmp_path / "faster_whisper_model"
    md.mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)

    captured = {}

    def fake_model(path, **kw):
        captured["path"] = path
        captured["kw"] = kw
        return "MODEL"

    monkeypatch.setattr(r, "_load_faster_whisper", lambda: fake_model)
    assert r._new_faster_model("base") == "MODEL"
    assert captured["path"] == str(md)
    assert captured["kw"]["local_files_only"] is True
    assert captured["kw"]["device"] == "cpu"
    assert captured["kw"]["compute_type"] == "int8"
    assert os.environ.get("HF_HUB_OFFLINE") == "1"


def test_new_faster_model_downloads_by_name_when_not_frozen(monkeypatch):
    """Source / pip install (no bundle): pass the model NAME and don't force
    local-only, so faster-whisper downloads/caches it as usual."""
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    captured = {}

    def fake_model(path, **kw):
        captured["path"] = path
        captured["kw"] = kw
        return "M"

    monkeypatch.setattr(r, "_load_faster_whisper", lambda: fake_model)
    r._new_faster_model("base")
    assert captured["path"] == "base"
    assert "local_files_only" not in captured["kw"]


def test_new_faster_model_compute_override(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setenv("STAR_WHISPER_COMPUTE", "float32")
    captured = {}
    monkeypatch.setattr(
        r, "_load_faster_whisper",
        lambda: lambda p, **kw: captured.update(kw=kw) or "M",
    )
    r._new_faster_model("base")
    assert captured["kw"]["compute_type"] == "float32"
