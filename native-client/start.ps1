param([string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $taskRoot 'client-work\windows-client' }
$taskExecutable = Join-Path $OutputDirectory 'CoreLicht.exe'
if (-not (Test-Path -LiteralPath $taskExecutable)) { throw 'Build the native client first.' }
$taskHealth = $null
try { $taskHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:18080/health' -TimeoutSec 2 } catch {}
if (-not $taskHealth -or $taskHealth.status -ne 'prototype') {
    # Check both ports before starting a service. Never stop an unknown process.
    foreach ($taskPort in @(18080,19090)) {
        $taskSocket = New-Object Net.Sockets.TcpClient
        try { $taskSocket.Connect('127.0.0.1',$taskPort);throw "Port $taskPort is occupied by an unrecognized service." }
        catch [Net.Sockets.SocketException] {} finally { $taskSocket.Dispose() }
    }
    $taskPython = (Get-Command python).Source
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList @(
        '-u','-m','game_server','--port','19090','--http-port','18080',
        '--database','client-work/device.sqlite3','--analysis','analysis',
        '--cdn-fixtures','client-work/cdn-fixtures','--allow-local-client-login','--reload-core'
    ) -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
      -RedirectStandardOutput (Join-Path $OutputDirectory 'server.stdout.log') `
      -RedirectStandardError (Join-Path $OutputDirectory 'server.stderr.log')
    $taskProcess.Id | Set-Content -LiteralPath (Join-Path $OutputDirectory 'server.pid')
    $taskReady = $false
    for ($taskAttempt=0; $taskAttempt -lt 20; $taskAttempt++) {
        try { $taskHealth=Invoke-RestMethod -Uri 'http://127.0.0.1:18080/health' -TimeoutSec 1
            if ($taskHealth.status -eq 'prototype') { $taskReady=$true;break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $taskReady) { throw 'Local server startup did not complete; inspect the local server logs.' }
}
Start-Process -FilePath $taskExecutable
