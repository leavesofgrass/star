"""Bootstrap entry point embedded as ``__main__.py`` inside ``star.pyz``.

This module is what runs first when you execute the fat zipapp::

    python star.pyz

WHY A BOOTSTRAP INSTEAD OF A PLAIN ZIPAPP
-----------------------------------------
A "thin" zipapp can run modules straight out of the zip via ``zipimport``.
That only works for *pure-Python* code.  Several of star's dependencies ship
compiled extension modules (``.so`` / ``.pyd`` / ``.dylib``) -- notably PyQt6
and PyMuPDF (``pymupdf``), and potentially the native bindings behind
``pytesseract``/``louis``.  Python's ``zipimport`` cannot load a compiled
extension directly out of a zip: the OS dynamic loader needs a real file on
disk.  A naive ``zipapp`` over a ``pip install --target`` tree therefore builds
cleanly but blows up at import time the moment one of those packages is touched.

To get genuine single-file portability we bundle the whole dependency tree as
*data* under the ``_payload/`` prefix inside the zip (it is never imported from
there), and on first run this bootstrap extracts that tree to a per-user cache
directory, puts it on ``sys.path``, and only then imports star.  This is the
same trick ``shiv`` uses; it is hand-rolled here to avoid adding a third-party
runtime/build dependency and so the extraction cache can mirror star's own
platform-specific config path convention exactly (see ``_cfg_root`` below).

IMPORTANT LIMITATIONS (documented at the source on purpose)
-----------------------------------------------------------
* A fat zipapp that bundles compiled extensions is **platform-specific**.  The
  ``.pyz`` produced on Linux contains Linux ``.so`` files and will not run on
  Windows or macOS, and vice versa.  Build one per platform you need.
* This does **not** bundle the system binaries star can shell out to
  (ffmpeg, Tesseract, liblouis, eSpeak-NG, DECtalk).  Those must still be on
  ``PATH``.  The fat zipapp removes the ``pip install`` step, not the
  system-dependency story.  (The self-contained PyInstaller ``star.exe`` is the
  artifact that bundles system binaries -- this is deliberately not that.)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Files bundled as data (not imported in place) live under this prefix.
_PAYLOAD_PREFIX = "_payload/"
_BUILD_ID_MEMBER = "_payload/.build_id"
_APP_NAME = "star"

# Private-artifact members (absent from the plain dependency-only star.pyz, so
# everything below is a no-op there).  See build_zipapp.py --private.
_VENDOR_PREFIX = "_vendor/"      # native Windows engines (bundle mode)
_DOCS_PREFIX = "_docs/"          # README / CHANGELOG / LICENSE / docs tree
_MANIFEST_MEMBER = "_private/manifest.json"
_BUILDVENDOR_MEMBER = "_private/build-vendor.py"  # fetch-on-first-run helper


def _archive_path() -> str:
    """Absolute path to the running ``star.pyz`` archive."""
    loader = globals().get("__loader__", None)
    archive = getattr(loader, "archive", None)
    if archive:
        return archive
    # Fallback: __file__ is ``.../star.pyz/__main__.py`` when run from a zip.
    return os.path.dirname(os.path.abspath(__file__))


def _cfg_root() -> Path:
    """Per-user config/cache root, mirroring ``star._runtime._CFG_ROOT``.

    Kept in sync with ``star/_runtime.py`` by hand: this bootstrap cannot
    import star, because star lives in the not-yet-extracted payload.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / _APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / _APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / _APP_NAME


def _ensure_extracted(archive: str) -> Path:
    """Extract the bundled dependency tree once and return its directory."""
    with zipfile.ZipFile(archive) as zf:
        try:
            build_id = zf.read(_BUILD_ID_MEMBER).decode("utf-8").strip()
        except KeyError:
            build_id = "unknown"

        target = _cfg_root() / "zipapp" / build_id
        marker = target / ".complete"
        if marker.is_file():
            return target

        target.parent.mkdir(parents=True, exist_ok=True)
        # Extract into a sibling temp dir, then atomically publish, so a
        # crashed or concurrent run can never leave a half-populated cache
        # that a later run would mistake for complete.
        tmp = Path(tempfile.mkdtemp(prefix="star-zipapp-", dir=str(target.parent)))
        try:
            for member in zf.namelist():
                if not member.startswith(_PAYLOAD_PREFIX) or member.endswith("/"):
                    continue
                rel = member[len(_PAYLOAD_PREFIX) :]
                if not rel or rel == ".build_id":
                    continue
                dest = tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
            (tmp / ".complete").write_text("ok", encoding="utf-8")
            try:
                os.replace(str(tmp), str(target))
                tmp = None  # published; nothing left to clean up
            except OSError:
                # Another process won the race (target now exists), or the
                # rename failed across a quirk.  If a complete cache is
                # present, use it; otherwise re-raise.
                if not marker.is_file():
                    raise
        finally:
            if tmp is not None and tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
        return target


