param([string]$PrivateDirectory = '')
$ErrorActionPreference = 'Stop'
$taskRepository = Split-Path -Parent $PSScriptRoot
if (-not $PrivateDirectory) { $PrivateDirectory = Join-Path (Split-Path -Parent $taskRepository) 'client-work' }
$taskAnalysis = Join-Path (Split-Path -Parent $taskRepository) 'analysis'
$taskAssets = Join-Path $PrivateDirectory 'windows-client\data'
$taskSourceDb = Join-Path $PrivateDirectory 'device.sqlite3'
$taskHttpPort = 18081
$taskTcpPort = 19091
if (-not (Test-Path -LiteralPath (Join-Path $taskAssets 'catalog.json'))) { throw 'Prepared Windows client data is missing.' }
if (-not (Test-Path -LiteralPath $taskSourceDb)) { throw 'Local test database is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskAnalysis 'config\dungeon.json'))) { throw 'Prepared dungeon analysis is missing.' }

$taskOutput = Join-Path $PrivateDirectory ('first-stage-check-' + (Get-Date -Format 'yyyyMMddHHmmssfff'))
$taskData = Join-Path $taskOutput 'data'
New-Item -ItemType Directory -Path $taskData -Force | Out-Null
& (Join-Path $PSScriptRoot 'build.ps1') -OutputDirectory $taskOutput
Copy-Item -LiteralPath (Join-Path $taskAssets 'catalog.json') -Destination $taskData
if (Test-Path -LiteralPath (Join-Path $taskAssets 'story.json')) { Copy-Item -LiteralPath (Join-Path $taskAssets 'story.json') -Destination $taskData }
Copy-Item -LiteralPath (Join-Path $taskAssets 'protocol') -Destination $taskData -Recurse
foreach ($taskName in @('ui','portraits')) {
    New-Item -ItemType Junction -Path (Join-Path $taskData $taskName) -Target (Join-Path $taskAssets $taskName) | Out-Null
}
$taskDatabase = Join-Path $taskOutput 'test.sqlite3'
Copy-Item -LiteralPath $taskSourceDb -Destination $taskDatabase
# Reset only the copied rehearsal records so the test proves a first clear.
& python -X utf8 -c "import sqlite3,sys; db=sqlite3.connect(sys.argv[1]); role=db.execute('SELECT id FROM roles WHERE uid=?',('windows-preview',)).fetchone()[0]; db.execute('DELETE FROM role_snapshots WHERE role_id=? AND domain=?',(role,'native_rehearsal')); db.execute('DELETE FROM native_battles WHERE role_id=?',(role,)); db.commit()" $taskDatabase
if ($LASTEXITCODE -ne 0) { throw 'Could not reset the isolated first-stage database.' }

foreach ($taskPort in @($taskHttpPort,$taskTcpPort)) {
    $taskSocket = New-Object Net.Sockets.TcpClient
    try { $taskSocket.Connect('127.0.0.1',$taskPort); throw "Port $taskPort is occupied; choose another isolated test port." }
    catch [Net.Sockets.SocketException] {} finally { $taskSocket.Dispose() }
}

$taskServer = $null
try {
    $taskServer = Start-Process -FilePath (Get-Command python).Source -ArgumentList @(
        '-u','-m','game_server','--port',"$taskTcpPort",'--http-port',"$taskHttpPort",
        '--database',$taskDatabase,'--analysis',$taskAnalysis,
        '--cdn-fixtures',(Join-Path $PrivateDirectory 'cdn-fixtures'),
        '--allow-local-client-login'
    ) -WorkingDirectory $taskRepository -WindowStyle Hidden -PassThru `
      -RedirectStandardOutput (Join-Path $taskOutput 'server.stdout.log') `
      -RedirectStandardError (Join-Path $taskOutput 'server.stderr.log')
    $taskReady = $false
    for ($taskAttempt=0; $taskAttempt -lt 40; $taskAttempt++) {
        try { $taskHealth=Invoke-RestMethod -Uri "http://127.0.0.1:$taskHttpPort/health" -TimeoutSec 1
            if ($taskHealth.status -eq 'prototype') { $taskReady=$true;break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if (-not $taskReady) { throw 'Isolated server startup failed; inspect server.stderr.log.' }
    $taskRun = Start-Process -FilePath (Join-Path $taskOutput 'CoreLicht.exe') -ArgumentList @('--game-smoke-test',"--http-port=$taskHttpPort","--tcp-port=$taskTcpPort") -WindowStyle Hidden -PassThru -Wait
    $taskResult = Get-Content -LiteralPath (Join-Path $taskData 'gameplay-smoke-result.json') -Raw | ConvertFrom-Json
    if ($taskRun.ExitCode -ne 0 -or -not $taskResult.success) { throw "First-stage UI smoke failed: $($taskResult.error)" }
    $taskResult | ConvertTo-Json -Compress
    Write-Output "Artifacts: $taskOutput"
} finally {
    if ($taskServer -and -not $taskServer.HasExited) { Stop-Process -Id $taskServer.Id }
}
