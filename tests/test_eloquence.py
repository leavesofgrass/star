"""EloquenceBackend (OpenEVV/ECI) — discovery, consent gate, WPM curve, rules.

Everything here runs WITHOUT the engine: the ctypes layer is exercised only
on a real Windows machine with OpenEVV present (it was, end to end, on
2026-09-25 — 13/13 word events at exact playback offsets).  These tests pin
the pure logic and the two measured OpenEVV quirk rules the module encodes:
the sample rate is query-only, and the callback never answers abort.
"""
import io
import zipfile

import pytest

import star.tts.eloquence as elo
from star.tts.eloquence import (
    EloquenceBackend,
    _speed_for_wpm,
    _split_words,
    _wav_bytes,
    find_eci_library,
    install_openevv,
)


class _Settings(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


# ── discovery ────────────────────────────────────────────────────────────────


def test_env_override_wins_and_must_exist(monkeypatch, tmp_path):
    dll = tmp_path / "eci.dll"
    dll.write_bytes(b"x")
    monkeypatch.setenv("STAR_ECI_LIBRARY", str(dll))
    assert find_eci_library() == str(dll)
    monkeypatch.setenv("STAR_ECI_LIBRARY", str(tmp_path / "missing.dll"))
    assert find_eci_library() is None  # explicit-but-wrong never falls through


def test_star_install_dir_probed_first(monkeypatch, tmp_path):
    monkeypatch.delenv("STAR_ECI_LIBRARY", raising=False)
    monkeypatch.setattr(elo, "ELOQUENCE_DIR", tmp_path)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "nope"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "nope"))
    assert find_eci_library() is None
    target = tmp_path / "eci-x86_64" / "eci.dll"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    assert find_eci_library() == str(target)


def test_available_is_windows_only(monkeypatch, tmp_path):
    dll = tmp_path / "eci.dll"
    dll.write_bytes(b"x")
    monkeypatch.setenv("STAR_ECI_LIBRARY", str(dll))
    monkeypatch.setattr(elo.sys, "platform", "linux")
    assert EloquenceBackend.available() is False
    monkeypatch.setattr(elo.sys, "platform", "win32")
    assert EloquenceBackend.available() is True


# ── consent gate ─────────────────────────────────────────────────────────────


def _fake_zip() -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("eci-x86_64/eci.dll", b"fake engine")
        z.writestr("eci-x86_64/eci.ini", b"[eci]")
        z.writestr("eci-x86/eci.dll", b"32-bit, not wanted")
        z.writestr("evv.exe", b"not wanted")
        z.writestr("LICENSE", b"license text")
        z.writestr("NOTICE", b"notice text")
    return bio.getvalue()


def test_install_refuses_without_acknowledgment(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: called.append(a) or (_ for _ in ()).throw(AssertionError),
    )
    s = _Settings()
    assert install_openevv(s, acknowledged=False) is None
    assert called == []  # the network was never touched
    assert "eloquence_license_ack" not in s


def test_install_respects_global_autoinstall_optout(monkeypatch):
    monkeypatch.setenv("STAR_NO_AUTOINSTALL", "1")
    assert install_openevv(_Settings(), acknowledged=True) is None


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_install_downloads_extracts_and_records_ack(monkeypatch, tmp_path):
    monkeypatch.delenv("STAR_NO_AUTOINSTALL", raising=False)
    monkeypatch.setattr(elo, "ELOQUENCE_DIR", tmp_path)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda url, timeout=0: _Resp(_fake_zip())
    )
    s = _Settings()
    path = install_openevv(s, acknowledged=True)
    assert path == str(tmp_path / "eci-x86_64" / "eci.dll")
    assert s["eloquence_license_ack"] is True
    # Only the 64-bit payload + provenance files; never the exes or x86.
    extracted = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    assert extracted == ["LICENSE", "NOTICE", "eci.dll", "eci.ini"]


# ── WPM curve (TextWeaver's measured calibration) ────────────────────────────


def test_speed_curve_endpoints_and_default():
    assert _speed_for_wpm(30) == 0  # below the floor clamps to speed 0
    assert _speed_for_wpm(158) == 50  # the engine default
    assert _speed_for_wpm(5000) == 200  # above the ceiling clamps
    assert _speed_for_wpm("nonsense") == 50


