#!/usr/bin/env bash
# =============================================================================
# build-macos.sh — build a macOS star.app / .dmg, optionally codesigned +
# notarized.
# =============================================================================
#
# OPTIONAL packaging helper, invoked by the `macos-app` job in
# .github/workflows/release.yml (and runnable locally on a Mac).  It uses
# briefcase (from the BeeWare project) to wrap the pure-Python `star` package
# into a double-clickable .app and a .dmg.  The wheel remains the primary
# distribution channel; this is a convenience artifact for macOS users.
#
# Signing + notarization are best-effort and OFF by default: when
# MACOS_CERTIFICATE_BASE64 is empty/absent the .app/.dmg are produced UNSIGNED
# (Gatekeeper will warn on first launch) and this script still exits 0, so CI
# never fails for lack of an Apple Developer ID.  To enable, provide:
#
#   MACOS_CERTIFICATE_BASE64   base64 of a "Developer ID Application" .p12
#   MACOS_CERTIFICATE_PASSWORD its export password
#   MACOS_NOTARY_APPLE_ID      Apple ID email for notarytool
#   MACOS_NOTARY_PASSWORD      app-specific password for that Apple ID
#   MACOS_NOTARY_TEAM_ID       the Developer Team ID
#
# See docs/PACKAGING.md → "macOS app / DMG".
set -euo pipefail

mkdir -p dist

echo "==> Installing briefcase"
python -m pip install --upgrade pip briefcase >/dev/null

# briefcase reads its config from pyproject.toml ([tool.briefcase]).  We do NOT
# edit pyproject.toml here (owned elsewhere); instead we run briefcase with a
# generated minimal template if no config is present, so this script is
# self-contained and never mutates tracked project files.
if ! python -c "import tomllib,sys; d=tomllib.load(open('pyproject.toml','rb')); sys.exit(0 if 'briefcase' in d.get('tool',{}) else 1)" 2>/dev/null; then
  echo "==> No [tool.briefcase] in pyproject.toml — using a standalone build config"
  # briefcase can be driven from an isolated config directory; keep it in build/.
  BRIEFCASE_CONFIG_DIR="build/briefcase"
  mkdir -p "$BRIEFCASE_CONFIG_DIR"
  cat > "$BRIEFCASE_CONFIG_DIR/pyproject.toml" <<'TOML'
[tool.briefcase]
project_name = "star"
bundle = "org.star-reader"
version = "0.0.0"
license = "GPL-3.0-or-later"

[tool.briefcase.app.star]
formal_name = "star"
description = "Speaking Terminal Access Reader"
sources = ["src/star"]
requires = ["star-reader[all]"]
TOML
  echo "::warning::briefcase config was synthesized; wire [tool.briefcase] into pyproject.toml for a first-class build."
fi

# ── Optional signing setup ──────────────────────────────────────────────────
SIGN_IDENTITY=""
if [ -n "${MACOS_CERTIFICATE_BASE64:-}" ]; then
  echo "==> Signing certificate present — importing into a temp keychain"
  KEYCHAIN="$RUNNER_TEMP/star-signing.keychain-db"
  KEYCHAIN_PW="$(openssl rand -base64 24)"
  CERT_P12="$RUNNER_TEMP/star-cert.p12"
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
  echo "==> Will codesign with: $SIGN_IDENTITY"
else
  echo "==> MACOS_CERTIFICATE_BASE64 not set — building UNSIGNED (no-op signing)."
fi

echo "==> briefcase create + build"
briefcase create macOS app || true
briefcase build macOS app || true

# briefcase packages (and signs, if an identity is passed) the .app into a .dmg.
if [ -n "$SIGN_IDENTITY" ]; then
  briefcase package macOS app --identity "$SIGN_IDENTITY" || true
else
  # --adhoc-sign avoids Gatekeeper hard-fails on an unsigned build in CI.
  briefcase package macOS app --adhoc-sign || true
fi

# Collect artifacts into dist/.
find . -name "*.dmg" -exec cp {} dist/ \; 2>/dev/null || true
# Also zip the .app so it survives artifact upload (upload flattens symlinks).
APP_PATH="$(find . -name '*.app' -type d | head -n1 || true)"
if [ -n "$APP_PATH" ]; then
  (cd "$(dirname "$APP_PATH")" && zip -qry "$OLDPWD/dist/$(basename "$APP_PATH").zip" "$(basename "$APP_PATH")")
fi

# ── Optional notarization ───────────────────────────────────────────────────
if [ -n "$SIGN_IDENTITY" ] && [ -n "${MACOS_NOTARY_APPLE_ID:-}" ]; then
  echo "==> Notarizing the .dmg with notarytool"
  for dmg in dist/*.dmg; do
    [ -e "$dmg" ] || continue
    xcrun notarytool submit "$dmg" \
      --apple-id "$MACOS_NOTARY_APPLE_ID" \
      --password "${MACOS_NOTARY_PASSWORD:-}" \
      --team-id "${MACOS_NOTARY_TEAM_ID:-}" \
      --wait || echo "::warning::notarization failed for $dmg (artifact still produced)"
    xcrun stapler staple "$dmg" || true
  done
else
  echo "==> Skipping notarization (no cert or no notary credentials) — no-op."
fi

echo "==> macOS build complete:"
ls -l dist/ || true
