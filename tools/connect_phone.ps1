param([string]$AdbPath='adb',[string]$Serial='',[switch]$RestartGame)
$ErrorActionPreference='Stop'
$taskHealth=Invoke-RestMethod -Uri 'http://127.0.0.1:18080/health' -TimeoutSec 3
if ($taskHealth.status -ne 'prototype') { throw 'Start CoreLichtServer.exe first.' }
$taskDevices=@(& $AdbPath devices)
if ($LASTEXITCODE -ne 0) { throw 'ADB is unavailable.' }
$taskOnline=@($taskDevices | ForEach-Object { if ($_ -match '^(\S+)\s+device\s*$') { $Matches[1] } })
if (-not $Serial) {
    if ($taskOnline.Count -ne 1) { throw 'Connect one authorized phone, or specify -Serial.' }
    $Serial=$taskOnline[0]
}
if ($taskOnline -notcontains $Serial) { throw 'The selected phone is not online and authorized.' }
foreach ($taskPort in @(18080,19090)) {
    & $AdbPath -s $Serial reverse "tcp:$taskPort" "tcp:$taskPort"
    if ($LASTEXITCODE -ne 0) { throw "Unable to connect phone port $taskPort." }
}
if ($RestartGame) {
    & $AdbPath -s $Serial shell am force-stop com.tw99.no23.an
    if ($LASTEXITCODE -ne 0) { throw 'Unable to stop the game.' }
    & $AdbPath -s $Serial shell am start -n com.tw99.no23.an/com.xxx.sy4399.MainActivity
    if ($LASTEXITCODE -ne 0) { throw 'Unable to launch the game.' }
}
Write-Output 'Phone connected to the local server. No app data was cleared.'
