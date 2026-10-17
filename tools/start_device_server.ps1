param([switch]$Restart, [switch]$RestartGame)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskAdb = 'D:\tool\platform-tools-latest-windows\platform-tools\adb.exe'
$taskPidFile = Join-Path $taskRoot 'analysis\device\server.pid'
if (Test-Path -LiteralPath $taskPidFile) {
    $taskOldId = [int](Get-Content -LiteralPath $taskPidFile)
    $taskOld = Get-CimInstance Win32_Process -Filter "ProcessId=$taskOldId"
    if ($taskOld) {
        if (-not $Restart) { throw 'Test server already exists; use -Restart.' }
        if ($taskOld.CommandLine -notmatch '(^|\s)-m\s+game_server(\s|$)') {
            throw 'Recorded process does not match the game test server; refusing to stop it.'
        }
        Stop-Process -Id $taskOldId
    }
}
$taskPython = (Get-Command python).Source
$taskServer = Start-Process -FilePath $taskPython -ArgumentList @(
    '-u','-m','game_server','--port','19090','--http-port','18080',
    '--database','client-work/device.sqlite3','--cdn-fixtures','client-work/cdn-fixtures',
    '--request-log','analysis/device/http_requests.jsonl',
    '--protocol-log','analysis/device/protocol_events.jsonl','--allow-local-client-login','--reload-core'
) -WorkingDirectory $taskRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $taskRoot 'analysis\device\server.stdout.log') `
    -RedirectStandardError (Join-Path $taskRoot 'analysis\device\server.stderr.log') -PassThru
$taskServer.Id | Set-Content -LiteralPath $taskPidFile
& $taskAdb reverse tcp:18080 tcp:18080
if ($LASTEXITCODE -ne 0) { throw 'Phone HTTP reverse failed.' }
& $taskAdb reverse tcp:19090 tcp:19090
if ($LASTEXITCODE -ne 0) { throw 'Phone game reverse failed.' }
if ($RestartGame) {
    & $taskAdb shell am force-stop com.tw99.no23.an
    & $taskAdb shell am start -n com.tw99.no23.an/com.xxx.sy4399.MainActivity
}
Write-Output "Local test server process: $($taskServer.Id)"
