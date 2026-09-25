<#
.SYNOPSIS
Select an accepted local candidate for the desktop launcher, retaining the old pointer.
.DESCRIPTION
PackageManifest must be a complete native candidate under .local/PackageWork.
NetworkReceipts are passed test_packaged_network.ps1 results for this candidate;
both environment maps require loopback coverage when present in the manifest.
VisualAcceptance is an operator-authored JSON receipt with this schema:
{"schema_version":1,"passed":true,"package_manifest_sha256":"<SHA256>",
 "maps_reviewed":["/Basketbroom/Maps/BB_Regulation","/Basketbroom/Maps/BB_Redrock","/Basketbroom/Maps/BB_Redwoods"]}
All manifest ArenaMaps must be reviewed. These gates do not certify complete
regulation, remote multiplayer, physical controllers or Hogwarts integration.
Plan performs validation without creating files. Promotion copies its evidence
to a unique .local/package-promotions directory and atomically replaces the
launcher pointer with the exact candidate manifest bytes. No files are deleted.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PackageManifest,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string[]]$NetworkReceipts,
    [Parameter(Mandatory)][string]$VisualAcceptance,
    [switch]$Plan
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$local = Join-Path $repo '.local'
$comparison = [StringComparison]::OrdinalIgnoreCase

function Get-ContainedPath([string]$Path, [string]$Root, [string]$Kind = 'Leaf') {
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [IO.Path]::IsPathRooted($Path)) {
        throw "An absolute path is required: $Path"
    }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    if (-not $full.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, $comparison)) {
        throw "Path is outside its required directory '$rootPath': $full"
    }
    if (-not (Test-Path -LiteralPath $full -PathType $Kind)) { throw "Missing $Kind path: $full" }
    # Reject junctions/symlinks in the local tree rather than following them out.
    $cursor = $full
    while ($cursor.Length -gt $repo.Length) {
        if (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Reparse points are not accepted for package promotion: $cursor"
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

function Get-Sha([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Same-Path([string]$Left, [string]$Right) {
    return [string]::Equals([IO.Path]::GetFullPath($Left), [IO.Path]::GetFullPath($Right), $comparison)
}

$manifestPath = Get-ContainedPath $PackageManifest (Join-Path $local 'PackageWork')
$manifestSha = Get-Sha $manifestPath
$package = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($package.Status -cne 'complete' -or $package.NativeRuntime -isnot [bool] -or -not $package.NativeRuntime) {
    throw 'The candidate must be a completed native runtime package.'
}
$archive = Get-ContainedPath $package.Archive (Join-Path $local 'Build') 'Container'
$executable = Get-ContainedPath $package.Executable $archive
$runtime = Get-ContainedPath (Join-Path (Split-Path -Parent $executable) 'BasketbroomDev\Binaries\Win64\BasketbroomDev.exe') $archive
$maps = @($package.ArenaMaps)
if (-not $maps.Count -or @($maps | Where-Object { $_ -isnot [string] -or $_ -notmatch '^/Basketbroom/Maps/BB_[A-Za-z0-9_]+$' }).Count) {
    throw 'The candidate must enumerate its ArenaMaps.'
}

$visualPath = Get-ContainedPath $VisualAcceptance $local
$visualSha = Get-Sha $visualPath
$visual = Get-Content -LiteralPath $visualPath -Raw | ConvertFrom-Json
if ($visual.schema_version -ne 1 -or $visual.passed -isnot [bool] -or -not $visual.passed -or $visual.package_manifest_sha256 -ne $manifestSha) {
    throw 'Visual acceptance must pass and identify this exact candidate manifest SHA-256.'
}
foreach ($map in $maps) {
    if (@($visual.maps_reviewed) -cnotcontains $map) { throw "Visual acceptance is missing map: $map" }
}

$networkEvidence = @()
foreach ($receipt in $NetworkReceipts) {
    $receiptPath = Get-ContainedPath $receipt (Join-Path $local 'packaged-network')
    $network = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    if ($network.Status -cne 'passed' -or -not (Same-Path $network.PackageManifest $manifestPath) -or
        -not (Same-Path $network.Executable $runtime) -or $maps -cnotcontains $network.Arena) {
        throw "Network receipt is not a passed result for this candidate: $receiptPath"
    }
    foreach ($role in @('server', 'client')) {
        $processes = @($network.Processes | Where-Object Role -CEQ $role)
        if ($processes.Count -ne 1 -or $processes[0].StartupIdentityVerified -ne $true -or
            -not (Same-Path $processes[0].Executable $runtime)) {
            throw "Network receipt has an unverified or wrong $role executable: $receiptPath"
        }
    }
    if ($network.Evidence.ServerBoundLoopback -ne $true -or [string]::IsNullOrWhiteSpace($network.Evidence.ServerClientJoinSucceeded) -or
        [string]::IsNullOrWhiteSpace($network.Evidence.ClientCompletedRegulationMapLoad)) {
        throw "Network receipt lacks loopback join/map-load evidence: $receiptPath"
    }
    $networkEvidence += [pscustomobject]@{ Path = $receiptPath; Sha256 = (Get-Sha $receiptPath); Arena = $network.Arena }
}
foreach ($map in @('/Basketbroom/Maps/BB_Redrock', '/Basketbroom/Maps/BB_Redwoods')) {
    if ($maps -ccontains $map -and @($networkEvidence.Arena) -cnotcontains $map) { throw "Network receipt missing for: $map" }
}

$result = [ordered]@{
    Status = 'validated'; PackageManifest = $manifestPath; PackageManifestSha256 = $manifestSha
    Executable = $executable; VisualAcceptance = $visualPath; VisualAcceptanceSha256 = $visualSha
    MapsReviewed = @($visual.maps_reviewed); NetworkReceipts = $networkEvidence
    Scope = 'Local package acceptance; loopback join and map travel are not full multiplayer certification'
}
if ($Plan) { [pscustomobject]$result; return }

$lock = $null
try {
    $lockPath = Join-Path $local 'package-promotion.lock'
    if (Test-Path -LiteralPath $lockPath) { $null = Get-ContainedPath $lockPath $local }
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $runName = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N')
    $receiptDirectory = Join-Path $local ('package-promotions\' + $runName)
    # Validate the destination parent before allowing creation through a junction.
    $promotionRoot = Split-Path -Parent $receiptDirectory
    if (Test-Path -LiteralPath $promotionRoot) { $null = Get-ContainedPath $promotionRoot $local 'Container' }
    New-Item -ItemType Directory -Path $receiptDirectory | Out-Null
    $evidenceFiles = @([pscustomobject]@{ Path = $manifestPath; Sha256 = $manifestSha; Name = 'candidate-manifest.json' },
        [pscustomobject]@{ Path = $visualPath; Sha256 = $visualSha; Name = 'visual-acceptance.json' })
    for ($i = 0; $i -lt $networkEvidence.Count; $i++) {
        $evidenceFiles += [pscustomobject]@{ Path = $networkEvidence[$i].Path; Sha256 = $networkEvidence[$i].Sha256; Name = "network-$i.json" }
    }
    foreach ($evidence in $evidenceFiles) {
        $copy = Join-Path $receiptDirectory $evidence.Name
        [IO.File]::Copy($evidence.Path, $copy, $false)
        if ((Get-Sha $copy) -ne $evidence.Sha256) { throw "Evidence changed during promotion: $($evidence.Path)" }
    }
    $pointer = Join-Path $local 'latest-package.json'
    $pending = Join-Path $receiptDirectory 'pending-pointer.json'
    [IO.File]::Copy((Join-Path $receiptDirectory 'candidate-manifest.json'), $pending, $false)
    $backup = $null
    if (Test-Path -LiteralPath $pointer) {
        $null = Get-ContainedPath $pointer $local
        $backup = Join-Path $receiptDirectory 'previous-latest-package.json'
        [IO.File]::Replace($pending, $pointer, $backup, $false)
    } else {
        [IO.File]::Move($pending, $pointer)
    }
    $result.Status = 'promoted'
    $result.PromotedUtc = [DateTime]::UtcNow.ToString('o')
    $result.PreviousPointerBackup = $backup
    $result.ReceiptDirectory = $receiptDirectory
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $receiptDirectory 'promotion.json') -Encoding UTF8
    [pscustomobject]$result
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
}
