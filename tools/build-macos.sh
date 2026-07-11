#!/usr/bin/env bash
# =============================================================================
# build-macos.sh — build a macOS star.app + .dmg with PyInstaller, optionally
# Developer-ID codesigned + notarized.
# =============================================================================
#
# OPTIONAL packaging helper, invoked by the `macos-app` job in
# .github/workflows/release.yml (and runnable locally on a Mac).  It drives
# PyInstaller through the shared star.spec — the SAME spec that builds the
# Windows star.exe — which on macOS (sys.platform == "darwin") packages the
# Analysis as a ONEDIR ``star.app`` bundle instead of a onefile .exe.  The wheel
# remains the primary distribution channel; this is a convenience artifact for
# macOS users who can't install Python.
#
# Speech on macOS comes from the OS, not from vendored binaries: the star.app
# ships pyttsx3 (→ NSSpeechSynthesizer) and star's AppleSay backend (/usr/bin/
# say), so no vendor/ tree is bundled (star.spec skips it on darwin).
#
# Offline dictation (faster-whisper / CTranslate2, ~140 MB) IS bundled by default
# now — the old openai-whisper + Torch stack was too heavy for a .app, but the
# CTranslate2 stack is light enough to ship out of the box.  Set STAR_MACOS_LEAN=1
# to skip it for a small/quick build.
#
# Signing + notarization are best-effort and OFF by default: with no
# MACOS_CERTIFICATE_BASE64 the .app is AD-HOC signed (``codesign -s -``) so it
# runs locally after the user clears Gatekeeper quarantine (right-click ▸ Open,
# or ``xattr -dr com.apple.quarantine star.app``), and this script still exits 0
# — CI never fails for lack of an Apple Developer ID.  To ship a Gatekeeper-clean
# artifact, provide:
#
#   MACOS_CERTIFICATE_BASE64   base64 of a "Developer ID Application" .p12
#   MACOS_CERTIFICATE_PASSWORD its export password
#   MACOS_NOTARY_APPLE_ID      Apple ID email for notarytool
#   MACOS_NOTARY_PASSWORD      app-specific password for that Apple ID
#   MACOS_NOTARY_TEAM_ID       the Developer Team ID
#
# See docs/PACKAGING.md → "macOS app / DMG".
set -euo pipefail

# This script lives in tools/, but the build (star.spec, dist/) is rooted at the
# project directory one level up.  Operate from there.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p dist build

info() { printf '==> %s\n' "$*"; }

VERSION="$(python -c "import tomllib,sys; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
ARCH="$(uname -m)"   # arm64 on Apple-Silicon runners, x86_64 on Intel
info "Building star $VERSION for macOS ($ARCH)"

# ── Isolated build venv ──────────────────────────────────────────────────────
VENV="$ROOT/.venv-build-macos"
if [ ! -d "$VENV" ]; then
  info "Creating build virtual environment (.venv-build-macos)"
  python -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install --upgrade pip >/dev/null

# ── Dependencies ─────────────────────────────────────────────────────────────
# Mirrors the Windows exe's runtime set, minus the Windows-only bits
# (windows-curses, comtypes/SAPI) and plus nothing Mac-specific beyond pyttsx3,
# which resolves to the NSSpeechSynthesizer driver at runtime.
info "Installing PyInstaller + runtime dependencies"
DEPS=(
  pyinstaller
  PyQt6
  pyttsx3
  # pyobjc lets pyttsx3's nsss driver drive NSSpeechSynthesizer for accurate
  # word-boundary highlighting; without it star still speaks via the `say`
  # backend, but highlighting falls back to timing estimates.
  pyobjc-core
  pyobjc-framework-Cocoa
  pdfminer.six
  python-docx
  python-pptx
  openpyxl
  odfpy
  watchdog
  # Study & writing aids (bundled so they work in the .app with no extra install)
  sumy
  genanki
  pyspellchecker
  deep-translator
  feedparser
  wordfreq
  pyphen
  # Small pure-Python fillers so nothing obvious is dark in `star --deps`
  pydub
  pyperclip
  py7zr
  rarfile
  # OCR wrappers (the Tesseract engine itself comes from Homebrew if present)
  pytesseract
  PyMuPDF
  Pillow
)
# Offline dictation via faster-whisper (CTranslate2) — bundled BY DEFAULT now.
# The old openai-whisper + Torch stack was multi-GB and too heavy for a .app;
# faster-whisper's whole stack is ~140 MB, so macOS finally ships dictation out
# of the box.  STAR_MACOS_LEAN=1 skips it for a small/quick build.
if [ -n "${STAR_MACOS_LEAN:-}" ]; then
  info "STAR_MACOS_LEAN set — skipping the dictation stack (small build)"
  export STAR_LEAN=1   # star.spec: don't pull in / bundle the dictation stack
else
  info "Bundling offline dictation (faster-whisper / CTranslate2)"
  DEPS+=(faster-whisper sounddevice)
fi
"$PY" -m pip install "${DEPS[@]}"

# Install star itself so its dist-info (entry-point metadata) exists for
# star.spec's copy_metadata("star-reader").  Without it the frozen app's plugin
# registry discovers ZERO TTS backends — a reader that can't speak.
info "Installing star-reader itself (entry-point metadata for the TTS registry)"
"$PY" -m pip install --no-deps --force-reinstall .

# ── Stage NLTK data (offline summarize + Define Word) ────────────────────────
# sumy's tokenizer needs punkt; Define Word needs wordnet + cmudict.  star.spec
# bundles build/nltk_data when present so both features work with no download.
if [ ! -f "$ROOT/build/nltk_data/corpora/wordnet.zip" ]; then
  info "Staging NLTK data (punkt + wordnet + cmudict) for offline summarize / Define Word"
  STAR_NLTK_DIR="$ROOT/build/nltk_data" "$PY" - <<'PY'
