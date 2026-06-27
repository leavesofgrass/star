"""WAVExporter — star.exporters plugin that synthesises plain text to WAV."""
from .._runtime import *  # noqa: F401,F403
from ..formats import Exporter
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
