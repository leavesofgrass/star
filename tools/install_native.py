#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provision *star*'s native (non-Python) engines on macOS and Linux.

This is the macOS/Linux counterpart of ``build-vendor.py``.  On Windows the
self-contained ``star.exe`` bundles the native engines from a downloaded
``vendor/`` tree; on macOS and Linux those engines are platform- and
arch-specific and ``star``'s ``_vendor_dir()`` only knows the Windows binary
names, so the supported strategy (see ``BUILD.md``) is to get
them from the **system package manager**.  This helper does exactly that for
the same set of engines ``build-vendor.py`` vendors on Windows:

  * **ffmpeg**     – MP3 / OGG / MP4 audio export
  * **Tesseract** (+ English data) – OCR of images and scanned PDFs
  * **liblouis** (+ tables) – Grade 2 (contracted) Braille
  * **Pandoc**     – high-fidelity markup conversion (RST, Org, LaTeX, ...)
  * **eSpeak-NG**  – offline fallback TTS voice (Linux; macOS uses ``say``)

It only installs what is missing, and prints the exact commands it runs so the
operation is transparent.  The Python packages (PyQt6, pyttsx3, the document
loaders, the ``louis`` binding, ...) come from the wheel / ``pip`` — see
``install.sh`` or ``pip install star-reader[all]``; this script deliberately
covers only the native engines that pip cannot provide.

Usage::

    python tools/install_native.py              # install whatever is missing
    python tools/install_native.py --dry-run     # just print what would run
    python tools/install_native.py --yes         # don't prompt before installing
    python tools/install_native.py ffmpeg pandoc # only the named engines
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Package managers.  ``install`` is the non-interactive install incantation;
# ``update`` (optional) refreshes the package index first; ``sudo`` marks the
# managers that need root (Homebrew must NOT be run with sudo).
# ---------------------------------------------------------------------------
MANAGERS = {
    "brew": {"install": ["brew", "install"], "update": None, "sudo": False},
    "apt": {
        "install": ["apt-get", "install", "-y"],
        "update": ["apt-get", "update"],
        "sudo": True,
    },
    "dnf": {"install": ["dnf", "install", "-y"], "update": None, "sudo": True},
    "pacman": {
        "install": ["pacman", "-S", "--needed", "--noconfirm"],
        "update": ["pacman", "-Sy"],
        "sudo": True,
    },
    "zypper": {
        "install": ["zypper", "--non-interactive", "install"],
        "update": None,
        "sudo": True,
    },
}

# Detection order on Linux (Homebrew is also honored on Linux if present).
_LINUX_MANAGER_ORDER = ["apt", "dnf", "pacman", "zypper", "brew"]

# ---------------------------------------------------------------------------
# Engines.  ``check`` is the binary that proves the engine is available;
# ``pkgs`` maps each package manager to the package name(s) to install.
# ---------------------------------------------------------------------------
ENGINES = {
    "ffmpeg": {
        "check": "ffmpeg",
        "why": "MP3 / OGG / MP4 audio export (WAV works without it)",
        "pkgs": {
            "brew": ["ffmpeg"],
            "apt": ["ffmpeg"],
            "dnf": ["ffmpeg"],
            "pacman": ["ffmpeg"],
            "zypper": ["ffmpeg"],
        },
    },
    "tesseract": {
        "check": "tesseract",
        "why": "OCR of images and scanned PDFs",
        "pkgs": {
            "brew": ["tesseract", "tesseract-lang"],
            "apt": ["tesseract-ocr", "tesseract-ocr-eng"],
            "dnf": ["tesseract", "tesseract-langpack-eng"],
            "pacman": ["tesseract", "tesseract-data-eng"],
            "zypper": ["tesseract-ocr", "tesseract-ocr-traineddata-english"],
        },
    },
    "liblouis": {
        # liblouis ships the lou_translate CLI alongside the shared library and
        # tables; its presence is a good proxy for "Grade 2 Braille will work"
        # once the `louis` Python binding (pip) is installed.
        "check": "lou_translate",
        "why": "Grade 2 (contracted) Braille (Grade 1 BRF is built in)",
        "pkgs": {
            "brew": ["liblouis"],
            "apt": ["liblouis-bin", "liblouis-data"],
            "dnf": ["liblouis", "liblouis-utils"],
            "pacman": ["liblouis"],
            "zypper": ["liblouis-tools", "liblouis-data"],
        },
    },
    "pandoc": {
        "check": "pandoc",
        "why": "high-fidelity markup conversion (RST, Org, LaTeX, ...)",
        "pkgs": {
            "brew": ["pandoc"],
            "apt": ["pandoc"],
            "dnf": ["pandoc"],
            "pacman": ["pandoc"],
            "zypper": ["pandoc"],
        },
    },
    "espeak-ng": {
        "check": "espeak-ng",
        "why": "offline fallback TTS voice",
        "macos": False,  # macOS uses the built-in `say` command instead
        "pkgs": {
            "brew": ["espeak-ng"],
            "apt": ["espeak-ng"],
            "dnf": ["espeak-ng"],
            "pacman": ["espeak-ng"],
            "zypper": ["espeak-ng"],
        },
    },
}

