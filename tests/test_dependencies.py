"""Tests for the optional-dependency harness (``star.diagnostics``).

These tests treat :data:`star.diagnostics.OPTIONAL_DEPENDENCIES` as the single
source of truth for star's optional dependencies and enforce two guarantees:

1. **Completeness** — every boolean import guard in the codebase (a ``_FLAG``
   set to ``True`` in a ``try`` and ``False`` in the matching ``except``) is
   registered in the harness, so a newly added optional dependency can never be
   silently dropped from ``star --deps``.
2. **Consistency** — whenever the harness reports a dependency as *available*,
   that dependency's probe modules really do import (or its binary is on PATH).
   A guard flag can never claim a package is present when it is not.

Everything here runs with *zero* optional dependencies installed: the harness
itself depends only on the standard library.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

import star
from star import diagnostics
from star.diagnostics import (
    OPTIONAL_DEPENDENCIES,
    dependency_status,
    format_dependency_report,
    probe_present,
)

_PKG_DIR = Path(star.__file__).parent
_REGISTERED_ATTRS = {
    d["attr"] for d in OPTIONAL_DEPENDENCIES if d.get("attr")
}


def _boolean_guard_flags() -> dict:
    """Map ``flag_name -> source_file`` for every boolean import guard.

    A boolean import guard is a module-level name assigned ``True`` in one place
    and ``False`` in another within the same file — the exact shape of star's
    ``try: import x; _X = True / except ImportError: _X = False`` pattern.  This
    deliberately ignores string/path guards (``_PDF``, ``_QT``, ``_WHISPER``,
    ``_PIPER_BIN`` …), which are registered by hand.
    """
    true_re = re.compile(r"^\s*(_[A-Z][A-Z0-9_]*)\s*=\s*True\b", re.MULTILINE)
    false_re = re.compile(r"^\s*(_[A-Z][A-Z0-9_]*)\s*=\s*False\b", re.MULTILINE)
    found: dict = {}
    for path in _PKG_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        trues = set(true_re.findall(text))
        falses = set(false_re.findall(text))
        for name in trues & falses:
            found[name] = path.name
    return found


def test_registry_basic_shape():
    """Every entry is well-formed and keys are unique."""
    assert OPTIONAL_DEPENDENCIES, "registry must not be empty"
    keys = [d["key"] for d in OPTIONAL_DEPENDENCIES]
    assert len(keys) == len(set(keys)), "duplicate dependency keys"
    required = {"key", "label", "group", "kind", "enables", "install"}
    for dep in OPTIONAL_DEPENDENCIES:
        missing = required - dep.keys()
        assert not missing, f"{dep.get('key')} missing fields: {missing}"
        assert dep["kind"] in {"bool", "string", "path", "binary", "probe"}


def test_every_boolean_guard_is_registered():
    """No optional dependency may exist in the code but be absent from --deps."""
    guards = _boolean_guard_flags()
    assert guards, "scan found no guard flags — the heuristic is broken"
    unregistered = {
        name: src for name, src in guards.items() if name not in _REGISTERED_ATTRS
    }
    assert not unregistered, (
        "these import guards are not registered in star.diagnostics "
        f"(add them to OPTIONAL_DEPENDENCIES): {unregistered}"
    )


def test_status_covers_whole_registry():
    statuses = dependency_status()
    assert len(statuses) == len(OPTIONAL_DEPENDENCIES)
    assert {s["key"] for s in statuses} == {d["key"] for d in OPTIONAL_DEPENDENCIES}
    for s in statuses:
        assert isinstance(s["available"], bool)
        assert s["error"] is None, f"{s['key']} guard module failed: {s['error']}"


@pytest.mark.parametrize(
    "dep", OPTIONAL_DEPENDENCIES, ids=[d["key"] for d in OPTIONAL_DEPENDENCIES]
)
def test_available_implies_really_present(dep):
    """If the harness says a dependency is available, it must truly be importable.

    This is the safety invariant: a guard flag claiming a package is present
    when the import would actually fail is exactly the bug that crashes the app
    at the point of use.  The reverse (package importable but flag ``False`` for
    a secondary reason, e.g. Coqui's heavier import failing) is allowed.
    """
    status = next(s for s in dependency_status() if s["key"] == dep["key"])
    if not status["available"]:
        pytest.skip(f"{dep['key']} not installed in this environment")
    probed = probe_present(dep)
    if probed is None:
        pytest.skip(f"{dep['key']} has no independent probe")
    assert probed is True, (
        f"{dep['key']} is reported available but its probe failed to import"
    )


def test_report_mentions_every_dependency():
    report = format_dependency_report()
    assert report.endswith("\n")
    assert "optional dependency status" in report
    for dep in OPTIONAL_DEPENDENCIES:
        assert dep["label"] in report, f"{dep['key']} label missing from report"
    # Missing dependencies must carry an actionable install hint.
    for s in dependency_status():
        if not s["available"]:
            assert s["install"] in report


def test_core_modules_self_consistent():
    """The harness reads the live guard flags, so this also asserts the new
    feature modules expose the flags the harness expects."""
    import star.feeds, star.translate, star.vocab  # noqa: F401

    by_key = {s["key"]: s for s in dependency_status()}
    for key in ("translate", "feeds", "vocab", "summarize", "flashcards"):
        assert key in by_key


def test_cli_deps_flag_runs():
    """``python -m star --deps`` prints the report and exits cleanly."""
    proc = subprocess.run(
        [sys.executable, "-m", "star", "--deps"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "optional dependency status" in proc.stdout
    assert "Qt GUI" in proc.stdout
