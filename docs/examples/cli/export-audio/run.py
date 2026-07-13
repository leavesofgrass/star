#!/usr/bin/env python3
"""Export a document to spoken audio with ``star``'s TTS library API.

star can synthesize any document it opens into a WAV file (or MP3/OGG/MP4 when
ffmpeg is installed). This example loads a short Markdown article, picks the
first available TTS voice, and writes a WAV to an ``out/`` directory — the same
pipeline the GUI's **File > Export > Audio…** uses.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        from star.documents import load_document
        from star.settings import Settings
        from star.tts import TTSManager
    except ImportError:
        print("This example needs star installed:  pip install star-reader")
        return 0

    settings = Settings()
    doc = load_document(str(HERE / "sample.md"), settings)
    mgr = TTSManager(settings)

    if not mgr.list_voices():
        print(
            "No TTS voices available on this system.\n"
            "Install a TTS engine (e.g. pip install pyttsx3) or run on a\n"
            "platform with system voices (Windows SAPI5 / macOS NSSpeech)."
        )
        return 0

    out_dir = Path.cwd() / "out"
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / "photosynthesis.wav"

    print(f"Document: {doc.title}")
    print(f"Voice:    {mgr.backend_name}")
    print(f"Saving:   {dest}")
    print()

    mgr.export_audio(doc.plain_text, str(dest))

    size_kb = dest.stat().st_size / 1024
    print(f"Done — {size_kb:.0f} KB written to {dest}")
    print()
    print("Tip: change the format by changing the extension:")
    print("  .mp3 / .ogg / .mp4 — requires ffmpeg or pydub")

    shutil.rmtree(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
