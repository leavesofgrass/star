"""Direct unit tests for :mod:`star.tts`.

``tts.py`` is the largest module in the project (the multi-backend speech
engine) and had **zero** direct tests: it was only ever exercised incidentally
through higher-level code paths.  This module pins the parts that are pure and
deterministic — and therefore testable without a sound card or a real speech
engine:

* the timestamped-subtitle pipeline (``_build_subtitle_cues`` /
  ``_format_subtitles`` / ``_fmt_subtitle_time`` / ``_generate_subtitles``),
* the WAV helpers (``_wav_duration_seconds`` / ``_apply_wav_adjustments`` /
  ``_convert_audio_format``),
* backend-local logic that needs no native library: Piper model resolution,
  eSpeak chunking, Coqui's player command, DECtalk voice/markup mapping, and
* :class:`TTSManager` backend selection and default-voice resolution.

The real engine backends are **never constructed** here.  Several of them load
a native library or spin up a COM/SAPI engine in ``__init__`` (e.g.
``Pyttsx3Backend._probe`` creates a real engine), which is both non-deterministic
and unsafe under CI.  Selection tests substitute lightweight fakes so the
ordering contract is verified without touching any real engine.
"""
import struct
import sys
import wave

import pytest

from star import tts
from star.plugins import override_plugins
from star.settings import Settings


# ── helpers ─────────────────────────────────────────────────────────────────