def test_speed_curve_star_default_matches_measurement():
    # star's default 265 wpm sits between the (75, 256) and (80, 287) points.
    assert _speed_for_wpm(265) in (76, 77)


def test_speed_curve_is_monotonic():
    speeds = [_speed_for_wpm(w) for w in range(58, 1200, 25)]
    assert speeds == sorted(speeds)


# ── word splitting + WAV framing ─────────────────────────────────────────────


def test_split_words_offsets_slice_the_source():
    text = "Star  speaks   with Eloquence."
    for w, off in _split_words(text):
        assert text[off : off + len(w)] == w


def test_wav_bytes_carries_rate_and_pcm():
    import wave

    data = _wav_bytes(b"\x00\x01" * 100, 11025)
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == 11025
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 100


# ── engine text encoding (the em-dash bug) ───────────────────────────────────


def test_em_dash_is_one_cp1252_byte_not_utf8():
    """First live bug report: fed UTF-8, an em-dash (E2 80 94 read as
    cp1252) was spoken as "a-circumflex, euro."  The engine must receive
    cp1252, where the em-dash is a single native byte."""
    out = elo._encode_for_engine("reads—like this")
    assert out == b"reads\x97like this"
    assert b"\xe2\x80" not in out  # no UTF-8 multi-byte sequences, ever


def test_common_typography_survives_in_cp1252():
    cases = {
        "‘quoted’": b"\x91quoted\x92",  # curly single quotes
        "“quoted”": b"\x93quoted\x94",  # curly double quotes
        "wait…": b"wait\x85",  # ellipsis
        "–range": b"\x96range",  # en dash
        "café": b"caf\xe9",  # Latin-1 letters pass through
    }
    for text, expected in cases.items():
        assert elo._encode_for_engine(text) == expected


def test_unmappable_characters_never_raise():
    out = elo._encode_for_engine("arrow → and CJK 日")
    assert isinstance(out, bytes) and b"arrow" in out
    for text in ("", " ", "—", "plain"):
        assert isinstance(elo._encode_for_engine(text), bytes)


def test_fallback_encoder_used_without_win32(monkeypatch):
    monkeypatch.setattr(elo, "_WIDE_CHAR_TO_MULTI_BYTE", None)
    assert elo._encode_for_engine("reads—like") == b"reads\x97like"


# ── the measured OpenEVV quirk rules stay encoded ────────────────────────────


def test_sample_rate_is_query_only_in_source():
    """eciSetParam(eciSampleRate, …) wedges OpenEVV (measured 2026-09-25):
    the module must never call it — parameter 5 is read with eciGetParam
    only.  This is a source-level tripwire for a rule no runtime test can
    check without the engine."""
    import inspect

    src = inspect.getsource(elo)
    assert "QUERY-ONLY" in src
    for line in src.splitlines():
        # A call site looks like `…lib.eciSetParam(h, …` — prose mentions in
        # docstrings/comments and the argtypes declaration are fine.
        if "lib.eciSetParam(" in line and "argtypes" not in line:
            pytest.fail(
                f"eciSetParam call found — sample rate is query-only: {line.strip()}"
            )


def test_callback_never_answers_abort():
    """Answering eciDataAbort (2) hangs eciSynchronize forever
    (openevv-bugs/repro_abort_hang.py); interruption must use eciStop."""
    import inspect

    src = inspect.getsource(elo._EciEngine._on_message)
    assert "return _DATA_PROCESSED" in src
    assert elo._DATA_PROCESSED == 1


# ── voice presets (probed against OpenEVV 2026-09-26) ────────────────────────


def test_preset_table_is_the_classic_eight():
    slugs = [s for s, _p, _n in elo._PRESET_VOICES]
    presets = [p for _s, p, _n in elo._PRESET_VOICES]
    assert presets == list(range(1, 9))
    assert len(set(slugs)) == 8
    assert slugs[0] == "reed"  # preset 1 stays the default voicing


def test_preset_for_voice_id_accepts_slug_name_and_number():
    assert elo._preset_for_voice_id("shelley") == 2
    assert elo._preset_for_voice_id("Shelley") == 2  # display name, any case
    assert elo._preset_for_voice_id("2") == 2
    assert elo._preset_for_voice_id(" grandpa ") == 8
    assert elo._preset_for_voice_id("") is None
    assert elo._preset_for_voice_id("nonsense") is None


