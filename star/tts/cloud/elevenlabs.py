"""ElevenLabsBackend — opt-in cloud neural voices over the ElevenLabs REST API.

Data-egress / consent notice
----------------------------
This backend sends the text being read to ElevenLabs' servers
(``https://api.elevenlabs.io``) to synthesize speech.  It transmits nothing
until the user has configured an ``elevenlabs_api_key`` **and** selected this
backend as the active TTS engine — see :mod:`star.tts.cloud` for the full
consent contract.  No SDK is required: every call is a plain ``urllib`` request.
"""
import urllib.error  # noqa: F401  (ensure urllib.error is bound for base.py)

from ..._runtime import *  # noqa: F401,F403
from .base import CloudBackend, CloudTTSError


class ElevenLabsBackend(CloudBackend):
    """Cloud neural TTS via `ElevenLabs <https://elevenlabs.io>`_.

    Setup
    -----
    1. Create an ElevenLabs account and copy your API key.
    2. Set ``elevenlabs_api_key`` in ``settings.json`` (or export
       ``ELEVENLABS_API_KEY``).
    3. Select the backend (``M-x tts-backend elevenlabs``) and, optionally, a
       voice id via ``tts_voice`` / :meth:`set_voice`.

    Only after both a key is present and this backend is chosen does any text
    leave the machine.  With no key the backend is unavailable and star keeps
    using a local engine.

    Voice selection
    ---------------
    A "voice" is an ElevenLabs voice id.  :meth:`list_voices` calls the
    ``/v1/voices`` endpoint when a key is configured, otherwise returns ``[]``.
    """

    name = "elevenlabs"
    # Inherits CloudBackend.priority (CLOUD_PRIORITY = 900) so it sorts *last*,
    # after every local engine — the documented "cloud auto-selects never" rule.
    api_key_setting = "elevenlabs_api_key"

    _API_ROOT = "https://api.elevenlabs.io"
    #: ElevenLabs' default multilingual model; a sensible, widely-available pick.
    _DEFAULT_MODEL = "eleven_multilingual_v2"
    #: "Rachel" — ElevenLabs' documented default public voice id.
    _DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"

    def __init__(
        self,
        rate: int = 265,
        volume: float = 1.0,
        voice: str = "",
        api_key: str = "",
        model: str = "",
    ) -> None:
        super().__init__(rate=rate, volume=volume, voice=voice, api_key=api_key)
        self._model = model or self._DEFAULT_MODEL

    # ── REST synthesis ───────────────────────────────────────────────────────

    def _voice_id(self) -> str:
        return self._voice or self._DEFAULT_VOICE

    def _synth_bytes(self, text: str, api_key: str) -> bytes:
        """POST to ``/v1/text-to-speech/{voice_id}`` and return WAV audio bytes.

        Requests PCM WAV (``output_format=pcm_16000`` wrapped as a WAV container
        via the ``Accept`` header) so the bytes drop straight into star's WAV
        playback path with no transcoding.  Raises :class:`CloudTTSError` on any
        network/API failure (handled in :meth:`CloudBackend._http_post`).
        """
        url = f"{self._API_ROOT}/v1/text-to-speech/{self._voice_id()}"
        body = json.dumps(
            {
                "text": text,
                "model_id": self._model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            }
        ).encode("utf-8")
        headers = {
            "xi-api-key": api_key,  # the provider's key header — never logged
            "Content-Type": "application/json",
            # Ask for a WAV container so star's WAV player accepts the bytes.
            "Accept": "audio/wav",
        }
        # ``output_format`` is a query param on this endpoint; pcm_16000 in a WAV
        # wrapper is broadly supported and matches the WAV Accept header.
        url = url + "?output_format=pcm_16000"
        audio = self._http_post(url, body, headers)
        if not audio:
            raise CloudTTSError(f"{self.name}: empty audio response from provider.")
        return audio

    # ── voice enumeration ────────────────────────────────────────────────────

    def list_voices(self) -> List[Dict[str, str]]:
        """Return the account's voices from ``/v1/voices``; ``[]`` with no key.

        Best-effort: any network/parse failure yields an empty list rather than
        raising (voice enumeration is not a synthesis action).
        """
        api_key = self._get_api_key()
        if not api_key:
            return []
        data = self._http_get_json(
            f"{self._API_ROOT}/v1/voices",
            {"xi-api-key": api_key, "Accept": "application/json"},
        )
        if not isinstance(data, dict):
            return []
        voices: List[Dict[str, str]] = []
        for v in data.get("voices", []) or []:
            if not isinstance(v, dict):
                continue
            vid = str(v.get("voice_id", "") or "")
            if not vid:
                continue
            # ElevenLabs reports language in the (optional) labels/fine_tuning;
            # fall back to "" when absent so the schema matches other backends.
            labels = v.get("labels") if isinstance(v.get("labels"), dict) else {}
            lang = str((labels or {}).get("language", "") or "")
            voices.append(
                {
                    "id": vid,
                    "name": str(v.get("name", "") or vid),
                    "lang": lang,
                }
            )
        return voices
