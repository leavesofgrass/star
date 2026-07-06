"""WAV duration, volume adjustment, and format-conversion helpers."""
from .._runtime import *  # noqa: F401,F403


def _apply_wav_adjustments(path: str, volume: float) -> None:
    """Scale WAV sample amplitudes by *volume* in-place.  Pure stdlib."""
    import struct
    import wave

    with wave.open(path, "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(params.nframes)

    sampwidth = params.sampwidth
    if sampwidth == 2:  # 16-bit PCM (most common)
        fmt = f"<{len(frames) // 2}h"
        samples = list(struct.unpack(fmt, frames))
        samples = [max(-32768, min(32767, int(s * volume))) for s in samples]
        frames = struct.pack(fmt, *samples)
        with wave.open(path, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(frames)


def _convert_audio_format(src_wav: str, dest_path: str) -> None:
    """Convert *src_wav* (WAV) to the format implied by *dest_path*'s extension.

    Supported output formats: ``.mp3``, ``.ogg``, ``.mp4``, ``.wav``.

    Conversion priority:

    1. **ffmpeg** — recommended; handles all formats cleanly.
       Install: https://ffmpeg.org/download.html
    2. **pydub** — pure-Python fallback (``pip install pydub``).
    3. **WAV copy** — if the extension is ``.wav`` no conversion is needed.

    Raises ``RuntimeError`` when the target format requires conversion but
    no suitable tool is available.
    """
    ext = Path(dest_path).suffix.lower()
    if ext == ".wav":
        shutil.copy2(src_wav, dest_path)
        return

    # --- ffmpeg -----------------------------------------------------------
    # Prefer the bundled ffmpeg (self-contained build); fall back to a
    # system install on PATH.
    _ffmpeg = (
        str(_FFMPEG_BUNDLED) if _FFMPEG_BUNDLED.is_file() else shutil.which("ffmpeg")
    )
    if _ffmpeg:
        cmd: List[str] = [_ffmpeg, "-y", "-i", src_wav]
        if ext == ".mp3":
            cmd += ["-codec:a", "libmp3lame", "-qscale:a", "2"]
        elif ext == ".ogg":
            cmd += ["-codec:a", "libvorbis", "-q:a", "4"]
        elif ext == ".mp4":
            # Audio-only MP4 (AAC inside an MPEG-4 container).
            cmd += ["-codec:a", "aac", "-b:a", "192k", "-vn"]
        # For other extensions let ffmpeg infer the codec from the name.
        cmd.append(dest_path)
        result = subprocess.run(cmd, capture_output=True, creationflags=_SUBPROCESS_FLAGS)
        if result.returncode == 0:
            return
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr.decode(errors='replace')}"
        )

    # --- pydub ------------------------------------------------------------
    try:
        from pydub import AudioSegment as _AS  # type: ignore[import]

        audio = _AS.from_wav(src_wav)
        fmt_map = {".mp3": "mp3", ".ogg": "ogg", ".mp4": "mp4"}
        fmt = fmt_map.get(ext, ext.lstrip("."))
        audio.export(dest_path, format=fmt)
        return
    except ImportError:
        pass

    raise RuntimeError(
        f"Cannot convert WAV to {ext!r}.\n"
        "Install ffmpeg (https://ffmpeg.org/download.html) "
        "or run: pip install pydub"
    )


def _wav_duration_seconds(path: str) -> float:
    """Return the duration of a WAV file in seconds (0.0 on any error)."""
    import wave

    try:
        with wave.open(path, "rb") as wf:
            rate = wf.getframerate()
            frames = wf.getnframes()
            return frames / float(rate) if rate else 0.0
    except Exception:
        return 0.0
