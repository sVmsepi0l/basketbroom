<#
.SYNOPSIS
Take one read-only snapshot of native Creator Kit Play/startup pressure.
.DESCRIPTION
Reads only process identity, memory counters, and allowlisted startup log entries.
Never reads process command lines, starts/stops processes, or changes settings.
A shader count is a sampled queue, not a countdown or completion estimate: Play
may discover additional material permutations. Missing evidence is not success.
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
    [switch]$Save
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$kit = [IO.Path]::GetFullPath($KitRoot)
$editorPath = Join-Path $kit 'Engine\Binaries\Win64\UE4Editor.exe'
$workerPath = Join-Path $kit 'Engine\Binaries\Win64\ShaderCompileWorker.exe'
$logPath = Join-Path $kit 'PhoenixGame\Saved\Logs\Phoenix.log'
$report = [ordered]@{
    SchemaVersion = 1
    SampledUtc = [DateTime]::UtcNow.ToString('o')
    Scope = 'One read-only native Creator Kit startup snapshot; no command lines or authentication logs.'
    Status = 'sampled'
    ExpectedEditorPath = $editorPath
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
        TailLinesRequested = $TailLines
        TailLinesRead = 0
        EditorAssociation = 'unverified; Phoenix.log is shared by this installation'
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
    $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'UE4Editor.exe' OR Name = 'ShaderCompileWorker.exe'" -Property Name,ProcessId,ParentProcessId,ExecutablePath,CreationDate)
    $editors = @($processes | Where-Object { $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $editorPath, [StringComparison]::OrdinalIgnoreCase) })
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
            if ([string]::Equals($live.Path, $editorPath, [StringComparison]::OrdinalIgnoreCase) -and
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
    $report.Log.Exists = [IO.File]::Exists($logPath)
    if ($report.Log.Exists) {
        $logInfo = Get-Item -LiteralPath $logPath
        $report.Log.LastWriteUtc = $logInfo.LastWriteTimeUtc.ToString('o')
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
        if ($report.Editors.Count -eq 1) {
            $report.Log.EditorAssociation = 'One matching editor; timestamps may include earlier runs. Log ownership is not proven.'
        } elseif ($report.Editors.Count -eq 0) {
            $report.Log.EditorAssociation = 'No verified editor; treat this log as historical.'
        } else {
            $report.Log.EditorAssociation = 'Multiple matching editors; this shared log cannot be attributed to one.'
        }
    } else { $report.Warnings += 'Phoenix.log does not exist at the expected location.' }
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
