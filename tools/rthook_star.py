"""PyInstaller runtime hook for the frozen star.exe.

Runs *before* any star code imports, so it can wire the bundled native tools
into the environment the libraries expect:

* **ffmpeg on PATH** — Whisper (dictation/transcription) shells out to the
  ``ffmpeg`` binary to decode audio. The self-contained build ships ffmpeg
  under ``<bundle>/ffmpeg/ffmpeg.exe``; prepend that folder to PATH so Whisper
  (and anything else that looks for ffmpeg on PATH) finds it without a system
  install.
* **Whisper model cache** — the build bundles the Whisper ``base`` model under
  ``<bundle>/whisper_cache/whisper/`` so dictation works offline on first
  launch. Point Whisper's cache lookup (``XDG_CACHE_HOME``) at it. Whisper
  verifies the checkpoint's checksum and loads it read-only, so the read-only
  bundle directory is fine; if the model is somehow absent it falls back to its
  normal download behaviour.
* **NLTK data path** — document summarization (sumy) tokenizes sentences with
  NLTK's ``punkt`` data. The build stages it under ``<bundle>/nltk_data``;
  point ``NLTK_DATA`` there so summarization works offline. If the data is
  absent, ``summarize_document`` still falls back to downloading it on demand.
"""

import os
import sys

_base = getattr(sys, "_MEIPASS", None)
if _base:
    _ffmpeg_dir = os.path.join(_base, "ffmpeg")
    if os.path.isdir(_ffmpeg_dir):
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    _whisper_cache = os.path.join(_base, "whisper_cache")
    if os.path.isdir(_whisper_cache):
        os.environ.setdefault("XDG_CACHE_HOME", _whisper_cache)

    _nltk_data = os.path.join(_base, "nltk_data")
    if os.path.isdir(_nltk_data):
        os.environ.setdefault("NLTK_DATA", _nltk_data)