def _write_wav(path, *, seconds=1.0, rate=8000, samples=None, sampwidth=2,
               nchannels=1):
    """Write a minimal mono PCM WAV and return its path (as ``str``)."""
    nframes = int(seconds * rate)
    if samples is None:
        samples = [0] * nframes
    if sampwidth == 2:
        frames = struct.pack(f"<{len(samples)}h", *samples)
    else:  # 8-bit unsigned
        frames = struct.pack(f"<{len(samples)}B", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(nchannels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(rate)
        wf.writeframes(frames)
    return str(path)


def _read_samples(path):
    with wave.open(str(path), "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(params.nframes)
    return list(struct.unpack(f"<{len(frames) // 2}h", frames))


# ============================================================================
# _fmt_subtitle_time
# ============================================================================


def test_fmt_subtitle_time_srt_uses_comma():
    assert tts._fmt_subtitle_time(0.0) == "00:00:00,000"


def test_fmt_subtitle_time_vtt_uses_dot():
    assert tts._fmt_subtitle_time(1.5, vtt=True) == "00:00:01.500"


def test_fmt_subtitle_time_hours_minutes_seconds():
    # 1h 1m 1.25s
    assert tts._fmt_subtitle_time(3661.25) == "01:01:01,250"


def test_fmt_subtitle_time_clamps_negative_to_zero():
    assert tts._fmt_subtitle_time(-5.0) == "00:00:00,000"


# ============================================================================
# _wav_duration_seconds
# ============================================================================


def test_wav_duration_seconds_reads_real_file(tmp_path):
    p = _write_wav(tmp_path / "a.wav", seconds=2.0, rate=8000)
    assert tts._wav_duration_seconds(p) == pytest.approx(2.0)


def test_wav_duration_seconds_missing_file_returns_zero(tmp_path):
    assert tts._wav_duration_seconds(str(tmp_path / "nope.wav")) == 0.0


def test_wav_duration_seconds_non_wav_returns_zero(tmp_path):
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not a wav file")
    assert tts._wav_duration_seconds(str(junk)) == 0.0


# ============================================================================
# _apply_wav_adjustments
# ============================================================================


def test_apply_wav_adjustments_scales_amplitude(tmp_path):
    p = _write_wav(tmp_path / "s.wav", samples=[100, -200, 300, -400])
    tts._apply_wav_adjustments(p, 0.5)
    assert _read_samples(p) == [50, -100, 150, -200]


def test_apply_wav_adjustments_clamps_to_int16_range(tmp_path):
    p = _write_wav(tmp_path / "s.wav", samples=[20000, -20000])
    tts._apply_wav_adjustments(p, 4.0)  # would overflow int16
    assert _read_samples(p) == [32767, -32768]


def test_apply_wav_adjustments_volume_one_is_identity(tmp_path):
    p = _write_wav(tmp_path / "s.wav", samples=[1, 2, 3, -3, -2, -1])
    tts._apply_wav_adjustments(p, 1.0)
    assert _read_samples(p) == [1, 2, 3, -3, -2, -1]


def test_apply_wav_adjustments_ignores_non_16bit(tmp_path):
    # 8-bit PCM is left untouched (the function only scales 16-bit).
    p = _write_wav(tmp_path / "s8.wav", samples=[10, 20, 30], sampwidth=1)
    tts._apply_wav_adjustments(p, 0.5)
    with wave.open(p, "rb") as wf:
        assert wf.getsampwidth() == 1
        assert list(wf.readframes(wf.getnframes())) == [10, 20, 30]


# ============================================================================
# _build_subtitle_cues
# ============================================================================


def test_build_subtitle_cues_empty_text():
    assert tts._build_subtitle_cues("", 10.0) == []


def test_build_subtitle_cues_zero_duration():
    assert tts._build_subtitle_cues("hello world", 0.0) == []


def test_build_subtitle_cues_word_level_one_cue_per_token():
    cues = tts._build_subtitle_cues("alpha beta gamma", 9.0, word_level=True)
    assert [c[2] for c in cues] == ["alpha", "beta", "gamma"]


def test_build_subtitle_cues_times_monotonic_and_span_duration():
    cues = tts._build_subtitle_cues("one two three four", 12.0, word_level=True)
    starts = [c[0] for c in cues]
    ends = [c[1] for c in cues]
    assert starts == sorted(starts)
    assert cues[0][0] == pytest.approx(0.0)
    assert ends[-1] == pytest.approx(12.0)
    # each cue ends no later than the next one starts
    for i in range(len(cues) - 1):
        assert ends[i] == pytest.approx(starts[i + 1])


def test_build_subtitle_cues_breaks_at_sentence_boundary():
    cues = tts._build_subtitle_cues("Hello world. Goodbye now.", 10.0)
    assert [c[2] for c in cues] == ["Hello world.", "Goodbye now."]


def test_build_subtitle_cues_respects_max_words():
    text = " ".join(f"w{i}" for i in range(30))
    cues = tts._build_subtitle_cues(text, 30.0, max_words=5)
    # every caption line is at most max_words tokens
    assert all(len(c[2].split()) <= 5 for c in cues)
    # all words are accounted for, in order
    assert " ".join(c[2] for c in cues) == text


# ============================================================================
# _format_subtitles
# ============================================================================


def test_format_subtitles_srt_structure():
    out = tts._format_subtitles([(0.0, 1.0, "hi"), (1.0, 2.0, "there")], "srt")
    lines = out.strip().splitlines()
    assert lines[0] == "1"
    assert "-->" in lines[1] and "," in lines[1]
    assert lines[2] == "hi"
    assert "2" in lines
    assert out.endswith("\n")


def test_format_subtitles_vtt_header_and_dot_separator():
    out = tts._format_subtitles([(0.0, 1.0, "hi")], "vtt")
    assert out.startswith("WEBVTT")
    assert "." in out.splitlines()[2]  # timestamp line uses a dot
    # VTT cues are not numbered
    assert "\n1\n" not in out


def test_format_subtitles_nudges_zero_length_cue():
    # end <= start must be pushed out so players accept the cue.
    out = tts._format_subtitles([(5.0, 5.0, "x")], "srt")
    assert "00:00:05,000 --> 00:00:05,050" in out


# ============================================================================
# _generate_subtitles
# ============================================================================


def test_generate_subtitles_produces_srt(tmp_path):
    wav = _write_wav(tmp_path / "g.wav", seconds=3.0)
    out = tts._generate_subtitles("Hello world. Goodbye now.", wav, "srt")
    assert "-->" in out
    assert "Hello world." in out


def test_generate_subtitles_empty_text_returns_empty(tmp_path):
    wav = _write_wav(tmp_path / "g.wav", seconds=3.0)
    assert tts._generate_subtitles("", wav, "srt") == ""


def test_generate_subtitles_no_duration_returns_empty(tmp_path):
    # A missing WAV gives 0.0 duration, so no cues can be timed.
    assert tts._generate_subtitles("hi there", str(tmp_path / "x.wav")) == ""


# ============================================================================
# ESpeakLibBackend._chunk_offsets  (static; no library needed)
# ============================================================================


def test_chunk_offsets_offsets_point_into_source():
    text = "First sentence. Second sentence! Third?"
    chunks = tts.ESpeakLibBackend._chunk_offsets(text)
    for chunk, off in chunks:
        assert text[off:off + len(chunk)] == chunk


def test_chunk_offsets_splits_overlong_sentence_at_whitespace():
    text = "word " * 50  # 250 chars, one "sentence", no terminal punctuation
    chunks = tts.ESpeakLibBackend._chunk_offsets(text.strip(), max_len=40)
    assert len(chunks) > 1
    assert all(len(c) <= 40 for c, _ in chunks)


def test_chunk_offsets_empty_text_falls_back():
    assert tts.ESpeakLibBackend._chunk_offsets("") == [("", 0)]


def test_chunk_offsets_concatenation_preserves_visible_text():
    text = "Alpha beta. Gamma delta epsilon."
    chunks = tts.ESpeakLibBackend._chunk_offsets(text)
    # joining the chunks reconstructs the non-whitespace content in order
    assert "".join(c for c, _ in chunks).split() == text.split()


# ============================================================================
# PiperBackend model resolution
# ============================================================================


def test_resolve_model_accepts_existing_onnx(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"x")
    assert tts.PiperBackend._resolve_model(str(model)) == str(model)


def test_resolve_model_ignores_non_onnx_voice(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    monkeypatch.setattr(tts.piper, "_piper_voice_dirs", lambda: [])
    assert tts.PiperBackend._resolve_model("not-a-model.txt") == ""


def test_resolve_model_uses_piper_model_env(tmp_path, monkeypatch):
    model = tmp_path / "env.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("PIPER_MODEL", str(model))
    assert tts.PiperBackend._resolve_model("") == str(model)


def test_resolve_model_scans_voice_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    (tmp_path / "found.onnx").write_bytes(b"x")
    monkeypatch.setattr(tts.piper, "_piper_voice_dirs", lambda: [tmp_path])
    assert tts.PiperBackend._resolve_model("") == str(tmp_path / "found.onnx")


def test_resolve_model_returns_empty_when_nothing_found(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    monkeypatch.setattr(tts.piper, "_piper_voice_dirs", lambda: [tmp_path])
    assert tts.PiperBackend._resolve_model("") == ""


def test_piper_voice_dirs_includes_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PIPER_VOICE_DIR", str(tmp_path))
    dirs = tts._piper_voice_dirs()
    assert tmp_path in dirs
    # the env override is searched first
    assert dirs[0] == tmp_path


def test_piper_length_scale_clamped(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    monkeypatch.setattr(tts.piper, "_piper_voice_dirs", lambda: [])
    assert tts.PiperBackend(rate=265)._length_scale() == pytest.approx(1.0)
    assert tts.PiperBackend(rate=10_000)._length_scale() == pytest.approx(0.4)
    assert tts.PiperBackend(rate=1)._length_scale() == pytest.approx(2.5)


def test_piper_config_for_finds_sidecar(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    monkeypatch.setattr(tts.piper, "_piper_voice_dirs", lambda: [])
    model = tmp_path / "v.onnx"
    model.write_bytes(b"x")
    backend = tts.PiperBackend()
    assert backend._config_for(str(model)) is None
    (tmp_path / "v.onnx.json").write_text("{}")
    assert backend._config_for(str(model)) == str(model) + ".json"


# ============================================================================
# CoquiBackend._player_cmd  (static, platform-dependent)
# ============================================================================


def test_player_cmd_windows(monkeypatch):
    monkeypatch.setattr(tts.sys, "platform", "win32")
    cmd = tts.CoquiBackend._player_cmd("C:\\tmp\\a.wav")
    assert cmd[0] == "powershell"
    assert any("a.wav" in part for part in cmd)


def test_player_cmd_macos(monkeypatch):
    monkeypatch.setattr(tts.sys, "platform", "darwin")
    assert tts.CoquiBackend._player_cmd("/tmp/a.wav") == ["afplay", "/tmp/a.wav"]


def test_player_cmd_linux_prefers_available_player(monkeypatch):
    monkeypatch.setattr(tts.sys, "platform", "linux")
    monkeypatch.setattr(tts.shutil, "which", lambda p: "/usr/bin/aplay" if p == "aplay" else None)
    assert tts.CoquiBackend._player_cmd("/tmp/a.wav") == ["aplay", "/tmp/a.wav"]


def test_player_cmd_linux_ffplay_gets_flags(monkeypatch):
    monkeypatch.setattr(tts.sys, "platform", "linux")
    monkeypatch.setattr(tts.shutil, "which", lambda p: "/usr/bin/ffplay" if p == "ffplay" else None)
    assert tts.CoquiBackend._player_cmd("/tmp/a.wav") == [
        "ffplay", "-nodisp", "-autoexit", "/tmp/a.wav"
    ]


def test_player_cmd_linux_none_when_no_player(monkeypatch):
    monkeypatch.setattr(tts.sys, "platform", "linux")
    monkeypatch.setattr(tts.shutil, "which", lambda p: None)
    assert tts.CoquiBackend._player_cmd("/tmp/a.wav") is None


# ============================================================================
# DECtalkDLLBackend voice + markup mapping  (no DLL loaded)
# ============================================================================


@pytest.fixture
def dectalk(monkeypatch):
    # __init__ would otherwise try to load DECtalk.dll; neutralise it so the
    # pure name/markup logic can be tested with no native dependency.
    monkeypatch.setattr(tts.DECtalkDLLBackend, "_load_library", classmethod(lambda cls: None))
    return tts.DECtalkDLLBackend


def test_voice_letter_known_names(dectalk):
    assert dectalk(voice="Paul")._voice_letter() == "p"
    assert dectalk(voice="Betty")._voice_letter() == "b"
    assert dectalk(voice="Harry")._voice_letter() == "h"


def test_voice_letter_accepts_single_letter_code(dectalk):
    assert dectalk(voice="h")._voice_letter() == "h"


def test_voice_letter_unknown_falls_back_to_paul(dectalk):
    assert dectalk(voice="SAPI_SomeRandomVoice")._voice_letter() == "p"
    # empty voice is normalised to Paul in __init__
    assert dectalk(voice="")._voice_letter() == "p"


def test_markup_embeds_voice_and_rate(dectalk):
    assert dectalk(rate=200, voice="Betty")._markup("Hello") == b"[:nb][:rate 200]Hello"


def test_markup_clamps_rate(dectalk):
    assert dectalk(rate=5, voice="Paul")._markup("x") == b"[:np][:rate 75]x"
    assert dectalk(rate=9999, voice="Paul")._markup("x") == b"[:np][:rate 650]x"


def test_dectalk_list_voices_has_nine(dectalk):
    voices = dectalk(voice="Paul").list_voices()
    assert len(voices) == 9
    assert all({"id", "name", "lang"} <= set(v) for v in voices)


# ============================================================================
# _convert_audio_format
# ============================================================================


def test_convert_audio_format_wav_is_copy(tmp_path):
    src = _write_wav(tmp_path / "in.wav", samples=[1, 2, 3])
    dest = tmp_path / "out.wav"
    tts._convert_audio_format(src, str(dest))
    assert dest.exists()
    assert dest.read_bytes() == (tmp_path / "in.wav").read_bytes()


def test_convert_audio_format_no_tool_raises(tmp_path, monkeypatch):
    src = _write_wav(tmp_path / "in.wav")
    # No ffmpeg (bundled or on PATH) and no importable pydub.
    monkeypatch.setattr(tts.shutil, "which", lambda _name: None)
    monkeypatch.setattr(tts.audio, "_FFMPEG_BUNDLED", tmp_path / "nonexistent-ffmpeg")
    monkeypatch.setitem(sys.modules, "pydub", None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        tts._convert_audio_format(src, str(tmp_path / "out.mp3"))


def test_convert_audio_format_uses_ffmpeg(tmp_path, monkeypatch):
    src = _write_wav(tmp_path / "in.wav")
    dest = tmp_path / "out.mp3"
    monkeypatch.setattr(tts.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(tts.audio, "_FFMPEG_BUNDLED", tmp_path / "nonexistent")
    calls = {}

    class _Result:
        returncode = 0
        stderr = b""

    def _fake_run(cmd, *a, **k):
        calls["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(tts.subprocess, "run", _fake_run)
    tts._convert_audio_format(src, str(dest))
    assert calls["cmd"][0] == "/usr/bin/ffmpeg"
    assert str(dest) == calls["cmd"][-1]
    assert "libmp3lame" in calls["cmd"]


def test_convert_audio_format_ffmpeg_failure_raises(tmp_path, monkeypatch):
    src = _write_wav(tmp_path / "in.wav")
    monkeypatch.setattr(tts.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(tts.audio, "_FFMPEG_BUNDLED", tmp_path / "nonexistent")

    class _Result:
        returncode = 1
        stderr = b"boom"

    monkeypatch.setattr(tts.subprocess, "run", lambda *a, **k: _Result())
    with pytest.raises(RuntimeError, match="ffmpeg conversion failed"):
        tts._convert_audio_format(src, str(tmp_path / "out.ogg"))


# ============================================================================
# Base contract: TTSBackend / SilentBackend
# ============================================================================


class _MinimalBackend(tts.TTSBackend):
    """Concrete backend implementing only the three required abstract methods,
    so the base class's optional no-op defaults can be exercised now that
    TTSBackend itself is an ABC and can no longer be instantiated."""

    name = "minimal"

    def available(self):
        return False

    def speak(self, text, on_word=None, on_done=None):
        if on_done:
            on_done()

    def stop(self):
        pass


def test_base_backend_is_abstract():
    # available/speak/stop are abstract — the bare base cannot be instantiated.
    with pytest.raises(TypeError):
        tts.TTSBackend()


def test_base_backend_optional_defaults_are_inert():
    b = _MinimalBackend()
    assert b.available() is False
    assert b.speaking is False
    assert b.list_voices() == []
    # no-op setters never raise
    b.set_rate(100)
    b.set_volume(0.5)
    b.set_voice("x")
    b.stop()


def test_silent_backend_speak_calls_on_done():
    done = []
    tts.SilentBackend().speak("hi", on_done=lambda: done.append(True))
    assert done == [True]


def test_base_backend_export_raises():
    with pytest.raises(RuntimeError, match="does not support audio file export"):
        _MinimalBackend().export_to_wav("hi", "out.wav")


def test_silent_backend_is_available():
    b = tts.SilentBackend()
    assert b.available() is True
    assert b.name == "silent"


# ============================================================================
# TTSManager — backend selection (with fake backends, no real engines)
# ============================================================================


def _fake_backend_cls(real_name, public_name, priority):
    """Build a lightweight stand-in for a real backend class.

    Availability is read from the class attribute ``_avail`` so a test can flip
    a single backend on/off without constructing any real engine.  ``priority``
    mirrors the real built-in so registry ordering — and thus auto-selection —
    matches production.
    """

    class _Fake(tts.TTSBackend):
        name = public_name
        _avail = False

        def __init__(self, *args, **kwargs):
            self.init_args = args
            self.init_kwargs = kwargs
            self.rate = self.volume = self.voice_set = None

        def available(self):
            return type(self)._avail

        def speak(self, text, on_word=None, on_done=None):
            if on_done:
                on_done()

        def stop(self):
            pass

        def set_rate(self, wpm):
            self.rate = wpm

        def set_volume(self, vol):
            self.volume = vol

        def set_voice(self, voice_id):
            self.voice_set = voice_id

        def list_voices(self):
            return []

    _Fake.__name__ = real_name
    _Fake.priority = priority
    return _Fake


# (real class attribute on tts → (public .name, priority)) for every backend
# selection may construct.  ESpeakLib/ESpeak share name "espeak"; the two DECtalk
# share "dectalk" — that mirrors the real module, where priority decides which
# implementation of a shared-name engine is tried first.
_BACKENDS = {
    "DECtalkDLLBackend": ("dectalk", 10),
    "Pyttsx3Backend": ("pyttsx3", 20),
    "AppleSayBackend": ("applesay", 30),
    "ESpeakLibBackend": ("espeak", 40),
    "ESpeakBackend": ("espeak", 50),
    "FestivalBackend": ("festival", 60),
    "DECtalkBackend": ("dectalk", 70),
    "PiperBackend": ("piper", 100),
    "CoquiBackend": ("coqui", 110),
}


@pytest.fixture
def fake_backends():
    """Replace every selectable backend with a controllable fake.

    Injects the fakes through the plugin registry (``override_plugins``) — the
    same path TTSManager now uses for discovery — so no real engine is ever
    constructed.  Returns the mapping ``{class_name: fake_class}`` so a test can
    mark one available via ``fakes["FestivalBackend"]._avail = True``.
    """
    fakes = {
        real_name: _fake_backend_cls(real_name, public, prio)
        for real_name, (public, prio) in _BACKENDS.items()
    }
    with override_plugins(backends=list(fakes.values())):
        yield fakes


def _manager(preference):
    s = Settings()
    s["tts_backend"] = preference
    s["tts_prefer_voice"] = ""  # skip default-voice resolution noise
    return tts.TTSManager(s)


def test_manager_all_unavailable_falls_back_to_silent(fake_backends):
    mgr = _manager("auto")
    assert mgr.backend_name == "silent"
    assert mgr.speaking is False
    assert mgr.current_word_idx == -1


def test_manager_auto_prefers_pyttsx3_when_available(fake_backends):
    fake_backends["Pyttsx3Backend"]._avail = True
    fake_backends["AppleSayBackend"]._avail = True
    assert _manager("auto").backend_name == "pyttsx3"


def test_manager_auto_dectalk_dll_outranks_pyttsx3(fake_backends):
    # In auto mode an available bundled DECtalk engine is inserted first.
    fake_backends["Pyttsx3Backend"]._avail = True
    fake_backends["DECtalkDLLBackend"]._avail = True
    assert _manager("auto").backend_name == "dectalk"


def test_manager_explicit_preference_selected(fake_backends):
    fake_backends["FestivalBackend"]._avail = True
    assert _manager("festival").backend_name == "festival"


def test_manager_silent_preference_is_silent(fake_backends):
    # No engine should even be probed for the "silent" preference.
    fake_backends["Pyttsx3Backend"]._avail = True
    assert _manager("silent").backend_name == "silent"


def test_manager_applies_rate_and_volume_to_selected_backend(fake_backends):
    fake_backends["FestivalBackend"]._avail = True
    s = Settings()
    s["tts_backend"] = "festival"
    s["tts_rate"] = 180
    s["tts_volume"] = 0.4
    s["tts_prefer_voice"] = ""
    mgr = tts.TTSManager(s)
    assert mgr._backend.rate == 180
    assert mgr._backend.volume == pytest.approx(0.4)


# ============================================================================
# TTSManager — word-map plumbing + default-voice resolution
# ============================================================================


def test_manager_setters(fake_backends):
    mgr = _manager("silent")
    sentinel = object()
    mgr.set_word_map([sentinel])
    assert mgr._word_map == [sentinel]

    def cb(_i=None):
        return None

    mgr.set_on_highlight(cb)
    mgr.set_on_done(cb)
    assert mgr._on_highlight is cb and mgr._on_done is cb


class _VoiceBackend(tts.TTSBackend):
    """A fake backend that exposes a fixed voice list and records set_voice."""

    name = "voicy"

    def __init__(self, voices):
        self._voices = voices
        self.chosen = None

    def available(self):
        return True

    def speak(self, text, on_word=None, on_done=None):
        if on_done:
            on_done()

    def stop(self):
        pass

    def list_voices(self):
        return self._voices

    def set_voice(self, voice_id):
        self.chosen = voice_id


def _voice_manager(fake_backends, voices, **settings):
    mgr = _manager("silent")
    mgr._backend = _VoiceBackend(voices)
    for k, v in settings.items():
        mgr._settings[k] = v
    return mgr


def test_resolve_default_voice_picks_us_variant_of_preferred(fake_backends):
    voices = [
        {"id": "eloq-gb", "name": "Eloquence Reed", "lang": "en-GB"},
        {"id": "eloq-us", "name": "Eloquence Reed", "lang": "en-US"},
        {"id": "other", "name": "Robotic", "lang": "en-US"},
    ]
    mgr = _voice_manager(fake_backends, voices, tts_voice="",
                         tts_prefer_voice="eloquence")
    mgr._resolve_default_voice()
    assert mgr._backend.chosen == "eloq-us"


def test_resolve_default_voice_first_match_when_no_us(fake_backends):
    voices = [
        {"id": "eloq-gb", "name": "Eloquence Reed", "lang": "en-GB"},
        {"id": "eloq-au", "name": "Eloquence Reed", "lang": "en-AU"},
    ]
    mgr = _voice_manager(fake_backends, voices, tts_voice="",
                         tts_prefer_voice="eloquence")
    mgr._resolve_default_voice()
    assert mgr._backend.chosen == "eloq-gb"


def test_resolve_default_voice_respects_explicit_user_voice(fake_backends):
    voices = [{"id": "eloq-us", "name": "Eloquence", "lang": "en-US"}]
    mgr = _voice_manager(fake_backends, voices, tts_voice="my-chosen-voice",
                         tts_prefer_voice="eloquence")
    mgr._resolve_default_voice()
    assert mgr._backend.chosen is None  # never overridden


def test_resolve_default_voice_no_preference_is_noop(fake_backends):
    voices = [{"id": "eloq-us", "name": "Eloquence", "lang": "en-US"}]
    mgr = _voice_manager(fake_backends, voices, tts_voice="", tts_prefer_voice="")
    mgr._resolve_default_voice()
    assert mgr._backend.chosen is None


def test_resolve_default_voice_no_match_is_noop(fake_backends):
    voices = [{"id": "robo", "name": "Robotic", "lang": "en-US"}]
    mgr = _voice_manager(fake_backends, voices, tts_voice="",
                         tts_prefer_voice="eloquence")
    mgr._resolve_default_voice()
    assert mgr._backend.chosen is None


# ── 0.1.22 audit: export guards + ElevenLabs RIFF wrap ───────────────────────


def test_export_audio_rejects_empty_text(tmp_path):
    """Empty/whitespace text must fail with a clear message, not reach
    pyttsx3's bare `assert text` (which surfaced as 'Audio export error: ')."""
    from star.settings import Settings
    from star.tts import TTSManager

    mgr = TTSManager(Settings())
    with pytest.raises(ValueError, match="no readable text"):
        mgr.export_audio("   \n  ", str(tmp_path / "out.wav"))
    with pytest.raises(ValueError, match="no readable text"):
        mgr.export_subtitles("", str(tmp_path / "out.srt"))


def test_elevenlabs_riff_wraps_raw_pcm():
    """output_format=pcm_16000 returns HEADERLESS PCM — the backend must wrap
    it in a real RIFF/WAV container before playback or .wav export."""
    from star.tts.cloud.elevenlabs import ElevenLabsBackend

    raw = b"\x00\x01" * 800  # fake 16-bit PCM samples
    wrapped = ElevenLabsBackend._riff_wrap(raw, 16000)
    assert wrapped[:4] == b"RIFF" and wrapped[8:12] == b"WAVE"
    import io
    import wave

    with wave.open(io.BytesIO(wrapped)) as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.readframes(w.getnframes()) == raw
