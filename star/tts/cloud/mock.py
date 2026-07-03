"""MockCloudBackend — a fake cloud provider for tests and offline demos.

Sends no network traffic: :meth:`_synth_bytes` returns a tiny in-memory WAV and
:meth:`list_voices` returns a fixed catalog.  It follows the exact same
key-gating and error contract as the real providers so tests can exercise
:class:`~star.tts.cloud.base.CloudBackend` behaviour (availability, fallback,
export) without credentials or a socket.
"""
import struct

from ..._runtime import *  # noqa: F401,F403
from .base import CloudBackend, CloudTTSError


def _tiny_wav(seconds: float = 0.05, rate: int = 8000) -> bytes:
    """Return a minimal silent mono 16-bit PCM WAV as bytes (no file I/O)."""
    nframes = max(1, int(seconds * rate))
    data = struct.pack(f"<{nframes}h", *([0] * nframes))
    byte_rate = rate * 2
    header = b"RIFF"
    header += struct.pack("<I", 36 + len(data))
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<IHHIIHH", 16, 1, 1, rate, byte_rate, 2, 16)
    header += b"data"
    header += struct.pack("<I", len(data))
    return header + data


class MockCloudBackend(CloudBackend):
    """A fully offline stand-in for a real cloud backend (tests only).

    Set ``fail=True`` to make synthesis raise :class:`CloudTTSError`, simulating
    a network/API failure so fallback paths can be tested.
    """

    name = "mockcloud"
    priority = 95
    api_key_setting = "mockcloud_api_key"

    def __init__(
        self,
        rate: int = 265,
        volume: float = 1.0,
        voice: str = "",
        api_key: str = "",
        fail: bool = False,
    ) -> None:
        super().__init__(rate=rate, volume=volume, voice=voice, api_key=api_key)
        self.fail = fail
        #: Records the text of every _synth_bytes call (test introspection).
        self.synth_calls: List[str] = []

    def _synth_bytes(self, text: str, api_key: str) -> bytes:
        self.synth_calls.append(text)
        if self.fail:
            raise CloudTTSError(f"{self.name}: simulated failure.")
        return _tiny_wav()

    def list_voices(self) -> List[Dict[str, str]]:
        if not self._get_api_key():
            return []
        return [
            {"id": "mock-en", "name": "Mock English", "lang": "en"},
            {"id": "mock-es", "name": "Mock Spanish", "lang": "es"},
        ]
