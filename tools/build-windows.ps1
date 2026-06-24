<#
.SYNOPSIS
    [DEPRECATED] Build a portable, single-file Windows binary of star (dist\star.exe).

.DESCRIPTION
    DEPRECATED MANUAL FALLBACK.  The primary, stable distribution artifact is now
    the pure-Python wheel (`python -m build`, published to PyPI — install with
    `pipx install star-reader`).  This PyInstaller path is retained only for
    maintainers who specifically need a self-contained .exe; it is no longer built
    by CI on tag pushes, and it requires the explicit -AllowDeprecatedExe opt-in
    below before it will run.

    Wraps PyInstaller using star.spec.  By default it creates an isolated
    build virtual environment (.venv-build), installs PyInstaller plus the
    recommended runtime dependencies, and produces a windowed, onefile
    executable that runs on Windows machines with no Python installed.

    The resulting dist\star.exe is self-contained and portable: copy it
    anywhere and double-click to launch the GUI.

.PARAMETER AllowDeprecatedExe
    Required opt-in acknowledging that the .exe build is deprecated.  Without it
    (or the STAR_ALLOW_EXE=1 environment variable) this script refuses to run and
    points you at the wheel build instead.

.PARAMETER UseCurrentEnv
    Skip creating .venv-build and build with the currently active Python
    environment instead (assumes the dependencies are already installed).

.PARAMETER Ocr
    Also install OCR dependencies (pytesseract, PyMuPDF, Pillow).  Note: OCR
    of scanned PDFs/images still requires the external Tesseract binary to be
    present on the target machine; it is not bundled.

.PARAMETER SkipInstall
    Do not run pip install; just run PyInstaller (deps assumed present).

.PARAMETER Lean
    Skip the offline dictation / transcription stack (openai-whisper + Torch +
    the Whisper "base" model).  Dictation is bundled BY DEFAULT so Windows users
    get it out of the box; -Lean produces a small, fast build (handy for quick
    test builds / CI iteration), and star simply reports dictation as
    unavailable in `star --deps` while every other feature works unchanged.

.EXAMPLE
    # Default: full build with offline voice dictation bundled (large, slow):
    powershell -ExecutionPolicy Bypass -File build-windows.ps1

.EXAMPLE
    # Lean build, no dictation stack (fast, small):
    powershell -ExecutionPolicy Bypass -File build-windows.ps1 -Lean

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File build-windows.ps1 -UseCurrentEnv -SkipInstall
#>
[CmdletBinding()]
param(
    [switch]$UseCurrentEnv,
    [switch]$Ocr,
    [switch]$SkipInstall,
    [switch]$Lean,
    [switch]$AllowDeprecatedExe
)

$ErrorActionPreference = "Stop"

# ── Deprecation gate ──────────────────────────────────────────────────────────
# The wheel is the primary, stable artifact.  The .exe is a manual fallback only,
# so require an explicit opt-in to avoid surprising anyone who runs this by habit.
if (-not $AllowDeprecatedExe -and $env:STAR_ALLOW_EXE -ne "1") {
    Write-Host "ERR The self-contained star.exe build is DEPRECATED." -ForegroundColor Red
    Write-Host ""
    Write-Host "The primary distribution artifact is the pure-Python wheel:" -ForegroundColor Yellow
    Write-Host "    python -m build           # -> dist/star_reader-<version>-py3-none-any.whl"
    Write-Host "    pipx install star-reader  # or: pip install star-reader"
    Write-Host ""
    Write-Host "If you really need the deprecated .exe, re-run with -AllowDeprecatedExe" -ForegroundColor Yellow
    Write-Host "(or set STAR_ALLOW_EXE=1).  See star/BUILD.md for details."
    exit 1
}
# This script lives in tools/, but the build (star.spec, vendor/, dist/) is
# rooted at the project directory one level up.  Operate from there.
$root = Split-Path -Parent $PSScriptRoot
Set-Location -Path $root

function Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "OK  $msg" -ForegroundColor Green }
function Die($msg)  { Write-Host "ERR $msg" -ForegroundColor Red; exit 1 }

# ── Locate a Python 3.11+ interpreter ───────────────────────────────────────
$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $ok = & $cand -c "import sys; print(1 if sys.version_info[:2] >= (3,11) else 0)" 2>$null
        if ($ok -eq "1") { $py = $cand; break }
    }
}
if (-not $py) { Die "Python 3.11+ not found. Install it from https://www.python.org/downloads/" }
Ok ("Using " + (& $py --version 2>&1))

# ── Build environment ───────────────────────────────────────────────────────
if (-not $UseCurrentEnv) {
    $venv = Join-Path $root ".venv-build"
    if (-not (Test-Path $venv)) {
        Info "Creating build virtual environment (.venv-build)"
        & $py -m venv $venv
    }
    $py = Join-Path $venv "Scripts\python.exe"
    Ok "Build venv ready"
}

