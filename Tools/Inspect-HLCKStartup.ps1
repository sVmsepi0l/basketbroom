<#
.SYNOPSIS
Take one read-only snapshot of native Creator Kit Play/startup pressure.
.DESCRIPTION
Reads only process identity, memory counters, and allowlisted startup log entries.
Never reads process command lines, starts/stops processes, or changes settings.
A shader count is a sampled queue, not a countdown or completion estimate: Play
may discover additional material permutations. Missing evidence is not success.
.PARAMETER LogPaths
Optional ordered candidate paths for diagnostics/tests. Defaults to the installed
project log followed by the current user's Creator Kit log. The newest write time
wins; equal times prefer the earlier candidate. Selection does not prove ownership.
.PARAMETER Save
Also save this JSON snapshot in the repository's ignored .local/hlck/startup folder.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File Tools/Inspect-HLCKStartup.ps1 -Save
#>
[CmdletBinding()]
param(
    [string]$KitRoot = 'C:\Program Files\HogwartsLegacyCreatorKit',
    [ValidateRange(100, 20000)][int]$TailLines = 5000,
    [ValidateRange(1, 100)][int]$EvidenceLines = 16,
    [string[]]$LogPaths = @(),
    [switch]$Save
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$kit = [IO.Path]::GetFullPath($KitRoot)
$editorPath = Join-Path $kit 'Engine\Binaries\Win64\UE4Editor.exe'
$editorPaths = @($editorPath, (Join-Path $kit 'Engine\Binaries\Win64\HogwartsLegacyCreatorKit.exe'))
$workerPath = Join-Path $kit 'Engine\Binaries\Win64\ShaderCompileWorker.exe'
if ($LogPaths.Count -eq 0) {
    $LogPaths = @(
        (Join-Path $kit 'PhoenixGame\Saved\Logs\Phoenix.log'),
        (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HogwartsLegacyCreatorKit\Saved\Logs\Phoenix.log')
    )
}
$logPath = $null
$report = [ordered]@{
    SchemaVersion = 2
    SampledUtc = [DateTime]::UtcNow.ToString('o')
    Scope = 'One read-only native Creator Kit startup snapshot; no command lines or authentication logs.'
    Status = 'sampled'
    ExpectedEditorPath = $editorPath
    ExpectedEditorPaths = $editorPaths
    EditorSelection = 'not_sampled'
    Editors = @()
    ShaderWorkers = [ordered]@{
        Attribution = 'Exact executable path, direct parent PID, and creation time not older than editor.'
        MatchingExecutableCount = $null
        UnattributedCount = $null
    }
    Memory = $null
    KitVolume = $null
    Log = [ordered]@{
        Path = $logPath
        Exists = $false
        LastWriteUtc = $null
        LastWriteAgeSecondsAtRead = $null
        Candidates = @()
        Selection = 'not_sampled'
        SelectionCaveat = 'Newest LastWriteTimeUtc among known files; equal times prefer earlier candidate order. Write times can change after selection and do not prove current editor ownership or shader readiness.'
        TailLinesRequested = $TailLines
        TailLinesRead = 0
        EditorAssociation = 'unverified; known log locations may contain earlier runs or another editor session'
        LastShaderQueueSampleInTail = $null
        LatestPlayLifecycle = @()
        LifecycleScan = 'not_sampled'
        LifecycleCaveat = 'Historical log markers only. A start without an end does not establish that PIE is currently active.'
        Evidence = @()
        Caveat = 'Sampled queue only, not an ETA. Counts may grow. Old entries are not current progress; absence of fatal markers does not prove a healthy runtime.'
    }
    Warnings = @()
    SavedReportPath = $null
}

try {
    # Request an explicit property list: never retrieve CommandLine.
    $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'UE4Editor.exe' OR Name = 'HogwartsLegacyCreatorKit.exe' OR Name = 'ShaderCompileWorker.exe'" -Property Name,ProcessId,ParentProcessId,ExecutablePath,CreationDate)
    $editors = @($processes | Where-Object {
        $candidateExecutable = $_.ExecutablePath
        $candidateExecutable -and @($editorPaths | Where-Object {
            [string]::Equals($_, $candidateExecutable, [StringComparison]::OrdinalIgnoreCase)
        }).Count -gt 0
    })
    $workers = @($processes | Where-Object { $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $workerPath, [StringComparison]::OrdinalIgnoreCase) })
    $report.EditorSelection = if ($editors.Count -eq 0) { 'no_verified_editor' } elseif ($editors.Count -eq 1) { 'one_verified_editor' } else { 'multiple_verified_editors; none selected' }
    if (@($processes | Where-Object { -not $_.ExecutablePath }).Count -gt 0) {
        $report.Warnings += 'Some matching process names had inaccessible executable paths and were not attributed.'
    }
    $attributedWorkers = 0
    foreach ($entry in $editors) {
        $ownedWorkers = @($workers | Where-Object {
            $_.ParentProcessId -eq $entry.ProcessId -and $null -ne $_.CreationDate -and
            $null -ne $entry.CreationDate -and $_.CreationDate -ge $entry.CreationDate
        })
        $attributedWorkers += $ownedWorkers.Count
        $item = [ordered]@{
            ProcessId = [int]$entry.ProcessId
            ExecutablePath = $entry.ExecutablePath
            StartedUtc = $(if ($null -ne $entry.CreationDate) { $entry.CreationDate.ToUniversalTime().ToString('o') } else { $null })
            Responding = $null
            CpuSecondsTotal = $null
            WorkingSetGiB = $null
            PrivateMemoryGiB = $null
            ShaderWorkerCount = $ownedWorkers.Count
            LiveMetricsStatus = 'unavailable'
        }
        $live = $null
        try {
            $live = Get-Process -Id $entry.ProcessId -ErrorAction Stop
            # Recheck the identity before joining the two samples; a PID may have exited/recycled.
            if ([string]::Equals($live.Path, $entry.ExecutablePath, [StringComparison]::OrdinalIgnoreCase) -and
                $null -ne $entry.CreationDate -and
                [math]::Abs(($live.StartTime.ToUniversalTime() - $entry.CreationDate.ToUniversalTime()).TotalMilliseconds) -lt 2) {
                $item.Responding = $live.Responding
                $item.CpuSecondsTotal = [math]::Round($live.TotalProcessorTime.TotalSeconds, 2)
                $item.WorkingSetGiB = [math]::Round($live.WorkingSet64 / 1GB, 2)
                $item.PrivateMemoryGiB = [math]::Round($live.PrivateMemorySize64 / 1GB, 2)
                $item.LiveMetricsStatus = 'sampled_same_process_identity'
            } else { $item.LiveMetricsStatus = 'identity_changed_or_unavailable' }
        } catch { $item.LiveMetricsStatus = 'process_exited_or_metrics_inaccessible' }
        finally { if ($null -ne $live) { $live.Dispose() } }
        $report.Editors += [pscustomobject]$item
    }
    $report.ShaderWorkers.MatchingExecutableCount = $workers.Count
    $report.ShaderWorkers.UnattributedCount = $workers.Count - $attributedWorkers
} catch {
    $report.Status = 'partial'
    $report.EditorSelection = 'query_failed'
    $report.Warnings += 'Could not query process identity. Run locally with permission to read the Creator Kit process metadata.'
}

try {
    $memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -Property AvailableMBytes,CommittedBytes,CommitLimit,PagesInputPersec
    $report.Memory = [ordered]@{
        AvailableGiB = [math]::Round($memory.AvailableMBytes / 1024, 2)
        CommittedGiB = [math]::Round($memory.CommittedBytes / 1GB, 2)
        CommitLimitGiB = [math]::Round($memory.CommitLimit / 1GB, 2)
        CommitHeadroomGiB = [math]::Round(($memory.CommitLimit - $memory.CommittedBytes) / 1GB, 2)
        PagesInputPerSecond = [long]$memory.PagesInputPersec
        Scope = 'Machine-wide sampled counters; page-in is not attributable to a single process.'
    }
} catch {
    $report.Status = 'partial'
    $report.Warnings += 'Machine memory counters were unavailable.'
}

try {
    $volume = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($kit))
    $report.KitVolume = [ordered]@{
        Root = $volume.Name
        AvailableGiB = [math]::Round($volume.AvailableFreeSpace / 1GB, 2)
        FreeGiB = [math]::Round($volume.TotalFreeSpace / 1GB, 2)
        TotalGiB = [math]::Round($volume.TotalSize / 1GB, 2)
        Scope = 'Volume containing the Creator Kit; does not identify pagefile locations.'
    }
} catch {
    $report.Status = 'partial'
    $report.Warnings += 'Creator Kit volume space counters were unavailable.'
}

