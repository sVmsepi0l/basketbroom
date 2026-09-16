<# Installs Microsoft's C++ compiler and Windows SDK. Windows may require user UAC approval. #>
[CmdletBinding()]
param([switch]$Plan)
$ErrorActionPreference = 'Stop'
$url = 'https://aka.ms/vs/stable/vs_BuildTools.exe'
$installerPath = Join-Path $PSScriptRoot '.local\Installers\vs_BuildTools.exe'
$arguments = @('--passive', '--wait', '--norestart', '--add', 'Microsoft.VisualStudio.Workload.VCTools',
    '--add', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
    '--add', 'Microsoft.VisualStudio.Component.Windows11SDK.26100',
    '--add', 'Microsoft.Net.Component.4.8.SDK',
    '--add', 'Microsoft.Net.Component.4.8.TargetingPack', '--includeRecommended')
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path -LiteralPath $vswhere) {
    $existingBuildTools = & $vswhere -latest -products Microsoft.VisualStudio.Product.BuildTools -property installationPath
    if ($existingBuildTools) {
        $arguments = @('modify', '--installPath', ('"{0}"' -f $existingBuildTools)) + $arguments
    }
}
if ($Plan) { [pscustomobject]@{ Source = $url; Installer = $installerPath; Arguments = $arguments }; return }
New-Item -ItemType Directory -Force -Path (Split-Path $installerPath) | Out-Null
if (-not (Test-Path -LiteralPath $installerPath)) { Invoke-WebRequest -Uri $url -OutFile $installerPath }
$signature = Get-AuthenticodeSignature -LiteralPath $installerPath
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'The installer does not have a valid Microsoft signature. No installation was started.'
}
Write-Host 'Approve the Windows administrator prompt to install the C++ compiler and Windows SDK.'
$process = Start-Process -FilePath $installerPath -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -notin @(0, 3010)) { throw "Build Tools setup returned $($process.ExitCode)." }
if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Setup ended but Visual Studio Installer was not found.' }
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) { throw 'Setup ended but a C++ compiler installation was not found.' }
Write-Host "C++ toolchain ready: $installation"
if ($process.ExitCode -eq 3010) { Write-Host 'Windows requests a restart before building.' }
