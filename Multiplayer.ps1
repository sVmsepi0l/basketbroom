[CmdletBinding()]
param(
    [ValidateSet('Host','Join','LocalTest')][string]$Mode = 'Host',
    [string]$Address = '127.0.0.1',
    [ValidateRange(1024,65535)][int]$Port = 7777,
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [switch]$EditorGame,
    [switch]$Practice,
    [ValidateSet('Auto','Classic','Redrock','Redwoods')][string]$Arena = 'Auto',
    [switch]$Bloodbroom,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Tools/Resolve-BBArena.ps1')
if ($Mode -eq 'Join' -and $Arena -ne 'Auto') { throw 'The host selects the arena; join without -Arena.' }
if ($Mode -eq 'Join' -and $Bloodbroom) { throw '-Bloodbroom is a host option. Join without this flag; the server selects the match variant.' }
if ($Address -notmatch '^[a-zA-Z0-9.-]+$') { throw 'Use a hostname or IPv4 address without a port or URL options.' }
$project = Join-Path $PSScriptRoot 'DevelopmentHarness\BasketbroomDev.uproject'
$module = Join-Path $PSScriptRoot 'DevelopmentHarness\Binaries\Win64\UnrealEditor-BasketbroomRuntime.dll'
$mapFile = Join-Path $PSScriptRoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Maps\BB_Regulation.umap'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$executable = $editor
$workingDirectory = $PSScriptRoot
$prefix = @(('"{0}"' -f $project))
$runtimeFlags = @('-game')
$runtime = 'Editor game'
if (-not $EditorGame) {
    $manifest = Join-Path $PSScriptRoot '.local\latest-package.json'
    if (Test-Path -LiteralPath $manifest -PathType Leaf) {
        $package = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
        if ($package.Status -eq 'complete' -and $package.NativeRuntime -and $package.EngineVersion -match '^5\.8(?:\.|$)' -and
            [IO.Path]::IsPathRooted($package.Executable) -and (Test-Path -LiteralPath $package.Executable -PathType Leaf)) {
            $executable = $package.Executable
            $workingDirectory = Split-Path -Parent $executable
            $prefix = @()
            $runtimeFlags = @()
            $runtime = 'Packaged game'
        }
    }
}
if ($runtime -eq 'Packaged game') {
    $available = if ($package.PSObject.Properties['ArenaMaps']) { @($package.ArenaMaps) } else { @('/Basketbroom/Maps/BB_Regulation') }
} else { $available = @(Get-BBEditorArenaMaps -Repository $PSScriptRoot) }
$venue = Resolve-BBArenaMap -Arena $Arena -AvailableMaps $available
$mapFile = Join-Path $PSScriptRoot ('DevelopmentHarness/Plugins/Basketbroom/Content/Maps/' + ($venue.Split('/')[-1]) + '.umap')
$map = $venue + '?listen'
if ($Practice) { $map += '?Practice=1' }
if ($Bloodbroom) { $map += '?Bloodbroom=1' }
if ($Mode -eq 'LocalTest') { $Address = '127.0.0.1' }
$hostArgs = $prefix + @($map) + $runtimeFlags + @("-port=$Port",'-windowed','-ResX=1280','-ResY=720','-NoSplash','-WinX=30','-WinY=30')
$joinArgs = $prefix + @("${Address}:$Port") + $runtimeFlags + @('-windowed','-ResX=1280','-ResY=720','-NoSplash','-WinX=140','-WinY=140')
if ($Mode -eq 'LocalTest') { $hostArgs += '-MULTIHOME=127.0.0.1'; $joinArgs += '-MULTIHOME=127.0.0.1' }
if ($Plan) { [pscustomobject]@{Mode=$Mode;Runtime=$runtime;Executable=$executable;HostArguments=$hostArgs;JoinArguments=$joinArgs};return }
$requiredFiles = if ($runtime -eq 'Packaged game') { @($executable) } else { @($module,$mapFile,$editor) }
foreach ($required in $requiredFiles) { if (-not (Test-Path -LiteralPath $required)) { throw "Native multiplayer build is not ready: $required. Build-Native.ps1 and stage_regulation.py are required." } }
$runDirectory = Join-Path $PSScriptRoot ('.local\Multiplayer\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
$hostLog = Join-Path $runDirectory 'host.log'
$clientLog = Join-Path $runDirectory 'client.log'
$hostArgs += @(('-abslog="{0}"' -f $hostLog),'-FORCELOGFLUSH')
$joinArgs += @(('-abslog="{0}"' -f $clientLog),'-FORCELOGFLUSH')
Write-Host "Opening Basketbroom multiplayer: $Mode ($runtime)."
if ($Mode -in @('Host','LocalTest')) {
    Start-Process -FilePath $executable -ArgumentList $hostArgs -WorkingDirectory $workingDirectory -WindowStyle Normal | Out-Null
}
if ($Mode -eq 'LocalTest') {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $listening = $false
    while ([DateTime]::UtcNow -lt $deadline -and -not $listening) {
        if (Test-Path -LiteralPath $hostLog) {
            $logText = Get-Content -LiteralPath $hostLog -Raw -ErrorAction SilentlyContinue
            $listening = $logText -match ("IpNetDriver listening on port " + $Port + '\b')
            if ($logText -match 'NetworkFailure|TravelFailure|Fatal error:') { throw "Host startup failed. See $hostLog" }
        }
        if (-not $listening) { Start-Sleep -Milliseconds 250 }
    }
    if (-not $listening) { throw "Host has not reported listening after 30 seconds. See $hostLog; the host window remains open." }
}
if ($Mode -in @('Join','LocalTest')) {
    Start-Process -FilePath $executable -ArgumentList $joinArgs -WorkingDirectory $workingDirectory -WindowStyle Normal | Out-Null
}
Write-Host 'Choose a position with 1-6 before play. The host presses Enter to begin.'
Write-Host "Logs: $runDirectory"
