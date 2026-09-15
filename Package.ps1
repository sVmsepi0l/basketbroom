<#
.SYNOPSIS
cook and package the standalone basketbroom game for Windows.
.DESCRIPTION
uses ue 5.8's precompiled unrealgame target for the training build, or builds
basketbroomdev when the native runtime module is enabled and staged.
development is the default so a playable build retains useful diagnostics.
every run receives fresh cook, stage, and archive directories; prior packages
are preserved. save the generated assets and stop play in editor first.
.EXAMPLE
.\Package.ps1 -plan
.EXAMPLE
.\Package.ps1
.EXAMPLE
.\Package.ps1 -configuration shipping -engineroot 'D:\Epic Games\UE_5.8'
#>
[cmdletbinding()]
param(
    [string]$engineroot = 'C:\Program Files\Epic Games\UE_5.8',
    [validateset('development', 'shipping')]
    [string]$configuration = 'development',
    [switch]$plan
)

$erroractionpreference = 'stop'
$reporoot = [IO.Path]::GetFullPath($PSScriptRoot)
$enginepath = [IO.Path]::GetFullPath($EngineRoot)
$projectpath = join-path $reporoot 'DevelopmentHarness\BasketbroomDev.uproject'
$versionpath = join-path $enginepath 'Engine\Build\Build.version'
$uatpath = join-path $enginepath 'Engine\Build\BatchFiles\RunUAT.bat'
$gamestem = if ($configuration -eq 'shipping') { 'unrealgame-win64-shipping' } else { 'unrealgame' }

