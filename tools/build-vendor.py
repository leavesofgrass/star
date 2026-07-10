#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the ``vendor/`` tree of native tools for the self-contained
Windows build of *star*.

It downloads and lays out native engines that are **not** Python packages, so
the single ``star.exe`` can do everything with nothing else installed on the
target machine:

  * **ffmpeg**   – MP3 / OGG / MP4 audio export
  * **Tesseract** (+ English data) – OCR of images and scanned PDFs
  * **liblouis** (+ tables + Python binding) – Grade 2 (contracted) Braille
  * **Pandoc**   – high-fidelity markup conversion (RST, Org, MediaWiki,
                   AsciiDoc, Textile, LaTeX, .doc, ...)
  * **DECtalk**  – the classic DECtalk synthesizer (optional TTS backend)

Resulting layout (mirrored into the PyInstaller bundle root by ``star.spec``;
``star``'s ``_vendor_dir()`` (in ``star/_runtime.py``) finds each tool
here or under ``sys._MEIPASS``)::

    vendor/
      ffmpeg/ffmpeg.exe
      tesseract/            tesseract.exe + *.dll + tessdata/(eng,osd)
      liblouis/
        liblouis.dll
        tables/             *.ctb / *.utb / ...
        louis/__init__.py   ctypes binding (loads $LIBLOUIS_DLL)
      pandoc/pandoc.exe
      dectalk/
        amd64/DECtalk.dll + dtalk_us.dic   (64-bit engine + dictionary)
        ia32/DECtalk.dll  + dtalk_us.dic   (32-bit engine + dictionary)

DECtalk is driven in-process by star's ctypes backend (the classic DECtalk
voices).  Both architectures are vendored so the backend can load the DLL that
matches the star.exe it is bundled into (a 64-bit process cannot load a 32-bit
DLL).  The engine reads ``dtalk_us.dic`` from the DLL's own folder, which is why
the dictionary is kept beside each ``DECtalk.dll``.

Usage::

    python build-vendor.py               # fetch anything missing
    python build-vendor.py --force       # re-fetch everything
    python build-vendor.py --no-dectalk  # omit DECtalk (public-release builds)

DECtalk is a commercial synthesizer mirrored on a community GitHub release; it
is fine for a private/personal build but must NOT be redistributed in a public
GitHub Release artifact — pass ``--no-dectalk`` for the CI/public exe.  The
whole ``vendor/`` tree is bundled by ``star.spec`` via a directory walk, so
simply not fetching DECtalk keeps it out of the frozen app (star's DECtalk
backend then reports itself unavailable, exactly as on any machine without it).

