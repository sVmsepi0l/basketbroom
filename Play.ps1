param(
    [string]$engineroot = 'C:\Program Files\Epic Games\UE_5.8',
    [validaterange(640, 7680)][int]$width = 1600,
    [validaterange(480, 4320)][int]$height = 900,
    [switch]$editorgame,
    [validateset('auto','training','regulation')][string]$mode = 'auto',
    [validateset('auto','classic','redrock','redwoods')][string]$arena = 'auto',
    [switch]$practice,
    [switch]$bloodbroom,
    [switch]$plan
)

$erroractionpreference = 'stop'
. (join-path $psscriptroot 'Tools/Resolve-BBArena.ps1')
if ($mode -eq 'training' -and $arena -notin @('auto','classic')) { throw 'environment arenas use the regulation game; omit -mode Training.' }
$gamearguments = @('-windowed', '-nosplash', "-resx=$width", "-resy=$height")
$map = $null
if ($mode -eq 'training') { $map = '/Basketbroom/Maps/BB_Arena' }
if ($mode -eq 'regulation') { $map = '/Basketbroom/Maps/BB_Regulation' }
if ($bloodbroom) {
    if ($mode -eq 'training') { throw 'bloodbroom requires the native regulation map; use -mode regulation or Auto.' }
    $map = '/Basketbroom/Maps/BB_Regulation'
}
$mapoptions = ''
if ($practice) { $mapoptions += '?practice=1' }
if ($bloodbroom) { $mapoptions += '?bloodbroom=1' }
$packageexecutable = $null
if (-not $editorgame) {
    $packagemanifest = join-path $psscriptroot '.local\latest-package.json'
    if (test-path -literalpath $packagemanifest -pathtype leaf) {
        try {
            $package = get-content -literalpath $packagemanifest -raw | convertfrom-json
            if ($package.Status -eq 'complete' -and
                -not [string]::IsNullOrWhiteSpace($package.Executable) -and
                [IO.Path]::IsPathRooted($package.Executable) -and
                (test-path -literalpath $package.Executable -pathtype leaf)) {
                $packageexecutable = $package.Executable
            }
        } catch {
            write-verbose "could not read the latest package pointer; using the editor game: $_"
        }
    }
}
if ($packageexecutable) {
    if (($mode -eq 'regulation' -or $practice -or $bloodbroom) -and -not $package.NativeRuntime) {
        throw 'the latest playable package is the training build. native regulation is waiting for a successful c++ build and packaging.'
    }
    if ($mode -ne 'training' -and $package.NativeRuntime) {
        $available = if ($package.PSObject.Properties['ArenaMaps']) { @($package.ArenaMaps) } else { @('/Basketbroom/Maps/BB_Regulation') }
        $map = resolve-bbarenamap -arena $arena -availablemaps $available
    }
    if ($map) { $gamearguments = @($map + $mapoptions) + $gamearguments }
    if ($plan) {
        [pscustomobject]@{runtime='packaged game';executable=$packageexecutable;arguments=$gamearguments;workingdirectory=(split-path -parent $packageexecutable)}
        return
    }
    write-host "opening packaged basketbroom ($width x $Height)."
    # the game is intentionally visible and interactive.
    start-process -filepath $packageexecutable -argumentlist $gamearguments -workingdirectory (split-path -parent $packageexecutable) -windowstyle normal
    return
}

$project = join-path $psscriptroot 'DevelopmentHarness\BasketbroomDev.uproject'
$editor = join-path $engineroot 'Engine\Binaries\Win64\UnrealEditor.exe'
$versionfile = join-path $engineroot 'Engine\Build\Build.version'
if (-not $map) {
    $descriptor = get-content -literalpath $project -raw | convertfrom-json
    $map = if (@($descriptor.Modules).Where({ $null -ne $_ }).Count -gt 0) { '/Basketbroom/Maps/BB_Regulation' } else { '/Basketbroom/Maps/BB_Arena' }
}
if ($map -ne '/Basketbroom/Maps/BB_Arena') { $map = resolve-bbarenamap -arena $arena -availablemaps @(get-bbeditorarenamaps -Repository $PSScriptRoot) }
$arenaFile = Join-Path $PSScriptRoot ('DevelopmentHarness\Plugins\Basketbroom\Content\Maps\' + ($map.Split('/')[-1]) + '.umap')

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
if (-not (Test-Path -LiteralPath $arenaFile -PathType Leaf)) {
    throw 'The generated arena is missing. Open the editor and run Tools/build_all.py as described in README.md.'
}

$arguments = @(
    ('"{0}"' -f $project),
    ($map + $mapOptions),
    '-game'
) + $gameArguments
if ($Plan) {
    [pscustomobject]@{Runtime='Editor game';Executable=$editor;Arguments=$arguments;WorkingDirectory=$PSScriptRoot}
    return
}
Write-Host "Opening Basketbroom in Unreal Engine 5.8 ($Width x $Height)."
# The game is intentionally visible and interactive.
Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Normal
