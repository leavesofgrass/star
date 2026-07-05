#!/usr/bin/env python3
"""Build a fat, single-file ``star.pyz`` (a self-extracting zipapp).

    Build:   python build_zipapp.py
    Output:  dist/star.pyz
    Run:     python dist/star.pyz   (e.g. python dist/star.pyz --list-themes)

WHAT THIS PRODUCES, AND WHAT IT IS NOT
--------------------------------------
This bundles star's own code **plus** its Python dependencies (the ``all``
extras group, read from pyproject.toml at build time -- never hardcoded here)
into one ``star.pyz`` file.  It exists so a user can go from

    "needs Python + the system binaries on PATH, AND a pip install step"

down to

    "needs Python + the system binaries on PATH" (no pip install step).

It removes the *packaging* step, not the system-dependency story.  It is
explicitly **not** a replacement for the PyInstaller ``star.exe`` (see
``star.spec``): that artifact additionally bundles the system binaries star
shells out to -- ffmpeg, Tesseract, liblouis, eSpeak-NG, DECtalk -- which is
not achievable in a zipapp.  Those binaries must still be on PATH to use the
features that need them.

THE COMPILED-EXTENSION PROBLEM (and how it is handled)
------------------------------------------------------
Some of star's dependencies ship compiled extension modules (PyQt6, pymupdf,
and possibly the native bindings under pytesseract/louis).  Python's
``zipimport`` cannot import a compiled ``.so``/``.pyd``/``.dylib`` straight out
of a zip -- those need to be real files on disk.  So a naive
``pip install --target staging/ .[all]`` followed by zipping ``staging/`` would
build cleanly but fail at runtime.

We use the self-extracting bootstrap approach (the same idea as ``shiv``):
the dependency tree is stored as *data* under ``_payload/`` inside the zip and
is never imported from there.  A tiny pure-Python ``__main__.py``
(``tools/zipapp_bootstrap.py``) extracts it once to a per-user cache directory
(mirroring star's own platform config-path convention), adds it to sys.path,
and then runs ``star.app.main``.  The bootstrap is hand-rolled rather than
pulling in ``shiv`` as a build dependency, both to keep the build free of new
third-party requirements and so the extraction cache matches star's existing
``_CFG_ROOT`` path scheme exactly.

CONSEQUENCE: because it bundles compiled extensions, ``star.pyz`` is
**platform-specific** -- a build made on Linux runs only on Linux, etc.  Build
one per target platform.  (This is the trade-off for genuine single-file
portability; a thin, pure-Python zipapp would be cross-platform but could not
carry PyQt6/pymupdf.)
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOTSTRAP = ROOT / "tools" / "zipapp_bootstrap.py"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
STAGING_DIR = BUILD_DIR / "zipapp-staging"
OUTPUT = DIST_DIR / "star.pyz"

# Where the bundled tree is stored inside the zip (as data, never imported
# from there).  Must stay in sync with tools/zipapp_bootstrap.py.
PAYLOAD_PREFIX = "_payload/"


def info(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def run(cmd: list) -> None:
    info(" ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def clean_staging() -> None:
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    # setuptools' in-tree build reuses build/lib and never prunes deleted
    # modules, so pre-refactor monoliths (markup.py, ttstext.py, …) leaked
    # into every locally built wheel — and into shipped pyz builds.  Purge
    # it before any pip wheel/install step so the wheel matches the tree.
    shutil.rmtree(ROOT / "build" / "lib", ignore_errors=True)


def pip_install_all() -> None:
    """Install star plus the ``all`` extras into the staging directory.

    ``".[all]"`` makes pip resolve the extras group straight from
    pyproject.toml, so the exact dependency list is never duplicated here.
    Real platform wheels for the building machine are used.
    """
    # Point pip's scratch space at a short path under build/.  On Windows a
    # long TEMP path makes pip switch to the ``\\?\`` extended-length prefix,
    # which the OS will not normalize -- and pip lays out console scripts via a
    # relative ``lib/python/../../bin`` path, so the unnormalizable ``..`` then
    # fails with ``[Errno 22] Invalid argument`` (e.g. on XlsxWriter's
    # vba_extract script).  A short temp dir keeps paths under MAX_PATH so the
    # prefix is never applied.
    tmpdir = BUILD_DIR / "pip-tmp"
    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["TMP"] = env["TEMP"] = env["TMPDIR"] = str(tmpdir)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(STAGING_DIR),
        f"{ROOT}[all]",
    ]
    info(" ".join(str(c) for c in cmd))
    try:
        subprocess.run(cmd, check=True, env=env)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def iter_payload_files():
    """Yield (absolute_path, archive_relative_path) for every staged file."""
    for path in sorted(STAGING_DIR.rglob("*")):
        if path.is_file():
            yield path, path.relative_to(STAGING_DIR).as_posix()


def compute_build_id() -> str:
    """A stable id for this build: platform + Python + a content hash.

    Naming the extraction cache after this id means a freshly built .pyz
    re-extracts instead of silently reusing an older bundle.
    """
    digest = hashlib.sha256()
    for abs_path, rel in iter_payload_files():
        digest.update(rel.encode("utf-8"))
        digest.update(str(abs_path.stat().st_size).encode("utf-8"))
    short = digest.hexdigest()[:12]
    pyver = f"py{sys.version_info.major}{sys.version_info.minor}"
    return f"{sys.platform}-{pyver}-{short}"


def build_pyz(build_id: str) -> None:
    """Assemble the .pyz atomically: write to a temp file, then publish."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    bootstrap_src = BOOTSTRAP.read_text(encoding="utf-8")

    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".star-", suffix=".pyz", dir=str(DIST_DIR)
    )
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        with open(tmp_path, "wb") as f:
            # Shebang so the file is also directly executable on Unix
            # (chmod +x star.pyz; ./star.pyz).  zip readers tolerate the
            # prepended line, exactly as the stdlib ``zipapp`` does.
            f.write(b"#!/usr/bin/env python3\n")
            with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("__main__.py", bootstrap_src)
                zf.writestr(PAYLOAD_PREFIX + ".build_id", build_id)
                count = 0
                for abs_path, rel in iter_payload_files():
                    zf.write(abs_path, PAYLOAD_PREFIX + rel)
                    count += 1
        info(f"Bundled {count} payload files (build id: {build_id})")
        try:
            os.chmod(tmp_path, 0o755)
        except OSError:
            pass
        os.replace(str(tmp_path), str(OUTPUT))
        tmp_path = None
    finally:
        # Never leave a partial/corrupt artifact behind.
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _extracted_cache_dir(build_id: str) -> Path:
    """Where the bootstrap extracts the payload (mirrors zipapp_bootstrap)."""
    app = "star"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        root = Path(base) / app
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / app
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        root = Path(base) / app
    return root / "zipapp" / build_id