# ── Dependencies ────────────────────────────────────────────────────────────
if (-not $SkipInstall) {
    Info "Upgrading pip and installing build + runtime dependencies"
    & $py -m pip install --upgrade pip | Out-Host

    $deps = @(
        "pyinstaller",
        "PyQt6",
        "pyttsx3",
        "comtypes",
        "pdfminer.six",
        "python-docx",
        "python-pptx",
        "openpyxl",
        "odfpy",
        "windows-curses",
        # Hot-folder watching (File > Watch Folder / --watch); without it the
        # watcher still works via directory polling, but watchdog gives real
        # filesystem events.
        "watchdog",
        # Study & writing aids (bundled so they work in star.exe with no extra
        # install): sumy = document summarization, genanki = Anki flashcard
        # export, pyspellchecker = edit-mode spell checking, deep-translator =
        # document translation, feedparser = RSS/Atom feed reading, wordfreq =
        # the difficult-word overlay (ships the frequency data it needs).
        "sumy",
        "genanki",
        "pyspellchecker",
        "deep-translator",
        "feedparser",
        "wordfreq"
    )
    if ($Ocr) { $deps += @("pytesseract", "PyMuPDF", "Pillow") }

    # Dictation / transcription is bundled BY DEFAULT (Windows users can't set it
    # up themselves): openai-whisper pulls in torch, numba, tiktoken, etc. — a
    # multi-GB install.  -Lean skips it for a fast, small build.
    if (-not $Lean) {
        Info "Bundling offline dictation stack (openai-whisper + Torch) -- large/slow build"
        $deps += @("openai-whisper", "sounddevice")
    } else {
        Info "Lean build: skipping the dictation stack (openai-whisper + Torch)"
    }

    # When the Tesseract engine has been vendored for the self-contained
    # build (see build-vendor.py), its Python wrappers must be bundled too,
    # so OCR actually works in the resulting star.exe.
    $vendorTess = Join-Path $root "vendor\tesseract"
    if ((Test-Path $vendorTess) -and (-not $Ocr)) {
        Info "vendor\tesseract present -> adding OCR Python wrappers"
        $deps += @("pytesseract", "PyMuPDF", "Pillow")
    }

    & $py -m pip install @deps | Out-Host
    Ok "Dependencies installed"
}

# ── Stage the Whisper model (offline dictation) — skipped only with -Lean ───
# Bundle the "base" model so transcription/dictation needs no first-run
# download.  star.spec picks it up from build\whisper_cache\whisper\base.pt.
if (-not $Lean) {
    $model = Join-Path $root "build\whisper_cache\whisper\base.pt"
    if (-not (Test-Path $model)) {
        Info "Staging Whisper 'base' model for offline dictation (~140 MB)"
        $env:STAR_MODEL_ROOT = Join-Path $root "build\whisper_cache\whisper"
        & $py -c "import os,whisper; r=os.environ['STAR_MODEL_ROOT']; os.makedirs(r,exist_ok=True); whisper._download(whisper._MODELS['base'], r, False); print('Whisper base model staged')" | Out-Host
    }
}

# ── Stage NLTK punkt data (offline document summarization) ──────────────────
# sumy's sentence tokenizer needs NLTK's punkt / punkt_tab data.  Download it
# into build\nltk_data so star.spec bundles it and Summarize works offline.
$nltkData = Join-Path $root "build\nltk_data"
if (-not (Test-Path (Join-Path $nltkData "tokenizers\punkt_tab"))) {
    Info "Staging NLTK punkt tokenizer data for offline summarization"
    $env:STAR_NLTK_DIR = $nltkData
    & $py -c "import os,nltk; d=os.environ['STAR_NLTK_DIR']; os.makedirs(d,exist_ok=True); nltk.download('punkt',download_dir=d); nltk.download('punkt_tab',download_dir=d); print('NLTK punkt data staged')" | Out-Host
}

# ── Build ───────────────────────────────────────────────────────────────────
# Tell star.spec whether to skip the dictation stack.  Set explicitly each way
# so a stale env var from a previous shell can never leak into the wrong build.
if ($Lean) {
    $env:STAR_LEAN = "1"
    Info "Running PyInstaller (LEAN build; no Torch/Whisper)"
} else {
    Remove-Item Env:STAR_LEAN -ErrorAction SilentlyContinue
    Info "Running PyInstaller WITH the dictation stack (Torch/Whisper) -- slow + large"
}
& $py -m PyInstaller --clean --noconfirm star.spec | Out-Host

$exe = Join-Path $root "dist\star.exe"
if (Test-Path $exe) {
    $size = "{0:N1} MB" -f ((Get-Item $exe).Length / 1MB)
    Ok "Built portable binary: $exe ($size)"
    Write-Host ""
    Write-Host "Copy dist\star.exe to any Windows machine and double-click to run." -ForegroundColor Green
} else {
    Die "Build finished but dist\star.exe was not found. Check the PyInstaller output above."
}
