[cmdletbinding()]
param(
    [string]$engineroot = 'C:\Program Files\Epic Games\UE_5.8',
    [validateset('editor','game')][string]$target = 'editor',
    [switch]$plan
)
$erroractionpreference = 'stop'
$project = join-path $psscriptroot 'DevelopmentHarness\BasketbroomDev.uproject'
$build = join-path $engineroot 'Engine\Build\BatchFiles\Build.bat'
$version = get-content -literalpath (join-path $engineroot 'Engine\Build\Build.version') -raw | convertfrom-json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8) { throw 'native basketbroom requires unreal engine 5.8.' }
$targetname = if ($target -eq 'editor') { 'basketbroomdeveditor' } else { 'basketbroomdev' }
$arguments = @($targetname, 'win64', 'development', ('-project=' + $project), '-waitmutex', '-nohotreloadfromide')
if ($plan) { [pscustomobject]@{ executable = $build; arguments = $arguments }; return }
$vswhere = join-path ${env:ProgramFiles(x86)} 'microsoft visual Studio\Installer\vswhere.exe'
if (-not (test-path -literalpath $vswhere)) { throw 'c++ compiler setup is needed. run Install-BuildTools.cmd, then retry.' }
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationpath
if (-not $installation) { throw 'msvc is missing. run Install-BuildTools.cmd, then retry.' }
$original = get-content -literalpath $project -raw
$descriptor = $original | convertfrom-json
$modules = @($descriptor.Modules).Where({ $null -ne $_ })
if (-not $modules.Where({ $_.Name -eq 'basketbroomruntime' }).Count) {
    $modules += [pscustomobject]@{ name='basketbroomruntime'; type='runtime'; loadingphase='default' }
    $descriptor | add-member noteproperty modules $modules -force
}
$descriptor | convertto-json -depth 8 | set-content -literalpath $project -encoding utf8
$log = join-path $psscriptroot '.local\native-build.log'
try {
    & $build @arguments 2>&1 | tee-object -filepath $log
    if ($lastexitcode -ne 0) { throw "unreal build failed with $LASTEXITCODE. see $log" }
} catch {
    # preserve the content-only playable editor configuration on an unsuccessful first migration.
    set-content -literalpath $project -value $original -encoding utf8
    throw
}
write-host 'native build completed. reopen the editor and stage Tools/stage_regulation.py.'
