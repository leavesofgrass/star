"""Whisper-based audio transcription and microphone capture."""
from ._runtime import *  # noqa: F401,F403


# =============================================================================
# Speech recognition  (Whisper dictation / transcription)
# =============================================================================


def _fmt_timestamp(seconds: float) -> str:
    """Format *seconds* as ``[hh:mm:ss]`` (or ``[mm:ss]`` under an hour)."""
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{sec:02d}]" if h else f"[{m:02d}:{sec:02d}]"


def _transcribe_audio(
    path: str, model_name: str = "base", timestamps: bool = False
) -> str:
    """Transcribe an audio file to text using Whisper (blocking).

    Works with either ``openai-whisper`` or ``faster-whisper``.  When
    *timestamps* is True each segment is prefixed with its start time as
    ``[hh:mm:ss]`` on its own line, producing a navigable transcript.
    Raises RuntimeError with install guidance when no backend is available.
    """
    if _WHISPER == "openai":
        model = _load_whisper().load_model(model_name)
        result = model.transcribe(path)
        if timestamps:
            segs = result.get("segments", []) or []
            return (
                "\n".join(
                    f"{_fmt_timestamp(s.get('start', 0))} {str(s.get('text', '')).strip()}"
                    for s in segs
                ).strip()
                or str(result.get("text", "")).strip()
            )
        return str(result.get("text", "")).strip()
    if _WHISPER == "faster":
        model = _load_faster_whisper()(model_name)
        segments, _info = model.transcribe(path)
        if timestamps:
            return "\n".join(
                f"{_fmt_timestamp(getattr(seg, 'start', 0))} {seg.text.strip()}"
                for seg in segments
            ).strip()
        return " ".join(seg.text for seg in segments).strip()
    raise RuntimeError(
        "Speech recognition requires Whisper:\n"
        "  pip install openai-whisper   (or: pip install faster-whisper)"
    )


def _record_audio_to_wav(seconds: float, samplerate: int = 16000) -> str:
    """Record *seconds* of mono microphone audio to a temp WAV; return its path."""
    if not _AUDIO_IN:
        raise RuntimeError(
            "Microphone capture requires sounddevice + numpy:\n"
            "  pip install sounddevice numpy"
        )
    import wave

    sd = _load_sounddevice()
    frames = int(seconds * samplerate)
    rec = sd.rec(frames, samplerate=samplerate, channels=1, dtype="int16")
    sd.wait()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        w.writeframes(rec.tobytes())
    return tmp.name
