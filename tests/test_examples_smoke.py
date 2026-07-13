"""Smoke test for the runnable examples under ``docs/examples/``.

Every ``docs/examples/<category>/<name>/run.py`` is executed in a clean working
directory and must exit 0.  Examples that can rot silently, will — this gate
keeps the ones shipped in the repo honest (they degrade gracefully and print
guidance rather than raising when an optional dependency is absent, so they stay
green in a minimal environment too).
"""
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_EXAMPLES = _REPO / "docs" / "examples"
# Examples are exactly two levels deep: docs/examples/<category>/<name>/run.py
_RUNNERS = sorted(_EXAMPLES.glob("*/*/run.py"))


def _example_id(path: Path) -> str:
    return path.relative_to(_EXAMPLES).parent.as_posix()


def test_examples_are_discovered() -> None:
    """Guard the discovery glob so a broken path can't make this pass vacuously."""
    assert len(_RUNNERS) >= 8, f"expected several example runners, found {_RUNNERS}"


@pytest.mark.parametrize("runner", _RUNNERS, ids=[_example_id(p) for p in _RUNNERS])
def test_example_runs_clean(runner: Path, tmp_path: Path) -> None:
    """Each example runs to exit 0 from a clean cwd (it finds its own inputs)."""
    result = subprocess.run(
        [sys.executable, str(runner)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"{_example_id(runner)} exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n"
        f"--- stderr ---\n{result.stderr[-2000:]}"
    )
