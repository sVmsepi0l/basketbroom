<#
.SYNOPSIS
create or refresh the current user's basketbroom practice desktop shortcut.
.DESCRIPTION
uses windows' resolved desktop known folder, including redirected desktops.
the shortcut invokes this checkout's stable Play.ps1 through installed powershell;
Play.ps1 selects the latest completed local package. no execution policy or other
security setting is changed. an unrelated existing Basketbroom.lnk is preserved.
#>
[cmdletbinding()]
param()

$erroractionpreference = 'stop'
$repodirectory = [IO.Path]::GetFullPath($PSScriptRoot)
$playscript = join-path $repodirectory 'Play.ps1'
if (-not (test-path -literalpath $playscript -pathtype leaf)) {
    throw "the basketbroom launcher is missing: '$playScript'."
}

# desktopdirectory resolves the current user's windows known folder, including
# onedrive or other redirection. do not guess a path beneath the user profile.
$desktopdirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
if ([string]::IsNullOrWhiteSpace($desktopDirectory) -or
    -not (test-path -literalpath $desktopdirectory -pathtype container)) {
    throw 'windows did not return an existing desktop folder for this user.'
}
$shortcutpath = join-path $desktopdirectory 'Basketbroom.lnk'
$powershellcommand = get-command -name pwsh.exe -commandtype application -erroraction silentlycontinue |
    select-object -first 1
$powershellpath = if ($powershellcommand) { $powerShellCommand.Source } else {
    join-path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
}
if (-not (test-path -literalpath $powershellpath -pathtype leaf)) {
    throw 'an installed powershell executable could not be found.'
}
$shortcutarguments = '-nologo -noprofile -noninteractive -windowstyle hidden -file "{0}" -practice' -f $playscript
$ownerdescription = 'basketbroom practice launcher (managed by Install-DesktopShortcut.ps1).'
$iconlocation = "$powershellpath,0"
$manifestpath = join-path $repodirectory '.local\latest-package.json'
if (test-path -literalpath $manifestpath -pathtype leaf) {
    try {
        $package = get-content -literalpath $manifestpath -raw | convertfrom-json
        if ($package.Status -eq 'complete' -and $package.NativeRuntime -eq $true -and
            -not [string]::IsNullOrWhiteSpace($package.Executable) -and
            [IO.Path]::IsPathRooted($package.Executable) -and
            (test-path -literalpath $package.Executable -pathtype leaf)) {
            $iconlocation = "$($package.Executable),0"
        }
    } catch {
        write-verbose "the current package icon is unavailable; using the powershell icon. $_"
    }
}

$shortcutshell = $null
$shortcut = $null
$verifiedshortcut = $null
$action = 'created'
try {
    $shortcutshell = new-object -comobject WScript.Shell
    if (test-path -literalpath $shortcutpath) {
        if (-not (test-path -literalpath $shortcutpath -pathtype leaf)) {
            throw "an unrelated item already exists at '$shortcutpath'; nothing was changed."
        }
        $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
        # refuse to replace a same-named shortcut unless this script owns it and
        # it still launches this checkout with the exact expected arguments.
        if ($shortcut.Description -ne $ownerdescription -or
            $shortcut.WorkingDirectory -ne $repodirectory -or
            $shortcut.Arguments -ne $shortcutarguments -or
            [IO.Path]::GetFileName($shortcut.TargetPath) -notin @('pwsh.exe', 'powershell.exe')) {
            throw "an unrelated or modified shortcut already exists at '$shortcutpath'; nothing was changed."
        }
        $action = 'updated'
    } else {
        $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    }
    $shortcut.TargetPath = $powershellpath
    $shortcut.Arguments = $shortcutarguments
    $shortcut.WorkingDirectory = $repodirectory
    $shortcut.Description = $ownerdescription
    $shortcut.IconLocation = $iconlocation
    # wsh supports normal/maximized/minimized startup; powershell's explicit
    # hidden option keeps the launcher shell out of the way. Play.ps1 opens the
    # game itself as a normal visible window.
    $shortcut.WindowStyle = 7
    $shortcut.Save()

    $verifiedshortcut = $shortcutShell.CreateShortcut($shortcutPath)
    if ($verifiedShortcut.TargetPath -ne $powershellpath -or
        $verifiedShortcut.Arguments -ne $shortcutarguments -or
        $verifiedShortcut.WorkingDirectory -ne $repodirectory -or
        $verifiedShortcut.Description -ne $ownerdescription -or
        $verifiedShortcut.WindowStyle -ne 7) {
        throw "the saved shortcut did not match the requested launcher: '$shortcutPath'."
    }
    [pscustomobject]@{
        action = $action
        shortcut = $shortcutpath
        targetpath = $verifiedShortcut.TargetPath
        arguments = $verifiedShortcut.Arguments
        workingdirectory = $verifiedShortcut.WorkingDirectory
        iconlocation = $verifiedShortcut.IconLocation
        windowstyle = $verifiedShortcut.WindowStyle
    }
} finally {
    foreach ($comobject in @($verifiedshortcut, $shortcut, $shortcutshell)) {
        if ($null -ne $comobject -and [Runtime.InteropServices.Marshal]::IsComObject($comObject)) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($comObject)
        }
    }
}