def test_list_voices_offers_every_preset(monkeypatch, tmp_path):
    dll = tmp_path / "eci.dll"
    dll.write_bytes(b"x")
    monkeypatch.setenv("STAR_ECI_LIBRARY", str(dll))
    monkeypatch.setattr(elo.sys, "platform", "win32")
    voices = EloquenceBackend().list_voices()
    assert [v["id"] for v in voices] == [s for s, _p, _n in elo._PRESET_VOICES]
    assert all(v["name"].endswith("(Eloquence)") for v in voices)


def test_speed_is_reapplied_after_preset_copy_in_source():
    """eciCopyVoice replaces EVERY setting of the working voice (measured;
    the NVDA driver re-reads its sliders for the same reason), so speak()
    must order the preset copy before set_speed/set_volume."""
    import inspect

    src = inspect.getsource(elo.EloquenceBackend.speak)
    assert src.index("load_preset") < src.index("set_speed")
    assert src.index("load_preset") < src.index("set_volume")


# ── the TUI consent flow (mirrors the GUI's engine-picker gate) ──────────────


class _FakeTTS:
    def __init__(self):
        self.changed: "list[str]" = []
        self.backend_name = "pyttsx3"

    def change_backend(self, name):
        self.changed.append(name)
        self.backend_name = name


def _make_tui_app():
    """Compose the real VoiceMixin onto a tiny fake app (the
    tests/test_tui_mixins.py pattern): only what the flow touches."""
    import queue

    from star.tui.mixin_voice import VoiceMixin

    class _App(VoiceMixin):
        def __init__(self):
            self.tts = _FakeTTS()
            self.settings = _Settings()
            self.notices: "list[str]" = []
            self.pager_shown: "list[str]" = []
            self.confirm_answer = True
            self._bg_queue = queue.Queue()

        def notify(self, msg, error=False, dur=None):
            self.notices.append(msg)

        def _show_text_pager(self, title, markdown):
            self.pager_shown.append(markdown)

        def _inline_confirm(self, prompt):
            return self.confirm_answer

    return _App()


@pytest.fixture
def _win32_voice_mixin(monkeypatch):
    import star.tui.mixin_voice as mv

    monkeypatch.setattr(mv.sys, "platform", "win32")
    return mv


def test_tui_switch_offers_install_when_engine_missing(
    monkeypatch, _win32_voice_mixin
):
    monkeypatch.setattr(elo, "find_eci_library", lambda: None)
    app = _make_tui_app()
    offered = []
    app._offer_eloquence_install = lambda: offered.append(True)
    app._change_backend_command("eloquence")
    assert offered == [True]
    assert app.tts.changed == []  # never switched to a missing engine


def test_tui_switch_passes_through_when_installed(monkeypatch, _win32_voice_mixin):
    monkeypatch.setattr(elo, "find_eci_library", lambda: "C:/x/eci.dll")
    app = _make_tui_app()
    app._change_backend_command("Eloquence")
    assert app.tts.changed == ["eloquence"]


def test_tui_consent_decline_downloads_nothing(monkeypatch, _win32_voice_mixin):
    monkeypatch.setattr(
        elo, "install_openevv",
        lambda *a, **k: pytest.fail("declined consent must not download"),
    )
    app = _make_tui_app()
    app.confirm_answer = False
    app._offer_eloquence_install()
    # The pager carried the licensing text verbatim, formatted.
    assert elo.OPENEVV_VERSION in app.pager_shown[0]
    assert "cannot" in app.pager_shown[0]  # the unlicensable-data sentence
    assert any("not installed" in n for n in app.notices)


def test_tui_consent_accept_downloads_and_switches(monkeypatch, _win32_voice_mixin):
    mv = _win32_voice_mixin

    class _SyncThread:
        def __init__(self, target=None, daemon=None, name=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(
        mv, "threading", type("T", (), {"Thread": _SyncThread})
    )
    seen = {}

    def _fake_install(settings, *, acknowledged):
        seen["ack"] = acknowledged
        return "C:/x/eci.dll"

    monkeypatch.setattr(elo, "install_openevv", _fake_install)
    app = _make_tui_app()
    app._offer_eloquence_install()
    while not app._bg_queue.empty():  # drain like _poll_bg_queue does
        app._bg_queue.get_nowait()()
    assert seen == {"ack": True}
    assert app.tts.changed == ["eloquence"]
    assert any("installed" in n for n in app.notices)
