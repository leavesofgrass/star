#!/usr/bin/env bash
# =============================================================================
# build-appimage-docker.sh — build star's Linux AppImage from ANY host OS.
# =============================================================================
#
# Wraps tools/build-appimage.sh in a python:3.13-slim container so the AppImage
# can be produced from Windows/macOS (or a Linux box without the toolchain).
# The source tree is COPIED into the container filesystem before building —
# building directly on a mounted Windows/NTFS volume would break the symlinks
# an AppDir requires — and only the finished artifact is copied back out to
# ./dist/.
#
# Usage (from the repo root; Docker must be running):
#   bash tools/build-appimage-docker.sh
#
# From Git Bash on Windows, MSYS path mangling is disabled automatically.
# Output: dist/star-<version>-x86_64.AppImage
#
# Runtime expectations of the artifact: the CLI runs on a bare distro with no
# system Python at all; the GUI additionally needs the standard desktop
# libraries every GUI distro ships (on a minimal/container Ubuntu:
#   apt install libgl1 libegl1 libglib2.0-0t64 libxkbcommon0 libdbus-1-3
#               libxcb-cursor0 libfontconfig1
# ).  Bundling libGL is deliberately avoided — it must match the host driver.
set -euo pipefail

cd "$(dirname "$0")/.."
HOST_DIR="$(pwd -W 2>/dev/null || pwd)"   # Windows drive path under Git Bash
mkdir -p dist

export MSYS_NO_PATHCONV=1
docker run --rm \
  -v "${HOST_DIR}:/host:ro" \
  -v "${HOST_DIR}/dist:/out" \
  -w /tmp python:3.13-slim bash -c '
set -euo pipefail
mkdir -p /src && cd /src
tar -C /host \
    --exclude=.venv --exclude=.git --exclude=build --exclude=dist \
    --exclude=wiki --exclude=__pycache__ --exclude=tools/_private \
    -cf - . | tar -xf -
apt-get update -qq >/dev/null
apt-get install -y -qq file desktop-file-utils >/dev/null 2>&1 || true
bash tools/build-appimage.sh
cp dist/*.AppImage /out/
echo "==> Artifact copied to host dist/"
'

ls -l dist/*.AppImage
