param([string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $taskRoot 'client-work\windows-client' }
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $taskCompiler)) { throw 'Windows .NET Framework compiler is unavailable.' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$taskOutput = Join-Path $OutputDirectory 'CoreLicht.exe'
& $taskCompiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$taskOutput" `
  /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll `
  /reference:System.Net.Http.dll (Join-Path $PSScriptRoot 'Protocol.cs') (Join-Path $PSScriptRoot 'Client.cs') (Join-Path $PSScriptRoot 'MobileView.cs') (Join-Path $PSScriptRoot 'Gameplay.cs') (Join-Path $PSScriptRoot 'VoiceAudio.cs')
if ($LASTEXITCODE -ne 0) { throw 'Native client build failed.' }
Write-Output "Built $taskOutput"
