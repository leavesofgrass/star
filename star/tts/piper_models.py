"""Piper voice-model catalog + on-demand download/cache.

Piper produces natural, neural-quality speech entirely offline, but its voice
*models* (a ``.onnx`` weights file plus a ``.onnx.json`` config) are large and
are **not** bundled with star.  This module gives star the same "fetch it the
first time it's wanted" ergonomics the OpenDyslexic font has (see
``star/fonts.py``):

* :data:`CATALOG` — a curated list of common Piper voices (name, language,
  quality, and the Hugging Face URLs of the two files each needs);
* :func:`installed_models` / :func:`is_installed` — detect which catalog voices
  are already cached under ``CACHE_DIR/piper``;
* :func:`fetch` — best-effort download of a catalog voice's two files into that
  cache directory.

Everything here is **offline-safe**: any network / IO error is logged and
swallowed, so callers always get a (possibly empty / unchanged) result and never
see an exception.  The download function is *injectable* (``fetcher=``) so tests
never touch the real network.

The models live in ``CACHE_DIR/piper`` — the same directory
``PiperBackend`` already scans (it is ``<config>/piper`` in
``_piper_voice_dirs``), so a freshly-fetched model is discovered automatically.
"""
from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from .._runtime import CACHE_DIR

_log = logging.getLogger("star.tts.piper_models")

# Hugging Face hosts the official rhasspy/piper-voices repository.  Each voice
# lives under ``<lang>/<locale>/<name>/<quality>/`` as ``<file>.onnx`` and
# ``<file>.onnx.json``.  We pin ``main`` (the repo has no tagged releases) and
# build the two URLs from a single relative path so a catalog row stays compact.
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


@dataclass(frozen=True)
class PiperVoice:
    """One downloadable Piper voice model.

    *key* is a stable identifier (``"en_US-lessac-medium"``) used as the cache
    filename stem and the catalog lookup key.  *rel_path* is the voice's path
    within the Hugging Face repo, without the ``.onnx`` suffix; the two file
    URLs are derived from it.
    """

    key: str
    name: str          # human-friendly display name
    language: str      # BCP-47-ish tag, e.g. "en_US"
    quality: str       # "x_low" | "low" | "medium" | "high"
    rel_path: str      # path in the HF repo, sans extension
    size_mb: int = 0   # approximate .onnx size, for UI hints (0 = unknown)

    # ── derived paths / URLs ────────────────────────────────────────────────

    @property
    def onnx_name(self) -> str:
        """Basename the ``.onnx`` file is cached under."""
        return f"{self.key}.onnx"

    @property
    def config_name(self) -> str:
        """Basename the ``.onnx.json`` config is cached under."""
        return f"{self.key}.onnx.json"

    @property
    def onnx_url(self) -> str:
        return f"{_HF_BASE}/{self.rel_path}.onnx"

    @property
    def config_url(self) -> str:
        return f"{_HF_BASE}/{self.rel_path}.onnx.json"

    @property
    def label(self) -> str:
        """One-line display label: ``English (US) — Lessac (medium)``."""
        return f"{self.name} [{self.language}] ({self.quality})"


# A small, curated catalog spanning star's five UI languages plus a couple of
# extra widely-used English voices.  Kept intentionally short — this is a
# "batteries-suggested" starter set, not an exhaustive mirror of the ~130 voices
# upstream ships.  size_mb values are approximate (medium ≈ 60 MB, low ≈ 20 MB).
CATALOG: List[PiperVoice] = [
    PiperVoice(
        "en_US-lessac-medium", "English (US) — Lessac", "en_US", "medium",
        "en/en_US/lessac/medium/en_US-lessac-medium", 63,
    ),
    PiperVoice(
        "en_US-amy-medium", "English (US) — Amy", "en_US", "medium",
        "en/en_US/amy/medium/en_US-amy-medium", 63,
    ),
    PiperVoice(
        "en_US-ryan-high", "English (US) — Ryan", "en_US", "high",
        "en/en_US/ryan/high/en_US-ryan-high", 114,
    ),
    PiperVoice(
        "en_GB-alan-medium", "English (GB) — Alan", "en_GB", "medium",
        "en/en_GB/alan/medium/en_GB-alan-medium", 63,
    ),
    PiperVoice(
        "es_ES-davefx-medium", "Español (ES) — Davefx", "es_ES", "medium",
        "es/es_ES/davefx/medium/es_ES-davefx-medium", 63,
    ),
    PiperVoice(
        "es_MX-claude-high", "Español (MX) — Claude", "es_MX", "high",
        "es/es_MX/claude/high/es_MX-claude-high", 114,
    ),
    PiperVoice(
        "fr_FR-siwis-medium", "Français (FR) — Siwis", "fr_FR", "medium",
        "fr/fr_FR/siwis/medium/fr_FR-siwis-medium", 63,
    ),
    PiperVoice(
        "de_DE-thorsten-medium", "Deutsch (DE) — Thorsten", "de_DE", "medium",
        "de/de_DE/thorsten/medium/de_DE-thorsten-medium", 63,
    ),
    PiperVoice(
        "pt_BR-faber-medium", "Português (BR) — Faber", "pt_BR", "medium",
        "pt/pt_BR/faber/medium/pt_BR-faber-medium", 63,
    ),
]

