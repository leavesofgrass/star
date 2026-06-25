# Releasing star

star's tests and builds run on GitHub Actions. This document describes how a
release is cut and what the automation produces.

> **Release model: wheel + PyPI only.** As of 0.1.9 the automated release builds
> and ships exactly one thing — the pure-Python **wheel + sdist**, published to
> **PyPI** (and attached to the GitHub Release). The platform `star.pyz` and the
> deprecated Windows `star.exe` are **not** built on tag pushes and are **not**
> attached to releases; they are build-it-yourself artifacts (see
> [Build-it-yourself artifacts](#build-it-yourself-artifacts)).

## Continuous integration (every push / PR)

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push to
`main` and every pull request:

- **`test`** — the `pytest` suite on a matrix of Linux / Windows / macOS across
  Python 3.11–3.13. One Linux leg also installs the pure-Python optional
  packages (`deep-translator`, `feedparser`, `wordfreq`, `sumy`, `genanki`,
  `pyspellchecker`) so the real-behaviour tests run, not just the
  graceful-degradation paths.
- **`lint`** — `ruff check` (currently **non-blocking**, so a style nit never
  walls a correctness-green PR). Tightening this into a required check is future
  work.

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
   git tag v0.1.11
   git push origin v0.1.11
   ```

Pushing a `v*` tag triggers
[`.github/workflows/release.yml`](../.github/workflows/release.yml), which builds
the wheel + sdist, publishes them to PyPI, and creates a GitHub Release with
auto-generated notes.

## What the release workflow builds

| Job | Artifact | Notes |
|---|---|---|
| `wheel` | `star_reader-<version>-py3-none-any.whl` + sdist | **The release.** Pure-Python, universal; one build serves every platform. `twine check` guards the long-description rendering before the PyPI upload. |
| `publish-testpypi` / `publish-pypi` | (uploads to PyPI) | Publishes the wheel + sdist via trusted publishing — pre-release tags to TestPyPI, final tags to PyPI. See **Publishing to PyPI** below. |
| `release` | GitHub Release | Attaches the wheel + sdist and auto-generated notes. |

The `windows-pyz` and `windows-exe` jobs **do not run on tag pushes**. They exist
only as manual `workflow_dispatch` options (`build_pyz: true` / `build_exe:
true`) for the rare case a maintainer needs one of those artifacts from CI; their
output is not attached to the release.

## Publishing to PyPI

The release workflow publishes the wheel and sdist to PyPI using
[**trusted publishing**](https://docs.pypi.org/trusted-publishers/) (OIDC) — no
API token is ever stored in the repo. The routing is by tag:

- **Pre-release tag** (contains a hyphen, e.g. `v0.1.11-rc1`) → **TestPyPI**.
- **Final tag** (e.g. `v0.1.11`) → **PyPI**.

Manual `workflow_dispatch` runs do not publish (no tag ref).

### The `ENABLE_PYPI` switch

Both publish jobs are gated on a repository **variable** `ENABLE_PYPI`. When it is
set to `true` the jobs run; otherwise they **skip** (the build and GitHub Release
still run, so you can exercise the whole pipeline before the trusted publisher is
active).

`ENABLE_PYPI` is currently **`true`**, so every final `v*` tag publishes to PyPI
automatically. To pause publishing, set *Settings → Secrets and variables →
Actions → Variables → `ENABLE_PYPI`* to anything other than `true` (or remove it).

### One-time setup (already done for this repo)

1. **Register the trusted publisher on PyPI / TestPyPI.** Project → *Publishing* →
   add a GitHub Actions trusted publisher: Owner `leavesofgrass`, Repository
   `star`, Workflow `release.yml`, Environment `pypi` (and `testpypi` on
   TestPyPI).
2. **Create the GitHub environments** `pypi` and `testpypi` (Repo *Settings →
   Environments*), optionally with required reviewers as a release gate.
3. **Rehearse on TestPyPI first.** Push a pre-release tag (`v0.1.11-rc1`), confirm
   `pip install -i https://test.pypi.org/simple/ star-reader` works, then push the
   final `v0.1.11` tag.

## Build-it-yourself artifacts

These are **not** part of the automated release. Build them locally only if you
specifically need them:

```bash
python -m build                                  # wheel + sdist        -> dist/   (the release)
python build_zipapp.py                           # fat zipapp (per-OS)  -> dist/star.pyz
pwsh tools/build-windows.ps1 -AllowDeprecatedExe # DEPRECATED exe       -> dist/star.exe
```

- **`star.pyz`** — a fat zipapp bundling `star` + the `[all]` extras. It is
  platform-specific (carries compiled extensions), so build it on the OS you
  intend to run it on. See [`docs/installation.md`](installation.md#single-file-build-starpyz).
- **`star.exe`** — **deprecated.** The PyInstaller binary is retained only as a
  manual fallback and requires the explicit `-AllowDeprecatedExe` opt-in. By
  default the build bundles the offline dictation stack (Whisper + Torch + the
  `base` model), which makes it large and slow; pass `-Lean` to skip it. To make
  the exe fully self-contained (ffmpeg, Tesseract, liblouis, Pandoc, DECtalk), run
  `python tools/build-vendor.py` (needs **7-Zip** on PATH) before the build. See
  [`star/BUILD.md`](../star/BUILD.md).

## Pre-release tags

Use a suffix (e.g. `v0.1.11-rc1`) for a dry run: the workflow still builds the
wheel, routes the publish to TestPyPI, and creates a (pre-)release you can inspect
before cutting the final tag.
