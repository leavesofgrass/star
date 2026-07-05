"""Tests for the opt-in cloud TTS backends (:mod:`star.tts.cloud`).

No real network and no credentials are ever used: the ``urllib`` layer is
monkeypatched so the request that *would* be sent can be inspected in-process.
These tests pin the parts of the cloud abstraction that must not regress:

* **key-gating** — ``available()`` is True iff a key is configured, and no
  network probe happens just because the backend exists;
* **request construction** — the ElevenLabs POST uses the right URL, the
  ``xi-api-key`` header carries the key, and the JSON body carries the text;
* **voice-list parsing** — ``/v1/voices`` JSON maps to star's voice dicts, and
  an absent key yields ``[]`` with no request;
* **recoverable fallback** — a network error raises :class:`CloudTTSError` (the
  signal ``TTSManager`` catches), never a bare/opaque exception;
* the pure **timing-divergence** benchmark helper.
"""
import io
import json
import urllib.error

import pytest

from star.tts.cloud import (
    CloudBackend,
    CloudTTSError,
    ElevenLabsBackend,
    MockCloudBackend,
    timing_divergence,
)
from star.tts.cloud import base as cloud_base


@pytest.fixture(autouse=True)
def _no_ambient_keys(monkeypatch):
    """Ensure no ambient API-key env var makes a "no key" test pass by accident."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("MOCKCLOUD_API_KEY", raising=False)


# ── fake urllib plumbing ─────────────────────────────────────────────────────


class _FakeResponse(io.BytesIO):
    """A context-manager BytesIO standing in for an http.client response."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _install_capture(monkeypatch, *, body=b"AUDIODATA", json_body=None):
    """Patch urllib.request.urlopen (as seen by base.py) to capture the request.

    Returns a dict that, after a call, holds the Request's ``url``, ``headers``,
    ``data`` (decoded body), and ``method``.
    """
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["method"] = req.get_method()
        captured["timeout"] = timeout
        raw = req.data
        captured["data"] = raw.decode("utf-8") if raw else None
        if json_body is not None:
            return _FakeResponse(json.dumps(json_body).encode("utf-8"))
        return _FakeResponse(body)

    monkeypatch.setattr(cloud_base.urllib.request, "urlopen", fake_urlopen)
    return captured


# ============================================================================
# key-gating / available()
# ============================================================================


def test_available_false_without_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    b = ElevenLabsBackend()
    assert b.available() is False


def test_available_true_with_explicit_key():
    b = ElevenLabsBackend(api_key="secret-key")
    assert b.available() is True


def test_available_does_not_touch_network(monkeypatch):
    # Any urlopen call during available() would blow up here.
    def boom(*a, **k):
        raise AssertionError("available() must not make a network request")

    monkeypatch.setattr(cloud_base.urllib.request, "urlopen", boom)
    assert ElevenLabsBackend(api_key="k").available() is True
    assert ElevenLabsBackend().available() is False


