[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$appProject = Join-Path $repositoryRoot 'src\Portico.App\Portico.App.csproj'
$financeProject = Join-Path $repositoryRoot 'tests\Portico.Finance.Tests\Portico.Finance.Tests.csproj'
$expectedRociRoot = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot '..\roci')).TrimEnd('\', '/')
$missingRociRoot = Join-Path ([System.IO.Path]::GetTempPath()) "portico-roci-source-$([guid]::NewGuid().ToString('N'))"

function Get-RociProperties([string] $rociRoot) {
    $arguments = @(
        'msbuild',
        $appProject,
        '-getProperty:RociRoot',
        '-getProperty:RociSourceRoot',
        '-nologo'
    )

    if ($rociRoot) {
        $arguments += "-p:ROCI_ROOT=$rociRoot"
    }

    $output = & dotnet @arguments 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Could not evaluate the Roci source properties: $output"
    }

    return ($output | ConvertFrom-Json).Properties
}

function Get-NormalizedPath([string] $path) {
    return [System.IO.Path]::GetFullPath($path).TrimEnd('\', '/')
}

$previousRociRoot = $env:ROCI_ROOT
try {
    Remove-Item Env:ROCI_ROOT -ErrorAction SilentlyContinue
    $defaultProperties = Get-RociProperties
    if ((Get-NormalizedPath $defaultProperties.RociSourceRoot) -ne $expectedRociRoot) {
        throw "The default Roci source root was '$($defaultProperties.RociSourceRoot)', not '$expectedRociRoot'."
    }

    $overrideProperties = Get-RociProperties $missingRociRoot
    if ((Get-NormalizedPath $overrideProperties.RociSourceRoot) -ne (Get-NormalizedPath $missingRociRoot)) {
        throw 'ROCI_ROOT did not override the default Roci source root.'
    }

    $env:ROCI_ROOT = $missingRociRoot
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $restoreOutput = & task restore 2>&1 | Out-String
        $restoreExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($restoreExitCode -eq 0) {
        throw 'task restore succeeded without a Roci checkout.'
    }

    $errorText = 'Roci source checkout not found'
    if ([regex]::Matches($restoreOutput, [regex]::Escape($errorText)).Count -ne 1) {
        throw "task restore did not return one clear Roci setup error: $restoreOutput"
    }

    if ($restoreOutput -match 'Skipping project') {
        throw "task restore evaluated missing Roci project references: $restoreOutput"
    }

    & dotnet restore $financeProject "-p:ROCI_ROOT=$missingRociRoot"
    if ($LASTEXITCODE -ne 0) {
        throw 'Finance restore required a Roci checkout.'
    }

    & dotnet test $financeProject --no-restore "-p:ROCI_ROOT=$missingRociRoot" --filter 'Category!=VisualCapture'
    if ($LASTEXITCODE -ne 0) {
        throw 'Finance tests required a Roci checkout.'
    }
}
finally {
    if ($null -eq $previousRociRoot) {
        Remove-Item Env:ROCI_ROOT -ErrorAction SilentlyContinue
    }
    else {
        $env:ROCI_ROOT = $previousRociRoot
    }
}

Write-Host 'Local Roci source contract passed.'
