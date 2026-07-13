#!/usr/bin/env python3
"""List star's registered plugins with ``star --plugins list``.

star discovers TTS backends, document-format handlers, and exporters through
``importlib.metadata`` entry points, so third-party packages can add their own.
This prints every registered plugin — the same mechanism the bundled
``docs/examples/plugin-template`` extends.
"""
import subprocess
import sys


def main() -> int:
    print("$ star --plugins list\n", flush=True)
    return subprocess.run(
        [sys.executable, "-m", "star", "--plugins", "list"]
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
