<#
.SYNOPSIS
Cook and package the standalone Basketbroom game for Windows.
.DESCRIPTION
Uses UE 5.8's precompiled UnrealGame target for the training build, or builds
BasketbroomDev when the native runtime module is enabled and staged.
Development is the default so a playable build retains useful diagnostics.
Every run receives fresh cook, stage, and archive directories; prior packages
are preserved. Save the generated assets and stop Play In Editor first.
.EXAMPLE
.\Package.ps1 -Plan
.EXAMPLE
.\Package.ps1
.EXAMPLE
.\Package.ps1 -Configuration Shipping -EngineRoot 'D:\Epic Games\UE_5.8'
#>
[CmdletBinding()]
param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [ValidateSet('Development', 'Shipping')]
    [string]$Configuration = 'Development',
    [switch]$Plan
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$enginePath = [IO.Path]::GetFullPath($EngineRoot)
$projectPath = Join-Path $repoRoot 'DevelopmentHarness\BasketbroomDev.uproject'
$versionPath = Join-Path $enginePath 'Engine\Build\Build.version'
$uatPath = Join-Path $enginePath 'Engine\Build\BatchFiles\RunUAT.bat'
$gameStem = if ($Configuration -eq 'Shipping') { 'UnrealGame-Win64-Shipping' } else { 'UnrealGame' }

