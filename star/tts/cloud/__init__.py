"""Opt-in cloud neural TTS backends.

Privacy / data-egress notice
----------------------------
Every backend in this package sends the text being read to a **third-party
online service** in order to synthesize speech.  That network egress happens
**only** after the user has (1) configured an API key for the provider *and*
(2) explicitly selected the cloud voice as the active TTS engine.  With no key
configured a cloud backend reports itself unavailable (:meth:`available` returns
``False``) and is *never* auto-selected — cloud voices sit at a deliberately
high ``priority`` so :class:`~star.tts.manager.TTSManager` never falls back to
them on its own.  No document text ever leaves the machine until the user makes
that explicit two-step choice.

star's core mission is offline, no-network reading; these backends are a purely
opt-in convenience for readers who want the highest-quality neural voices and
accept the trade-off.  A missing key or a network / API failure raises a
:class:`CloudTTSError`, which the manager catches to fall back to a local engine
— the user is never sent to a dead end or told to run ``pip``.
"""
from .base import CloudBackend, CloudTTSError, timing_divergence
from .elevenlabs import ElevenLabsBackend
from .mock import MockCloudBackend

__all__ = [
    "CloudBackend",
    "CloudTTSError",
    "ElevenLabsBackend",
    "MockCloudBackend",
    "timing_divergence",
]