try {
    # Inspect only these explicit candidates. Do not infer association from file
    # recency, traverse account folders, or read process launch arguments.
    $newestWriteUtc = $null
    foreach ($candidatePath in $LogPaths) {
        $candidate = [ordered]@{
            Path = [IO.Path]::GetFullPath($candidatePath)
            Exists = $false
            MetadataStatus = 'absent'
            LastWriteUtc = $null
            AgeSecondsAtRead = $null
            Selected = $false
        }
        try {
            if (Test-Path -LiteralPath $candidate.Path -PathType Leaf) {
                $info = Get-Item -LiteralPath $candidate.Path -ErrorAction Stop
                $candidate.Exists = $true
                $candidate.MetadataStatus = 'sampled'
                $candidate.LastWriteUtc = $info.LastWriteTimeUtc.ToString('o')
                $candidate.AgeSecondsAtRead = [math]::Round(([DateTime]::UtcNow - $info.LastWriteTimeUtc).TotalSeconds, 1)
                # Strictly greater retains the first candidate on exact ties.
                if ($null -eq $newestWriteUtc -or $info.LastWriteTimeUtc -gt $newestWriteUtc) {
                    $newestWriteUtc = $info.LastWriteTimeUtc
                    $logPath = $candidate.Path
                    $report.Log.LastWriteAgeSecondsAtRead = $candidate.AgeSecondsAtRead
                }
            }
        } catch {
            $candidate.MetadataStatus = 'unavailable'
            $report.Status = 'partial'
            $report.Warnings += 'One known log candidate had unreadable metadata; the selection uses only successfully sampled files.'
        }
        $report.Log.Candidates += [pscustomobject]$candidate
    }
    if ($null -ne $logPath) {
        $report.Log.Path = $logPath
        $report.Log.Exists = $true
        $report.Log.LastWriteUtc = $newestWriteUtc.ToString('o')
        $report.Log.Selection = 'newest_known_log'
        # Mark exactly one entry even when diagnostic candidate paths repeat.
        $selectedMarked = $false
        foreach ($candidate in $report.Log.Candidates) {
            if (-not $selectedMarked -and [string]::Equals($candidate.Path, $logPath, [StringComparison]::OrdinalIgnoreCase)) {
                $candidate.Selected = $true
                $selectedMarked = $true
            }
        }
        $lines = @(Get-Content -LiteralPath $logPath -Tail $TailLines -Encoding UTF8)
        $report.Log.TailLinesRead = $lines.Count
        $evidence = New-Object 'System.Collections.Generic.List[object]'
        foreach ($line in $lines) {
            # Match UE's structured prefix, then use a narrow category/message allowlist.
            $match = [regex]::Match($line, '^\[(?<time>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]\[\s*\d+\](?<category>Log[A-Za-z0-9_]+):\s*(?<message>.*)$')
            if (-not $match.Success) { continue }
            $category = $match.Groups['category'].Value
            $message = $match.Groups['message'].Value
            $stamp = [DateTime]::ParseExact($match.Groups['time'].Value, 'yyyy.MM.dd-HH.mm.ss:fff', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal).ToUniversalTime()
            $fatal = [regex]::Match($message, '(?:Fatal error:|Assertion failed:|Ensure condition failed:)')
            $allowed = ($category -eq 'LogShaderCompilers' -and $message -match '(?:shaders left to compile|Started \d+ .*shader compile jobs|Submitted \d+ shader compile jobs|Using .*shader compiler|Shader compiling)') -or
                ($category -eq 'LogMaterial' -and $message -match '(?:Missing cached shadermap|compiling)') -or
                ($category -eq 'LogPlayLevel' -and $message -match '^(?:Display: )?(?:Creating play world package|PIE(?: |:)|PlayLevel:|Play in editor)') -or
                ($category -eq 'LogLoad' -and $message -match '^(?:Display: )?(?:LoadMap:|Took .*LoadMap|LoadMap took)') -or
                ($category -eq 'LogWorld' -and $message -match '^(?:Display: )?(?:Bringing |Tearing |UWorld::CleanupWorld|CleanupWorld|InitWorld)')
            if ($fatal.Success) {
                # Retain only the marker: assertion/fatal payloads can contain arbitrary application data.
                $message = $fatal.Value + ' [details omitted]'
                $allowed = $true
            }
            if (-not $allowed -or $message -match '(?i)(?:auth|token|password|credential|login|secret|https?://|command.?line)') { continue }
            if ($message.Length -gt 1200) { $message = $message.Substring(0, 1200) + ' [truncated]' }
            $evidence.Add([pscustomobject]@{ TimestampUtc = $stamp.ToString('o'); Category = $category; Message = $message })
            if ($category -eq 'LogShaderCompilers') {
                $queue = [regex]::Match($message, 'shaders left to compile\s+(?<count>\d+)')
                if ($queue.Success) {
                    $report.Log.LastShaderQueueSampleInTail = [ordered]@{
                        Pending = [long]$queue.Groups['count'].Value
                        TimestampUtc = $stamp.ToString('o')
                        AgeSecondsAtRead = [math]::Round(([DateTime]::UtcNow - $stamp).TotalSeconds, 1)
                        Meaning = 'Last logged queue in the sampled tail; additional shaders may be enqueued.'
                    }
                }
            }
        }
        $report.Log.Evidence = @($evidence | Select-Object -Last $EvidenceLines)
        # Shader chatter can push Play startup/cleanup out of the tail. Scan the
        # file through a shared reader, retaining only six narrow lifecycle markers.
        # A line cap keeps this a bounded inspection even if the file is enormous.
        $lifecycle = New-Object 'System.Collections.Generic.Queue[object]'
        $stream = $null
        $reader = $null
        $scanned = 0
        try {
            $stream = [IO.File]::Open($logPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
                ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
            $reader = [IO.StreamReader]::new($stream)
            while ($scanned -lt 200000 -and $null -ne ($line = $reader.ReadLine())) {
                $scanned++
                $match = [regex]::Match($line, '^\[(?<time>\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]\[\s*\d+\](?<category>LogPlayLevel|LogWorld):\s*(?<message>.*)$')
                if (-not $match.Success) { continue }
                $category = $match.Groups['category'].Value
                $message = $match.Groups['message'].Value
                if ($message -match '(?i)(?:auth|token|password|credential|login|secret|https?://|command.?line)') { continue }
                $transition = $null
                if ($category -eq 'LogPlayLevel') {
                    if ($message -match '^(?:Display: )?Creating play world package:') { $transition = 'play_world_creation_requested' }
                    elseif ($message -match '^(?:Display: )?PIE: Created PIE world') { $transition = 'play_world_created' }
                    elseif ($message -match '^(?:Display: )?PIE:.*(?:EndPlay|Shutting down PIE|PIE session ended)') { $transition = 'play_end_marker' }
                } elseif ($message -match 'UEDPIE_') {
                    if ($message -match '^(?:Display: )?(?:BeginTearingDown|Tearing down)') { $transition = 'play_world_teardown' }
                    elseif ($message -match '^(?:Display: )?(?:UWorld::CleanupWorld|CleanupWorld)') { $transition = 'play_world_cleanup' }
                }
                if ($null -eq $transition) { continue }
                $stamp = [DateTime]::ParseExact($match.Groups['time'].Value, 'yyyy.MM.dd-HH.mm.ss:fff', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal).ToUniversalTime()
                if ($message.Length -gt 1200) { $message = $message.Substring(0, 1200) + ' [truncated]' }
                $lifecycle.Enqueue([pscustomobject]@{ TimestampUtc = $stamp.ToString('o'); Transition = $transition; Category = $category; Message = $message })
                if ($lifecycle.Count -gt 6) { $null = $lifecycle.Dequeue() }
            }
            $report.Log.LifecycleScan = if ($reader.EndOfStream) { 'reached_current_end_of_file' } else { '200000_line_cap_reached; later_lifecycle_unknown' }
            $report.Log.LatestPlayLifecycle = @($lifecycle.ToArray())
        } finally {
            if ($null -ne $reader) { $reader.Dispose() }
            elseif ($null -ne $stream) { $stream.Dispose() }
        }
        if ($report.EditorSelection -eq 'query_failed') {
            $report.Log.EditorAssociation = 'Editor query failed; current process association is unknown.'
        } elseif ($report.Editors.Count -eq 1) {
            $report.Log.EditorAssociation = 'One matching editor; timestamps may include earlier runs. Log ownership is not proven.'
        } elseif ($report.Editors.Count -eq 0) {
            $report.Log.EditorAssociation = 'No verified editor; treat this log as historical.'
        } else {
            $report.Log.EditorAssociation = 'Multiple matching editors; this shared log cannot be attributed to one.'
        }
    } else {
        $report.Log.Selection = 'no_readable_known_log'
        $report.Warnings += 'No known Phoenix.log candidate had readable file metadata.'
    }
} catch {
    $report.Status = 'partial'
    $report.Warnings += 'Could not finish reading the allowlisted live log evidence; existing fields may be partial.'
}

if ($Save) {
    $directory = Join-Path $repo '.local\hlck\startup'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $name = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8) + '.json'
    $report.SavedReportPath = Join-Path $directory $name
}
$json = $report | ConvertTo-Json -Depth 8
if ($Save) { [IO.File]::WriteAllText($report.SavedReportPath, $json, [Text.UTF8Encoding]::new($false)) }
Write-Output $json
