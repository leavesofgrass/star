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


def _transcribe_samples(
    samples: Any, model_name: str = "base", samplerate: int = 16000
) -> str:
    """Transcribe in-memory 16-bit mono PCM (16 kHz) WITHOUT ffmpeg.

    Whisper accepts a float32 ndarray directly, so the microphone-dictation
    path can skip the WAV → ffmpeg round-trip entirely.  That matters twice
    over in a frozen, windowed build: ffmpeg-via-subprocess flashes a console
    window (star.exe has no console), and it made dictation depend on ffmpeg
    being found on PATH.  Feeding the samples straight in avoids both.
    """
    import numpy as np

    if samples is None or len(samples) == 0:
        return ""
    audio = np.asarray(samples, dtype=np.float32).flatten() / 32768.0
    if _WHISPER == "openai":
        model = _load_whisper().load_model(model_name)
        return str(model.transcribe(audio).get("text", "")).strip()
    if _WHISPER == "faster":
        model = _load_faster_whisper()(model_name)
        segments, _info = model.transcribe(audio)
        return " ".join(seg.text for seg in segments).strip()
    raise RuntimeError(
        "Speech recognition requires Whisper:\n"
        "  pip install openai-whisper   (or: pip install faster-whisper)"
    )


def _audio_in_now() -> bool:
    """Whether microphone capture is available, checked FRESH (not the import-
    time ``_AUDIO_IN`` snapshot).  numpy + sounddevice import cleanly mid-run,
    so a same-session install works without a restart — and the GUI's install
    gate and this check then always agree, so a stale flag can never surface a
    ``pip install`` message the user was told they'd never see."""
    return _module_available("numpy") and _module_available("sounddevice")


def _record_audio_to_wav(seconds: float, samplerate: int = 16000) -> str:
    """Record *seconds* of mono microphone audio to a temp WAV; return its path."""
    if not _audio_in_now():
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


class StreamRecorder:
    """Record from the microphone until the caller says stop — no fixed length.

    Backs the "press Stop when you're done" dictation UI: a fixed-duration
    ``sd.rec`` forces the user to guess how long they'll talk, so this opens a
    non-blocking ``InputStream`` whose callback (running on sounddevice's own
    audio thread) appends each block to a list.  ``elapsed`` lets the UI show a
    live timer; ``stop`` closes the stream and writes the accumulated audio to
    a temp WAV, returning its path (or "" if nothing was captured).
    """

    def __init__(self, samplerate: int = 16000) -> None:
        if not _audio_in_now():  # fresh check — same-session install works
            raise RuntimeError(
                "Microphone capture requires sounddevice + numpy:\n"
                "  pip install sounddevice numpy"
            )
        self._sd = _load_sounddevice()
        self._samplerate = samplerate
        self._blocks: List[Any] = []
        self._stream = None
        self._start_t = 0.0

    def _callback(self, indata, _frames, _time, _status) -> None:
        # Copy: sounddevice reuses the buffer after the callback returns.
        self._blocks.append(indata.copy())

    def start(self) -> None:
        self._start_t = time.monotonic()
        self._stream = self._sd.InputStream(
            samplerate=self._samplerate,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start_t if self._start_t else 0.0

    def stop_samples(self) -> Any:
        """Stop recording and return the captured int16 mono samples.

        Returns a numpy array, or None when nothing was captured (immediate
        stop / no input).  This is the ffmpeg-free path — feed the result to
        _transcribe_samples.  Safe to call once; further calls return None."""
        if self._stream is None:
            return None
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
        if not self._blocks:
            return None
        import numpy as _np

        return _np.concatenate(self._blocks, axis=0)

    def stop(self) -> str:
        """Stop recording and write the captured audio to a temp WAV.

        Returns the WAV path, or "" when no audio was captured.  Kept for
        file-based consumers; the dictation path uses stop_samples instead."""
        samples = self.stop_samples()
        if samples is None:
            return ""
        import wave

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self._samplerate)
            w.writeframes(samples.tobytes())
        return tmp.name

    def cancel(self) -> None:
        """Discard the recording without producing a file."""
        self._blocks = []
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
