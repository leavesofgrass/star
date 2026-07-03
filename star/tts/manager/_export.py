"""ExportMixin — Piper catalog helpers and WAV/audio/subtitle export.

Carved verbatim from the former ``star/tts/manager.py`` module; format
inference, temp-file handling, and subtitle generation are unchanged.
"""
from ..._runtime import *  # noqa: F401,F403
from ..audio import _convert_audio_format
from ..subtitles import _generate_subtitles


class ExportMixin:
    """Piper voice catalog access and audio/subtitle export."""

    def piper_catalog(self) -> List[Dict[str, str]]:
        """Return the downloadable Piper voice catalog (see PiperBackend).

        Available regardless of the active backend so the voice manager can
        offer Piper downloads even when another engine is currently selected.
        """
        from ..piper import PiperBackend

        return PiperBackend.catalog_voices()

    def installed_piper_models(self) -> List[str]:
        """Return the cached Piper catalog models' ``.onnx`` paths."""
        from ..piper import PiperBackend

        return PiperBackend.installed_model_paths()

    def download_piper_model(self, key: str, **kwargs: Any) -> str:
        """Download the catalog Piper voice *key*; return its cached path or ""."""
        from ..piper import PiperBackend

        return PiperBackend.download_model(key, **kwargs)

    def export_audio(
        self,
        text: str,
        dest_path: str,
        subtitle_path: Optional[str] = None,
        subtitle_format: str = "srt",
        subtitle_word_level: bool = False,
    ) -> None:
        """Synthesize *text* and save it to *dest_path*.

        The output format is inferred from the file extension:

        * ``.wav``  — written directly by the backend (no extras needed).
        * ``.mp3``  — requires **ffmpeg** or **pydub**.
        * ``.ogg``  — requires **ffmpeg** or **pydub**.
        * ``.mp4``  — requires **ffmpeg** or **pydub** (audio-only AAC).

        When *subtitle_path* is given a synchronized SRT/VTT caption track is
        written there using the same synthesized audio, so no second synthesis
        is needed.  *subtitle_format* is ``"srt"`` or ``"vtt"``
        and *subtitle_word_level* emits one cue per word instead of grouping
        tokens into sentence-length caption lines.

        This method **blocks** until synthesis and conversion are complete.
        Call it from a background thread when used in a GUI to avoid
        freezing the interface.
        """
        ext = Path(dest_path).suffix.lower()
        if ext == ".wav":
            self._backend.export_to_wav(text, dest_path)
            if subtitle_path:
                self._write_subtitles(
                    text,
                    dest_path,
                    subtitle_path,
                    subtitle_format,
                    subtitle_word_level,
                )
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            self._backend.export_to_wav(text, tmp_wav)
            if subtitle_path:
                self._write_subtitles(
                    text,
                    tmp_wav,
                    subtitle_path,
                    subtitle_format,
                    subtitle_word_level,
                )
            _convert_audio_format(tmp_wav, dest_path)
        finally:
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _write_subtitles(
        text: str,
        wav_path: str,
        sub_path: str,
        fmt: str = "srt",
        word_level: bool = False,
    ) -> None:
        """Generate and write an SRT/VTT caption track for the synthesized WAV."""
        subs = _generate_subtitles(text, wav_path, fmt=fmt, word_level=word_level)
        if subs:
            Path(sub_path).write_text(subs, encoding="utf-8")

    def export_subtitles(
        self,
        text: str,
        sub_path: str,
        fmt: str = "srt",
        word_level: bool = False,
    ) -> None:
        """Synthesize *text* to a temporary WAV solely to measure its duration,
        then write a synchronized SRT/VTT caption track to *sub_path*.

        Use this when only captions are wanted (no audio file).  **Blocks**
        until synthesis is complete.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            self._backend.export_to_wav(text, tmp_wav)
            self._write_subtitles(text, tmp_wav, sub_path, fmt, word_level)
        finally:
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass
