<#
two-process, loopback-only connection smoke for the latest native package.
this verifies handshake/join and client map travel, not roles, scoring,
replication correctness, remote networking, or a complete regulation match.

UE5.8 source confirms port= in CoreMisc.cpp/FUrlConfig::Init, multihome= in
SocketSubsystem.cpp, server-side join succeeded in World.cpp, and client-side
welcomed by server in PendingNetGame.cpp. that file also replaces name= with
the online nickname, so a separate bbnetsmoke= url option identifies the run.
no editor or firewall changes.
#>
[cmdletbinding()]
param(
    [validaterange(1024, 65535)][int]$port = 18779,
    [validaterange(5, 30)][int]$timeoutseconds = 30,
    [switch]$bloodbroom,
    [validateset('classic', 'redrock', 'redwoods')][string]$arena = 'classic'
)

$erroractionpreference = 'stop'
set-strictmode -version 2.0
$repo = [IO.Path]::GetFullPath((Join-Path $psscriptroot '..'))
$runname = (get-date -format 'yyyymmdd-hhmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$rundirectory = join-path $repo ('.local\packaged-network\' + $runname)
new-item -itemtype directory -path $rundirectory -force | out-null
$reportpath = join-path $rundirectory 'result.json'
$serverlog = join-path $rundirectory 'server.log'
$clientlog = join-path $rundirectory 'client.log'
$clientname = 'bbnetclient_' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$owned = new-object 'System.Collections.Generic.List[object]'
$watch = [Diagnostics.Stopwatch]::new()
$report = [ordered]@{
    status = 'not_run'
    scope = 'two local packaged processes: loopback connection/join and client map travel only'
    requestedvariant = $(if ($bloodbroom) { 'bloodbroom' } else { 'basketbroom' })
    excludes = @('variant activation/replication', 'role selection', 'score replication', 'remote connectivity', 'Latency/load', 'full regulation gameplay')
    startedutc = [DateTime]::UtcNow.ToString('o')
    timeoutseconds = $timeoutseconds
    address = '127.0.0.1'
    port = $port
    executable = $null
    clientname = $clientname
    logs = [ordered]@{ server = $serverlog; client = $clientlog }
    processes = @()
    bindings = @()
    evidence = [ordered]@{}
    logerrors = @()
    error = $null
    cleanup = @()
}

function read-livelog([string]$path) {
    if (-not [IO.File]::Exists($Path)) { return '' }
    # unreal still has its log open. explicit sharing permits live reads.
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

function find-evidence([string]$text, [string]$pattern) {
    $found = [regex]::Match($Text, $pattern, [Text.RegularExpressions.RegexOptions]::Multiline)
    if ($found.Success) { return $found.Value.Trim() }
    return $null
}

function find-logerrors([string]$text, [string]$role) {
    $pattern = '^.*(?:Fatal error:|Assertion failed:|Ensure condition failed:|Log[^:\r\n]+:\s*(?:Error|Fatal):|NetworkFailure|TravelFailure|Join failure:).*$'
    foreach ($entry in [regex]::Matches($Text, $pattern, [Text.RegularExpressions.RegexOptions]::Multiline)) {
        [pscustomobject]@{ role = $role; line = $entry.Value.Trim() }
    }
}

function wait-ownedgameidentity($record, [int]$timeoutmilliseconds = 5000) {
    $metadatawatch = [Diagnostics.Stopwatch]::StartNew()
    try {
        do {
            $Record.Process.Refresh()
            if ($Record.Process.HasExited) {
                throw "$($Record.Role) exited during startup with code $($Record.Process.ExitCode)."
            }
            $rawpath = $null
            $startedutc = $null
            # MainModule/Path may not be populated immediately after creation.
            # retry missing metadata, but reject an observed identity mismatch.
            try { $rawpath = $Record.Process.Path } catch { }
            try { $startedutc = $Record.Process.StartTime.ToUniversalTime() } catch { }
            if (-not [string]::IsNullOrWhiteSpace($rawPath)) {
                if (-not [IO.Path]::IsPathRooted($rawPath)) { throw 'started process reported a non-absolute executable path.' }
                $actualpath = [IO.Path]::GetFullPath($rawPath)
                if (-not [string]::Equals($actualPath, $Record.Executable, [StringComparison]::OrdinalIgnoreCase)) {
                    throw "$($Record.Role) process executable differs from the selected package."
                }
                if ($null -ne $startedutc -and $startedUtc.Ticks -gt 0) {
                    $Record.StartTimeUtcTicks = $startedUtc.Ticks
                    $Record.StartupIdentityVerified = $true
                    $Record.Receipt.Executable = $actualpath
                    $Record.Receipt.StartTimeUtc = $startedUtc.ToString('o')
                    $Record.Receipt.StartupIdentityVerified = $true
                    return
                }
            }
            if ($metadataWatch.ElapsedMilliseconds -lt $timeoutmilliseconds) { start-sleep -milliseconds 50 }
        } while ($metadataWatch.ElapsedMilliseconds -lt $timeoutmilliseconds)
        throw "$($Record.Role) executable/start-time metadata was unavailable after $timeoutmilliseconds ms."
    } finally {
        $metadataWatch.Stop()
        $Record.Receipt.MetadataWaitMilliseconds = $metadataWatch.ElapsedMilliseconds
    }
}

function start-ownedgame([string]$role, [string[]]$arguments) {
    # direct Process.Start with useshellexecute=false retains the os creation
    # handle. cleanup can target that exact process even while Path/StartTime
    # metadata is late; it never reopens a pid or searches by executable name.
    $startinfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $script:mainExecutable
    $startInfo.Arguments = [string]::Join(' ', $arguments)
    $startInfo.WorkingDirectory = $script:packageRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startinfo
    if (-not $process.Start()) { $process.Dispose(); throw "$role process did not start." }
    $record = [pscustomobject]@{
        role = $role; id = $process.Id; process = $process
        executable = $script:mainExecutable; starttimeutcticks = 0l
        starteddirectly = $true; creationhandle = $process.SafeHandle
        startupidentityverified = $false; receipt = $null
    }
    $script:owned.Add($record)
    $record.Receipt = [pscustomobject]@{
        role = $role; id = $record.Id; requestedexecutable = $script:mainExecutable
        executable = $null; starttimeutc = $null; arguments = $arguments
        ownership = 'original_process_creation_handle'; startupidentityverified = $false
        metadatawaitmilliseconds = 0l
    }
    $script:report.Processes += $record.Receipt
    if ($record.CreationHandle.IsInvalid -or $record.CreationHandle.IsClosed) {
        throw "$role did not retain a valid process creation handle."
    }
    wait-ownedgameidentity $record
    return $record
}

function stop-ownedgame($record) {
    $result = [ordered]@{
        role = $Record.Role; id = $Record.Id; outcome = 'already_exited'
        identitybasis = 'original_process_creation_handle'
        startupidentityverified = $Record.StartupIdentityVerified
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
        # Process.Start retained this handle before metadata verification. a
        # late/missing image path cannot redirect it to a recycled PID. kill and
        # waitforexit act on the same original process object and owned handle.
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
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'this packaged test requires Windows.' }
    if (-not (get-command get-netudpendpoint -erroraction silentlycontinue)) { throw 'get-netudpendpoint is required to verify the actual loopback binding.' }
    $manifestpath = join-path $repo '.local\latest-package.json'
    $package = get-content -literalpath $manifestpath -raw | convertfrom-json
    if ($package.Status -ne 'complete' -or $package.NativeRuntime -ne $true) { throw 'the latest package is not a completed native runtime package.' }
    if ($package.Configuration -ne 'development') { throw 'use a development package so connection logs are available.' }
    if ($package.EngineVersion -notmatch '^5\.8(?:\.|$)') { throw 'this smoke test expects the UE5.8 native package.' }
    if (-not [IO.Path]::IsPathRooted($package.Executable) -or -not (test-path -literalpath $package.Executable -pathtype leaf)) {
        throw 'the package bootstrap executable is missing or not an absolute path.'
    }
    $packageroot = [IO.Path]::GetFullPath((Split-Path -parent $package.Executable))
    $archive = [IO.Path]::GetFullPath($package.Archive).TrimEnd('\') + '\'
    if (-not ($packageroot + '\').StartsWith($archive, [StringComparison]::OrdinalIgnoreCase)) { throw 'package root is outside its recorded archive.' }
    # launch the main executable directly: the bootstrap would hide the game PID.
    $mainexecutable = [IO.Path]::GetFullPath((Join-Path $packageroot 'BasketbroomDev\Binaries\Win64\BasketbroomDev.exe'))
    if (-not (test-path -literalpath $mainexecutable -pathtype leaf)) { throw "packaged main executable missing: $mainexecutable" }
    $report.Executable = $mainexecutable
    $report.PackageManifest = $manifestpath

    $ipproperties = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
    $occupied = @($ipProperties.GetActiveUdpListeners() | where-object { $_.Port -eq $port })
    if ($occupied.Count -gt 0) { throw "udp port $port is already in use; no processes were started." }
    $reservation = [Net.Sockets.UdpClient]::new([Net.Sockets.AddressFamily]::InterNetwork)
    try {
        $reservation.Client.ExclusiveAddressUse = $true
        $reservation.Client.Bind([Net.IPEndPoint]::new([Net.IPAddress]::Loopback, $port))
    } finally { $reservation.Dispose() }

    $common = @('-nullrhi', '-unattended', '-nosound', '-nosplash', '-MULTIHOME=127.0.0.1', '-forcelogflush')
    . (join-path $psscriptroot 'Resolve-BBArena.ps1')
    $availablemaps = @('/Basketbroom/Maps/BB_Regulation')
    if ($null -ne $package.PSObject.Properties['ArenaMaps']) { $availablemaps = @($package.ArenaMaps) }
    $selectedmap = resolve-bbarenamap -arena $arena -availablemaps $availablemaps
    $report.Arena = $selectedmap
    $mappattern = [regex]::Escape($selectedMap)
    $hostmap = $selectedmap + '?listen?practice=1'
    if ($bloodbroom) { $hostmap += '?bloodbroom=1' }
    $serverarguments = @($hostmap, "-port=$port") + $common + @(('-abslog="{0}"' -f $serverlog))
    # nmt_challenge copies url options but overrides name= with GetNickname().
    # use an otherwise inert url option to correlate this client's join.
    $clientarguments = @("127.0.0.1:${Port}?BBNetSmoke=$clientName") + $common + @(('-abslog="{0}"' -f $clientlog))
    $report.Status = 'running'
    $watch.Start()
    $server = start-ownedgame 'server' $serverarguments
    $client = $null
    $boundloopback = $false
    $servertext = ''
    $clienttext = ''
    while ($watch.Elapsed.TotalSeconds -lt $timeoutseconds) {
        $servertext = read-livelog $serverlog
        $clienttext = read-livelog $clientlog
        $errors = @(find-logerrors $servertext 'server') + @(find-logerrors $clienttext 'client')
        if ($errors.Count -gt 0) {
            $report.LogErrors = $errors
            throw 'the packaged processes logged an engine or network error; see logerrors and the complete logs.'
        }
        foreach ($entry in $owned) {
            $entry.Process.Refresh()
            if ($entry.Process.HasExited) { throw "$($entry.Role) exited before verification, code $($entry.Process.ExitCode)." }
        }
        $listening = find-evidence $servertext ('^.*IpNetDriver listening on port ' + $port + '\b.*$')
        if ($listening -and -not $boundloopback) {
            $endpoints = @(get-netudpendpoint -owningprocess $server.Id -localport $port -erroraction silentlycontinue)
            if ($endpoints.Count -gt 0) {
                $report.Bindings = @($endpoints | select-object localaddress, localport, owningprocess)
                if (@($endpoints | where-object { $_.LocalAddress -ne '127.0.0.1' }).Count -gt 0) {
                    throw 'the server bound an address other than ipv4 loopback.'
                }
                $boundloopback = $true
            }
        }
        if ($boundloopback -and $null -eq $client) { $client = start-ownedgame 'client' $clientarguments }

        $accepted = find-evidence $servertext '^.*NotifyAcceptedConnection:.*127\.0\.0\.1.*$'
        $request = find-evidence $servertext ('^.*Join request:.*\?BBNetSmoke=' + [regex]::Escape($clientName) + '(?:\?|\s|$).*$')
        $joined = $null
        if ($request) {
            $requestindex = $serverText.IndexOf($request, [StringComparison]::Ordinal)
            if ($requestindex -ge 0) { $joined = find-evidence ($serverText.Substring($requestIndex)) '^.*Join succeeded:.*$' }
        }
        $welcomed = find-evidence $clienttext ('^.*Welcomed by server \(Level: ' + $mappattern + '(?:\?|\)|\s|$).*$')
        $loaded = $null
        if ($welcomed) {
            $welcomeindex = $clientText.IndexOf($welcomed, [StringComparison]::Ordinal)
            if ($welcomeindex -ge 0) {
                $loaded = find-evidence ($clientText.Substring($welcomeIndex)) ('^.*LogLoad: took .*LoadMap\(' + $mappattern + '\).*$')
            }
        }
        $report.Evidence = [ordered]@{
            serverlistening = $listening; serverboundloopback = $boundloopback
            serveracceptedloopback = $accepted; serverreceivedtaggedclientjoin = $request
            serverclientjoinsucceeded = $joined; clientwelcomedtoregulation = $welcomed
            clientcompletedregulationmapload = $loaded
        }
        if ($boundloopback -and $accepted -and $request -and $joined -and $welcomed -and $loaded) {
            $report.Status = 'passed'
            break
        }
        start-sleep -milliseconds 200
    }
    if ($report.Status -ne 'passed') { throw "connection evidence was incomplete after $timeoutseconds seconds." }
} catch {
    if ($report.Status -eq 'running') { $report.Status = 'failed' }
    $report.Error = $_.Exception.Message
} finally {
    if ($watch.IsRunning) { $watch.Stop() }
    for ($index = $owned.Count - 1; $index -ge 0; $index--) {
        $report.Cleanup += stop-ownedgame $owned[$index]
    }
    $badcleanup = @($report.Cleanup | where-object { $_.Outcome -notin @('already_exited', 'stopped_owned_process') })
    if ($badCleanup.Count -gt 0 -and $report.Status -eq 'passed') {
        $report.Status = 'failed'
        $report.Error = 'connection passed, but exact-process cleanup could not be completed; inspect Cleanup.'
    }
    $report.ElapsedSeconds = [Math]::Round($watch.Elapsed.TotalSeconds, 3)
    $report.FinishedUtc = [DateTime]::UtcNow.ToString('o')
    $report | convertto-json -depth 8 | set-content -literalpath $reportpath -encoding utf8
}

write-host "packaged loopback smoke: $($report.Status). Report: $reportpath"
[pscustomobject]$report
if ($report.Status -ne 'passed') { throw "packaged loopback smoke $($report.Status): $($report.Error)" }
