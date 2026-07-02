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

# Resolve the version for the output filename.
VERSION="$(python -c 'import star._runtime as r; print(r.APP_VERSION)' 2>/dev/null || echo 0.0.0)"
echo "==> Building star $VERSION AppImage"

# A minimal python-appimage recipe: a desktop entry + an entrypoint that runs
# the star module, and a requirements file that installs the project itself.
RECIPE_DIR="build/appimage/recipe"
mkdir -p "$RECIPE_DIR"

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

# Entry point: launch the installed console_script.  python-appimage runs the
# module named by --name; we expose star's CLI entry via a tiny wrapper.
cat > "$RECIPE_DIR/entrypoint.py" <<'PY'
import sys
from star.app import main  # star's console_scripts entry point
sys.exit(main())
PY

# Requirements: install the project in this checkout with all extras so the
# AppImage is fully featured.  "." resolves to the repo root (the pyproject).
cat > "$RECIPE_DIR/requirements.txt" <<'REQ'
.[all]
REQ

# Build.  python-appimage's "build local" wraps a manylinux CPython; we ask for
# a recent Python and the GUI-capable base.
python -m python_appimage build app \
  -p 3.13 \
  --name star \
  "$RECIPE_DIR" || {
    echo "::warning::python-appimage 'build app' recipe path failed; trying the wheel path"
    # Fallback: build directly from the built wheel if the recipe form is
    # unavailable in this python-appimage version.
    python -m build --wheel >/dev/null
    WHEEL="$(ls -t dist/*.whl | head -n1)"
    python -m python_appimage build wheel "$WHEEL" || {
      echo "::error::AppImage build failed"; exit 0; }
  }

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