$requiredFiles = @(
    $projectPath,
    $versionPath,
    $uatPath,
    (Join-Path $enginePath 'Engine\Build\InstalledBuild.txt'),
    (Join-Path $enginePath 'Engine\Binaries\DotNET\AutomationTool\AutomationTool.dll'),
    (Join-Path $enginePath 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'),
    (Join-Path $enginePath ('Engine\Binaries\Win64\{0}.exe' -f $gameStem)),
    (Join-Path $enginePath ('Engine\Binaries\Win64\{0}.target' -f $gameStem)),
    (Join-Path $repoRoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Maps\BB_Arena.umap'),
    (Join-Path $repoRoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Blueprints\BP_BBGameMode.uasset')
)
foreach ($requiredPath in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Packaging prerequisite is missing: '$requiredPath'. Use an installed UE 5.8 build and generate/save the Basketbroom assets first."
    }
}

$engineVersion = Get-Content -LiteralPath $versionPath -Raw | ConvertFrom-Json
if ($engineVersion.MajorVersion -ne 5 -or $engineVersion.MinorVersion -ne 8) {
    throw "Basketbroom requires UE 5.8. Selected engine is $($engineVersion.MajorVersion).$($engineVersion.MinorVersion)."
}

$projectDescriptor = Get-Content -LiteralPath $projectPath -Raw | ConvertFrom-Json
$native = @($projectDescriptor.Modules).Where({ $null -ne $_ }).Count -gt 0
$cookMaps = '/Basketbroom/Maps/BB_Arena'
if ($native) {
    $nativeMap = Join-Path $repoRoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Maps\BB_Regulation.umap'
    if (-not (Test-Path -LiteralPath $nativeMap)) { throw 'Compile the native editor and run Tools/stage_regulation.py before packaging the native game.' }
    $cookMaps += '+/Basketbroom/Maps/BB_Regulation'
}
$pythonPlugin = @($projectDescriptor.Plugins | Where-Object { $_.Name -eq 'PythonScriptPlugin' -and $_.Enabled })
foreach ($pluginReference in $pythonPlugin) {
    if (@($pluginReference.TargetAllowList).Count -ne 1 -or $pluginReference.TargetAllowList[0] -ne 'Editor') {
        throw 'Set PythonScriptPlugin TargetAllowList to ["Editor"] in BasketbroomDev.uproject. Its runtime preload module otherwise requires a new native game target.'
    }
}

$runName = '{0}-{1}' -f $Configuration, (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$workPath = Join-Path $repoRoot ('.local\PackageWork\' + $runName)
$archivePath = Join-Path $repoRoot ('.local\Build\' + $runName)
$cookPath = Join-Path $workPath 'Cooked\Windows'
$stagePath = Join-Path $workPath 'Stage'
$logPath = Join-Path $workPath 'BuildCookRun.log'
$cookProject = $projectPath
if (-not $native) {
    # UAT discovers *.Target.cs even before the new runtime module is enabled.
    # A fresh source-free project cooks the working Blueprint build independently.
    $cookProject = Join-Path $workPath 'Project\BasketbroomDev.uproject'
}

# BuildCookRun resolves content-only projects to the installed UnrealGame
# executable. skipbuild avoids a native compile; Blueprint bytecode is cooked.
# The explicit Windows cook directory also matches UAT's staging lookup.
$uatArguments = @(
    '-nocompileuat',
    'BuildCookRun',
    ('-project=' + $cookProject),
    '-nop4',
    '-utf8output',
    '-unattended',
    '-installed',
    '-platform=Win64',
    ('-clientconfig=' + $Configuration),
    $(if ($native) { '-build' } else { '-skipbuild' }),
    '-nocompileeditor',
    '-cook',
    ('-map=' + $cookMaps),
    ('-CookOutputDir=' + $cookPath),
    '-stage',
    ('-stagingdirectory=' + $stagePath),
    '-nocleanstage',
    '-pak',
    '-iostore',
    '-package',
    '-prereqs',
    '-nodebuginfo',
    '-archive',
    ('-archivedirectory=' + $archivePath)
)
if ($native) { $uatArguments += '-target=BasketbroomDev' }

Write-Host ("UE {0}.{1}.{2} | Win64 {3}" -f $engineVersion.MajorVersion, $engineVersion.MinorVersion, $engineVersion.PatchVersion, $Configuration)
Write-Host "Project: $projectPath"
Write-Host "Archive: $archivePath"
Write-Host "Build log: $logPath"
if ($Plan) {
    Write-Host 'Validated packaging inputs. No packaging process was started.'
    Write-Output ([pscustomobject]@{ Executable = $uatPath; Arguments = $uatArguments; Archive = $archivePath })
    return
}

foreach ($newPath in @($workPath, $archivePath)) {
    if (Test-Path -LiteralPath $newPath) {
        throw "Refusing to reuse an existing package directory: '$newPath'. Run again for a fresh destination."
    }
    New-Item -ItemType Directory -Path $newPath | Out-Null
}
if (-not $native) {
    $cookProjectRoot = Split-Path -Parent $cookProject
    New-Item -ItemType Directory -Path $cookProjectRoot | Out-Null
    Copy-Item -LiteralPath $projectPath -Destination $cookProject
    Copy-Item -LiteralPath (Join-Path $repoRoot 'DevelopmentHarness\Config') -Destination (Join-Path $cookProjectRoot 'Config') -Recurse
    New-Item -ItemType Junction -Path (Join-Path $cookProjectRoot 'Plugins') -Target (Join-Path $repoRoot 'DevelopmentHarness\Plugins') | Out-Null
}

Write-Host 'Cooking the saved arena and packaging its game assets.'
Push-Location -LiteralPath $repoRoot
try {
    & $uatPath @uatArguments 2>&1 | Tee-Object -FilePath $logPath
    $uatExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($uatExitCode -ne 0) {
    throw "Packaging failed with exit code $uatExitCode. See '$logPath'. Existing builds have been preserved."
}

$gameExecutables = @(Get-ChildItem -LiteralPath $archivePath -Filter 'BasketbroomDev.exe' -File -Recurse |
    Sort-Object { $_.FullName.Length })
if ($gameExecutables.Count -eq 0) {
    throw "AutomationTool completed but the packaged BasketbroomDev.exe was not found under '$archivePath'. See '$logPath'."
}
$gamePath = $gameExecutables[0].FullName
$result = [ordered]@{
    Status = 'complete'
    Configuration = $Configuration
    EngineVersion = '{0}.{1}.{2}' -f $engineVersion.MajorVersion, $engineVersion.MinorVersion, $engineVersion.PatchVersion
    Archive = $archivePath
    Executable = $gamePath
    Log = $logPath
    NativeRuntime = $native
}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workPath 'package-result.json') -Encoding UTF8
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $repoRoot '.local\latest-package.json') -Encoding UTF8
Write-Host "Playable package ready: $gamePath"
Write-Output ([pscustomobject]$result)
