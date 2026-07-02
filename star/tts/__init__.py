"""Text-to-speech backends and the TTS manager (package split from tts.py).

Re-exports the full public surface of the former ``star/tts.py`` module so
``from star.tts import X`` and the ``star.backends`` entry-points keep resolving.
"""
import abc  # noqa: F401  (kept for namespace parity with the old module)

from .._runtime import *  # noqa: F401,F403
from ..settings import Settings  # noqa: F401
from ..formats import Exporter  # noqa: F401

from .base import TTSBackend
from .silent import SilentBackend
from .festival import FestivalBackend
from .coqui import CoquiBackend
from .piper import PiperBackend, _piper_voice_dirs
from . import piper_models
from .pyttsx3 import Pyttsx3Backend
from .espeak import ESpeakBackend, ESpeakLibBackend
from .dectalk import DECtalkDLLBackend, DECtalkBackend
from .applesay import AppleSayBackend
from .audio import (
    _apply_wav_adjustments,
    _convert_audio_format,
    _wav_duration_seconds,
)
from .subtitles import (
    _build_subtitle_cues,
    _fmt_subtitle_time,
    _format_subtitles,
    _generate_subtitles,
)
from .manager import TTSManager, _SCReader
from .exporters import WAVExporter

# Explicit re-export surface (mirrors the old flat module).  Private helpers are
# listed too because external callers (star.video) and the tests import them by
# name from ``star.tts``.
__all__ = [
    "TTSBackend", "TTSManager", "WAVExporter",
    "SilentBackend", "FestivalBackend", "CoquiBackend", "PiperBackend",
    "Pyttsx3Backend", "ESpeakBackend", "ESpeakLibBackend",
    "DECtalkDLLBackend", "DECtalkBackend", "AppleSayBackend",
    "_SCReader", "_piper_voice_dirs", "piper_models",
    "_apply_wav_adjustments", "_convert_audio_format", "_wav_duration_seconds",
    "_build_subtitle_cues", "_fmt_subtitle_time", "_format_subtitles",
    "_generate_subtitles",
]
