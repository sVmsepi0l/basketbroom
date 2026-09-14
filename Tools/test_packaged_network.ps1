<#
Two-process, loopback-only connection smoke for the latest native package.
This verifies handshake/join and client map travel, not roles, scoring,
replication correctness, remote networking, or a complete regulation match.

UE5.8 source confirms Port= in CoreMisc.cpp/FUrlConfig::Init, MULTIHOME= in
SocketSubsystem.cpp, server-side Join succeeded in World.cpp, and client-side
Welcomed by server in PendingNetGame.cpp. That file also replaces Name= with
the online nickname, so a separate BBNetSmoke= URL option identifies the run.
No editor or firewall changes.
#>
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 18779,
    [ValidateRange(5, 30)][int]$TimeoutSeconds = 30,
    [switch]$Bloodbroom
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runName = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$runDirectory = Join-Path $repo ('.local\packaged-network\' + $runName)
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
$reportPath = Join-Path $runDirectory 'result.json'
$serverLog = Join-Path $runDirectory 'server.log'
$clientLog = Join-Path $runDirectory 'client.log'
$clientName = 'BBNetClient_' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$owned = New-Object 'System.Collections.Generic.List[object]'
$watch = [Diagnostics.Stopwatch]::new()
$report = [ordered]@{
    Status = 'not_run'
    Scope = 'Two local packaged processes: loopback connection/join and client map travel only'
    RequestedVariant = $(if ($Bloodbroom) { 'bloodbroom' } else { 'basketbroom' })
    Excludes = @('Variant activation/replication', 'Role selection', 'Score replication', 'Remote connectivity', 'Latency/load', 'Full regulation gameplay')
    StartedUtc = [DateTime]::UtcNow.ToString('o')
    TimeoutSeconds = $TimeoutSeconds
    Address = '127.0.0.1'
    Port = $Port
    Executable = $null
    ClientName = $clientName
    Logs = [ordered]@{ Server = $serverLog; Client = $clientLog }
    Processes = @()
    Bindings = @()
    Evidence = [ordered]@{}
    LogErrors = @()
    Error = $null
    Cleanup = @()
}

function Read-LiveLog([string]$Path) {
    if (-not [IO.File]::Exists($Path)) { return '' }
    # Unreal still has its log open. Explicit sharing permits live reads.
    $stream = $null
    $reader = $null
    try {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read,
            ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $reader = [IO.StreamReader]::new($stream)
        return $reader.ReadToEnd()
    } finally {
        if ($null -ne $reader) { $reader.Dispose() }
        elseif ($null -ne $stream) { $stream.Dispose() }
    }
}

function Find-Evidence([string]$Text, [string]$Pattern) {
    $found = [regex]::Match($Text, $Pattern, [Text.RegularExpressions.RegexOptions]::Multiline)
    if ($found.Success) { return $found.Value.Trim() }
    return $null
}

function Find-LogErrors([string]$Text, [string]$Role) {
    $pattern = '^.*(?:Fatal error:|Assertion failed:|Ensure condition failed:|Log[^:\r\n]+:\s*(?:Error|Fatal):|NetworkFailure|TravelFailure|Join failure:).*$'
    foreach ($entry in [regex]::Matches($Text, $pattern, [Text.RegularExpressions.RegexOptions]::Multiline)) {
        [pscustomobject]@{ Role = $Role; Line = $entry.Value.Trim() }
    }
}

function Wait-OwnedGameIdentity($Record, [int]$TimeoutMilliseconds = 5000) {
    $metadataWatch = [Diagnostics.Stopwatch]::StartNew()
    try {
        do {
            $Record.Process.Refresh()
            if ($Record.Process.HasExited) {
                throw "$($Record.Role) exited during startup with code $($Record.Process.ExitCode)."
            }
            $rawPath = $null
            $startedUtc = $null
            # MainModule/Path may not be populated immediately after creation.
            # Retry missing metadata, but reject an observed identity mismatch.
            try { $rawPath = $Record.Process.Path } catch { }
            try { $startedUtc = $Record.Process.StartTime.ToUniversalTime() } catch { }
            if (-not [string]::IsNullOrWhiteSpace($rawPath)) {
                if (-not [IO.Path]::IsPathRooted($rawPath)) { throw 'Started process reported a non-absolute executable path.' }
                $actualPath = [IO.Path]::GetFullPath($rawPath)
                if (-not [string]::Equals($actualPath, $Record.Executable, [StringComparison]::OrdinalIgnoreCase)) {
                    throw "$($Record.Role) process executable differs from the selected package."
                }
                if ($null -ne $startedUtc -and $startedUtc.Ticks -gt 0) {
                    $Record.StartTimeUtcTicks = $startedUtc.Ticks
                    $Record.StartupIdentityVerified = $true
                    $Record.Receipt.Executable = $actualPath
                    $Record.Receipt.StartTimeUtc = $startedUtc.ToString('o')
                    $Record.Receipt.StartupIdentityVerified = $true
                    return
                }
            }
            if ($metadataWatch.ElapsedMilliseconds -lt $TimeoutMilliseconds) { Start-Sleep -Milliseconds 50 }
        } while ($metadataWatch.ElapsedMilliseconds -lt $TimeoutMilliseconds)
        throw "$($Record.Role) executable/start-time metadata was unavailable after $TimeoutMilliseconds ms."
    } finally {
        $metadataWatch.Stop()
        $Record.Receipt.MetadataWaitMilliseconds = $metadataWatch.ElapsedMilliseconds
    }
}

function Start-OwnedGame([string]$Role, [string[]]$Arguments) {
    # Direct Process.Start with UseShellExecute=false retains the OS creation
    # handle. Cleanup can target that exact process even while Path/StartTime
    # metadata is late; it never reopens a PID or searches by executable name.
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $script:mainExecutable
    $startInfo.Arguments = [string]::Join(' ', $Arguments)
    $startInfo.WorkingDirectory = $script:packageRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { $process.Dispose(); throw "$Role process did not start." }
    $record = [pscustomobject]@{
        Role = $Role; Id = $process.Id; Process = $process
        Executable = $script:mainExecutable; StartTimeUtcTicks = 0L
        StartedDirectly = $true; CreationHandle = $process.SafeHandle
        StartupIdentityVerified = $false; Receipt = $null
    }
    $script:owned.Add($record)
    $record.Receipt = [pscustomobject]@{
        Role = $Role; Id = $record.Id; RequestedExecutable = $script:mainExecutable
        Executable = $null; StartTimeUtc = $null; Arguments = $Arguments
        Ownership = 'original_process_creation_handle'; StartupIdentityVerified = $false
        MetadataWaitMilliseconds = 0L
    }
    $script:report.Processes += $record.Receipt
    if ($record.CreationHandle.IsInvalid -or $record.CreationHandle.IsClosed) {
        throw "$Role did not retain a valid process creation handle."
    }
    Wait-OwnedGameIdentity $record
    return $record
}

function Stop-OwnedGame($Record) {
    $result = [ordered]@{
        Role = $Record.Role; Id = $Record.Id; Outcome = 'already_exited'
        IdentityBasis = 'original_process_creation_handle'
        StartupIdentityVerified = $Record.StartupIdentityVerified
    }
    try {
        $candidate = $Record.Process
        if (-not $Record.StartedDirectly -or $null -eq $candidate -or $null -eq $Record.CreationHandle -or
            $Record.CreationHandle.IsInvalid -or $Record.CreationHandle.IsClosed -or
            $candidate.Id -ne $Record.Id -or
            -not [object]::ReferenceEquals($candidate.SafeHandle, $Record.CreationHandle)) {
            $result.Outcome = 'refused_identity_mismatch'
            return [pscustomobject]$result
        }
        $candidate.Refresh()
        if ($candidate.HasExited) { return [pscustomobject]$result }
        # Process.Start retained this handle before metadata verification. A
        # late/missing image path cannot redirect it to a recycled PID. Kill and
        # WaitForExit act on the same original Process object and owned handle.
        $candidate.Kill()
        $stopped = $candidate.WaitForExit(5000)
        $result.Outcome = if ($stopped) { 'stopped_owned_process' } else { 'stop_timeout' }
    } catch {
        $result.Outcome = 'cleanup_error'
        $result.Error = $_.Exception.Message
    } finally {
        if ($null -ne $Record.Process -and $result.Outcome -in @('already_exited','stopped_owned_process')) {
            $Record.Process.Dispose()
        }
    }
    return [pscustomobject]$result
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'This packaged test requires Windows.' }
    if (-not (Get-Command Get-NetUDPEndpoint -ErrorAction SilentlyContinue)) { throw 'Get-NetUDPEndpoint is required to verify the actual loopback binding.' }
    $manifestPath = Join-Path $repo '.local\latest-package.json'
    $package = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($package.Status -ne 'complete' -or $package.NativeRuntime -ne $true) { throw 'The latest package is not a completed native runtime package.' }
    if ($package.Configuration -ne 'Development') { throw 'Use a Development package so connection logs are available.' }
    if ($package.EngineVersion -notmatch '^5\.8(?:\.|$)') { throw 'This smoke test expects the UE5.8 native package.' }
    if (-not [IO.Path]::IsPathRooted($package.Executable) -or -not (Test-Path -LiteralPath $package.Executable -PathType Leaf)) {
        throw 'The package bootstrap executable is missing or not an absolute path.'
    }
    $packageRoot = [IO.Path]::GetFullPath((Split-Path -Parent $package.Executable))
    $archive = [IO.Path]::GetFullPath($package.Archive).TrimEnd('\') + '\'
    if (-not ($packageRoot + '\').StartsWith($archive, [StringComparison]::OrdinalIgnoreCase)) { throw 'Package root is outside its recorded archive.' }
    # Launch the main executable directly: the bootstrap would hide the game PID.
    $mainExecutable = [IO.Path]::GetFullPath((Join-Path $packageRoot 'BasketbroomDev\Binaries\Win64\BasketbroomDev.exe'))
    if (-not (Test-Path -LiteralPath $mainExecutable -PathType Leaf)) { throw "Packaged main executable missing: $mainExecutable" }
    $report.Executable = $mainExecutable
    $report.PackageManifest = $manifestPath

    $ipProperties = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
    $occupied = @($ipProperties.GetActiveUdpListeners() | Where-Object { $_.Port -eq $Port })
    if ($occupied.Count -gt 0) { throw "UDP port $Port is already in use; no processes were started." }
    $reservation = [Net.Sockets.UdpClient]::new([Net.Sockets.AddressFamily]::InterNetwork)
    try {
        $reservation.Client.ExclusiveAddressUse = $true
        $reservation.Client.Bind([Net.IPEndPoint]::new([Net.IPAddress]::Loopback, $Port))
    } finally { $reservation.Dispose() }

    $common = @('-nullrhi', '-unattended', '-nosound', '-nosplash', '-MULTIHOME=127.0.0.1', '-FORCELOGFLUSH')
    $hostMap = '/Basketbroom/Maps/BB_Regulation?listen?Practice=1'
    if ($Bloodbroom) { $hostMap += '?Bloodbroom=1' }
    $serverArguments = @($hostMap, "-port=$Port") + $common + @(('-abslog="{0}"' -f $serverLog))
    # NMT_Challenge copies URL options but overrides Name= with GetNickname().
    # Use an otherwise inert URL option to correlate this client's join.
    $clientArguments = @("127.0.0.1:${Port}?BBNetSmoke=$clientName") + $common + @(('-abslog="{0}"' -f $clientLog))
    $report.Status = 'running'
    $watch.Start()
    $server = Start-OwnedGame 'server' $serverArguments
    $client = $null
    $boundLoopback = $false
    $serverText = ''
    $clientText = ''
    while ($watch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $serverText = Read-LiveLog $serverLog
        $clientText = Read-LiveLog $clientLog
        $errors = @(Find-LogErrors $serverText 'server') + @(Find-LogErrors $clientText 'client')
        if ($errors.Count -gt 0) {
            $report.LogErrors = $errors
            throw 'The packaged processes logged an engine or network error; see LogErrors and the complete logs.'
        }
        foreach ($entry in $owned) {
            $entry.Process.Refresh()
            if ($entry.Process.HasExited) { throw "$($entry.Role) exited before verification, code $($entry.Process.ExitCode)." }
        }
        $listening = Find-Evidence $serverText ('^.*IpNetDriver listening on port ' + $Port + '\b.*$')
        if ($listening -and -not $boundLoopback) {
            $endpoints = @(Get-NetUDPEndpoint -OwningProcess $server.Id -LocalPort $Port -ErrorAction SilentlyContinue)
            if ($endpoints.Count -gt 0) {
                $report.Bindings = @($endpoints | Select-Object LocalAddress, LocalPort, OwningProcess)
                if (@($endpoints | Where-Object { $_.LocalAddress -ne '127.0.0.1' }).Count -gt 0) {
                    throw 'The server bound an address other than IPv4 loopback.'
                }
                $boundLoopback = $true
            }
        }
        if ($boundLoopback -and $null -eq $client) { $client = Start-OwnedGame 'client' $clientArguments }

        $accepted = Find-Evidence $serverText '^.*NotifyAcceptedConnection:.*127\.0\.0\.1.*$'
        $request = Find-Evidence $serverText ('^.*Join request:.*\?BBNetSmoke=' + [regex]::Escape($clientName) + '(?:\?|\s|$).*$')
        $joined = $null
        if ($request) {
            $requestIndex = $serverText.IndexOf($request, [StringComparison]::Ordinal)
            if ($requestIndex -ge 0) { $joined = Find-Evidence ($serverText.Substring($requestIndex)) '^.*Join succeeded:.*$' }
        }
        $welcomed = Find-Evidence $clientText '^.*Welcomed by server \(Level: /Basketbroom/Maps/BB_Regulation.*$'
        $loaded = $null
        if ($welcomed) {
            $welcomeIndex = $clientText.IndexOf($welcomed, [StringComparison]::Ordinal)
            if ($welcomeIndex -ge 0) {
                $loaded = Find-Evidence ($clientText.Substring($welcomeIndex)) '^.*LogLoad: Took .*LoadMap\(/Basketbroom/Maps/BB_Regulation\).*$'
            }
        }
        $report.Evidence = [ordered]@{
            ServerListening = $listening; ServerBoundLoopback = $boundLoopback
            ServerAcceptedLoopback = $accepted; ServerReceivedTaggedClientJoin = $request
            ServerClientJoinSucceeded = $joined; ClientWelcomedToRegulation = $welcomed
            ClientCompletedRegulationMapLoad = $loaded
        }
        if ($boundLoopback -and $accepted -and $request -and $joined -and $welcomed -and $loaded) {
            $report.Status = 'passed'
            break
        }
        Start-Sleep -Milliseconds 200
    }
    if ($report.Status -ne 'passed') { throw "Connection evidence was incomplete after $TimeoutSeconds seconds." }
} catch {
    if ($report.Status -eq 'running') { $report.Status = 'failed' }
    $report.Error = $_.Exception.Message
} finally {
    if ($watch.IsRunning) { $watch.Stop() }
    for ($index = $owned.Count - 1; $index -ge 0; $index--) {
        $report.Cleanup += Stop-OwnedGame $owned[$index]
    }
    $badCleanup = @($report.Cleanup | Where-Object { $_.Outcome -notin @('already_exited', 'stopped_owned_process') })
    if ($badCleanup.Count -gt 0 -and $report.Status -eq 'passed') {
        $report.Status = 'failed'
        $report.Error = 'Connection passed, but exact-process cleanup could not be completed; inspect Cleanup.'
    }
    $report.ElapsedSeconds = [Math]::Round($watch.Elapsed.TotalSeconds, 3)
    $report.FinishedUtc = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
}

Write-Host "Packaged loopback smoke: $($report.Status). Report: $reportPath"
[pscustomobject]$report
if ($report.Status -ne 'passed') { throw "Packaged loopback smoke $($report.Status): $($report.Error)" }
