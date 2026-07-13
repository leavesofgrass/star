#!/usr/bin/env python3
"""Show which optional features are available with ``star --deps``.

star's core runs on the standard library; every extra capability (OCR, offline
dictionary, translation, knowledge-graph, speech-to-text, …) is optional. This
prints a status report of what's installed and what each missing piece unlocks —
a zero-setup way to see where your install stands.
"""
import subprocess
import sys


def main() -> int:
    print("$ star --deps\n", flush=True)
    return subprocess.run([sys.executable, "-m", "star", "--deps"]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