Requirements: internet access, and **7-Zip** (``7z.exe``) to unpack the
Tesseract installer (its NSIS installer otherwise demands UAC elevation).
Run this once before ``pyinstaller --clean star.spec``.
"""

import io
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

# This script lives in tools/, but vendor/ belongs at the project root (one
# level up) so star.spec and star's _vendor_dir() find it.
VENDOR = Path(__file__).resolve().parent.parent / "vendor"
_UA = {"User-Agent": "Mozilla/5.0"}

# ffmpeg: gyan.dev "essentials" build (static, includes libmp3lame/libvorbis/AAC).
# The URL is version-agnostic (always the current release).
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# Tesseract: UB-Mannheim Windows installer (pinned for reproducibility).
TESSERACT_URL = (
    "https://digi.bib.uni-mannheim.de/tesseract/"
    "tesseract-ocr-w64-setup-5.4.0.20240606.exe"
)

# liblouis: official GitHub release (win64 binaries + source for the binding).
LOUIS_VERSION = "3.38.0"
LOUIS_BASE = f"https://github.com/liblouis/liblouis/releases/download/v{LOUIS_VERSION}/"

# Pandoc: official GitHub release (single self-contained Windows binary).
PANDOC_VERSION = "3.10"
PANDOC_URL = (
    f"https://github.com/jgm/pandoc/releases/download/{PANDOC_VERSION}/"
    f"pandoc-{PANDOC_VERSION}-windows-x86_64.zip"
)

# DECtalk: community-maintained GitHub release.  The vs2022 build ships both
# 64-bit (AMD64) and 32-bit (IA32) DECtalk.dll + dtalk_us.dic, so the in-process
# ctypes backend can load whichever matches the star.exe architecture.
DECTALK_VERSION = "2023-10-30"
DECTALK_URL = (
    f"https://github.com/dectalk/dectalk/releases/download/{DECTALK_VERSION}/vs2022.zip"
)

# eSpeak-NG: official Windows installer.  Provides the 64-bit ``libespeak-ng.dll``
# and the ``espeak-ng-data`` tree, which star drives in-process via ctypes for
# real, audio-position-tagged word events (used to keep the reading highlight in
# sync with playback).  1.52.0 is the first release that ships a 64-bit DLL.
ESPEAK_VERSION = "1.52.0"
ESPEAK_URL = (
    f"https://github.com/espeak-ng/espeak-ng/releases/download/{ESPEAK_VERSION}/"
    "espeak-ng.msi"
)


def _download(url: str) -> bytes:
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=900).read()


def _find_7zip() -> str:
    for cand in (
        shutil.which("7z"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ):
        if cand and Path(cand).is_file():
            return cand
    return ""


def fetch_ffmpeg(force: bool) -> None:
    dst = VENDOR / "ffmpeg" / "ffmpeg.exe"
    if dst.is_file() and not force:
        print("ffmpeg: already present")
        return
    print("ffmpeg: fetching ...")
    z = zipfile.ZipFile(io.BytesIO(_download(FFMPEG_URL)))
    name = next(n for n in z.namelist() if n.endswith("bin/ffmpeg.exe"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with z.open(name) as src, open(dst, "wb") as out:
        shutil.copyfileobj(src, out)
    print(f"  -> {dst}  ({dst.stat().st_size // (1024 * 1024)} MB)")


def fetch_tesseract(force: bool) -> None:
    dst = VENDOR / "tesseract"
    if (dst / "tesseract.exe").is_file() and not force:
        print("tesseract: already present")
        return
    sevenzip = _find_7zip()
    if not sevenzip:
        sys.exit(
            "ERROR: 7-Zip is required to unpack the Tesseract installer.\n"
            "Install it from https://www.7-zip.org/ and re-run."
        )
    print("tesseract: fetching ...")
    VENDOR.mkdir(parents=True, exist_ok=True)
    setup = VENDOR / "tesseract-setup.exe"
    setup.write_bytes(_download(TESSERACT_URL))
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    print("  extracting with 7-Zip ...")
    subprocess.run(
        [sevenzip, "x", str(setup), "-o" + str(dst), "-y"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    setup.unlink(missing_ok=True)
    # Prune training tools, docs, and Java helpers — keep the engine, its DLLs,
    # and the language data (eng + osd).
    for d in ("$PLUGINSDIR", "doc"):
        shutil.rmtree(dst / d, ignore_errors=True)
    for f in list(dst.iterdir()):
        if not f.is_file():
            continue
        low = f.name.lower()
        if low.endswith((".html", ".jar")):
            f.unlink()
        elif low.endswith(".exe") and f.name != "tesseract.exe":
            f.unlink()
    tessdata = dst / "tessdata"
    if tessdata.is_dir():
        for j in tessdata.glob("*.jar"):
            j.unlink()
    print(f"  -> {dst}  (tesseract.exe + DLLs + tessdata: eng, osd)")


def fetch_liblouis(force: bool) -> None:
    dst = VENDOR / "liblouis"
    have = (dst / "liblouis.dll").is_file() and (
        dst / "louis" / "__init__.py"
    ).is_file()
    if have and not force:
        print("liblouis: already present")
        return
    print("liblouis: fetching ...")
    (dst / "tables").mkdir(parents=True, exist_ok=True)
    (dst / "louis").mkdir(parents=True, exist_ok=True)

    # 1) win64 binaries: liblouis.dll + the translation tables.
    zb = zipfile.ZipFile(
        io.BytesIO(_download(LOUIS_BASE + f"liblouis-{LOUIS_VERSION}-win64.zip"))
    )
    with zb.open("bin/liblouis.dll") as src, open(dst / "liblouis.dll", "wb") as out:
        shutil.copyfileobj(src, out)
    n_tables = 0
    for n in zb.namelist():
        if n.startswith("share/liblouis/tables/") and not n.endswith("/"):
            target = dst / "tables" / os.path.basename(n)
            with zb.open(n) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            n_tables += 1

    # 2) Python binding: generate louis/__init__.py from the source template,
    #    swapping the compile-time SONAME for a runtime lookup of $LIBLOUIS_DLL
    #    (which star points at the bundled DLL).
    zs = zipfile.ZipFile(
        io.BytesIO(_download(LOUIS_BASE + f"liblouis-{LOUIS_VERSION}.zip"))
    )
    tin = next(n for n in zs.namelist() if n.endswith("python/louis/__init__.py.in"))
    txt = zs.read(tin).decode("utf-8")
    old = 'liblouis = _loader["###LIBLOUIS_SONAME###"]'
    new = (
        "import os as _os\n"
        'liblouis = _loader[_os.environ.get("LIBLOUIS_DLL", "liblouis")]'
    )
    if old not in txt:
        sys.exit(
            "ERROR: liblouis binding template changed; update build-vendor.py "
            "(could not find the DLL load line to patch)."
        )
    txt = txt.replace(old, new)
    if "###" in txt:
        sys.exit("ERROR: unsubstituted placeholder remains in louis/__init__.py")
    (dst / "louis" / "__init__.py").write_text(txt, encoding="utf-8")
    print(f"  -> {dst}  (liblouis.dll + {n_tables} tables + Python binding)")


def fetch_pandoc(force: bool) -> None:
    dst = VENDOR / "pandoc" / "pandoc.exe"
    if dst.is_file() and not force:
        print("pandoc: already present")
        return
    print("pandoc: fetching ...")
    z = zipfile.ZipFile(io.BytesIO(_download(PANDOC_URL)))
    name = next(n for n in z.namelist() if n.endswith("pandoc.exe"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with z.open(name) as src, open(dst, "wb") as out:
        shutil.copyfileobj(src, out)
    print(f"  -> {dst}  ({dst.stat().st_size // (1024 * 1024)} MB)")


def fetch_dectalk(force: bool) -> None:
    dst = VENDOR / "dectalk"
    if (dst / "amd64" / "DECtalk.dll").is_file() and not force:
        print("dectalk: already present")
        return
    print("dectalk: fetching ...")
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    z = zipfile.ZipFile(io.BytesIO(_download(DECTALK_URL)))
    # The archive holds per-arch trees (``AMD64/`` and ``IA32/``).  star's
    # in-process backend loads the DLL whose architecture matches star.exe and
    # chdirs into its folder so the engine finds dtalk_us.dic, so keep the
    # engine DLL + dictionary (and the language DLL) split by architecture.
    keep = {"dectalk.dll", "dtalk_us.dic", "dtalk_us.dll"}
    counts = {"amd64": 0, "ia32": 0}
    for n in z.namelist():
        if n.endswith("/"):
            continue
        low = n.lower()
        if "amd64" in low:
            arch = "amd64"
        elif "ia32" in low or "win32" in low or "x86" in low:
            arch = "ia32"
        else:
            continue
        base = os.path.basename(n)
        if base.lower() not in keep:
            continue
        out_dir = dst / arch
        out_dir.mkdir(parents=True, exist_ok=True)
        with z.open(n) as src, open(out_dir / base, "wb") as out:
            shutil.copyfileobj(src, out)
        counts[arch] += 1
    print(f"  -> {dst}  (amd64: {counts['amd64']} files, ia32: {counts['ia32']} files)")
    if not (dst / "amd64" / "DECtalk.dll").is_file():
        print(
            "  NOTE: no AMD64 DECtalk.dll was found in the archive; a 64-bit\n"
            "        star.exe needs it.  Check the DECtalk release layout if the\n"
            "        DECtalk voice does not appear."
        )


def fetch_espeak(force: bool) -> None:
    dst = VENDOR / "espeak-ng"
    have = (dst / "libespeak-ng.dll").is_file() and (dst / "espeak-ng-data").is_dir()
    if have and not force:
        print("espeak-ng: already present")
        return
    if sys.platform != "win32":
        # The vendored DLL is a Windows binary for the self-contained star.exe.
        # On macOS/Linux, eSpeak-NG comes from the system package manager
        # (tools/install_native.py), so nothing is vendored here.
        print("espeak-ng: skipped (Windows-only vendoring)")
        return
    print("espeak-ng: fetching ...")
    VENDOR.mkdir(parents=True, exist_ok=True)
    msi = VENDOR / "espeak-ng.msi"
    msi.write_bytes(_download(ESPEAK_URL))
    # The MSI keeps its directory tree in the MSI tables, which a plain 7-Zip
    # extraction flattens (destroying espeak-ng-data/'s sub-structure).  An
    # administrative install (``msiexec /a``) reconstructs the real tree, needs
    # no elevation, and makes no system changes — it just lays the files out.
    work = VENDOR / "_espeak_msi"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    print("  extracting with msiexec /a ...")
    rc = subprocess.run(
        ["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={work}"],
        check=False,
    ).returncode
    # msiexec may hand off to the Windows Installer service and return before
    # the files are fully written, so poll briefly for the expected output.
    deadline = time.monotonic() + 60.0
    dll_src = None
    while time.monotonic() < deadline:
        dll_src = next((p for p in work.rglob("libespeak-ng.dll")), None)
        if dll_src and (dll_src.parent / "espeak-ng-data").is_dir():
            break
        time.sleep(0.5)
    if dll_src is None or not (dll_src.parent / "espeak-ng-data").is_dir():
        msi.unlink(missing_ok=True)
        shutil.rmtree(work, ignore_errors=True)
        sys.exit(
            f"ERROR: msiexec admin-extract of espeak-ng.msi failed (rc={rc}); "
            "libespeak-ng.dll / espeak-ng-data not found."
        )
    src_dir = dll_src.parent  # the "eSpeak NG" folder
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dll_src, dst / "libespeak-ng.dll")
    shutil.copytree(src_dir / "espeak-ng-data", dst / "espeak-ng-data")
    msi.unlink(missing_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    n = sum(1 for _ in (dst / "espeak-ng-data").rglob("*") if _.is_file())
    print(f"  -> {dst}  (libespeak-ng.dll + espeak-ng-data: {n} files)")


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    include_dectalk = "--no-dectalk" not in args
    fetch_ffmpeg(force)
    fetch_tesseract(force)
    fetch_liblouis(force)
    fetch_pandoc(force)
    if include_dectalk:
        fetch_dectalk(force)
    else:
        print("dectalk: skipped (--no-dectalk; excluded from public builds)")
    fetch_espeak(force)
    total = sum(f.stat().st_size for f in VENDOR.rglob("*") if f.is_file())
    print(f"\nvendor/ ready at {VENDOR}  ({total // (1024 * 1024)} MB)")
    print("Next: python -m PyInstaller --clean --noconfirm star.spec")


if __name__ == "__main__":
    main()
