[CmdletBinding()]
param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [ValidateSet('Editor','Game')][string]$Target = 'Editor',
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'DevelopmentHarness\BasketbroomDev.uproject'
$build = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
$version = Get-Content -LiteralPath (Join-Path $EngineRoot 'Engine\Build\Build.version') -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8) { throw 'Native Basketbroom requires Unreal Engine 5.8.' }
$targetName = if ($Target -eq 'Editor') { 'BasketbroomDevEditor' } else { 'BasketbroomDev' }
$arguments = @($targetName, 'Win64', 'Development', ('-Project=' + $project), '-WaitMutex', '-NoHotReloadFromIDE')
if ($Plan) { [pscustomobject]@{ Executable = $build; Arguments = $arguments }; return }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw 'C++ compiler setup is needed. Run Install-BuildTools.cmd, then retry.' }
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) { throw 'MSVC is missing. Run Install-BuildTools.cmd, then retry.' }
$original = Get-Content -LiteralPath $project -Raw
$descriptor = $original | ConvertFrom-Json
$modules = @($descriptor.Modules).Where({ $null -ne $_ })
if (-not $modules.Where({ $_.Name -eq 'BasketbroomRuntime' }).Count) {
    $modules += [pscustomobject]@{ Name='BasketbroomRuntime'; Type='Runtime'; LoadingPhase='Default' }
    $descriptor | Add-Member NoteProperty Modules $modules -Force
}
$descriptor | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $project -Encoding UTF8
$log = Join-Path $PSScriptRoot '.local\native-build.log'
try {
    & $build @arguments 2>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) { throw "Unreal build failed with $LASTEXITCODE. See $log" }
} catch {
    # Preserve the content-only playable editor configuration on an unsuccessful first migration.
    Set-Content -LiteralPath $project -Value $original -Encoding UTF8
    throw
}
Write-Host 'Native build completed. Reopen the editor and stage Tools/stage_regulation.py.'