$requiredfiles = @(
    $projectpath,
    $versionpath,
    $uatpath,
    (join-path $enginepath 'Engine\Build\InstalledBuild.txt'),
    (join-path $enginepath 'Engine\Binaries\DotNET\AutomationTool\AutomationTool.dll'),
    (join-path $enginepath 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'),
    (join-path $enginepath ('Engine\Binaries\Win64\{0}.exe' -f $gamestem)),
    (join-path $enginepath ('Engine\Binaries\Win64\{0}.target' -f $gamestem)),
    (join-path $reporoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Maps\BB_Arena.umap'),
    (join-path $reporoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Blueprints\BP_BBGameMode.uasset')
)
foreach ($requiredpath in $requiredfiles) {
    if (-not (test-path -literalpath $requiredpath -pathtype leaf)) {
        throw "packaging prerequisite is missing: '$requiredPath'. use an installed ue 5.8 build and generate/save the basketbroom assets first."
    }
}

$engineversion = get-content -literalpath $versionpath -raw | convertfrom-json
if ($engineVersion.MajorVersion -ne 5 -or $engineVersion.MinorVersion -ne 8) {
    throw "basketbroom requires ue 5.8. selected engine is $($engineVersion.MajorVersion).$($engineVersion.MinorVersion)."
}

$projectdescriptor = get-content -literalpath $projectpath -raw | convertfrom-json
$native = @($projectDescriptor.Modules).Where({ $null -ne $_ }).Count -gt 0
$cookmaps = '/Basketbroom/Maps/BB_Arena'
if ($native) {
    $nativemap = join-path $reporoot 'DevelopmentHarness\Plugins\Basketbroom\Content\Maps\BB_Regulation.umap'
    if (-not (test-path -literalpath $nativemap)) { throw 'compile the native editor and run Tools/stage_regulation.py before packaging the native game.' }
    $cookmaps += '+/Basketbroom/Maps/BB_Regulation'
    foreach ($venue in @('bb_redrock','bb_redwoods')) {
        $venuefile = join-path $reporoot ('DevelopmentHarness/Plugins/Basketbroom/Content/Maps/' + $venue + '.umap')
        if (-not (test-path -literalpath $venuefile -pathtype leaf)) { throw "stage both environment arenas before packaging: $venuefile" }
        $cookmaps += '+/Basketbroom/Maps/' + $venue
    }
}
$pythonplugin = @($projectDescriptor.Plugins | where-object { $_.Name -eq 'pythonscriptplugin' -and $_.Enabled })
foreach ($pluginreference in $pythonplugin) {
    if (@($pluginReference.TargetAllowList).Count -ne 1 -or $pluginReference.TargetAllowList[0] -ne 'editor') {
        throw 'set pythonscriptplugin targetallowlist to ["editor"] in BasketbroomDev.uproject. its runtime preload module otherwise requires a new native game target.'
    }
}

$runname = '{0}-{1}' -f $configuration, (get-date -format 'yyyymmdd-hhmmss-fff')
$workpath = join-path $reporoot ('.local\PackageWork\' + $runname)
$archivepath = join-path $reporoot ('.local\Build\' + $runname)
$cookpath = join-path $workpath 'Cooked\Windows'
$stagepath = join-path $workpath 'stage'
$logpath = join-path $workpath 'BuildCookRun.log'
$cookproject = $projectpath
if (-not $native) {
    # uat discovers *.Target.cs even before the new runtime module is enabled.
    # a fresh source-free project cooks the working blueprint build independently.
    $cookproject = join-path $workpath 'Project\BasketbroomDev.uproject'
}

# buildcookrun resolves content-only projects to the installed unrealgame
# executable. skipbuild avoids a native compile; blueprint bytecode is cooked.
# the explicit windows cook directory also matches uat's staging lookup.
$uatarguments = @(
    '-nocompileuat',
    'buildcookrun',
    ('-project=' + $cookproject),
    '-nop4',
    '-utf8output',
    '-unattended',
    '-installed',
    '-platform=win64',
    ('-clientconfig=' + $configuration),
    $(if ($native) { '-build' } else { '-skipbuild' }),
    '-nocompileeditor',
    '-cook',
    ('-map=' + $cookmaps),
    ('-cookoutputdir=' + $cookpath),
    '-stage',
    ('-stagingdirectory=' + $stagepath),
    '-nocleanstage',
    '-pak',
    '-iostore',
    '-package',
    '-prereqs',
    '-nodebuginfo',
    '-archive',
    ('-archivedirectory=' + $archivepath)
)
if ($native) { $uatarguments += '-target=basketbroomdev' }

write-host ("ue {0}.{1}.{2} | win64 {3}" -f $engineVersion.MajorVersion, $engineVersion.MinorVersion, $engineVersion.PatchVersion, $configuration)
write-host "Project: $projectpath"
write-host "Archive: $archivepath"
write-host "build log: $logpath"
if ($plan) {
    write-host 'validated packaging inputs. no packaging process was started.'
    write-output ([pscustomobject]@{ executable = $uatpath; arguments = $uatarguments; archive = $archivepath })
    return
}

foreach ($newpath in @($workpath, $archivepath)) {
    if (test-path -literalpath $newpath) {
        throw "refusing to reuse an existing package directory: '$newPath'. run again for a fresh destination."
    }
    new-item -itemtype directory -path $newpath | out-null
}
if (-not $native) {
    $cookprojectroot = split-path -parent $cookproject
    new-item -itemtype directory -path $cookprojectroot | out-null
    copy-item -literalpath $projectpath -destination $cookproject
    copy-item -literalpath (join-path $reporoot 'DevelopmentHarness\Config') -destination (join-path $cookprojectroot 'config') -recurse
    new-item -itemtype junction -path (join-path $cookprojectroot 'plugins') -target (join-path $reporoot 'DevelopmentHarness\Plugins') | out-null
}

write-host 'cooking the saved arena and packaging its game assets.'
push-location -literalpath $reporoot
try {
    & $uatpath @uatarguments 2>&1 | tee-object -filepath $logpath
    $uatexitcode = $lastexitcode
} finally {
    pop-location
}
if ($uatexitcode -ne 0) {
    throw "packaging failed with exit code $uatExitCode. see '$logPath'. existing builds have been preserved."
}

$gameexecutables = @(get-childitem -literalpath $archivepath -filter 'BasketbroomDev.exe' -file -recurse |
    sort-object { $_.FullName.Length })
if ($gameExecutables.Count -eq 0) {
    throw "automationtool completed but the packaged BasketbroomDev.exe was not found under '$archivePath'. see '$logPath'."
}
$gamepath = $gameExecutables[0].FullName
$result = [ordered]@{
    status = 'complete'
    configuration = $configuration
    engineversion = '{0}.{1}.{2}' -f $engineVersion.MajorVersion, $engineVersion.MinorVersion, $engineVersion.PatchVersion
    archive = $archivepath
    executable = $gamepath
    log = $logpath
    nativeruntime = $native
    arenamaps = @($cookMaps.Split('+') | where-object { $_ -ne '/Basketbroom/Maps/BB_Arena' })
}
$result | convertto-json | set-content -literalpath (join-path $workpath 'package-result.json') -encoding utf8
$result | convertto-json | set-content -literalpath (join-path $reporoot '.local\latest-package.json') -encoding utf8
write-host "playable package ready: $gamepath"
write-output ([pscustomobject]$result)