#: Mapping of catalog key → :class:`PiperVoice`, for O(1) lookup.
_BY_KEY = {v.key: v for v in CATALOG}


def catalog() -> List[PiperVoice]:
    """Return a copy of the voice catalog (safe for callers to sort/filter)."""
    return list(CATALOG)


def get(key: str) -> Optional[PiperVoice]:
    """Return the catalog voice with *key*, or ``None`` if unknown."""
    return _BY_KEY.get(key)


def models_dir() -> Path:
    """Return (and create) the directory where Piper models are cached.

    This is ``CACHE_DIR/piper`` — one of the directories ``PiperBackend`` already
    scans (via ``_piper_voice_dirs`` → ``<config>/piper``), so anything fetched
    here is picked up by the backend automatically.
    """
    path = CACHE_DIR / "piper"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def model_path(voice: PiperVoice) -> Path:
    """The cache path the *voice*'s ``.onnx`` file lives (or would live) at."""
    return models_dir() / voice.onnx_name


def config_path(voice: PiperVoice) -> Path:
    """The cache path the *voice*'s ``.onnx.json`` config lives at."""
    return models_dir() / voice.config_name


def is_installed(voice: PiperVoice) -> bool:
    """True when both the ``.onnx`` and its ``.onnx.json`` are cached.

    Piper needs the config sidecar as well as the weights, so a half-download
    (one file present, the other missing) counts as *not* installed.
    """
    try:
        return model_path(voice).is_file() and config_path(voice).is_file()
    except OSError:
        return False


def installed_models() -> List[PiperVoice]:
    """Return the catalog voices currently cached, in catalog order."""
    return [v for v in CATALOG if is_installed(v)]


def installed_keys() -> List[str]:
    """Return just the keys of the cached catalog voices (for reporting)."""
    return [v.key for v in installed_models()]


def _default_fetcher(url: str, timeout: int) -> bytes:
    """Download *url* and return its bytes (the real network path).

    Isolated so :func:`fetch` can accept an injected ``fetcher`` in tests and
    never touch the network.
    """
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.read()


def fetch(
    voice: PiperVoice,
    timeout: int = 60,
    force: bool = False,
    fetcher: Optional[Callable[[str, int], bytes]] = None,
) -> Optional[Path]:
    """Best-effort download of *voice*'s two files into :func:`models_dir`.

    Returns the cached ``.onnx`` :class:`~pathlib.Path` on success, or ``None``
    if the download failed (offline, HTTP error, IO error) — this function
    **never raises**, mirroring ``star.fonts.fetch``.

    *fetcher* is an injection point: it is called as ``fetcher(url, timeout)``
    and must return the file's bytes.  Tests pass a stub so no real network
    request is made; production uses :func:`_default_fetcher`.
    """
    if fetcher is None:
        fetcher = _default_fetcher
    if is_installed(voice) and not force:
        return model_path(voice)
    targets = (
        (voice.onnx_url, model_path(voice)),
        (voice.config_url, config_path(voice)),
    )
    for url, target in targets:
        if target.is_file() and not force:
            continue
        try:
            data = fetcher(url, timeout)
            target.write_bytes(data)
        except Exception:  # noqa: BLE001 — offline-safe: log and give up.
            _log.warning("failed to fetch Piper model from %s", url, exc_info=True)
            # Remove a partial write so a later retry re-fetches cleanly and
            # is_installed() never reports a half-download as ready.
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return None
    return model_path(voice) if is_installed(voice) else None
