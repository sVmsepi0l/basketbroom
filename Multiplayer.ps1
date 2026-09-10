[CmdletBinding()]
param(
    [ValidateSet('Host','Join','LocalTest')][string]$Mode = 'Host',
    [string]$Address = '127.0.0.1',
    [ValidateRange(1024,65535)][int]$Port = 7777,
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [switch]$Practice,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
if ($Address -notmatch '^[a-zA-Z0-9.-]+$') { throw 'Use a hostname or IPv4 address without a port or URL options.' }
$project = Join-Path $PSScriptRoot 'DevelopmentHarness\BasketbroomDev.uproject'
$module = Join-Path $PSScriptRoot 'DevelopmentHarness\Binaries\Win64\UnrealEditor-BasketbroomRuntime.dll'
$mapFile = Join-Path $PSScriptRoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Maps\BB_Regulation.umap'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$map = '/Basketbroom/Maps/BB_Regulation?listen'
if ($Practice) { $map += '?Practice=1' }
$hostArgs = @(('"{0}"' -f $project),$map,'-game',"-port=$Port",'-windowed','-ResX=1280','-ResY=720','-NoSplash','-WinX=30','-WinY=30')
$joinArgs = @(('"{0}"' -f $project),("${Address}:$Port"),'-game','-windowed','-ResX=1280','-ResY=720','-NoSplash','-WinX=140','-WinY=140')
if ($Plan) { [pscustomobject]@{Mode=$Mode;Executable=$editor;HostArguments=$hostArgs;JoinArguments=$joinArgs};return }
foreach ($required in @($module,$mapFile,$editor)) { if (-not (Test-Path -LiteralPath $required)) { throw "Native multiplayer build is not ready: $required. Build-Native.ps1 and stage_regulation.py are required." } }
if ($Mode -in @('Host','LocalTest')) {
    Start-Process -FilePath $editor -ArgumentList $hostArgs -WorkingDirectory $PSScriptRoot -WindowStyle Normal | Out-Null
}
if ($Mode -eq 'LocalTest') { Start-Sleep -Seconds 8 }
if ($Mode -in @('Join','LocalTest')) {
    Start-Process -FilePath $editor -ArgumentList $joinArgs -WorkingDirectory $PSScriptRoot -WindowStyle Normal | Out-Null
}
