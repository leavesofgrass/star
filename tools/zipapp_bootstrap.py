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

import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# Files bundled as data (not imported in place) live under this prefix.
_PAYLOAD_PREFIX = "_payload/"
_BUILD_ID_MEMBER = "_payload/.build_id"
_APP_NAME = "star"


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


def main() -> None:
    site = _ensure_extracted(_archive_path())
    sys.path.insert(0, str(site))
    from star.app import main as _star_main

    _star_main()


if __name__ == "__main__":
    main()