def _verify_compiled_extensions(build_id: str) -> None:
    """Prove the *compiled* dependencies actually load from the extraction.

    ``--list-themes`` alone is not enough: star imports PyQt6/PyMuPDF under
    guarded ``try/except``, so a silently-failed compiled-extension import
    would not change its exit code.  Here we import those extensions directly
    from the extracted cache and fail loudly if any does not load -- this is
    what genuinely catches a broken compiled-extension bootstrap.
    """
    extracted = _extracted_cache_dir(build_id)
    if not extracted.is_dir():
        raise RuntimeError(f"extraction cache not found: {extracted}")
    checks = (
        "import PyQt6.QtCore, fitz; print('compiled-ok', PyQt6.QtCore.PYQT_VERSION_STR)"
    )
    code = f"import sys; sys.path.insert(0, {str(extracted)!r}); {checks}"
    info("Smoke test: importing compiled extensions (PyQt6, PyMuPDF) from cache")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0 or "compiled-ok" not in (proc.stdout or ""):
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        raise RuntimeError(
            "compiled-extension import failed -- the fat zipapp bootstrap is "
            f"broken (exit {proc.returncode}); stderr={(proc.stderr or '').strip()!r}"
        )
    info(f"Compiled extensions OK -- {(proc.stdout or '').strip()}")


def smoke_test(build_id: str) -> None:
    """Run the built .pyz and verify it actually works end to end.

    This is the step that catches a broken compiled-extension bootstrap: a
    .pyz can look fine yet fail to import PyQt6/PyMuPDF at runtime.  First we
    run ``--list-themes`` (which forces the extract-and-import path and exits
    cleanly), then we directly confirm the compiled extensions load.
    """
    info(f"Smoke test: {OUTPUT.name} --list-themes")
    proc = subprocess.run(
        [sys.executable, str(OUTPUT), "--list-themes"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or not out:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        raise RuntimeError(
            f"smoke test failed (exit {proc.returncode}); "
            f"stdout={out!r} stderr={(proc.stderr or '').strip()!r}"
        )
    themes = ", ".join(out.split())
    info(f"Smoke test OK -- themes: {themes}")
    _verify_compiled_extensions(build_id)


def _cleanup_build_artifacts() -> None:
    """Remove transient build leftovers, preserving unrelated build/ contents.

    ``pip install .[all]`` builds star's own wheel in-tree, so setuptools
    drops ``build/lib``, ``build/bdist.*`` and ``star_reader.egg-info`` into
    the project.  Clean those plus our staging/temp dirs, but leave anything
    else under build/ alone (e.g. the PyInstaller ``build/whisper_cache``).
    """
    for path in (
        STAGING_DIR,
        BUILD_DIR / "pip-tmp",
        BUILD_DIR / "lib",
        ROOT / "star_reader.egg-info",
    ):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    if BUILD_DIR.exists():
        for child in BUILD_DIR.glob("bdist.*"):
            shutil.rmtree(child, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a fat star.pyz zipapp.")
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Do not delete the staging directory afterward (for debugging).",
    )
    parser.add_argument(
        "--no-smoke-test",
        action="store_true",
        help="Skip the post-build smoke test (not recommended).",
    )
    args = parser.parse_args()

    if not BOOTSTRAP.is_file():
        raise FileNotFoundError(f"bootstrap not found: {BOOTSTRAP}")

    try:
        info("Creating clean staging directory")
        clean_staging()
        info("Installing star and the [all] extras into staging")
        pip_install_all()
        build_id = compute_build_id()
        info("Assembling star.pyz")
        build_pyz(build_id)
        if not args.no_smoke_test:
            smoke_test(build_id)
    finally:
        if not args.keep_staging:
            _cleanup_build_artifacts()

    info(f"Done: {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"\nERROR: command failed with exit code {exc.returncode}\n")
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001 -- fail loudly, non-zero, no partial artifact
        sys.stderr.write(f"\nERROR: {exc}\n")
        raise SystemExit(1)
