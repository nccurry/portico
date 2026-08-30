[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TaskArgs
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyprojectPath = Join-Path $RepoRoot "pyproject.toml"
$BinDir = Join-Path $RepoRoot ".tools\bin"
$TaskExe = Join-Path $BinDir "task.exe"

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

function Test-TaskVersion {
    param([string]$Version)

    if (-not (Test-Path -LiteralPath $TaskExe)) {
        return $false
    }

    $output = & $TaskExe --version 2>$null
    return $LASTEXITCODE -eq 0 -and ($output -join " ") -match [regex]::Escape($Version)
}

function Get-TaskArchitecture {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture
    if ($arch -eq "Arm64") {
        return "arm64"
    }
    if ($arch -eq "X64") {
        return "amd64"
    }

    throw "Unsupported processor architecture for Task installation: $arch"
}

function Install-Task {
    param([string]$Version)

    if (Test-TaskVersion -Version $Version) {
        return
    }

    $arch = Get-TaskArchitecture
    $url = "https://github.com/go-task/task/releases/download/v$Version/task_windows_$arch.zip"
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) "portico-task-$Version-$([Guid]::NewGuid())"
    $archivePath = Join-Path $tempDir "task.zip"

    Write-Host "[SETUP] Installing Task $Version"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

    try {
        Invoke-WebRequest -Uri $url -OutFile $archivePath -UseBasicParsing
        Expand-Archive -LiteralPath $archivePath -DestinationPath $tempDir -Force

        $task = Get-ChildItem -LiteralPath $tempDir -Recurse -Filter "task.exe" |
            Select-Object -First 1
        if ($null -eq $task) {
            throw "task.exe was not found in $url"
        }

        Copy-Item -LiteralPath $task.FullName -Destination $TaskExe -Force
    }
    finally {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$TaskVersion = Get-BootstrapVersion "task"
Install-Task -Version $TaskVersion
& $TaskExe --version
Assert-NativeSuccess -Command "task --version" -ExitCode $LASTEXITCODE

$TaskArgs = @($TaskArgs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($TaskArgs.Count -eq 0) {
    $TaskArgs = @("setup")
}

Push-Location $RepoRoot
try {
    & $TaskExe @TaskArgs
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
