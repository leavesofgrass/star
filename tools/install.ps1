<#
    star — Speaking Terminal Access Reader
    Dependency installer for Windows (PowerShell).

    Usage (from the project folder):
        powershell -ExecutionPolicy Bypass -File .\install.ps1
        powershell -ExecutionPolicy Bypass -File .\install.ps1 -Profile all
        powershell -ExecutionPolicy Bypass -File .\install.ps1 -Profile minimal -NoVenv

    Profiles:
        minimal      GUI + TTS only
        recommended  GUI + TTS + common document formats (default)
        all          every optional Python package

    By default a virtual environment is created in .\.venv so your system
    Python is left untouched.

    Copyright (C) 2026 Jon Pielaet — GPL-3.0-or-later
#>
[CmdletBinding()]
param(
    [ValidateSet('minimal', 'recommended', 'all')]
    [string]$Profile = 'recommended',
    [switch]$NoVenv
)

$ErrorActionPreference = 'Stop'

function Say  ($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function OK   ($m) { Write-Host "  + $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "  x $m" -ForegroundColor Red; exit 1 }

Say "Installing star dependencies for Windows (profile: $Profile)"

# ── Locate Python 3.11+ ──────────────────────────────────────────────────────
$py = $null
foreach ($cand in @('python', 'py')) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $ok = & $cand -c "import sys; print(1 if sys.version_info[:2] >= (3,11) else 0)" 2>$null
        if ($ok -eq '1') { $py = $cand; break }
    }
}
if (-not $py) {
    Die "Python 3.11+ not found. Install it from https://www.python.org/downloads/ (check 'Add python.exe to PATH')."
}
OK ("Using " + (& $py --version 2>&1))

# ── Virtual environment ──────────────────────────────────────────────────────
if (-not $NoVenv) {
    if (-not (Test-Path ".venv")) {
        Say "Creating virtual environment in .\.venv"
        & $py -m venv .venv
    }
    $py = ".\.venv\Scripts\python.exe"
    OK "Using .\.venv  (activate later with: .\.venv\Scripts\Activate.ps1)"
}

Say "Upgrading pip"
& $py -m pip install --upgrade pip | Out-Null
OK "pip is up to date"

# ── Package sets ─────────────────────────────────────────────────────────────
# windows-curses is required for the --tui terminal mode on Windows.
$gui    = @('PyQt6')
$tts    = @('pyttsx3')
$common = @('pdfminer.six', 'python-docx', 'python-pptx', 'windows-curses')
$extra  = @('pytesseract', 'pymupdf', 'odfpy', 'openpyxl', 'pypandoc', 'louis', 'pydub')

switch ($Profile) {
    'minimal'     { $pkgs = $gui + $tts + @('windows-curses') }
    'recommended' { $pkgs = $gui + $tts + $common }
    'all'         { $pkgs = $gui + $tts + $common + $extra }
}

Say ("Installing Python packages: " + ($pkgs -join ' '))
try {
    & $py -m pip install @pkgs
    OK "Python packages installed"
} catch {
    Warn "PyQt6 can fail on older systems; retrying GUI with PyQt5"
    try { & $py -m pip install PyQt5 } catch { Warn "Qt GUI install failed — star will still run in --tui mode" }
}

# ── Optional external tools ──────────────────────────────────────────────────
Say "Checking optional external tools"
function Check-Bin ($name, $why) {
    if (Get-Command $name -ErrorAction SilentlyContinue) { OK "$name found ($why)" }
    else { Warn "$name missing — $why" }
}
Check-Bin ffmpeg    "needed only for MP3/OGG/MP4 audio export (WAV works without it)"
Check-Bin tesseract "needed only for OCR of scanned PDFs/images"

Write-Host ""
Write-Host "star is ready." -ForegroundColor Green
if (-not $NoVenv) {
    Write-Host "  Run it with:   .\.venv\Scripts\star.exe"
} else {
    Write-Host "  Run it with:   $py -m star"
}
Write-Host "  Force the terminal UI:  star --tui"
