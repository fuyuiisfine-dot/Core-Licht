param([switch]$Smoke,[switch]$GameSmoke)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskOutput=Join-Path $taskRoot 'client-work\windows-client'
$taskCompiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
Push-Location $taskRoot
try {
    & python (Join-Path $taskRoot 'tools\prepare_native_wire_tests.py')
    if ($LASTEXITCODE -ne 0) { throw 'Fixture generation failed.' }
    & $taskCompiler /nologo /target:exe "/out:$taskOutput\WireTests.exe" `
        /reference:System.Web.Extensions.dll /reference:System.Net.Http.dll `
        (Join-Path $PSScriptRoot 'Protocol.cs') (Join-Path $PSScriptRoot 'WireTests.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Protocol test build failed.' }
    & (Join-Path $taskOutput 'WireTests.exe') (Join-Path $taskOutput 'data\protocol') (Join-Path $taskOutput 'wire-tests.json')
    if ($LASTEXITCODE -ne 0) { throw 'Cross-language protocol test failed.' }
    if ($Smoke -or $GameSmoke) {
        & (Join-Path $PSScriptRoot 'build.ps1')
        $taskMode=if ($GameSmoke) { '--game-smoke-test' } else { '--smoke-test' }
        $taskResultName=if ($GameSmoke) { 'data\gameplay-smoke-result.json' } else { 'data\smoke-result.json' }
        $taskRun=Start-Process -FilePath (Join-Path $taskOutput 'CoreLicht.exe') -ArgumentList $taskMode -WindowStyle Hidden -PassThru -Wait
        $taskResult=Get-Content -LiteralPath (Join-Path $taskOutput $taskResultName) -Raw | ConvertFrom-Json
        if ($taskRun.ExitCode -ne 0 -or -not $taskResult.success) { throw 'Native connection test failed.' }
        $taskResult | ConvertTo-Json
    }
} finally { Pop-Location }
