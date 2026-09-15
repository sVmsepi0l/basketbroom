<# installs microsoft's c++ compiler and windows SDK. windows may require user uac approval. #>
[cmdletbinding()]
param([switch]$plan)
$erroractionpreference = 'stop'
$url = 'https://aka.ms/vs/stable/vs_BuildTools.exe'
$installerpath = join-path $psscriptroot '.local\Installers\vs_BuildTools.exe'
$arguments = @('--passive', '--wait', '--norestart', '--add', 'Microsoft.VisualStudio.Workload.VCTools',
    '--add', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
    '--add', 'Microsoft.VisualStudio.Component.Windows11SDK.26100',
    '--add', 'Microsoft.Net.Component.4.8.SDK',
    '--add', 'Microsoft.Net.Component.4.8.TargetingPack', '--includerecommended')
$vswhere = join-path ${env:ProgramFiles(x86)} 'microsoft visual Studio\Installer\vswhere.exe'
if (test-path -literalpath $vswhere) {
    $existingbuildtools = & $vswhere -latest -products Microsoft.VisualStudio.Product.BuildTools -property installationpath
    if ($existingbuildtools) {
        $arguments = @('modify', '--installpath', ('"{0}"' -f $existingbuildtools)) + $arguments
    }
}
if ($plan) { [pscustomobject]@{ source = $url; installer = $installerpath; arguments = $arguments }; return }
new-item -itemtype directory -force -path (split-path $installerpath) | out-null
if (-not (test-path -literalpath $installerpath)) { invoke-webrequest -uri $url -outfile $installerpath }
$signature = get-authenticodesignature -literalpath $installerpath
if ($signature.Status -ne 'valid' -or $signature.SignerCertificate.Subject -notmatch 'o=microsoft corporation') {
    throw 'the installer does not have a valid microsoft signature. no installation was started.'
}
write-host 'approve the windows administrator prompt to install the c++ compiler and windows SDK.'
$process = start-process -filepath $installerpath -argumentlist $arguments -windowstyle hidden -wait -passthru
if ($process.ExitCode -notin @(0, 3010)) { throw "build tools setup returned $($process.ExitCode)." }
if (-not (test-path -literalpath $vswhere)) { throw 'setup ended but visual studio installer was not found.' }
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationpath
if (-not $installation) { throw 'setup ended but a c++ compiler installation was not found.' }
write-host "c++ toolchain ready: $installation"
if ($process.ExitCode -eq 3010) { write-host 'windows requests a restart before building.' }
