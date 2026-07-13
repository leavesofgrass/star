#!/usr/bin/env python3
"""List available TTS voices with ``star --list-voices``.

star supports many TTS engines — pyttsx3 (SAPI5 / NSSpeech / eSpeak), the macOS
``say`` command, eSpeak-NG, Festival, Piper (neural, offline), Coqui, DECtalk,
and ElevenLabs. This prints every voice star can see on your system, the same
output the GUI's Voice Manager (F4) shows.
"""
import subprocess
import sys


def main() -> int:
    print("$ star --list-voices\n", flush=True)
    return subprocess.run(
        [sys.executable, "-m", "star", "--list-voices"]
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
