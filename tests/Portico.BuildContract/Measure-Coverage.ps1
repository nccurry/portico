[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')][string] $Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$resultsRoot = Join-Path ([System.IO.Path]::GetTempPath()) "portico-coverage-$([guid]::NewGuid().ToString('N'))"
$assertCoverage = Join-Path $PSScriptRoot 'Assert-Coverage.ps1'
$passed = $false

try {
    foreach ($name in @('Finance', 'Application')) {
        $project = Join-Path $repositoryRoot "tests\Portico.$name.Tests\Portico.$name.Tests.csproj"
        $results = Join-Path $resultsRoot $name

        & dotnet restore $project "-p:Configuration=$Configuration"
        if ($LASTEXITCODE -ne 0) { throw "Could not restore Portico.$name.Tests." }

        & dotnet build $project --no-restore --configuration $Configuration '-p:TreatWarningsAsErrors=true'
        if ($LASTEXITCODE -ne 0) { throw "Could not build Portico.$name.Tests." }

        & dotnet test $project --no-build --no-restore "-p:Configuration=$Configuration" --collect 'Code Coverage;Format=cobertura' --results-directory $results
        if ($LASTEXITCODE -ne 0) { throw "Portico.$name.Tests failed during coverage collection." }

        $reports = @(Get-ChildItem -LiteralPath $results -Filter '*.cobertura.xml' -Recurse -File)
        if ($reports.Count -ne 1) {
            throw "Expected one Cobertura report from Portico.$name.Tests; found $($reports.Count)."
        }

        & $assertCoverage -ReportPath $reports[0].FullName -PackageName "Portico.$name"
    }
    $passed = $true
}
finally {
    $temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\', '/')
    $resolvedResults = [System.IO.Path]::GetFullPath($resultsRoot)
    if ([System.IO.Path]::GetDirectoryName($resolvedResults).TrimEnd('\', '/') -eq $temporaryRoot -and
        [System.IO.Path]::GetFileName($resolvedResults) -match '^portico-coverage-[0-9a-f]{32}$' -and
        (Test-Path -LiteralPath $resolvedResults) -and $passed) {
        Remove-Item -LiteralPath $resolvedResults -Recurse -Force
    }
    elseif (Test-Path -LiteralPath $resolvedResults) {
        Write-Host "Coverage reports retained at $resolvedResults"
    }
}
