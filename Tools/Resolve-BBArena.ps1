# Shared launcher venue resolution; only named, available regulation maps.
function Resolve-BBArenaMap {
    param([ValidateSet('Auto','Classic','Redrock','Redwoods')][string]$Arena,
          [string[]]$AvailableMaps)
    $known = @{Classic='/Basketbroom/Maps/BB_Regulation'; Redrock='/Basketbroom/Maps/BB_Redrock'; Redwoods='/Basketbroom/Maps/BB_Redwoods'}
    if ($Arena -eq 'Auto') { $Arena = if ($AvailableMaps -contains $known.Redrock) { 'Redrock' } else { 'Classic' } }
    $chosen = $known[$Arena]
    if ($AvailableMaps -notcontains $chosen) { throw "The selected build does not contain the $Arena arena. Package its saved map first, or select an available arena." }
    return $chosen
}
function Get-BBEditorArenaMaps {
    param([string]$Repository)
    foreach ($name in @('BB_Regulation','BB_Redrock','BB_Redwoods')) {
        if (Test-Path -LiteralPath (Join-Path $Repository "DevelopmentHarness/Plugins/Basketbroom/Content/Maps/$name.umap") -PathType Leaf) { "/Basketbroom/Maps/$name" }
    }
}
