<# Isolated file-only acceptance for Promote-Package.ps1. No actual package pointer or game process is touched. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path $repo ('.local\package-promotion-tests\' + [Guid]::NewGuid().ToString('N'))
$fixtureTools = Join-Path $fixture 'Tools'
$fixtureLocal = Join-Path $fixture '.local'
$work = Join-Path $fixtureLocal 'PackageWork\candidate'
$archive = Join-Path $fixtureLocal 'Build\candidate'
$networkRoot = Join-Path $fixtureLocal 'packaged-network'
$runtime = Join-Path $archive 'Windows\BasketbroomDev\Binaries\Win64\BasketbroomDev.exe'
foreach ($directory in @($fixtureTools, $work, (Split-Path -Parent $runtime), $networkRoot)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$helper = Join-Path $fixtureTools 'Promote-Package.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Promote-Package.ps1') -Destination $helper
$bootstrap = Join-Path $archive 'Windows\BasketbroomDev.exe'
# Placeholders are never executed. They only exercise containment and presence checks.
[IO.File]::WriteAllText($bootstrap, 'fixture bootstrap, not executable')
[IO.File]::WriteAllText($runtime, 'fixture runtime, not executable')
$manifest = Join-Path $work 'package-result.json'
$visual = Join-Path $fixtureLocal 'visual.json'
$pointer = Join-Path $fixtureLocal 'latest-package.json'
$oldPointer = '{"Status":"complete","fixture":"previous accepted package"}'
[IO.File]::WriteAllText($pointer, $oldPointer)
$maps = @('/Basketbroom/Maps/BB_Regulation', '/Basketbroom/Maps/BB_Redrock', '/Basketbroom/Maps/BB_Redwoods')
$networkPaths = @((Join-Path $networkRoot 'redrock.json'), (Join-Path $networkRoot 'redwoods.json'))
$passed = New-Object 'System.Collections.Generic.List[string]'

function Write-Json($Value, [string]$Path) { $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding UTF8 }
function Restore-Fixture {
    Write-Json ([ordered]@{ Status = 'complete'; NativeRuntime = $true; Archive = $archive; Executable = $bootstrap; ArenaMaps = $maps }) $manifest
    Write-Json ([ordered]@{ schema_version = 1; passed = $true; package_manifest_sha256 = (Get-FileHash -LiteralPath $manifest).Hash; maps_reviewed = $maps }) $visual
    for ($i = 0; $i -lt 2; $i++) {
        Write-Json ([ordered]@{
            Status = 'passed'; PackageManifest = $manifest; Executable = $runtime; Arena = $maps[$i + 1]
            Processes = @(@{ Role = 'server'; Executable = $runtime; StartupIdentityVerified = $true },
                @{ Role = 'client'; Executable = $runtime; StartupIdentityVerified = $true })
            Evidence = @{ ServerBoundLoopback = $true; ServerClientJoinSucceeded = 'fixture joined'; ClientCompletedRegulationMapLoad = 'fixture loaded' }
        }) $networkPaths[$i]
    }
}
function Run-Plan { & $helper -PackageManifest $manifest -NetworkReceipts $networkPaths -VisualAcceptance $visual -Plan }
function Expect-Rejection([string]$Name, [scriptblock]$Mutation, [scriptblock]$Action = { Run-Plan }) {
    Restore-Fixture
    & $Mutation
    $rejected = $false
    try { $null = & $Action } catch { $rejected = $true }
    if (-not $rejected) { throw "Expected rejection: $Name" }
    if ([IO.File]::ReadAllText($pointer) -cne $oldPointer) { throw "Rejected validation changed pointer: $Name" }
    $passed.Add($Name)
}

Restore-Fixture
$plan = Run-Plan
if ($plan.Status -ne 'validated' -or [IO.File]::ReadAllText($pointer) -cne $oldPointer -or
    (Test-Path -LiteralPath (Join-Path $fixtureLocal 'package-promotions'))) { throw 'Plan mutated package state.' }
$passed.Add('plan_validates_without_pointer_or_receipt_mutation')
Expect-Rejection 'wrong_visual_candidate_hash' {
    $receipt = Get-Content -LiteralPath $visual -Raw | ConvertFrom-Json
    $receipt.package_manifest_sha256 = '0' * 64
    Write-Json $receipt $visual
}
Expect-Rejection 'failed_visual_review' {
    $receipt = Get-Content -LiteralPath $visual -Raw | ConvertFrom-Json
    $receipt.passed = $false
    Write-Json $receipt $visual
}
Expect-Rejection 'missing_reviewed_map' {
    $receipt = Get-Content -LiteralPath $visual -Raw | ConvertFrom-Json
    $receipt.maps_reviewed = @($maps[0])
    Write-Json $receipt $visual
}
Expect-Rejection 'incomplete_candidate' {
    $receipt = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $receipt.Status = 'building'
    Write-Json $receipt $manifest
}
Expect-Rejection 'candidate_outside_build_directory' {
    $receipt = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $receipt.Archive = $fixtureTools
    Write-Json $receipt $manifest
}
Expect-Rejection 'failed_network_receipt' {
    $receipt = Get-Content -LiteralPath $networkPaths[0] -Raw | ConvertFrom-Json
    $receipt.Status = 'failed'
    Write-Json $receipt $networkPaths[0]
}
Expect-Rejection 'network_process_from_another_package' {
    $receipt = Get-Content -LiteralPath $networkPaths[0] -Raw | ConvertFrom-Json
    $receipt.Processes[0].Executable = $bootstrap
    Write-Json $receipt $networkPaths[0]
}
Expect-Rejection 'missing_environment_network_coverage' {} {
    & $helper -PackageManifest $manifest -NetworkReceipts @($networkPaths[0]) -VisualAcceptance $visual -Plan
}
Expect-Rejection 'manifest_outside_packagework' {
    Copy-Item -LiteralPath $manifest -Destination (Join-Path $fixtureLocal 'outside.json')
} {
    & $helper -PackageManifest (Join-Path $fixtureLocal 'outside.json') -NetworkReceipts $networkPaths -VisualAcceptance $visual -Plan
}

Restore-Fixture
$promotion = & $helper -PackageManifest $manifest -NetworkReceipts $networkPaths -VisualAcceptance $visual
if ($promotion.Status -ne 'promoted' -or (Get-FileHash -LiteralPath $pointer).Hash -ne (Get-FileHash -LiteralPath $manifest).Hash -or
    [IO.File]::ReadAllText($promotion.PreviousPointerBackup) -cne $oldPointer) { throw 'Promotion did not preserve and replace exact pointer bytes.' }
$firstBackup = $promotion.PreviousPointerBackup
$firstReceipt = $promotion.ReceiptDirectory
$passed.Add('promotion_replaces_exact_bytes_and_preserves_previous_pointer')
$second = & $helper -PackageManifest $manifest -NetworkReceipts $networkPaths -VisualAcceptance $visual
if ($second.ReceiptDirectory -eq $firstReceipt -or [IO.File]::ReadAllText($firstBackup) -cne $oldPointer -or
    (Get-FileHash -LiteralPath $second.PreviousPointerBackup).Hash -ne (Get-FileHash -LiteralPath $manifest).Hash) { throw 'Repeated promotion overwrote historical evidence.' }
$passed.Add('repeated_promotion_preserves_unique_immutable_backups')
$report = [ordered]@{ Status = 'passed'; Passed = $passed.Count; Tests = @($passed.ToArray()); Fixture = $fixture; Scope = 'File-only isolated package promotion; no real launcher pointer modified' }
Write-Json $report (Join-Path $fixture 'result.json')
[pscustomobject]$report