import os, nltk
d = os.environ["STAR_NLTK_DIR"]
os.makedirs(d, exist_ok=True)
for pkg in ("punkt", "punkt_tab", "wordnet", "omw-1.4", "cmudict"):
    nltk.download(pkg, download_dir=d)
print("NLTK data staged")
PY
fi

# ── Stage the CTranslate2 'base' model directory (offline dictation) ─────────
# star.spec bundles build/faster_whisper_model/ so dictation runs with no HF
# download.  Skipped for a lean build (no dictation stack installed).
if [ -z "${STAR_MACOS_LEAN:-}" ] && [ ! -f "$ROOT/build/faster_whisper_model/model.bin" ]; then
  info "Staging faster-whisper 'base' CTranslate2 model for offline dictation"
  STAR_FW_DIR="$ROOT/build/faster_whisper_model" "$PY" - <<'PY'
import os
from huggingface_hub import snapshot_download
d = os.environ["STAR_FW_DIR"]
snapshot_download(repo_id="Systran/faster-whisper-base", local_dir=d)
print("faster-whisper base model staged")
PY
fi

# ── Build the .app ───────────────────────────────────────────────────────────
info "Running PyInstaller (star.spec → dist/star.app)"
"$PY" -m PyInstaller --clean --noconfirm star.spec

APP="dist/star.app"
if [ ! -d "$APP" ]; then
  echo "ERR PyInstaller finished but $APP was not produced." >&2
  exit 1
fi
info "Built $APP"

# ── Codesign ─────────────────────────────────────────────────────────────────
# Entitlements: the hardened runtime blocks the microphone unless we grant the
# audio-input entitlement (dictation) — write a minimal plist for signing.
ENTITLEMENTS="build/star-entitlements.plist"
cat > "$ENTITLEMENTS" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key><true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
  <key>com.apple.security.cs.disable-library-validation</key><true/>
  <key>com.apple.security.device.audio-input</key><true/>
</dict>
</plist>
PLIST

SIGN_IDENTITY=""
if [ -n "${MACOS_CERTIFICATE_BASE64:-}" ]; then
  info "Signing certificate present — importing into a temp keychain"
  KEYCHAIN="${RUNNER_TEMP:-$TMPDIR}/star-signing.keychain-db"
  KEYCHAIN_PW="$(openssl rand -base64 24)"
  CERT_P12="${RUNNER_TEMP:-$TMPDIR}/star-cert.p12"
  echo "$MACOS_CERTIFICATE_BASE64" | base64 --decode > "$CERT_P12"
  security create-keychain -p "$KEYCHAIN_PW" "$KEYCHAIN"
  security set-keychain-settings -lut 21600 "$KEYCHAIN"
  security unlock-keychain -p "$KEYCHAIN_PW" "$KEYCHAIN"
  security import "$CERT_P12" -k "$KEYCHAIN" \
    -P "${MACOS_CERTIFICATE_PASSWORD:-}" -T /usr/bin/codesign
  security set-key-partition-list -S apple-tool:,apple: -k "$KEYCHAIN_PW" "$KEYCHAIN" >/dev/null
  security list-keychains -d user -s "$KEYCHAIN" $(security list-keychains -d user | tr -d '"')
  SIGN_IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN" | awk -F'"' 'NR==1{print $2}')"
  rm -f "$CERT_P12"
fi

if [ -n "$SIGN_IDENTITY" ]; then
  info "Developer-ID signing with hardened runtime: $SIGN_IDENTITY"
  # Sign inside-out: nested code first, then the bundle.  --deep is deprecated
  # but reliable here for the many bundled dylibs; the outer sign pins options.
  codesign --force --deep --timestamp --options runtime \
    --entitlements "$ENTITLEMENTS" --sign "$SIGN_IDENTITY" "$APP"
  codesign --verify --strict --verbose=2 "$APP"
else
  info "No signing cert — AD-HOC signing (runs locally after clearing quarantine)."
  codesign --force --deep --sign - "$APP"
fi

# ── Package a DMG ────────────────────────────────────────────────────────────
DMG="dist/star-$VERSION-macos-$ARCH.dmg"
info "Packaging $DMG"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # drag-to-install affordance
rm -f "$DMG"
hdiutil create -volname "star $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

# Sign the DMG too when we have an identity (notarization staples to the DMG).
if [ -n "$SIGN_IDENTITY" ]; then
  codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG"
fi

# Also zip the .app so it survives artifact upload intact (symlinks/bundle).
info "Zipping $APP for artifact upload"
( cd dist && ditto -c -k --sequesterRsrc --keepParent "star.app" "star-$VERSION-macos-$ARCH.app.zip" )

# ── Notarize (only with a Developer-ID identity + notary credentials) ────────
if [ -n "$SIGN_IDENTITY" ] && [ -n "${MACOS_NOTARY_APPLE_ID:-}" ]; then
  info "Notarizing $DMG with notarytool (waits for Apple)"
  if xcrun notarytool submit "$DMG" \
      --apple-id "$MACOS_NOTARY_APPLE_ID" \
      --password "${MACOS_NOTARY_PASSWORD:-}" \
      --team-id "${MACOS_NOTARY_TEAM_ID:-}" \
      --wait; then
    xcrun stapler staple "$DMG" || echo "::warning::stapler failed for $DMG"
  else
    echo "::warning::notarization failed for $DMG (unsigned-equivalent artifact still produced)"
  fi
else
  info "Skipping notarization (no Developer-ID cert or no notary credentials)."
fi

info "macOS build complete:"
ls -lh dist/*.dmg dist/*.app.zip 2>/dev/null || true
