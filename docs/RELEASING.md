# Releasing star

star's tests and builds run on GitHub Actions. This document describes how a
release is cut and what the automation produces.

> **Release model: wheel + PyPI, plus self-contained downloads.** The automated
> release publishes the pure-Python **wheel + sdist** to **PyPI** (and attaches
> them to the GitHub Release). Since 0.1.22 every `v*` tag also builds and
> attaches double-click, no-Python-needed downloads: the **Linux AppImage**, and
> (as of 0.1.24) the **self-contained Windows `star.exe`** and the **macOS
> `star.app`/DMG** (Apple Silicon). Only the platform `star.pyz` is **not** built
> on tag pushes — it is a build-it-yourself artifact (see
> [Build-it-yourself artifacts](#build-it-yourself-artifacts)).

## Continuous integration (every push / PR)

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push to
`main` and every pull request:

- **`test`** — the `pytest` suite on a matrix of Linux / Windows / macOS across
  Python 3.11–3.13. One Linux leg also installs the pure-Python optional
  packages (`deep-translator`, `feedparser`, `wordfreq`, `sumy`, `genanki`,
  `pyspellchecker`) so the real-behaviour tests run, not just the
  graceful-degradation paths.
- **`lint`** — `ruff check`, **blocking as of 0.1.14**: the tree is kept
  ruff-clean, so a new unused import or ambiguous name fails CI and walls the PR.
- **`full-fat`** — one Linux leg with the *entire* optional-dependency surface
  (`.[all,test]` plus spaCy + its language model) installed, so every feature's
  real-behaviour branch runs; the cross-feature integration net.
- **`coverage`** — enforces **per-module coverage floors** (a ratchet). One suite
  run collects coverage and each gated module (`tts`, `documents`, `render`,
  `citations`, `obsidian`, `graph`, `markup`, `ttstext`, `dictionary`,
  `autodeps`, `library`, `export`, `gui.preferences`) is checked against its own
  `--fail-under`; dropping below any floor fails CI.

The suite is written to pass with **none** of the optional packages installed —
checks that need a package `skip` when it is absent. The dependency harness
(`tests/test_dependencies.py`) additionally fails if a new optional import guard
is added without registering it in `star.diagnostics`.

## Cutting a release

1. **Bump the version** in two places (they must match):
   - `star/_runtime.py` → `__version__`
   - `pyproject.toml` → `version`
2. **Update the changelog**: add a new section at the top of
   `star/CHANGELOG.md` (Keep-a-Changelog format) describing the release.
3. **Update the version references**: the wheel-filename install examples in
   `docs/installation.md` and `star/BUILD.md`.
4. **Commit** the version bump on `main` (or via PR).
5. **Tag and push**:
   ```bash
   git tag v0.1.24
   git push origin v0.1.24
   ```
6. **Watch the platform builds and verify every binary attached.** A `v*` tag
   builds three self-contained binaries in parallel — the Windows `star.exe`
   (`windows-exe`), the **macOS `star.app`/DMG** (`macos-app`), and the Linux
   AppImage (`linux-appimage`) — and the `release` job waits for all three before
   publishing the GitHub Release. Confirm all three are attached to the Release:
   - `star-<version>-windows-x64.exe`
   - `star-<version>-macos-arm64.dmg` **and** `…-macos-arm64.app.zip`
   - `star-<version>-x86_64.AppImage`

   > **macOS is verified only on the runner.** The `.app` is PyInstaller-built on
   > a `macos-latest` (Apple-Silicon) runner and **cannot be produced or checked
   > from a Windows/Linux dev box** — exactly like the AppImage needs a Linux
   > container. So the `macos-app` job's success on the tag *is* the validation.
   > If it's the first tag after a change to `star.spec` / `tools/build-macos.sh`,
   > you can rehearse it without cutting a real tag via a manual
   > `workflow_dispatch` run with `build_installers: true` (see the job's `if:`
   > gate). It is **Apple-Silicon (arm64) only** — Intel Macs install from PyPI.

Pushing a `v*` tag triggers
[`.github/workflows/release.yml`](../.github/workflows/release.yml), which builds
the wheel + sdist, publishes them to PyPI, and creates a GitHub Release with
auto-generated notes plus the three platform binaries above.

## What the release workflow builds

| Job | Artifact | Notes |
|---|---|---|
| `wheel` | `star_reader-<version>-py3-none-any.whl` + sdist | **The release.** Pure-Python, universal; one build serves every platform. `twine check` guards the long-description rendering before the PyPI upload. |
| `publish-testpypi` / `publish-pypi` | (uploads to PyPI) | Publishes the wheel + sdist via trusted publishing — pre-release tags to TestPyPI, final tags to PyPI. See **Publishing to PyPI** below. |
| `windows-exe` | `star-<version>-windows-x64.exe` | Self-contained double-click Windows binary (Python + GUI + every loader + offline dictation + vendored native tools; **DECtalk excluded** via `--no-dectalk`). Built on every `v*` tag and attached to the Release. It is the long pole (~5-10 min for the PyInstaller build now that the dictation stack is faster-whisper, not Torch); PyPI publishing (`needs: [wheel]`) is **not** delayed by it. |
| `macos-app` | `star-<version>-macos-arm64.dmg` + `.app.zip` | Self-contained macOS app, PyInstaller-built from the same `star.spec` (darwin → `.app` bundle). Speech uses the built-in Apple voices, so no native engines are bundled; ad-hoc-signed by default, Developer-ID codesigned + notarized when the `MACOS_*` secrets are set. **Apple-Silicon (arm64) only.** Built on every `v*` tag (default since 0.1.24) and attached to the Release. |
| `linux-appimage` | `star-*.AppImage` | Self-contained Linux binary. A **default** release artifact since 0.1.22, attached to the Release. |
| `release` | GitHub Release | Attaches the wheel + sdist, the Windows `.exe`, the macOS `.app`/DMG, the Linux AppImage, and auto-generated notes. |

The `windows-exe` (self-contained `star.exe`), `macos-app` (`.app`/DMG) and
`linux-appimage` jobs **run on every `v*` tag** and their output is attached to
the GitHub Release; a manual `workflow_dispatch` can also force them
(`build_exe: true` / `build_installers: true`). Only the `windows-pyz` job stays
manual-only — it does **not** run on tag pushes and is not attached to the release
(`workflow_dispatch` with `build_pyz: true`).

## Publishing to PyPI

The release workflow publishes the wheel and sdist to PyPI using
[**trusted publishing**](https://docs.pypi.org/trusted-publishers/) (OIDC) — no
API token is ever stored in the repo. The routing is by tag:

- **Pre-release tag** (contains a hyphen, e.g. `v0.1.24-rc1`) → **TestPyPI**.
- **Final tag** (e.g. `v0.1.24`) → **PyPI**.

Manual `workflow_dispatch` runs do not publish (no tag ref).

### The `ENABLE_PYPI` switch

Both publish jobs are gated on a repository **variable** `ENABLE_PYPI`. When it is
set to `true` the jobs run; otherwise they **skip** (the build and GitHub Release
still run, so you can exercise the whole pipeline before the trusted publisher is
active).

`ENABLE_PYPI` is currently **`true`**, so every final `v*` tag runs the publish
job. The deployment requires a maintainer to approve it before the upload
proceeds — GitHub shows a *Review deployments* button on the run. To pause
publishing entirely, set *Settings → Secrets and variables → Actions →
Variables → `ENABLE_PYPI`* to anything other than `true` (or remove it).

### One-time setup (already done for this repo)

1. **Register the trusted publisher on PyPI / TestPyPI.** Project → *Publishing* →
   add a GitHub Actions trusted publisher: Owner `leavesofgrass`, Repository
   `star`, Workflow `release.yml`, Environment `pypi` (and `testpypi` on
   TestPyPI).
2. **Create the GitHub environments** `pypi` and `testpypi` (Repo *Settings →
   Environments*).
3. **Rehearse on TestPyPI first.** Push a pre-release tag (`v0.1.24-rc1`), confirm
   `pip install -i https://test.pypi.org/simple/ star-reader` works, then push the
   final `v0.1.24` tag.

## Build-it-yourself artifacts

These are **not** part of the automated release. Build them locally only if you
specifically need them:

```bash
python -m build                                  # wheel + sdist        -> dist/   (the release)
python build_zipapp.py                           # fat zipapp (per-OS)  -> dist/star.pyz
pwsh tools/build-windows.ps1 -AllowDeprecatedExe # self-contained exe (same recipe CI ships) -> dist/star.exe
```

- **`star.pyz`** — a fat zipapp bundling `star` + the `[all]` extras. It is
  platform-specific (carries compiled extensions), so build it on the OS you
  intend to run it on. See [`docs/installation.md`](installation.md#single-file-build-starpyz).
- **`star.exe`** — the self-contained Windows binary. This is now a **supported
  release artifact**: the `windows-exe` CI job builds it on every `v*` tag and
  attaches it to the GitHub Release (see [What the release workflow
  builds](#what-the-release-workflow-builds)). To build the *same* binary
  locally, run `tools/build-windows.ps1`; the script keeps a safety opt-in
  (`-AllowDeprecatedExe` or `STAR_ALLOW_EXE=1`) so nobody kicks off the slow
  build by habit. By default it bundles the offline dictation stack
  (faster-whisper + the `base` CTranslate2 model, ~140 MB — no Torch); pass
  `-Lean` to skip it. To vendor the native tools (ffmpeg, Tesseract, liblouis, Pandoc) into the
  exe, run `python tools/build-vendor.py --no-dectalk` (needs **7-Zip** on PATH)
  before the build — the public release exe deliberately **excludes** DECtalk.
  See [`star/BUILD.md`](../star/BUILD.md).

## Pre-release tags

Use a suffix (e.g. `v0.1.24-rc1`) for a dry run: the workflow still builds the
wheel, routes the publish to TestPyPI, and creates a (pre-)release you can inspect
before cutting the final tag.

## Optional signing & native installers

The release workflow also carries **optional, off-by-default** jobs for
GPG-signing the wheel/sdist and building native installers (Windows NSIS +
Authenticode, macOS `.app`/DMG + notarization, Linux AppImage). Each is *skipped*
— never failed — when its enabling variable/secret is absent, so they never block
the wheel/PyPI pipeline or the manual `pypi` approval gate. See
[`PACKAGING.md`](PACKAGING.md) for what each job does and exactly which GitHub
secrets/certificates a maintainer must configure to turn them on.
