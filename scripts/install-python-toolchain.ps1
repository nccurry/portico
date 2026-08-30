[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyprojectPath = Join-Path $RepoRoot "pyproject.toml"
$BinDir = Join-Path $RepoRoot ".tools\bin"
$UvExe = Join-Path $BinDir "uv.exe"

if ([string]::IsNullOrWhiteSpace($env:UV_PYTHON_INSTALL_DIR)) {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $RepoRoot ".tools\python"
}
if ([string]::IsNullOrWhiteSpace($env:UV_CACHE_DIR)) {
    $env:UV_CACHE_DIR = Join-Path $RepoRoot ".local\uv-cache"
}

function Get-BootstrapVersion {
    param([string]$Name)

    $pattern = "^\s*$Name\s*=\s*""([^""]+)"""
    foreach ($line in Get-Content -LiteralPath $PyprojectPath) {
        if ($line -match $pattern) {
            return $Matches[1]
        }
    }

    throw "Missing $Name version in $PyprojectPath"
}

function Assert-NativeSuccess {
    param(
        [string]$Command,
        [int]$ExitCode
    )

    if ($ExitCode -ne 0) {
        throw "$Command failed with exit code $ExitCode"
    }
}

function Test-UvVersion {
    param([string]$Version)

    if (-not (Test-Path -LiteralPath $UvExe)) {
        return $false
    }

    $output = & $UvExe --version 2>$null
    return $LASTEXITCODE -eq 0 -and ($output -join " ") -match [regex]::Escape($Version)
}

function Get-UvTarget {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture
    if ($arch -eq "Arm64") {
        return "aarch64-pc-windows-msvc"
    }
    if ($arch -eq "X64") {
        return "x86_64-pc-windows-msvc"
    }

    throw "Unsupported processor architecture for uv installation: $arch"
}

function Install-Uv {
    param([string]$Version)

    if (Test-UvVersion -Version $Version) {
        return
    }

    $target = Get-UvTarget
    $url = "https://github.com/astral-sh/uv/releases/download/$Version/uv-$target.zip"
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) "portico-uv-$Version-$([Guid]::NewGuid())"
    $archivePath = Join-Path $tempDir "uv.zip"

    Write-Host "[SETUP] Installing uv $Version"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

    try {
        Invoke-WebRequest -Uri $url -OutFile $archivePath -UseBasicParsing
        Expand-Archive -LiteralPath $archivePath -DestinationPath $tempDir -Force

        $uv = Get-ChildItem -LiteralPath $tempDir -Recurse -Filter "uv.exe" |
            Select-Object -First 1
        $uvx = Get-ChildItem -LiteralPath $tempDir -Recurse -Filter "uvx.exe" |
            Select-Object -First 1
        if ($null -eq $uv) {
            throw "uv.exe was not found in $url"
        }

        Copy-Item -LiteralPath $uv.FullName -Destination $UvExe -Force
        if ($null -ne $uvx) {
            Copy-Item -LiteralPath $uvx.FullName -Destination (Join-Path $BinDir "uvx.exe") -Force
        }
    }
    finally {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$PythonVersion = Get-BootstrapVersion "python"
$UvVersion = Get-BootstrapVersion "uv"

Install-Uv -Version $UvVersion
& $UvExe --version
Assert-NativeSuccess -Command "uv --version" -ExitCode $LASTEXITCODE

Write-Host "[SETUP] Ensuring Python $PythonVersion"
& $UvExe python install --no-bin --no-registry $PythonVersion
Assert-NativeSuccess -Command "uv python install" -ExitCode $LASTEXITCODE
