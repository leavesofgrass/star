#!/usr/bin/env bash
# =============================================================================
# build-appimage.sh — build a self-contained Linux star.AppImage.
# =============================================================================
#
# OPTIONAL packaging helper, invoked by the `linux-appimage` job in
# .github/workflows/release.yml (and runnable locally on Linux).  It uses
# python-appimage to bundle a relocatable CPython runtime + the `star-reader`
# wheel (with the [all] extras) into a single executable AppImage that runs on
# most modern Linux distributions with no install step and no system Python.
#
# The wheel remains the primary distribution channel; the AppImage is a
# convenience artifact for users who want a "download and run" binary.  No
# signing is performed here — AppImages are conventionally distributed alongside
# a detached GPG signature, which the separate `sign-artifacts` job provides.
#
# See docs/PACKAGING.md → "Linux AppImage".
set -euo pipefail

mkdir -p dist build/appimage

# python-appimage builds an AppImage from a "recipe" (an entrypoint + a list of
# pip requirements).  We install it, then point it at the local project so the
# AppImage carries the exact source in this checkout (plus the [all] extras).
echo "==> Installing python-appimage"
python -m pip install --upgrade pip python-appimage >/dev/null

# Resolve the version for the output filename.  Parse pyproject.toml rather
# than importing star (a bare build container may lack the runtime deps).
VERSION="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || echo 0.0.0)"
echo "==> Building star $VERSION AppImage"

# A minimal python-appimage recipe: a desktop entry + an entrypoint that runs
# the star module, and a requirements file that installs the project itself.
RECIPE_DIR="build/appimage/recipe"
mkdir -p "$RECIPE_DIR"

# Icon: REQUIRED by appimagetool (the .desktop names Icon=star, and the build
# aborts if star.png is absent).  The repo is deliberately asset-free (GUI
# icons are QPainter-drawn), so render a 256×256 PNG here with pure stdlib —
# a dark rounded tile with the app's orange five-pointed star.
python - "$RECIPE_DIR/star.png" <<'ICON'
import math, struct, sys, zlib

SIZE = 256
BG, TILE, STAR = (0, 0, 0, 0), (24, 27, 34, 255), (255, 135, 0, 255)  # orange #ff8700

def star_points(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / n * i - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def inside(px, py, poly):
    hit = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit

poly = star_points(SIZE / 2, SIZE / 2 + 8, 96, 38)
rows = []
R, PAD = 40, 16  # tile corner radius / margin
for y in range(SIZE):
    row = bytearray([0])  # filter byte
    for x in range(SIZE):
        dx = max(PAD + R - x, x - (SIZE - PAD - R), 0)
        dy = max(PAD + R - y, y - (SIZE - PAD - R), 0)
        in_tile = (PAD <= x < SIZE - PAD and PAD <= y < SIZE - PAD
                   and dx * dx + dy * dy <= R * R)
        px = STAR if inside(x + .5, y + .5, poly) else (TILE if in_tile else BG)
        row += bytes(px)
    rows.append(bytes(row))

def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
       + chunk(b"IEND", b""))
open(sys.argv[1], "wb").write(png)
print(f"==> Rendered {sys.argv[1]} ({len(png)} bytes)")
ICON

cat > "$RECIPE_DIR/star.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=star
Comment=Speaking Terminal Access Reader
Exec=star
Icon=star
Categories=Utility;Accessibility;
Terminal=false
DESKTOP

# Entry point: python-appimage installs this as the AppImage's AppRun after
# template substitution — it must be a SHELL script ({{ python }} expands to
# the bundled interpreter, e.g. "python3.13"; $APPDIR is set by the runtime).
# A bare .py here would be executed by bash and explode on `import`.
cat > "$RECIPE_DIR/entrypoint.sh" <<'SH'
#! /bin/bash
{{ python-executable }} -m star "$@"
SH

# Requirements: install the project in this checkout with all extras so the
# AppImage is fully featured.  Must be an ABSOLUTE path: python-appimage runs
# pip from inside the extracted AppDir, so a bare "." would not resolve to the
# repo root ("Directory '.[all]' is not installable").
cat > "$RECIPE_DIR/requirements.txt" <<REQ
${PWD}[all]
REQ

# Build.  python-appimage's "build local" wraps a manylinux CPython; we ask for
# a recent Python and the GUI-capable base.
# (No fallback path: `build app` is the one supported recipe form — this
# python-appimage has no `build wheel` subcommand.  Fail loudly instead.)
python -m python_appimage build app \
  -p 3.13 \
  --name star \
  "$RECIPE_DIR" || { echo "::error::AppImage build failed"; exit 1; }

# Collect the produced AppImage into dist/ with a versioned name.
APPIMAGE="$(ls -t ./*.AppImage 2>/dev/null | head -n1 || true)"
if [ -n "$APPIMAGE" ]; then
  cp "$APPIMAGE" "dist/star-${VERSION}-x86_64.AppImage"
  chmod +x "dist/star-${VERSION}-x86_64.AppImage"
  echo "==> Built dist/star-${VERSION}-x86_64.AppImage"
else
  echo "::warning::no .AppImage produced — check python-appimage output above."
fi

ls -l dist/ || true
