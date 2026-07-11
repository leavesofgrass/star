"""PyInstaller runtime hook for the frozen star.exe.

Runs *before* any star code imports, so it can wire the bundled native tools
into the environment the libraries expect:

* **ffmpeg on PATH** — audio export (M4B audiobook) and other tools shell out to
  the ``ffmpeg`` binary. The self-contained build ships ffmpeg under
  ``<bundle>/ffmpeg/ffmpeg.exe``; prepend that folder to PATH so anything that
  looks for ffmpeg on PATH finds it without a system install. (Dictation itself
  decodes audio via faster-whisper's bundled PyAV, so it no longer needs this.)
* **Offline dictation** — the build bundles the faster-whisper (CTranslate2)
  ``base`` model directory under ``<bundle>/faster_whisper_model/``;
  ``_runtime._new_faster_model`` loads it with ``local_files_only=True``. Force
  Hugging Face fully offline here, before any faster-whisper import, so no
  model-resolution path can reach the network.
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

    if os.path.isdir(os.path.join(_base, "faster_whisper_model")):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    _nltk_data = os.path.join(_base, "nltk_data")
    if os.path.isdir(_nltk_data):
        os.environ.setdefault("NLTK_DATA", _nltk_data)
