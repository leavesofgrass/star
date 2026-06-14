#!/usr/bin/env bash
#
# star — Speaking Terminal Access Reader
# Cross-platform dependency installer for Linux and macOS.
#
# Usage:
#   ./install.sh                 # interactive: recommended setup (GUI + TTS + common formats)
#   ./install.sh --all           # install every optional Python package
#   ./install.sh --minimal       # GUI + TTS only
#   ./install.sh --no-venv       # install into the current environment, not a venv
#   ./install.sh --help
#
# This script never touches the system Python site-packages without asking:
# by default it creates a local virtual environment in ./.venv.
#
# Copyright (C) 2026 Jon Pielaet — GPL-3.0-or-later

set -euo pipefail

# ── Pretty output ────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD=$(printf '\033[1m'); DIM=$(printf '\033[2m'); RESET=$(printf '\033[0m')
  GREEN=$(printf '\033[32m'); YELLOW=$(printf '\033[33m'); CYAN=$(printf '\033[36m'); RED=$(printf '\033[31m')
else
  BOLD=""; DIM=""; RESET=""; GREEN=""; YELLOW=""; CYAN=""; RED=""
fi
say()  { printf '%s\n' "${CYAN}==>${RESET} ${BOLD}$*${RESET}"; }
ok()   { printf '%s\n' "${GREEN}  ✓${RESET} $*"; }
warn() { printf '%s\n' "${YELLOW}  !${RESET} $*"; }
err()  { printf '%s\n' "${RED}  ✗${RESET} $*" >&2; }

# ── Argument parsing ─────────────────────────────────────────────────────────
PROFILE="recommended"
USE_VENV=1
for arg in "$@"; do
  case "$arg" in
    --all)      PROFILE="all" ;;
    --minimal)  PROFILE="minimal" ;;
    --no-venv)  USE_VENV=0 ;;
    -h|--help)
      sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) err "Unknown option: $arg"; exit 2 ;;
  esac
done

# ── Detect platform ──────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macOS" ;;
  Linux)  PLATFORM="Linux" ;;
  *)      PLATFORM="$OS" ;;
esac
say "Installing star dependencies for ${PLATFORM} (profile: ${PROFILE})"

# ── Locate a suitable Python (>= 3.8) ────────────────────────────────────────
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,8) else 1)'; then
      PY="$cand"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  err "Python 3.8+ not found. Install it first:"
  if [ "$PLATFORM" = "macOS" ]; then
    err "  brew install python    (or download from https://www.python.org/downloads/)"
  else
    err "  sudo apt install python3 python3-pip python3-venv    # Debian/Ubuntu"
    err "  sudo dnf install python3 python3-pip                 # Fedora"
  fi
  exit 1
fi
ok "Using $($PY --version 2>&1) at $(command -v "$PY")"

# ── Virtual environment ──────────────────────────────────────────────────────
if [ "$USE_VENV" -eq 1 ]; then
  if [ ! -d ".venv" ]; then
    say "Creating virtual environment in ./.venv"
    "$PY" -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PY="python"
  ok "Activated ./.venv  (re-activate later with: source .venv/bin/activate)"
fi

PIP="$PY -m pip"
say "Upgrading pip"
$PIP install --upgrade pip >/dev/null
ok "pip is up to date"

# ── Python package sets ──────────────────────────────────────────────────────
# GUI + TTS are the backbone of the experience.
GUI_PKGS=(PyQt6)
TTS_PKGS=(pyttsx3)
# macOS native speech ("say") needs no Python package, but pyttsx3's macOS
# driver needs pyobjc to drive NSSpeechSynthesizer.
if [ "$PLATFORM" = "macOS" ]; then
  TTS_PKGS+=(pyobjc)
fi
COMMON_PKGS=(pdfminer.six python-docx python-pptx)
EXTRA_PKGS=(pytesseract pymupdf odfpy openpyxl pypandoc louis pydub)

PKGS=()
case "$PROFILE" in
  minimal)     PKGS=("${GUI_PKGS[@]}" "${TTS_PKGS[@]}") ;;
  recommended) PKGS=("${GUI_PKGS[@]}" "${TTS_PKGS[@]}" "${COMMON_PKGS[@]}") ;;
  all)         PKGS=("${GUI_PKGS[@]}" "${TTS_PKGS[@]}" "${COMMON_PKGS[@]}" "${EXTRA_PKGS[@]}") ;;
esac

say "Installing Python packages: ${PKGS[*]}"
if $PIP install "${PKGS[@]}"; then
  ok "Python packages installed"
else
  warn "PyQt6 can fail on older systems; retrying GUI with PyQt5"
  $PIP install PyQt5 || warn "Qt GUI install failed — star will still run in --tui mode"
fi

# ── External binaries (best-effort, with guidance) ───────────────────────────
say "Checking optional external tools"
check_bin() {  # name, why
  if command -v "$1" >/dev/null 2>&1; then ok "$1 found ($2)"; else warn "$1 missing — $2"; fi
}
check_bin ffmpeg   "needed only for MP3/OGG/MP4 audio export (WAV works without it)"
check_bin tesseract "needed only for OCR of scanned PDFs/images"
if [ "$PLATFORM" = "Linux" ]; then
  check_bin espeak-ng "fallback TTS voice; install: sudo apt install espeak-ng"
fi
if [ "$PLATFORM" = "macOS" ]; then
  check_bin say "macOS native speech — used by default (Eloquence voices supported)"
fi

cat <<EOF

${BOLD}${GREEN}star is ready.${RESET}
EOF
if [ "$USE_VENV" -eq 1 ]; then
  printf '%s\n' "  Run it with:   ${BOLD}source .venv/bin/activate && python star.py${RESET}"
else
  printf '%s\n' "  Run it with:   ${BOLD}$PY star.py${RESET}"
fi
printf '%s\n' "  Force the terminal UI:  ${BOLD}python star.py --tui${RESET}"
printf '%s\n' "  ${DIM}Optional tools above are only needed for the features noted.${RESET}"
