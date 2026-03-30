#Requires -Version 5.1
<#
.SYNOPSIS
    One-liner installer for The Embedinator CLI on Windows.

.DESCRIPTION
    Downloads the latest embedinator binary from GitHub Releases, verifies the
    SHA-256 checksum, installs to %LOCALAPPDATA%\Programs\embedinator\, and adds
    that directory to the user PATH via the registry.

.PARAMETER Version
    Install a specific version instead of the latest (e.g., "0.1.0").

.EXAMPLE
    irm https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.ps1 | iex

.EXAMPLE
    & { $Version = '0.1.0'; irm https://raw.githubusercontent.com/Bruno-Ghiberto/The-Embedinator/main/cli/scripts/install.ps1 | iex }

.NOTES
    Requires internet access and PowerShell 5.1+.
    A new terminal window is required after installation for PATH changes to take effect.
#>

[CmdletBinding()]
param(
    [string]$Version = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
$Repo          = 'Bruno-Ghiberto/The-Embedinator'
$BinaryName    = 'embedinator'
$ReleasesApi   = "https://api.github.com/repos/$Repo/releases"
$GitHubDlBase  = "https://github.com/$Repo/releases/download"
$InstallDir    = Join-Path $env:LOCALAPPDATA 'Programs\embedinator'

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
function Write-Info    { param([string]$Msg) Write-Host "[embedinator] $Msg" -ForegroundColor Cyan }
function Write-Success { param([string]$Msg) Write-Host "[embedinator] $Msg" -ForegroundColor Green }
function Write-Warn    { param([string]$Msg) Write-Host "[embedinator] WARNING: $Msg" -ForegroundColor Yellow }
function Write-Err     { param([string]$Msg) Write-Host "[embedinator] ERROR: $Msg" -ForegroundColor Red }

function Stop-WithError {
    param([string]$Msg)
    Write-Err $Msg
    exit 1
}

# ---------------------------------------------------------------------------
# Architecture detection
# ---------------------------------------------------------------------------
function Get-Arch {
    $machine = [System.Environment]::GetEnvironmentVariable('PROCESSOR_ARCHITECTURE')
    switch ($machine) {
        'AMD64'  { return 'amd64' }
        'ARM64'  { return 'arm64' }
        default  { Stop-WithError "Unsupported architecture: $machine. Only amd64 and arm64 are supported." }
    }
}

# ---------------------------------------------------------------------------
# GitHub Releases API: find latest cli/v* tag
# ---------------------------------------------------------------------------
function Get-LatestVersion {
    $url = "$ReleasesApi`?per_page=50"
    try {
        $response = Invoke-RestMethod -Uri $url -TimeoutSec 15
    } catch {
        Stop-WithError "Failed to query GitHub Releases API: $_`nCheck your internet connection."
    }

    foreach ($release in $response) {
        if ($release.tag_name -match '^cli/v(.+)$') {
            return $Matches[1]
        }
    }

    Stop-WithError "Could not determine the latest CLI version from GitHub Releases.`nTry again later or download manually from: https://github.com/$Repo/releases"
}

# ---------------------------------------------------------------------------
# Download helper with progress
# ---------------------------------------------------------------------------
function Invoke-Download {
    param(
        [string]$Url,
        [string]$Destination
    )
    Write-Info "  -> $Url"
    try {
        # Use BITS if available for better progress display; fallback to Invoke-WebRequest
        if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
            Start-BitsTransfer -Source $Url -Destination $Destination -ErrorAction Stop
        } else {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -TimeoutSec 120 -ErrorAction Stop
            $ProgressPreference = 'Continue'
        }
    } catch {
        Stop-WithError "Download failed from ${Url}: $_"
    }
}

# ---------------------------------------------------------------------------
# SHA-256 checksum verification
# ---------------------------------------------------------------------------
function Test-Checksum {
    param(
        [string]$ArchivePath,
        [string]$ChecksumsPath
    )
    $archiveBasename = Split-Path $ArchivePath -Leaf
    $checksumContent = Get-Content $ChecksumsPath -Raw

    # Find line matching "  <filename>"
    $expectedHash = $null
    foreach ($line in $checksumContent -split "`n") {
        $line = $line.Trim()
        if ($line -match "^([a-fA-F0-9]{64})\s+$([regex]::Escape($archiveBasename))$") {
            $expectedHash = $Matches[1].ToLower()
            break
        }
    }

    if (-not $expectedHash) {
        Stop-WithError "Checksum entry not found for $archiveBasename in checksums.txt"
    }

    $actualHash = (Get-FileHash -Algorithm SHA256 -Path $ArchivePath).Hash.ToLower()

    if ($actualHash -ne $expectedHash) {
        Stop-WithError "Checksum mismatch for ${archiveBasename}.`n  Expected: $expectedHash`n  Got:      $actualHash`nThe downloaded file may be corrupted or tampered with. Aborting installation."
    }

    Write-Success "Checksum verified."
}

# ---------------------------------------------------------------------------
# Add directory to user PATH (registry, persistent)
# ---------------------------------------------------------------------------
function Add-ToUserPath {
    param([string]$Dir)

    $registryPath = 'Registry::HKEY_CURRENT_USER\Environment'
    $currentPath  = (Get-ItemProperty -Path $registryPath -Name 'Path' -ErrorAction SilentlyContinue).Path

    if ($null -eq $currentPath) {
        $currentPath = ''
    }

    # Normalise separators and check for presence
    $pathParts = $currentPath -split ';' | Where-Object { $_ -ne '' }
    $alreadyInPath = $pathParts | Where-Object { $_.TrimEnd('\') -ieq $Dir.TrimEnd('\') }

    if ($alreadyInPath) {
        return
    }

    $newPath = ($pathParts + $Dir) -join ';'
    Set-ItemProperty -Path $registryPath -Name 'Path' -Value $newPath -Type ExpandString

    # Notify running shells via WM_SETTINGCHANGE (best-effort, not critical)
    try {
        $sig = @'
[DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg,
    UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
        $type = Add-Type -MemberDefinition $sig -Name 'Win32' -Namespace 'NativeMethods' -PassThru
        $result = [UIntPtr]::Zero
        $type::SendMessageTimeout([IntPtr]0xFFFF, 0x001A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$result) | Out-Null
    } catch {
        # Non-fatal — PATH update still persists in registry
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
function Main {
    Write-Host ''
    Write-Info 'Installing The Embedinator CLI...'
    Write-Host ''

    $arch = Get-Arch
    Write-Info "Detected platform: windows/$arch"

    # Resolve version
    $resolvedVersion = $Version
    if ($resolvedVersion) {
        # Strip leading 'v' if provided (e.g., v0.1.0 -> 0.1.0)
        $resolvedVersion = $resolvedVersion -replace '^v', ''
        Write-Info "Requested version: v$resolvedVersion"
    } else {
        Write-Info 'Checking latest release...'
        $resolvedVersion = Get-LatestVersion
        Write-Info "Latest version: v$resolvedVersion"
    }

    # Build asset names
    $archiveName   = "embedinator_v${resolvedVersion}_windows_${arch}.zip"
    $tag           = "cli/v${resolvedVersion}"
    $downloadUrl   = "$GitHubDlBase/$tag/$archiveName"
    $checksumsUrl  = "$GitHubDlBase/$tag/checksums.txt"

    # Temporary working directory
    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

    try {
        $archivePath   = Join-Path $tmpDir $archiveName
        $checksumsPath = Join-Path $tmpDir 'checksums.txt'

        # Download
        Write-Info "Downloading $archiveName..."
        Invoke-Download -Url $downloadUrl -Destination $archivePath

        Write-Info 'Downloading checksums...'
        Invoke-Download -Url $checksumsUrl -Destination $checksumsPath

        # Verify checksum
        Write-Info 'Verifying checksum...'
        Test-Checksum -ArchivePath $archivePath -ChecksumsPath $checksumsPath

        # Extract
        Write-Info 'Extracting binary...'
        Expand-Archive -Path $archivePath -DestinationPath $tmpDir -Force

        $extractedBinary = Join-Path $tmpDir "$BinaryName.exe"
        if (-not (Test-Path $extractedBinary)) {
            Stop-WithError "Expected binary '$BinaryName.exe' not found in archive."
        }

        # Install to target directory
        Write-Info "Installing to $InstallDir..."
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

        $installPath = Join-Path $InstallDir "$BinaryName.exe"
        Copy-Item -Path $extractedBinary -Destination $installPath -Force

        # Add to user PATH
        Write-Info 'Adding to user PATH...'
        Add-ToUserPath -Dir $InstallDir

        # Verify installation (best-effort — may fail if PATH not yet active in this shell)
        $versionOutput = & $installPath version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Binary installed but 'embedinator version' exited with an error. This may be harmless."
        }

        Write-Host ''
        Write-Success "The Embedinator CLI v$resolvedVersion installed successfully!"
        Write-Host ''
        Write-Host "  Installed to: $installPath" -ForegroundColor White
        Write-Host ''
        Write-Host '  IMPORTANT: Open a new terminal window for PATH changes to take effect.' -ForegroundColor Yellow
        Write-Host ''
        Write-Host '  Next steps:' -ForegroundColor White
        Write-Host ''
        Write-Host '    1. Open a new PowerShell or Command Prompt window'
        Write-Host '    2. Run: embedinator'
        Write-Host '       (First run launches the setup wizard - no git clone needed)'
        Write-Host ''
        Write-Host '  Common commands:' -ForegroundColor White
        Write-Host ''
        Write-Host '    embedinator           Run setup wizard (first time) or start services'
        Write-Host '    embedinator start     Start all services'
        Write-Host '    embedinator stop      Stop all services'
        Write-Host '    embedinator status    Show service health'
        Write-Host '    embedinator doctor    Diagnose common problems'
        Write-Host ''
        Write-Host "  Documentation: https://github.com/$Repo" -ForegroundColor Cyan
        Write-Host ''

    } finally {
        # Clean up temp directory
        Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Main
