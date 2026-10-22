param(
    [Parameter(Mandatory=$true)][string]$ClientDirectory,
    [Parameter(Mandatory=$true)][string]$ServerExecutable,
    [Parameter(Mandatory=$true)][string]$NsisCompiler,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$taskSource = Join-Path (Split-Path -Parent $PSScriptRoot) 'native-client'
$ClientDirectory = (Resolve-Path -LiteralPath $ClientDirectory).Path
$ServerExecutable = (Resolve-Path -LiteralPath $ServerExecutable).Path
$NsisCompiler = (Resolve-Path -LiteralPath $NsisCompiler).Path
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$taskLauncher = Join-Path $OutputDirectory 'CoreLichtLauncher.exe'
& $taskCompiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$taskLauncher" /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll (Join-Path $taskSource 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
$taskGuide = Join-Path $OutputDirectory 'Windows-README.txt'
Copy-Item -LiteralPath (Join-Path $taskSource 'Windows-README.txt') -Destination $taskGuide
$taskInstaller = Join-Path $OutputDirectory 'CoreLicht-Windows-Setup.exe'
& $NsisCompiler /V2 "/DOUTPUT=$taskInstaller" "/DCLIENT=$ClientDirectory" "/DLAUNCHER=$taskLauncher" "/DSERVER=$ServerExecutable" "/DGUIDE=$taskGuide" (Join-Path $taskSource 'installer.nsi')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
$taskHash = (Get-FileHash -LiteralPath $taskInstaller -Algorithm SHA256).Hash.ToLowerInvariant()
"$taskHash  CoreLicht-Windows-Setup.exe" | Set-Content -LiteralPath (Join-Path $OutputDirectory 'SHA256SUMS-Windows-Native.txt') -Encoding ascii
Write-Output "Built $taskInstaller"