# Engines whose package may live in a third-party repo on some distros.
_NOTES = {
    ("dnf", "ffmpeg"): (
        "ffmpeg on Fedora/RHEL usually needs the RPM Fusion repo; if the "
        "install fails, enable it first:\n"
        "    sudo dnf install "
        "https://download1.rpmfusion.org/free/fedora/"
        "rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm"
    ),
}


def _detect_manager() -> str:
    """Return the name of the package manager to use, or '' if none found."""
    if sys.platform == "darwin":
        return "brew" if shutil.which("brew") else ""
    for name in _LINUX_MANAGER_ORDER:
        tool = MANAGERS[name]["install"][0]
        if shutil.which(tool):
            return name
    return ""


def _engine_applies(name: str) -> bool:
    """Whether an engine is relevant on this platform."""
    spec = ENGINES[name]
    if sys.platform == "darwin" and spec.get("macos") is False:
        return False
    return True


def _with_sudo(cmd: list[str], needs_sudo: bool) -> list[str]:
    """Prefix a command with sudo on Linux when not already root."""
    if needs_sudo and os.geteuid() != 0 and shutil.which("sudo"):
        return ["sudo", *cmd]
    return cmd


def _run(cmd: list[str], dry_run: bool) -> int:
    print("    $ " + " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.run(cmd).returncode


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="install_native.py",
        description=(
            "Install star's native engines (ffmpeg, Tesseract, liblouis, "
            "Pandoc, eSpeak-NG) via the system package manager on macOS/Linux."
        ),
    )
    ap.add_argument(
        "engines",
        nargs="*",
        choices=sorted(ENGINES),
        metavar="ENGINE",
        help="limit to these engines (default: all that apply to this OS)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print commands without running them"
    )
    ap.add_argument(
        "--yes", "-y", action="store_true", help="don't prompt before installing"
    )
    args = ap.parse_args()

    if sys.platform == "win32":
        print(
            "This helper is for macOS and Linux.\n"
            "On Windows the native engines are bundled into the portable "
            "star.exe — run `python build-vendor.py` then build with "
            "build-windows.ps1 (see BUILD.md)."
        )
        return 1
    if sys.platform not in ("darwin", "linux"):
        print(f"Unsupported platform: {sys.platform}. See BUILD.md.")
        return 1

    requested = args.engines or [e for e in ENGINES if _engine_applies(e)]
    requested = [e for e in requested if _engine_applies(e)]

    # Report current status and collect what's missing.
    print(f"Platform: {platform.platform()}")
    missing = []
    for name in requested:
        present = shutil.which(ENGINES[name]["check"]) is not None
        mark = "found" if present else "MISSING"
        print(f"  {name:12s} {mark:8s} — {ENGINES[name]['why']}")
        if not present:
            missing.append(name)

    if not missing:
        print("\nAll requested native engines are already installed.")
        return 0

    mgr = _detect_manager()
    if not mgr:
        if sys.platform == "darwin":
            print(
                "\nNo Homebrew found. Install it from https://brew.sh/ and "
                "re-run, or install the engines manually."
            )
        else:
            print(
                "\nNo supported package manager found "
                "(apt/dnf/pacman/zypper/brew). Install the engines with your "
                "distribution's package manager manually."
            )
        return 1

    spec = MANAGERS[mgr]

    # Build the package list (dedup, preserve order).
    pkgs: list[str] = []
    for name in missing:
        for p in ENGINES[name]["pkgs"].get(mgr, []):
            if p not in pkgs:
                pkgs.append(p)
        note = _NOTES.get((mgr, name))
        if note:
            print(f"\nNote ({name}): {note}")

    if not pkgs:
        print(
            f"\nNo package mapping for '{mgr}' — install manually: {', '.join(missing)}"
        )
        return 1

    print(f"\nUsing package manager: {mgr}")
    print(f"Will install: {', '.join(pkgs)}")

    if not args.yes and not args.dry_run:
        try:
            reply = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            reply = ""
        if reply not in ("y", "yes"):
            print(
                "Aborted. (Re-run with --dry-run to preview, or --yes to skip this prompt.)"
            )
            return 1

    rc = 0
    if spec["update"]:
        rc = _run(_with_sudo(spec["update"], spec["sudo"]), args.dry_run)
    if rc == 0:
        rc = _run(_with_sudo([*spec["install"], *pkgs], spec["sudo"]), args.dry_run)

    if args.dry_run:
        print("\n(dry run — nothing was installed)")
        return 0

    # Re-check and report.
    print()
    still = [n for n in missing if shutil.which(ENGINES[n]["check"]) is None]
    for name in missing:
        ok = shutil.which(ENGINES[name]["check"]) is not None
        print(f"  {name:12s} {'installed' if ok else 'STILL MISSING'}")
    if still:
        print(
            f"\nSome engines could not be installed automatically: {', '.join(still)}"
        )
        return 1
    print("\nNative engines ready. For the Python side, install the wheel or:")
    print("    pip install star-reader[all]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