def test_key_read_from_env(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    b = ElevenLabsBackend()
    assert b.available() is False
    monkeypatch.setenv("ELEVENLABS_API_KEY", "env-key")
    assert b.available() is True


def test_cloud_priority_is_high_enough_to_never_auto_select():
    # Cloud must sort *after* every local engine so `auto` never reaches it.
    assert ElevenLabsBackend.priority >= 95
    assert MockCloudBackend.priority >= 95


def test_elevenlabs_inherits_cloud_priority_last():
    """ElevenLabs must not override the base cloud priority: it inherits
    CLOUD_PRIORITY (900) so it sorts *last*, honouring the documented
    "cloud auto-selects never" invariant (no stray low override)."""
    from star.tts.cloud.base import CLOUD_PRIORITY

    assert ElevenLabsBackend.priority == CLOUD_PRIORITY == 900


# ============================================================================
# request construction
# ============================================================================


def test_synth_request_url_headers_and_body(monkeypatch):
    captured = _install_capture(monkeypatch, body=b"WAVBYTES")
    b = ElevenLabsBackend(api_key="tok-123", voice="voiceXYZ")
    audio = b._synth_bytes("hello world", "tok-123")

    # pcm_16000 responses are HEADERLESS PCM: the backend must wrap them in a
    # real RIFF/WAV container (the raw payload survives inside verbatim).
    assert audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
    assert audio.endswith(b"WAVBYTES")
    assert captured["method"] == "POST"
    assert captured["url"].startswith(
        "https://api.elevenlabs.io/v1/text-to-speech/voiceXYZ"
    )
    # Header names are normalised (Title-Case) by urllib's Request.
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["xi-api-key"] == "tok-123"
    assert headers["accept"] == "audio/wav"
    body = json.loads(captured["data"])
    assert body["text"] == "hello world"
    assert "model_id" in body


def test_synth_uses_default_voice_when_unset(monkeypatch):
    captured = _install_capture(monkeypatch)
    b = ElevenLabsBackend(api_key="tok")
    b._synth_bytes("x", "tok")
    assert ElevenLabsBackend._DEFAULT_VOICE in captured["url"]


def test_export_to_wav_writes_returned_bytes(monkeypatch, tmp_path):
    _install_capture(monkeypatch, body=b"RIFFxxxx")
    dest = tmp_path / "out.wav"
    ElevenLabsBackend(api_key="tok").export_to_wav("hi", str(dest))
    assert dest.read_bytes() == b"RIFFxxxx"


def test_export_to_wav_without_key_raises(tmp_path):
    with pytest.raises(CloudTTSError):
        ElevenLabsBackend().export_to_wav("hi", str(tmp_path / "o.wav"))


# ============================================================================
# voice-list parsing
# ============================================================================


def test_list_voices_parses_provider_json(monkeypatch):
    payload = {
        "voices": [
            {"voice_id": "v1", "name": "Rachel", "labels": {"language": "en"}},
            {"voice_id": "v2", "name": "Diego"},
            {"name": "no-id-should-be-skipped"},
        ]
    }
    _install_capture(monkeypatch, json_body=payload)
    voices = ElevenLabsBackend(api_key="tok").list_voices()
    ids = [v["id"] for v in voices]
    assert ids == ["v1", "v2"]  # entry with no voice_id dropped
    assert voices[0] == {"id": "v1", "name": "Rachel", "lang": "en"}
    assert voices[1]["lang"] == ""  # missing labels → empty lang


def test_list_voices_empty_without_key(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("list_voices() must not call the network with no key")

    monkeypatch.setattr(cloud_base.urllib.request, "urlopen", boom)
    assert ElevenLabsBackend().list_voices() == []


def test_list_voices_network_failure_returns_empty(monkeypatch):
    def fail(*a, **k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(cloud_base.urllib.request, "urlopen", fail)
    assert ElevenLabsBackend(api_key="tok").list_voices() == []


# ============================================================================
# recoverable fallback on failure
# ============================================================================


def test_network_error_raises_recoverable(monkeypatch):
    def fail(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(cloud_base.urllib.request, "urlopen", fail)
    b = ElevenLabsBackend(api_key="tok")
    with pytest.raises(CloudTTSError):
        b._synth_bytes("hi", "tok")


def test_http_error_raises_recoverable_without_leaking_key(monkeypatch):
    def fail(*a, **k):
        raise urllib.error.HTTPError(
            url="https://api.elevenlabs.io",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"bad key"}'),
        )

    monkeypatch.setattr(cloud_base.urllib.request, "urlopen", fail)
    b = ElevenLabsBackend(api_key="super-secret")
    with pytest.raises(CloudTTSError) as exc:
        b._synth_bytes("hi", "super-secret")
    # The recoverable error must not embed the API key.
    assert "super-secret" not in str(exc.value)
    assert "401" in str(exc.value)


def test_speak_without_key_raises_for_manager_fallback():
    # The manager relies on this synchronous raise to fall back to a local engine.
    with pytest.raises(CloudTTSError):
        ElevenLabsBackend().speak("hello")


def test_empty_audio_response_raises(monkeypatch):
    _install_capture(monkeypatch, body=b"")
    with pytest.raises(CloudTTSError):
        ElevenLabsBackend(api_key="tok")._synth_bytes("hi", "tok")


# ============================================================================
# MockCloudBackend (the fake provider)
# ============================================================================


def test_mock_backend_gating_and_synth():
    assert MockCloudBackend().available() is False
    b = MockCloudBackend(api_key="k")
    assert b.available() is True
    audio = b._synth_bytes("hello", "k")
    assert audio[:4] == b"RIFF"  # a real WAV header
    assert b.synth_calls == ["hello"]


def test_mock_backend_failure_mode():
    b = MockCloudBackend(api_key="k", fail=True)
    with pytest.raises(CloudTTSError):
        b._synth_bytes("hello", "k")


def test_mock_backend_voice_list():
    assert MockCloudBackend().list_voices() == []
    voices = MockCloudBackend(api_key="k").list_voices()
    assert {v["id"] for v in voices} == {"mock-en", "mock-es"}


def test_mock_export_to_wav(tmp_path):
    dest = tmp_path / "m.wav"
    MockCloudBackend(api_key="k").export_to_wav("hi", str(dest))
    assert dest.read_bytes()[:4] == b"RIFF"


# ============================================================================
# CloudBackend is a proper TTSBackend subclass
# ============================================================================


def test_cloud_backend_is_tts_backend():
    from star.tts.base import TTSBackend

    assert issubclass(CloudBackend, TTSBackend)
    assert issubclass(ElevenLabsBackend, CloudBackend)


def test_setters_do_not_crash():
    b = ElevenLabsBackend(api_key="k")
    b.set_rate(300)
    b.set_volume(0.5)
    b.set_voice("newvoice")
    assert b._voice == "newvoice"
    assert b.speaking is False


# ============================================================================
# timing-divergence benchmark helper
# ============================================================================


def test_timing_divergence_identical_is_zero():
    r = timing_divergence([0.0, 1.0, 2.0], [0.0, 1.0, 2.0])
    assert r["compared"] == 3.0
    assert r["mean_abs"] == 0.0
    assert r["max_abs"] == 0.0
    assert r["rms"] == 0.0
    assert r["mean_signed"] == 0.0


def test_timing_divergence_known_values():
    # a is consistently 0.1s ahead of b (a - b = -0.1).
    a = [0.0, 1.0, 2.0]
    b = [0.1, 1.1, 2.1]
    r = timing_divergence(a, b)
    assert r["compared"] == 3.0
    assert r["mean_abs"] == pytest.approx(0.1)
    assert r["max_abs"] == pytest.approx(0.1)
    assert r["rms"] == pytest.approx(0.1)
    assert r["mean_signed"] == pytest.approx(-0.1)


def test_timing_divergence_unequal_lengths_uses_overlap():
    r = timing_divergence([0.0, 1.0, 2.0, 3.0], [0.0, 1.0])
    assert r["compared"] == 2.0


def test_timing_divergence_empty_is_safe():
    r = timing_divergence([], [])
    assert r == {
        "compared": 0.0,
        "mean_abs": 0.0,
        "max_abs": 0.0,
        "rms": 0.0,
        "mean_signed": 0.0,
    }
