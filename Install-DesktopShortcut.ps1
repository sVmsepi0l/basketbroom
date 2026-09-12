<#
.SYNOPSIS
Create or refresh the current user's Basketbroom Practice desktop shortcut.
.DESCRIPTION
Uses Windows' resolved Desktop known folder, including redirected desktops.
The shortcut invokes this checkout's stable Play.ps1 through installed PowerShell;
Play.ps1 selects the latest completed local package. No execution policy or other
security setting is changed. An unrelated existing Basketbroom.lnk is preserved.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoDirectory = [IO.Path]::GetFullPath($PSScriptRoot)
$playScript = Join-Path $repoDirectory 'Play.ps1'
if (-not (Test-Path -LiteralPath $playScript -PathType Leaf)) {
    throw "The Basketbroom launcher is missing: '$playScript'."
}

# DesktopDirectory resolves the current user's Windows known folder, including
# OneDrive or other redirection. Do not guess a path beneath the user profile.
$desktopDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
if ([string]::IsNullOrWhiteSpace($desktopDirectory) -or
    -not (Test-Path -LiteralPath $desktopDirectory -PathType Container)) {
    throw 'Windows did not return an existing Desktop folder for this user.'
}
$shortcutPath = Join-Path $desktopDirectory 'Basketbroom.lnk'
$powerShellCommand = Get-Command -Name pwsh.exe -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
$powerShellPath = if ($powerShellCommand) { $powerShellCommand.Source } else {
    Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
}
if (-not (Test-Path -LiteralPath $powerShellPath -PathType Leaf)) {
    throw 'An installed PowerShell executable could not be found.'
}
$shortcutArguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File "{0}" -Practice' -f $playScript
$ownerDescription = 'Basketbroom Practice launcher (managed by Install-DesktopShortcut.ps1).'
$iconLocation = "$powerShellPath,0"
$manifestPath = Join-Path $repoDirectory '.local\latest-package.json'
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    try {
        $package = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ($package.Status -eq 'complete' -and $package.NativeRuntime -eq $true -and
            -not [string]::IsNullOrWhiteSpace($package.Executable) -and
            [IO.Path]::IsPathRooted($package.Executable) -and
            (Test-Path -LiteralPath $package.Executable -PathType Leaf)) {
            $iconLocation = "$($package.Executable),0"
        }
    } catch {
        Write-Verbose "The current package icon is unavailable; using the PowerShell icon. $_"
    }
}

$shortcutShell = $null
$shortcut = $null
$verifiedShortcut = $null
$action = 'created'
try {
    $shortcutShell = New-Object -ComObject WScript.Shell
    if (Test-Path -LiteralPath $shortcutPath) {
        if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
            throw "An unrelated item already exists at '$shortcutPath'; nothing was changed."
        }
        $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
        # Refuse to replace a same-named shortcut unless this script owns it and
        # it still launches this checkout with the exact expected arguments.
        if ($shortcut.Description -ne $ownerDescription -or
            $shortcut.WorkingDirectory -ne $repoDirectory -or
            $shortcut.Arguments -ne $shortcutArguments -or
            [IO.Path]::GetFileName($shortcut.TargetPath) -notin @('pwsh.exe', 'powershell.exe')) {
            throw "An unrelated or modified shortcut already exists at '$shortcutPath'; nothing was changed."
        }
        $action = 'updated'
    } else {
        $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    }
    $shortcut.TargetPath = $powerShellPath
    $shortcut.Arguments = $shortcutArguments
    $shortcut.WorkingDirectory = $repoDirectory
    $shortcut.Description = $ownerDescription
    $shortcut.IconLocation = $iconLocation
    # WSH supports normal/maximized/minimized startup; PowerShell's explicit
    # Hidden option keeps the launcher shell out of the way. Play.ps1 opens the
    # game itself as a normal visible window.
    $shortcut.WindowStyle = 7
    $shortcut.Save()

    $verifiedShortcut = $shortcutShell.CreateShortcut($shortcutPath)
    if ($verifiedShortcut.TargetPath -ne $powerShellPath -or
        $verifiedShortcut.Arguments -ne $shortcutArguments -or
        $verifiedShortcut.WorkingDirectory -ne $repoDirectory -or
        $verifiedShortcut.Description -ne $ownerDescription -or
        $verifiedShortcut.WindowStyle -ne 7) {
        throw "The saved shortcut did not match the requested launcher: '$shortcutPath'."
    }
    [pscustomobject]@{
        Action = $action
        Shortcut = $shortcutPath
        TargetPath = $verifiedShortcut.TargetPath
        Arguments = $verifiedShortcut.Arguments
        WorkingDirectory = $verifiedShortcut.WorkingDirectory
        IconLocation = $verifiedShortcut.IconLocation
        WindowStyle = $verifiedShortcut.WindowStyle
    }
} finally {
    foreach ($comObject in @($verifiedShortcut, $shortcut, $shortcutShell)) {
        if ($null -ne $comObject -and [Runtime.InteropServices.Marshal]::IsComObject($comObject)) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($comObject)
        }
    }
}
