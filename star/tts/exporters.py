"""Exporters — star.exporters plugins that synthesise speech to audio files.

``WAVExporter`` writes plain text to a single WAV; ``M4BExporter`` builds a
chaptered audiobook (``.m4b``), synthesising each heading-delimited chapter and
stitching them with ffmpeg (see :mod:`star.audiobook` for the pure logic).
"""
from .._runtime import *  # noqa: F401,F403
from ..formats import Exporter
from .audio import _wav_duration_seconds
from .pyttsx3 import Pyttsx3Backend


class WAVExporter(Exporter):
    """Synthesize the document's plain text to a WAV file.

    Uses the ``backend`` keyword if supplied, otherwise builds a
    :class:`Pyttsx3Backend` from the ``settings`` keyword (mirroring how
    :func:`star.video.export_video` obtains a default engine).  Raises
    ``RuntimeError`` if the chosen backend does not support WAV export.
    """

    name = "wav"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".wav"})

    @classmethod
    def available(cls) -> bool:
        # At least one built-in backend (e.g. pyttsx3/eSpeak) supports WAV
        # export; whether a given engine does is decided at export time.
        return True

    def export(self, document, path, **kwargs) -> None:
        text = (getattr(document, "plain_text", "") or "").strip()
        if not text:
            raise ValueError("Document has no readable text to synthesize")
        backend = kwargs.get("backend")
        if backend is None:
            settings = kwargs.get("settings")
            backend = Pyttsx3Backend(
                rate=int(settings.get("tts_rate", 265)) if settings else 265,
                volume=float(settings.get("tts_volume", 1.0)) if settings else 1.0,
                voice=str(settings.get("tts_voice", "")) if settings else "",
            )
        backend.export_to_wav(text, str(path))


class M4BExporter(Exporter):
    """Export the document as a chaptered audiobook (``.m4b``).

    Chapters are derived from the document's Markdown headings (falling back to a
    single chapter).  Each chapter is synthesised to a temp WAV via the TTS
    backend, then ffmpeg concatenates + AAC-encodes them into an MP4/M4B with
    embedded chapter markers and (when the document metadata names one) cover art.

    Requires **ffmpeg** on PATH and a WAV-capable TTS backend.  ``export`` raises
    ``RuntimeError`` (never a pip/dead-end message) when ffmpeg is missing so
    callers can surface a clear status.
    """

    name = "m4b"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".m4b"})

    @classmethod
    def available(cls) -> bool:
        # Needs ffmpeg to mux/encode; a WAV-capable backend is always buildable
        # (Pyttsx3Backend.export_to_wav / eSpeak), so gate purely on ffmpeg here
        # and surface a per-chapter synthesis failure at export time.
        from ..audiobook import find_ffmpeg

        return bool(find_ffmpeg())

    def export(self, document, path, **kwargs) -> None:
        from ..audiobook import (
            build_chapters_metadata,
            build_concat_list,
            build_ffmpeg_m4b_args,
            cover_path_from_document,
            derive_chapters,
            find_ffmpeg,
        )

        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError(
                "M4B export needs ffmpeg — install ffmpeg and put it on PATH."
            )

        settings = kwargs.get("settings")
        chapters = derive_chapters(document, fallback_title=kwargs.get("title", ""))
        if not chapters:
            raise ValueError("Document has no readable text to synthesize")

        backend = kwargs.get("backend")
        if backend is None:
            backend = Pyttsx3Backend(
                rate=int(settings.get("tts_rate", 265)) if settings else 265,
                volume=float(settings.get("tts_volume", 1.0)) if settings else 1.0,
                voice=str(settings.get("tts_voice", "")) if settings else "",
            )

        bitrate = str(settings.get("audiobook_bitrate", "128k")) if settings else "128k"
        progress = kwargs.get("progress")
        cancel = kwargs.get("cancel")

        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            wav_paths: List[str] = []
            durations: List[float] = []
            total = len(chapters)
            for i, chapter in enumerate(chapters):
                if cancel is not None and cancel():
                    raise RuntimeError("M4B export cancelled")
                if progress is not None:
                    progress(i, total, chapter.title)
                wav_path = str(td / f"chapter_{i:04d}.wav")
                backend.export_to_wav(chapter.text, wav_path)
                dur = _wav_duration_seconds(wav_path)
                wav_paths.append(wav_path)
                durations.append(dur)

            if progress is not None:
                progress(total, total, "Encoding audiobook…")

            concat_path = str(td / "concat.txt")
            Path(concat_path).write_text(build_concat_list(wav_paths), encoding="utf-8")

            meta_text = build_chapters_metadata(
                chapters,
                durations,
                album=str(getattr(document, "title", "") or ""),
                artist=str((getattr(document, "metadata", {}) or {}).get("author", "")),
            )
            meta_path = str(td / "chapters.txt")
            Path(meta_path).write_text(meta_text, encoding="utf-8")

            cover = cover_path_from_document(document)
            argv = build_ffmpeg_m4b_args(
                ffmpeg, concat_path, meta_path, str(path),
                cover_path=cover, bitrate=bitrate,
            )
            result = subprocess.run(argv, capture_output=True, creationflags=_SUBPROCESS_FLAGS)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg failed building M4B:\n{stderr[:2000]}")
