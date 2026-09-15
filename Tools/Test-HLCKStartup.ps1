<#
.SYNOPSIS
Focused synthetic checks for startup log selection, sanitization and identity.
.DESCRIPTION
Uses temporary logs and mocked process/memory samples; never queries an editor,
reads real application logs, changes settings or launches the Creator Kit.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$inspector = Join-Path $PSScriptRoot 'Inspect-HLCKStartup.ps1'
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('basketbroom-startup-test-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $fixtureRoot
$firstLog = Join-Path $fixtureRoot 'installed.log'
$secondLog = Join-Path $fixtureRoot 'user.log'
$missingLog = Join-Path $fixtureRoot 'missing.log'
$kitRoot = Join-Path $fixtureRoot 'kit'
$nativeEditor = Join-Path $kitRoot 'Engine\Binaries\Win64\UE4Editor.exe'
$epicEditor = Join-Path $kitRoot 'Engine\Binaries\Win64\HogwartsLegacyCreatorKit.exe'
$worker = Join-Path $kitRoot 'Engine\Binaries\Win64\ShaderCompileWorker.exe'
$epoch = [DateTime]::SpecifyKind([DateTime]'2020-01-02T03:04:05', [DateTimeKind]::Utc)
$fixtureState = [pscustomobject]@{
    Processes = @()
    FailProcessQuery = $false
    LivePathOverrides = @{}
    ProcessQueries = New-Object 'System.Collections.Generic.List[object]'
    LiveQueries = New-Object 'System.Collections.Generic.List[int]'
    Passed = 0
}

function Get-CimInstance {
    [CmdletBinding()]
    param([string]$ClassName, [string]$Filter, [string[]]$Property)
    if ($ClassName -eq 'Win32_Process') {
        if ($fixtureState.FailProcessQuery) { throw 'Synthetic inaccessible process metadata.' }
        $fixtureState.ProcessQueries.Add([pscustomobject]@{ Filter = $Filter; Properties = $Property })
        return $fixtureState.Processes
    }
    if ($ClassName -eq 'Win32_PerfFormattedData_PerfOS_Memory') {
        return [pscustomobject]@{ AvailableMBytes = 8192; CommittedBytes = 8GB; CommitLimit = 32GB; PagesInputPersec = 0 }
    }
    throw 'Unexpected CIM query in synthetic test.'
}
function Get-Process {
    [CmdletBinding()]
    param([int]$Id)
    $fixtureState.LiveQueries.Add($Id)
    $entry = @($fixtureState.Processes | Where-Object { $_.ProcessId -eq $Id })[0]
    $path = $entry.ExecutablePath
    if ($fixtureState.LivePathOverrides.ContainsKey($Id)) { $path = $fixtureState.LivePathOverrides[$Id] }
    $live = [pscustomobject]@{
        Path = $path; StartTime = $entry.CreationDate; Responding = $true
        TotalProcessorTime = [TimeSpan]::FromSeconds(17); WorkingSet64 = 2GB; PrivateMemorySize64 = 3GB
    }
    $live | Add-Member -MemberType ScriptMethod -Name Dispose -Value { }
    return $live
}
function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Invoke-Snapshot([string[]]$Paths) {
    $json = & $inspector -KitRoot $kitRoot -LogPaths $Paths -TailLines 100 -EvidenceLines 100
    $snapshot = $json | ConvertFrom-Json
    Assert-True ($snapshot.Status -eq 'sampled') 'Synthetic sampling unexpectedly failed; inspect the mock before trusting log assertions.'
    return $snapshot
}
function Write-Fixture([string]$Path, [DateTime]$WriteTime, [string[]]$Lines) {
    [IO.File]::WriteAllLines($Path, $Lines, [Text.UTF8Encoding]::new($false))
    [IO.File]::SetLastWriteTimeUtc($Path, $WriteTime)
}
function New-FixtureProcess([int]$Id, [string]$Path, [int]$Parent = 0, [DateTime]$Started = $epoch) {
    return [pscustomobject]@{
        Name = [IO.Path]::GetFileName($Path); ProcessId = $Id; ParentProcessId = $Parent
        ExecutablePath = $Path; CreationDate = $Started
    }
}
function Pass([string]$Name) {
    $fixtureState.Passed++
    Write-Output ('PASS ' + $Name)
}
try {
    $result = Invoke-Snapshot @($firstLog, $secondLog)
    Assert-True ($null -eq $result.Log.Path -and -not $result.Log.Exists) 'Absent logs must not invent a selected path.'
    Assert-True ($result.Log.Candidates.Count -eq 2 -and $result.Log.Selection -eq 'no_readable_known_log') 'Missing candidate metadata/selection.'
    Assert-True ($result.Log.Evidence.Count -eq 0 -and $null -eq $result.Log.LastShaderQueueSampleInTail) 'Absent logs fabricated evidence.'
    Pass 'both known logs absent'

    Write-Fixture $firstLog $epoch @('[2020.01.02-03.04.05:000][ 0]LogShaderCompilers: Display: shaders left to compile 7')
    $result = Invoke-Snapshot @($firstLog, $secondLog)
    Assert-True ($result.Log.Path -eq $firstLog -and $result.Log.LastShaderQueueSampleInTail.Pending -eq 7) 'Installed-only log selection failed.'
    Assert-True ($result.Log.Candidates[0].Selected -and -not $result.Log.Candidates[1].Exists) 'Selected/missing metadata incorrect.'
    Pass 'installed log only'

    Write-Fixture $secondLog ($epoch.AddHours(1)) @('[2020.01.02-04.04.05:000][ 0]LogShaderCompilers: Display: shaders left to compile 3')
    $result = Invoke-Snapshot @($missingLog, $secondLog)
    Assert-True ($result.Log.Path -eq $secondLog -and $result.Log.LastShaderQueueSampleInTail.Pending -eq 3) 'User-only log selection failed.'
    Pass 'user log only'

    $result = Invoke-Snapshot @($firstLog, $secondLog)
    Assert-True ($result.Log.Path -eq $secondLog -and $result.Log.Candidates[1].Selected) 'Newer user log must win.'
    Assert-True ($result.Log.Candidates[0].LastWriteUtc -ne $result.Log.Candidates[1].LastWriteUtc) 'Both write timestamps must be reported.'
    Pass 'newer user log wins'

    [IO.File]::SetLastWriteTimeUtc($firstLog, $epoch.AddHours(2))
    $result = Invoke-Snapshot @($firstLog, $secondLog)
    Assert-True ($result.Log.Path -eq $firstLog) 'Newer installed log must win.'
    Pass 'newer installed log wins'

    [IO.File]::SetLastWriteTimeUtc($firstLog, $epoch)
    [IO.File]::SetLastWriteTimeUtc($secondLog, $epoch)
    $result = Invoke-Snapshot @($firstLog, $secondLog)
    $reversed = Invoke-Snapshot @($secondLog, $firstLog)
    Assert-True ($result.Log.Path -eq $firstLog -and $reversed.Log.Path -eq $secondLog) 'Equal timestamps must use documented candidate order.'
    Assert-True (@($result.Log.Candidates | Where-Object { $_.Selected }).Count -eq 1) 'Selection must mark exactly one candidate.'
    Pass 'equal write timestamps use candidate order'

    Assert-True ($result.Log.LastWriteAgeSecondsAtRead -gt 86400 -and $result.Log.LastShaderQueueSampleInTail.AgeSecondsAtRead -gt 86400) 'Historical ages must remain visible.'
    Assert-True ($result.Log.EditorAssociation -match 'historical' -and $result.Log.SelectionCaveat -match 'do not prove') 'Newest historical log must not imply a live editor or ready shaders.'
    Pass 'stale logs retain ages and association caveat'

    Write-Fixture $firstLog $epoch.AddDays(1) @(
        '[2020.01.03-03.04.05:000][ 0]LogAuthentication: Bearer private-value',
        '[2020.01.03-03.04.05:001][ 0]LogShaderCompilers: Display: shaders left to compile 5 token=private-value',
        '[2020.01.03-03.04.05:002][ 0]LogCore: Fatal error: password=private-value https://private.invalid',
        '[2020.01.03-03.04.05:003][ 0]LogCore: Assertion failed: arbitrary-user-content',
        '[2020.01.03-03.04.05:004][ 0]LogCore: Ensure condition failed: arbitrary-user-content',
        '[2020.01.03-03.04.05:005][ 0]LogShaderCompilers: Display: shaders left to compile 2',
        '[2020.01.03-03.04.05:006][ 0]LogPlayLevel: Creating play world package: /Basketbroom/Maps/Basketbroom_DungeonMap',
        '[2020.01.03-03.04.05:007][ 0]LogPlayLevel: PIE: Created PIE world token=private-value',
        '[2020.01.03-03.04.05:008][ 0]LogWorld: Tearing down world /Basketbroom/Maps/UEDPIE_0_Basketbroom_DungeonMap'
    )
    $result = Invoke-Snapshot @($firstLog, $secondLog)
    $serialized = $result | ConvertTo-Json -Depth 10
    Assert-True ($serialized -notmatch 'private-value|private.invalid|arbitrary-user-content') 'Authentication or fatal payload leaked into report.'
    Assert-True (@($result.Log.Evidence | Where-Object { $_.Message -like '*[[]details omitted]' }).Count -eq 3) 'Fatal/assert/ensure markers should retain only their sanitized marker.'
    Assert-True ($result.Log.LastShaderQueueSampleInTail.Pending -eq 2 -and $result.Log.LatestPlayLifecycle.Count -eq 2) 'Allowed queue/lifecycle evidence was lost.'
    Pass 'fatal payload sanitization and lifecycle allowlist'

    $fixtureState.Processes = @((New-FixtureProcess 10 $nativeEditor))
    $result = Invoke-Snapshot @($firstLog)
    Assert-True ($result.EditorSelection -eq 'one_verified_editor' -and $result.Editors[0].ProcessId -eq 10) 'Exact UE4Editor path was not recognized.'
    Assert-True ($result.Editors[0].LiveMetricsStatus -eq 'sampled_same_process_identity') 'UE4Editor live identity was not verified.'
    Pass 'legacy native editor exact executable path'

    $fixtureState.Processes = @(
        (New-FixtureProcess 11 $epicEditor),
        (New-FixtureProcess 20 $worker 11 $epoch.AddSeconds(1)),
        (New-FixtureProcess 21 $worker 11 $epoch.AddSeconds(-1)),
        (New-FixtureProcess 22 $worker 99 $epoch.AddSeconds(1))
    )
    $result = Invoke-Snapshot @($firstLog)
    Assert-True ($result.EditorSelection -eq 'one_verified_editor' -and $result.Editors[0].ProcessId -eq 11) 'Exact Epic editor path was not recognized.'
    Assert-True ($result.Editors[0].LiveMetricsStatus -eq 'sampled_same_process_identity') 'Epic live metrics compared with wrong executable.'
    Assert-True ($result.Editors[0].ShaderWorkerCount -eq 1 -and $result.ShaderWorkers.UnattributedCount -eq 2) 'Worker parent/creation checks were relaxed.'
    Assert-True ($result.ExpectedEditorPaths.Count -eq 2 -and $result.Log.EditorAssociation -match 'not proven') 'Supported paths or unverified log association missing.'
    Pass 'Epic editor exact path and worker ownership'

    $fixtureState.Processes = @((New-FixtureProcess 30 (Join-Path $fixtureRoot 'impostor\HogwartsLegacyCreatorKit.exe')))
    $beforeQueries = $fixtureState.LiveQueries.Count
    $result = Invoke-Snapshot @($firstLog)
    Assert-True ($result.EditorSelection -eq 'no_verified_editor' -and $result.Editors.Count -eq 0) 'Executable basename alone must not authorize process attribution.'
    Assert-True ($fixtureState.LiveQueries.Count -eq $beforeQueries) 'An impostor path triggered live metrics.'
    Pass 'same-name process outside kit rejected'

    $fixtureState.Processes = @((New-FixtureProcess 10 $nativeEditor), (New-FixtureProcess 11 $epicEditor))
    $result = Invoke-Snapshot @($firstLog)
    Assert-True ($result.EditorSelection -like 'multiple_verified_editors*' -and $result.Editors.Count -eq 2) 'Multiple native names must remain ambiguous.'
    Assert-True ($result.Log.EditorAssociation -match 'Multiple matching editors') 'Log was falsely attributed under multiple editors.'
    Pass 'both native editor names reported without selecting one'

    $fixtureState.Processes = @((New-FixtureProcess 11 $epicEditor))
    $fixtureState.LivePathOverrides[11] = $nativeEditor
    $result = Invoke-Snapshot @($firstLog)
    Assert-True ($result.Editors[0].LiveMetricsStatus -eq 'identity_changed_or_unavailable' -and $null -eq $result.Editors[0].Responding) 'Recycled identity using another allowed path must fail the exact matched-entry recheck.'
    Pass 'live identity must match its sampled executable'

    Assert-True ($fixtureState.ProcessQueries.Count -gt 0) 'Synthetic process queries did not run.'
    foreach ($query in $fixtureState.ProcessQueries) {
        Assert-True ($query.Filter -match "Name = 'HogwartsLegacyCreatorKit.exe'") 'Epic editor missing from explicit query filter.'
        Assert-True ((@($query.Properties | Sort-Object) -join ',') -eq 'CreationDate,ExecutablePath,Name,ParentProcessId,ProcessId') 'Process query retrieved unexpected metadata.'
    }
    Pass 'process sampling excludes command lines'

    $fixtureState.FailProcessQuery = $true
    $result = (& $inspector -KitRoot $kitRoot -LogPaths @($firstLog) -TailLines 100) | ConvertFrom-Json
    Assert-True ($result.Status -eq 'partial' -and $result.EditorSelection -eq 'query_failed') 'Unavailable process metadata must remain a partial snapshot.'
    Assert-True ($result.Log.EditorAssociation -match 'unknown' -and $result.Log.EditorAssociation -notmatch 'No verified editor') 'A failed process query must not claim the editor is absent.'
    Pass 'failed process query leaves current association unknown'
    Write-Output ("Passed {0} focused startup inspector checks." -f $fixtureState.Passed)
} finally {
    # Only remove the three exact synthetic files and the now-empty GUID directory.
    # There is no recursive deletion and the inspector is never called with -Save.
    foreach ($fixture in @($firstLog, $secondLog, $missingLog)) {
        if (Test-Path -LiteralPath $fixture -PathType Leaf) { Remove-Item -LiteralPath $fixture -Force }
    }
    Remove-Item -LiteralPath $fixtureRoot -Force
}