def _read_build_id(archive: str) -> str:
    try:
        with zipfile.ZipFile(archive) as zf:
            return zf.read(_BUILD_ID_MEMBER).decode("utf-8").strip()
    except (KeyError, OSError):
        return "unknown"


def _extract_prefix(zf: zipfile.ZipFile, prefix: str, dest: Path) -> bool:
    """Extract every member under *prefix* into *dest* (atomic temp+replace).

    Returns True if any file was written.  The destination is replaced wholesale
    so a rebuilt artifact never leaves stale files behind."""
    members = [m for m in zf.namelist() if m.startswith(prefix) and not m.endswith("/")]
    if not members:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="star-extract-", dir=str(dest.parent)))
    try:
        for m in members:
            rel = m[len(prefix):]
            if not rel:
                continue
            out = tmp / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m) as src, open(out, "wb") as o:
                shutil.copyfileobj(src, o)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        os.replace(str(tmp), str(dest))
        tmp = None
    finally:
        if tmp is not None and Path(tmp).exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return True


def _should_skip_fetch() -> bool:
    """True when a first-run engine download should be skipped: explicitly
    disabled, or a quick CLI command that needs no native engines (so we never
    download hundreds of MB just to print --version / --list-themes)."""
    if os.environ.get("STAR_SKIP_VENDOR_FETCH"):
        return True
    quick = {
        "--version", "-V", "--list-themes", "--list-backends", "--list-voices",
        "--deps", "--help", "-h", "--plain", "--keytest",
    }
    return any(a in quick for a in sys.argv[1:])


def _run_first_run_fetch(zf: zipfile.ZipFile, vroot: Path) -> None:
    """Fetch-on-first-run: run the bundled build-vendor.py into *vroot*.

    Best effort — engines that fail (e.g. Tesseract with no 7-Zip on the target)
    are skipped; the features that need them degrade gracefully.  star runs
    regardless."""
    try:
        script_bytes = zf.read(_BUILDVENDOR_MEMBER)
    except KeyError:
        return
    sys.stderr.write(
        "star: first run — downloading native engines (ffmpeg, Pandoc, eSpeak-NG, "
        "DECtalk, …). This happens once.\n"
    )
    tmpdir = Path(tempfile.mkdtemp(prefix="star-fetch-"))
    script = tmpdir / "build-vendor.py"
    script.write_bytes(script_bytes)
    vroot.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [sys.executable, str(script), "--dest", str(vroot), "--best-effort"],
            check=False,
        )
    except Exception:  # noqa: BLE001 — never let a failed fetch abort launch
        pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if any(vroot.rglob("*")):
        (vroot / ".complete").write_text("ok", encoding="utf-8")


def _setup_vendor(archive: str, build_id: str) -> None:
    """Make the private artifact's native engines available via STAR_VENDOR_DIR.

    Bundle mode: extract the bundled ``_vendor/`` tree once.  Fetch mode:
    download on first run.  No manifest (plain star.pyz) → no-op."""
    vroot = _cfg_root() / "vendor" / build_id
    if (vroot / ".complete").is_file():
        os.environ.setdefault("STAR_VENDOR_DIR", str(vroot))
        return
    with zipfile.ZipFile(archive) as zf:
        try:
            manifest = json.loads(zf.read(_MANIFEST_MEMBER).decode("utf-8"))
        except (KeyError, ValueError):
            return  # not a private artifact
        if manifest.get("has_vendor"):
            # Bundle mode: cheap, local extraction — always do it.
            if _extract_prefix(zf, _VENDOR_PREFIX, vroot):
                (vroot / ".complete").write_text("ok", encoding="utf-8")
        elif manifest.get("mode") == "fetch":
            if _should_skip_fetch():
                return  # quick command / disabled — don't download engines now
            _run_first_run_fetch(zf, vroot)
    if vroot.is_dir() and any(vroot.iterdir()):
        os.environ["STAR_VENDOR_DIR"] = str(vroot)


def _setup_docs(archive: str, build_id: str) -> None:
    """Extract the bundled documentation once to ``<cfg>/docs``."""
    dest = _cfg_root() / "docs"
    if (dest / f".{build_id}").is_file():
        return
    with zipfile.ZipFile(archive) as zf:
        if _extract_prefix(zf, _DOCS_PREFIX, dest):
            (dest / f".{build_id}").write_text("ok", encoding="utf-8")


def main() -> None:
    archive = _archive_path()
    build_id = _read_build_id(archive)
    site = _ensure_extracted(archive)
    sys.path.insert(0, str(site))
    # Private-artifact setup (no-ops for the plain dependency-only star.pyz).
    # Never let optional setup abort the launch.
    try:
        _setup_vendor(archive, build_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        _setup_docs(archive, build_id)
    except Exception:  # noqa: BLE001
        pass
    from star.app import main as _star_main

    _star_main()


if __name__ == "__main__":
    main()
