<#
.SYNOPSIS
    Build a Windows NSIS installer (star-setup.exe) around the fat zipapp, and
    Authenticode-sign it when a code-signing certificate is supplied.

.DESCRIPTION
    OPTIONAL packaging helper, invoked by the ``windows-installer`` job in
    ``.github/workflows/release.yml`` (and runnable locally).  It wraps the
    prebuilt ``star.pyz`` fat zipapp in a click-through installer that drops the
    zipapp + a launcher .cmd under the user's Programs folder and creates a Start
    Menu shortcut.  The wheel remains the primary distribution channel; this is a
    convenience artifact for users who want a double-click install.

    Signing is best-effort and OFF by default: when the environment variable
    ``WINDOWS_CERT_PFX_BASE64`` is empty/absent the installer is produced
    UNSIGNED (SmartScreen will warn on first run) and the script still succeeds,
    so CI never fails for lack of a certificate.  Provide a base64-encoded .pfx
    in ``WINDOWS_CERT_PFX_BASE64`` and its password in ``WINDOWS_CERT_PASSWORD``
    to enable Authenticode signing via signtool.

.PARAMETER Payload
    Path to the prebuilt star.pyz (default: dist\star.pyz).

.PARAMETER OutDir
    Where to write star-setup.exe (default: dist).

.NOTES
    Requires makensis (NSIS) on PATH.  signtool (Windows SDK) is only needed when
    signing.  This script never touches PyPI or the release pipeline; a missing
    cert is a no-op, not an error.
#>
[CmdletBinding()]
param(
    [string]$Payload = "dist/star.pyz",
    [string]$OutDir = "dist"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Payload)) {
    throw "Payload not found: $Payload - build it first with 'python build_zipapp.py'."
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Derive the version from the running package so the installer metadata matches.
$version = (& python -c "import star._runtime as r; print(r.APP_VERSION)").Trim()
if (-not $version) { $version = "0.0.0" }
Write-Host "Building star-setup.exe for version $version"

$payloadFull = (Resolve-Path $Payload).Path
$outFull = (Resolve-Path $OutDir).Path
$setupExe = Join-Path $outFull "star-setup-$version.exe"

# Emit a self-contained NSIS script.  Kept minimal on purpose: install the
# zipapp + a launcher, add a Start Menu entry, and register an uninstaller.
# The NSIS body is a fully-literal single-quoted here-string (no PowerShell
# interpolation, so NSIS's own ``$INSTDIR`` / ``$SMPROGRAMS`` variables and the
# ``$\r$\n`` escapes pass through untouched).  The three build-time values
# (version, payload path, output path) are supplied as NSIS !define lines that
# we prepend, so no escaping gymnastics are needed.
$nsiBody = @'
Name "star ${STAR_VERSION}"
OutFile "${STAR_OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\star"
RequestExecutionLevel user
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File "${STAR_PAYLOAD}"
  ; Launcher: run the zipapp with pythonw (windowed) so no console flashes.
  FileOpen $0 "$INSTDIR\star.cmd" w
  FileWrite $0 "@echo off$\r$\n"
  FileWrite $0 "start "" pythonw ""%~dp0star.pyz"" %*$\r$\n"
  FileClose $0
  CreateDirectory "$SMPROGRAMS\star"
  CreateShortcut "$SMPROGRAMS\star\star.lnk" "$INSTDIR\star.cmd"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  CreateShortcut "$SMPROGRAMS\star\Uninstall star.lnk" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\star.pyz"
  Delete "$INSTDIR\star.cmd"
  Delete "$INSTDIR\uninstall.exe"
  Delete "$SMPROGRAMS\star\star.lnk"
  Delete "$SMPROGRAMS\star\Uninstall star.lnk"
  RMDir "$SMPROGRAMS\star"
  RMDir "$INSTDIR"
SectionEnd
'@

# Prepend the build-time !defines (these DO come from PowerShell variables).
$nsiHeader = @(
    "!define STAR_VERSION `"$version`""
    "!define STAR_OUTFILE `"$setupExe`""
    "!define STAR_PAYLOAD `"$payloadFull`""
) -join "`r`n"

$nsiPath = Join-Path $outFull "star.nsi"
Set-Content -Path $nsiPath -Value ($nsiHeader + "`r`n" + $nsiBody) -Encoding UTF8

# Locate makensis.
$makensis = (Get-Command makensis -ErrorAction SilentlyContinue)
if (-not $makensis) {
    $candidate = "C:\Program Files (x86)\NSIS\makensis.exe"
    if (Test-Path $candidate) { $makensis = $candidate }
    else { throw "makensis not found on PATH (install NSIS)." }
} else {
    $makensis = $makensis.Source
}

& "$makensis" "$nsiPath"
if ($LASTEXITCODE -ne 0) { throw "makensis failed with exit code $LASTEXITCODE" }
Write-Host "Built $setupExe"

# -- Optional Authenticode signing ------------------------------------------
$pfxB64 = $env:WINDOWS_CERT_PFX_BASE64
if ([string]::IsNullOrWhiteSpace($pfxB64)) {
    Write-Host "::notice::WINDOWS_CERT_PFX_BASE64 not set - installer left UNSIGNED (no-op)."
    exit 0
}

Write-Host "Signing certificate present - Authenticode-signing the installer."
$pfxPath = Join-Path $env:TEMP "star-signing.pfx"
[IO.File]::WriteAllBytes($pfxPath, [Convert]::FromBase64String($pfxB64))
try {
    $signtool = (Get-Command signtool -ErrorAction SilentlyContinue)
    if (-not $signtool) {
        # Best-effort locate the newest signtool in the Windows SDK.
        $found = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse `
            -Filter signtool.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "x64" } |
            Select-Object -Last 1
        if (-not $found) { throw "signtool not found (install the Windows SDK)." }
        $signtool = $found.FullName
    } else {
        $signtool = $signtool.Source
    }
    & "$signtool" sign /f "$pfxPath" /p "$env:WINDOWS_CERT_PASSWORD" `
        /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "$setupExe"
    if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }
    Write-Host "Signed $setupExe"
}
finally {
    Remove-Item $pfxPath -Force -ErrorAction SilentlyContinue
}
