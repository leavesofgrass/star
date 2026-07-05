# Packaging & distribution

This document is the maintainer reference for **every way star is packaged and
shipped**, and for the **optional** code-signing / installer jobs in the release
workflow. It complements [`RELEASING.md`](RELEASING.md) (which covers the
day-to-day "cut a release" procedure) and [`installation.md`](installation.md)
(the user-facing install instructions).

> **TL;DR for the release model.** The **wheel + sdist published to PyPI** is
> the one and only *automated* artifact and the primary distribution channel.
> Everything else on this page — the `.pyz`, GPG signatures, and the native
> installers (Windows/macOS/Linux) — is **optional and gated off by default**.
> None of it can fail or block the wheel/PyPI pipeline: each optional job is
> *skipped* (not failed) when its enabling variable/secret is absent.

---

## Distribution channels

| Channel | Artifact | Built by | Default? | Notes |
|---|---|---|---|---|
| **PyPI wheel + sdist** | `star_reader-<v>-py3-none-any.whl` + `.tar.gz` | `wheel` job (tag push) | ✅ automated | Pure-Python, universal. Install: `pipx install star-reader`. The canonical release. |
| **Fat zipapp** | `star.pyz` | `python build_zipapp.py` / `windows-pyz` job (manual) | ⚙️ manual | Bundles `star` + `[all]` extras; platform-specific (carries compiled wheels). See [installation.md](installation.md#single-file-build-starpyz). |
| **Windows installer** | `star-setup-<v>.exe` | `windows-installer` job (optional) | 🔒 opt-in | NSIS click-through installer around `star.pyz`; Authenticode-signed when a cert is provided. |
| **macOS app / DMG** | `star.app.zip` + `star-<v>.dmg` | `macos-app` job (optional) | 🔒 opt-in | briefcase-built `.app`/`.dmg`; codesigned + notarized when an Apple Developer ID is provided. |
| **Linux AppImage** | `star-<v>-x86_64.AppImage` | `linux-appimage` job | ✅ | Self-contained via python-appimage; built on every `v*` tag and attached to the GitHub Release (default since 0.1.22). |
| **GPG signatures** | `*.whl.asc`, `*.tar.gz.asc` | `sign-artifacts` job (optional) | 🔒 opt-in | Detached armored signatures for the wheel + sdist. |
| **Deprecated exe** | `star.exe` | `windows-exe` job (manual) | ⚠️ deprecated | PyInstaller onefile; manual fallback only. See [RELEASING.md](RELEASING.md). |

"Default? ✅" runs on every `v*` tag. "⚙️ manual" runs only via
`workflow_dispatch`. "🔒 opt-in" runs only when its enabling variable/secret is
configured (details below) — otherwise the job is **skipped**, never failed.

---

## The optional CI jobs (and exactly how they are gated)

All of these live in [`.github/workflows/release.yml`](../.github/workflows/release.yml),
appended *after* the existing `wheel` / `publish-pypi` / `release` jobs. They are
**deliberately not in the `release` job's `needs:`** — the GitHub Release does
not wait on them — but any artifact they *do* produce is swept up by the
release's download-all step and attached automatically.

### 1. `sign-artifacts` — GPG-sign the wheel + sdist

- **What it does:** imports a private key, then writes a detached armored
  signature (`.asc`) next to each `.whl`/`.tar.gz`. Users verify with
  `gpg --verify star_reader-<v>.whl.asc star_reader-<v>.whl`.
- **Gate:** job-level `if: vars.ENABLE_GPG_SIGNING == 'true'`. Absent → skipped.
- **Maintainer secrets/variables required to enable:**
  - variable `ENABLE_GPG_SIGNING = true`
  - secret `GPG_PRIVATE_KEY` — the **ASCII-armored** private key
    (`gpg --armor --export-secret-keys <KEYID>`)
  - secret `GPG_PASSPHRASE` — the key's passphrase
- **Publish the public key** (keyserver or repo) so users can import it.

### 2. `windows-installer` — NSIS installer (+ Authenticode)

- **What it does:** builds `star.pyz`, then runs [`tools/build-nsis.ps1`](../tools/build-nsis.ps1)
  to wrap it in `star-setup-<v>.exe` (installs the zipapp + a launcher + a Start
  Menu shortcut under `%LOCALAPPDATA%\Programs\star`). Authenticode-signs the
  installer **only if** a cert is present; otherwise ships it unsigned.
- **Gate:** manual `workflow_dispatch` with `build_installers: true`, **or**
  `vars.ENABLE_INSTALLERS == 'true'`. Absent → skipped.
- **Maintainer secrets to enable signing** (installer still builds *unsigned*
  without them):
  - secret `WINDOWS_CERT_PFX_BASE64` — base64 of your code-signing `.pfx`
    (`base64 -w0 cert.pfx`)
  - secret `WINDOWS_CERT_PASSWORD` — the `.pfx` export password
- **Cert source:** an OV/EV Authenticode certificate from a CA (DigiCert,
  Sectigo, …). EV certs give instant SmartScreen reputation.

### 3. `macos-app` — `.app` / DMG (+ codesign & notarize)

- **What it does:** runs [`tools/build-macos.sh`](../tools/build-macos.sh),
  which uses **briefcase** to build `star.app` and a `.dmg`. codesigns with a
  Developer ID and notarizes with `notarytool` **only if** the cert +
  credentials are present; otherwise ad-hoc-signs (Gatekeeper will warn).
- **Gate:** manual `build_installers: true`, **or** `vars.ENABLE_INSTALLERS == 'true'`.
- **Maintainer secrets to enable signing/notarization** (unsigned build still
  produced without them):
  - `MACOS_CERTIFICATE_BASE64` — base64 of a "Developer ID Application" `.p12`
  - `MACOS_CERTIFICATE_PASSWORD` — the `.p12` password
  - `MACOS_NOTARY_APPLE_ID` — Apple ID email for notarization
  - `MACOS_NOTARY_PASSWORD` — an **app-specific password** for that Apple ID
  - `MACOS_NOTARY_TEAM_ID` — your Apple Developer Team ID
- **Note:** briefcase reads `[tool.briefcase]` from `pyproject.toml`. That file
  is owned outside this packaging work, so the script **synthesizes a minimal
  config** if none exists (and warns). For a first-class macOS build, a
  maintainer should add a `[tool.briefcase]` section to `pyproject.toml`.

### 4. `linux-appimage` — self-contained AppImage

- **What it does:** runs [`tools/build-appimage.sh`](../tools/build-appimage.sh),
  which uses **python-appimage** to bundle a relocatable CPython + `star-reader[all]`
  into `star-<v>-x86_64.AppImage`. No signing here — pair it with the `.asc`
  from `sign-artifacts`.
- **Gate:** runs on **every `v*` tag** (default release artifact since 0.1.22 —
  the publish job waits for it via `needs`, but a failed AppImage build never
  blocks the wheel/sdist release). Also runs via manual `build_installers: true`
  or `vars.ENABLE_INSTALLERS == 'true'`.
- **No secrets required.**

**Building locally from any OS (Docker):**

```bash
bash tools/build-appimage-docker.sh     # → dist/star-<v>-x86_64.AppImage
```

This wraps the same build script in a `python:3.13-slim` container (the source
is copied into the container filesystem first — AppDirs need symlinks, which a
mounted Windows volume can't hold — and only the artifact is copied back out).

**Runtime expectations:** the CLI (`star --version`, `--tui`, conversion) runs
on a bare distro with **no system Python at all** (verified on pristine
Ubuntu 24.04 and Debian 12 containers). The **GUI** additionally needs the
standard desktop libraries that every graphical distro already ships; only on
a minimal/container image would you install them by hand
(`libgl1 libegl1 libglib2.0-0t64 libxkbcommon0 libdbus-1-3 libxcb-cursor0
libfontconfig1` on Ubuntu). Bundling `libGL` is deliberately avoided — it must
match the host's graphics driver. In containers/CI, run the AppImage with
`--appimage-extract-and-run` (no FUSE needed).

---

## Enabling everything: maintainer checklist

Set these under **Settings → Secrets and variables → Actions**:

**Variables**
- `ENABLE_PYPI = true` — the PyPI trusted-publisher jobs (already documented in
  [RELEASING.md](RELEASING.md); unchanged by this work).
- `ENABLE_GPG_SIGNING = true` — turn on `sign-artifacts`.
- `ENABLE_INSTALLERS = true` — turn on all three native installers on every tag
  (or leave unset and trigger them per-run via the `build_installers` dispatch
  input).

**Secrets**
- GPG: `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE`
- Windows: `WINDOWS_CERT_PFX_BASE64`, `WINDOWS_CERT_PASSWORD`
- macOS: `MACOS_CERTIFICATE_BASE64`, `MACOS_CERTIFICATE_PASSWORD`,
  `MACOS_NOTARY_APPLE_ID`, `MACOS_NOTARY_PASSWORD`, `MACOS_NOTARY_TEAM_ID`

Every one of these is **optional**. With none of them set, the release pipeline
behaves exactly as it does today: build the wheel, publish to PyPI (behind the
manual `pypi` environment approval gate), and create the GitHub Release.

---

## Homebrew (planned, not yet automated)

A Homebrew formula/cask is the natural macOS install path once the notarized
`.app` is stable. It is **not** wired into CI yet. When ready:

1. Create a tap repo (e.g. `leavesofgrass/homebrew-star`).
2. Add a formula that `pip install`s `star-reader` into a vendored virtualenv,
   or a cask that downloads the notarized `.dmg`.
3. A future `homebrew-bump` job (gated on a `HOMEBREW_TAP_TOKEN` secret) can
   open a PR against the tap on each release. This job does not exist yet —
   track it as a follow-up.

Flatpak (Linux) is a similar future channel; the AppImage covers "download and
run" in the meantime.

---

## In-app update check

star ships a best-effort update checker in [`star/update.py`](../star/update.py):
`check_for_update()` queries the PyPI JSON API for the newest `star-reader`
release and reports whether a newer version exists (cached briefly, offline-safe,
never raises). It has no third-party dependencies. Wiring it into a GUI menu item
or a `--check-update` CLI flag is a follow-up (those modules are owned
elsewhere); the function is exposed and unit-tested today.

---

## Auditing the pipeline locally

- **Validate the workflow YAML:**
  `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml', encoding='utf-8'))"`
- **Dry-run the installers locally** (no secrets → unsigned):
  - Windows: `python build_zipapp.py; pwsh tools/build-nsis.ps1`
  - macOS: `bash tools/build-macos.sh`
  - Linux: `bash tools/build-appimage.sh`
