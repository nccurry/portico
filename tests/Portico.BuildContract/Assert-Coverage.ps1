[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $ReportPath,
    [Parameter(Mandatory = $true)][string] $PackageName,
    [double] $MinimumLinePercent = 95,
    [double] $MinimumBranchPercent = 90
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
    throw "Coverage report not found: $ReportPath"
}

[xml] $report = Get-Content -LiteralPath $ReportPath -Raw
$packages = @($report.coverage.packages.package | Where-Object { $_.name -ceq $PackageName })
if ($packages.Count -ne 1) {
    throw "Expected one Cobertura package named '$PackageName'; found $($packages.Count)."
}

$package = $packages[0]
if (@($package.classes.class).Count -eq 0) {
    throw "Cobertura package '$PackageName' has no measured classes."
}

$culture = [System.Globalization.CultureInfo]::InvariantCulture
$lineRate = [double]::Parse([string] $package.'line-rate', $culture)
$branchRate = [double]::Parse([string] $package.'branch-rate', $culture)
if ([double]::IsNaN($lineRate) -or [double]::IsInfinity($lineRate) -or
    [double]::IsNaN($branchRate) -or [double]::IsInfinity($branchRate) -or
    $lineRate -lt 0 -or $lineRate -gt 1 -or $branchRate -lt 0 -or $branchRate -gt 1) {
    throw "Cobertura package '$PackageName' has an invalid coverage rate."
}

$linePercent = 100 * $lineRate
$branchPercent = 100 * $branchRate
$lineText = $linePercent.ToString('F2', $culture)
$branchText = $branchPercent.ToString('F2', $culture)
Write-Host "$PackageName coverage: $lineText% lines, $branchText% branches."

if ($linePercent -lt $MinimumLinePercent -or $branchPercent -lt $MinimumBranchPercent) {
    throw "$PackageName coverage is below the required $MinimumLinePercent% lines and $MinimumBranchPercent% branches."
}
