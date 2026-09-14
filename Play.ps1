param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [ValidateRange(640, 7680)][int]$Width = 1600,
    [ValidateRange(480, 4320)][int]$Height = 900,
    [switch]$EditorGame,
    [ValidateSet('Auto','Training','Regulation')][string]$Mode = 'Auto',
    [switch]$Practice,
    [switch]$Bloodbroom,
    [switch]$Plan
)

$ErrorActionPreference = 'Stop'
$gameArguments = @('-windowed', '-NoSplash', "-ResX=$Width", "-ResY=$Height")
$map = $null
if ($Mode -eq 'Training') { $map = '/Basketbroom/Maps/BB_Arena' }
if ($Mode -eq 'Regulation') { $map = '/Basketbroom/Maps/BB_Regulation' }
if ($Bloodbroom) {
    if ($Mode -eq 'Training') { throw 'Bloodbroom requires the native Regulation map; use -Mode Regulation or Auto.' }
    $map = '/Basketbroom/Maps/BB_Regulation'
}
$mapOptions = ''
if ($Practice) { $mapOptions += '?Practice=1' }
if ($Bloodbroom) { $mapOptions += '?Bloodbroom=1' }
$packageExecutable = $null
if (-not $EditorGame) {
    $packageManifest = Join-Path $PSScriptRoot '.local\latest-package.json'
    if (Test-Path -LiteralPath $packageManifest -PathType Leaf) {
        try {
            $package = Get-Content -LiteralPath $packageManifest -Raw | ConvertFrom-Json
            if ($package.Status -eq 'complete' -and
                -not [string]::IsNullOrWhiteSpace($package.Executable) -and
                [IO.Path]::IsPathRooted($package.Executable) -and
                (Test-Path -LiteralPath $package.Executable -PathType Leaf)) {
                $packageExecutable = $package.Executable
            }
        } catch {
            Write-Verbose "Could not read the latest package pointer; using the editor game: $_"
        }
    }
}
if ($packageExecutable) {
    if (($Mode -eq 'Regulation' -or $Practice -or $Bloodbroom) -and -not $package.NativeRuntime) {
        throw 'The latest playable package is the training build. Native regulation is waiting for a successful C++ build and packaging.'
    }
    if ($Practice -and -not $map) { $map = '/Basketbroom/Maps/BB_Regulation' }
    if ($map) { $gameArguments = @($map + $mapOptions) + $gameArguments }
    if ($Plan) {
        [pscustomobject]@{Runtime='Packaged game';Executable=$packageExecutable;Arguments=$gameArguments;WorkingDirectory=(Split-Path -Parent $packageExecutable)}
        return
    }
    Write-Host "Opening packaged Basketbroom ($Width x $Height)."
    # The game is intentionally visible and interactive.
    Start-Process -FilePath $packageExecutable -ArgumentList $gameArguments -WorkingDirectory (Split-Path -Parent $packageExecutable) -WindowStyle Normal
    return
}

$project = Join-Path $PSScriptRoot 'DevelopmentHarness\BasketbroomDev.uproject'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$versionFile = Join-Path $EngineRoot 'Engine\Build\Build.version'
if (-not $map) {
    $descriptor = Get-Content -LiteralPath $project -Raw | ConvertFrom-Json
    $map = if (@($descriptor.Modules).Where({ $null -ne $_ }).Count -gt 0) { '/Basketbroom/Maps/BB_Regulation' } else { '/Basketbroom/Maps/BB_Arena' }
}
$arena = Join-Path $PSScriptRoot ('DevelopmentHarness\Plugins\Basketbroom\Content\Maps\' + ($map.Split('/')[-1]) + '.umap')

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
if (-not (Test-Path -LiteralPath $arena -PathType Leaf)) {
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
