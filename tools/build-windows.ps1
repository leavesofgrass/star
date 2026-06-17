<#
.SYNOPSIS
    Build a portable, single-file Windows binary of star (dist\star.exe).

.DESCRIPTION
    Wraps PyInstaller using star.spec.  By default it creates an isolated
    build virtual environment (.venv-build), installs PyInstaller plus the
    recommended runtime dependencies, and produces a windowed, onefile
    executable that runs on Windows machines with no Python installed.

    The resulting dist\star.exe is self-contained and portable: copy it
    anywhere and double-click to launch the GUI.

.PARAMETER UseCurrentEnv
    Skip creating .venv-build and build with the currently active Python
    environment instead (assumes the dependencies are already installed).

.PARAMETER Ocr
    Also install OCR dependencies (pytesseract, PyMuPDF, Pillow).  Note: OCR
    of scanned PDFs/images still requires the external Tesseract binary to be
    present on the target machine; it is not bundled.

.PARAMETER SkipInstall
    Do not run pip install; just run PyInstaller (deps assumed present).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File build-windows.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File build-windows.ps1 -UseCurrentEnv -SkipInstall
#>
[CmdletBinding()]
param(
    [switch]$UseCurrentEnv,
    [switch]$Ocr,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
# This script lives in tools/, but the build (star.spec, vendor/, dist/) is
# rooted at the project directory one level up.  Operate from there.
$root = Split-Path -Parent $PSScriptRoot
Set-Location -Path $root

function Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "OK  $msg" -ForegroundColor Green }
function Die($msg)  { Write-Host "ERR $msg" -ForegroundColor Red; exit 1 }

# ── Locate a Python 3.8+ interpreter ────────────────────────────────────────
$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $ok = & $cand -c "import sys; print(1 if sys.version_info[:2] >= (3,8) else 0)" 2>$null
        if ($ok -eq "1") { $py = $cand; break }
    }
}
if (-not $py) { Die "Python 3.8+ not found. Install it from https://www.python.org/downloads/" }
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
        # Dictation / transcription (bundled so the feature works out of the
        # box).  openai-whisper pulls in torch, numba, tiktoken, etc.; this is
        # a multi-GB install by design.  sounddevice provides mic capture.
        "openai-whisper",
        "sounddevice"
    )
    if ($Ocr) { $deps += @("pytesseract", "PyMuPDF", "Pillow") }

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

# ── Stage the Whisper model (offline dictation) ─────────────────────────────
# Bundle the "base" model so transcription/dictation needs no first-run
# download.  star.spec picks it up from build\whisper_cache\whisper\base.pt.
$model = Join-Path $root "build\whisper_cache\whisper\base.pt"
if (-not (Test-Path $model)) {
    Info "Staging Whisper 'base' model for offline dictation (~140 MB)"
    $env:STAR_MODEL_ROOT = Join-Path $root "build\whisper_cache\whisper"
    & $py -c "import os,whisper; r=os.environ['STAR_MODEL_ROOT']; os.makedirs(r,exist_ok=True); whisper._download(whisper._MODELS['base'], r, False); print('Whisper base model staged')" | Out-Host
}

# ── Build ───────────────────────────────────────────────────────────────────
Info "Running PyInstaller (bundling Torch/Whisper makes this slow + large)"
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
