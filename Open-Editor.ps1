param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8'
)

$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'DevelopmentHarness\BasketbroomDev.uproject'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$versionFile = Join-Path $EngineRoot 'Engine\Build\Build.version'

if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) {
    throw "Unreal Engine 5.8 was not found at '$EngineRoot'. Pass -EngineRoot with your UE_5.8 folder."
}
if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
    throw "Cannot verify this Unreal installation: '$versionFile' is missing."
}
$version = Get-Content -LiteralPath $versionFile -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8) {
    throw "Basketbroom requires Unreal Engine 5.8. Selected engine is $($version.MajorVersion).$($version.MinorVersion)."
}
if (-not (Test-Path -LiteralPath $project -PathType Leaf)) {
    throw "Basketbroom project is missing: '$project'."
}

Write-Host 'Opening the Basketbroom Unreal Engine 5.8 project.'
# The editor is intentionally visible for interactive authoring.
Start-Process -FilePath $editor -ArgumentList @(('"{0}"' -f $project), '-NoSplash') -WorkingDirectory $PSScriptRoot
