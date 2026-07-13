#!/usr/bin/env python3
"""Extract a document's reading text with ``star --plain`` (no GUI).

``star --plain FILE`` prints the clean reading text of any supported document to
stdout and exits — handy for piping star's document loaders into other tools
(search, word counts, another TTS engine, …).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "sample.md"


def main() -> int:
    print(f"$ star --plain {SAMPLE.name}\n", flush=True)
    # Invoke the installed `star` via the current interpreter so the example
    # uses whichever star is on this machine.
    result = subprocess.run(
        [sys.executable, "-m", "star", "--plain", str(SAMPLE)],
        text=True,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
