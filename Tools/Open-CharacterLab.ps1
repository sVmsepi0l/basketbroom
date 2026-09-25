<#
Open the isolated UE5.8 MetaHuman authoring project used for Basketbroom players.
Generated designs and exports remain in .local until separately reviewed.
The playable project's descriptor, renderer settings, assets and launcher are not edited.
#>
[CmdletBinding()]
param(
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8',
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$lab = Join-Path $repo '.local\CharacterLab'
$project = Join-Path $lab 'BasketbroomCharacterLab.uproject'
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$version = Get-Content -LiteralPath (Join-Path $EngineRoot 'Engine\Build\Build.version') -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8) { throw 'Character authoring requires UE5.8.' }
$required = @(
    $editor,
    (Join-Path $EngineRoot 'Engine\Plugins\MetaHuman\MetaHumanCharacter\MetaHumanCharacter.uplugin'),
    (Join-Path $EngineRoot 'Engine\Plugins\MetaHuman\MetaHumanCharacter\Content\Optional\Presets\Ada.uasset'),
    (Join-Path $EngineRoot 'Engine\Plugins\MetaHuman\MetaHumanCharacter\Content\Optional\Presets\Omari.uasset')
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing MetaHuman Creator prerequisite: $path" }
}
$arguments = @(
    ('"{0}"' -f $project), '-NoSplash', '-NoSourceControl',
    ('-ExecCmds="py {0}/Tools/editor_bridge.py"' -f $repo.Replace('\','/')),
    ('-ABSLOG="{0}/.local/ue5/character-lab.log"' -f $repo.Replace('\','/'))
)
if ($Plan) {
    [pscustomobject]@{Project=$project;Editor=$editor;Arguments=$arguments;PlayableProjectChanged=$false}
    return
}
if (Test-Path -LiteralPath $project) {
    $existing = Get-Content -LiteralPath $project -Raw | ConvertFrom-Json
    if ($existing.EngineAssociation -ne '5.8' -or
        @($existing.Plugins | Where-Object { $_.Name -eq 'MetaHumanCharacter' -and $_.Enabled }).Count -ne 1) {
        throw 'Existing CharacterLab descriptor differs; inspect it rather than overwriting it.'
    }
} else {
    New-Item -ItemType Directory -Path (Join-Path $lab 'Config') -Force | Out-Null
    [ordered]@{
        FileVersion=3; EngineAssociation='5.8'; Category='Character authoring'
        Description='Basketbroom human player authoring; isolated from playable build'
        Plugins=@(
            @{Name='MetaHumanCharacter';Enabled=$true},
            @{Name='PythonScriptPlugin';Enabled=$true;TargetAllowList=@('Editor')},
            @{Name='EditorScriptingUtilities';Enabled=$true;TargetAllowList=@('Editor')}
        )
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $project -Encoding utf8
}
$config = Join-Path $lab 'Config\DefaultEngine.ini'
if (-not (Test-Path -LiteralPath $config)) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $config) -Force | Out-Null
    @'
[/Script/Engine.RendererSettings]
r.SkinCache.CompileShaders=True
r.GPUSkin.Support16BitBoneIndex=True
r.GPUSkin.UnlimitedBoneInfluences=True
r.RayTracing=False
r.DefaultFeature.MotionBlur=False

[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX12
-D3D12TargetedShaderFormats=PCD3D_SM5
+D3D12TargetedShaderFormats=PCD3D_SM6
'@ | Set-Content -LiteralPath $config -Encoding utf8
}
# The existing bridge has one UE5 mailbox, so only one UE5 editor may own it.
$running = @(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'")
if ($running.Count) { throw 'A UE5 editor is already open. Use its current bridge, or close it cleanly before opening CharacterLab.' }
# Intentionally visible: character authoring and any Epic login require the user-facing editor.
Start-Process -FilePath $editor -ArgumentList $arguments -WindowStyle Normal
