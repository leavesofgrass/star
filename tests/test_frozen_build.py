"""Regression guards for the frozen-build (PyInstaller) failure classes.

Three bugs shipped in the first standalone star.exe because a dependency was
silently absent or a subprocess popped a console; these tests pin the fixes:

* autodeps must be fully OFF in a frozen bundle — sys.executable IS star.exe,
  so "spawn pip" would relaunch star once per package and install nothing;
* every subprocess star spawns must pass creationflags=_SUBPROCESS_FLAGS, or
  a windowed build flashes a focus-stealing console per pandoc/ffmpeg/espeak
  call (the flag is 0 on POSIX, so this is safe to require unconditionally).
"""
import re
from pathlib import Path

from star import autodeps

STAR_DIR = Path(__file__).resolve().parent.parent / "star"


# ── autodeps in a frozen bundle ──────────────────────────────────────────────


def test_autodeps_disabled_when_frozen(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert autodeps.enabled() is False
    # Even the explicit user-initiated path must refuse: there is no pip.
    assert autodeps.install_now([("nosuchpkg", "nosuchpkg")]) is False


def test_autodeps_frozen_beats_the_override(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    autodeps.set_enabled(True)
    try:
        assert autodeps.enabled() is False
    finally:
        autodeps.set_enabled(None)


# ── console-window suppression on every subprocess ───────────────────────────

_CALL_RE = re.compile(r"subprocess\.(run|Popen|check_output|check_call|call)\(")


def _matching_paren(text: str, open_idx: int) -> int:
    depth, i, n = 0, open_idx, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        if c == "#":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise AssertionError("unbalanced parens")


def test_every_subprocess_call_suppresses_the_console_window():
    offenders = []
    for path in STAR_DIR.rglob("*.py"):
        src = path.read_text(encoding="utf-8", errors="replace")
        for m in _CALL_RE.finditer(src):
            open_idx = m.end() - 1
            seg = src[open_idx + 1 : _matching_paren(src, open_idx)]
            if "creationflags" not in seg:
                line = src[: m.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(STAR_DIR.parent)}:{line}")
    assert not offenders, (
        "subprocess call(s) without creationflags=_SUBPROCESS_FLAGS — in a "
        "windowed build each one flashes a focus-stealing console window:\n  "
        + "\n  ".join(offenders)
    )
