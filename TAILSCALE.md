# Licht Tailscale 測試

Server 位址：100.73.138.15。HTTP TCP 18080、遊戲 TCP 19090。
Server 僅監聽這個位址，來源允許 Tailscale IPv4 範圍；仍受 tailnet 存取政策限制。

目前已啟動，沿用隔離測試資料庫。關閉後，在專案根目錄執行：

```powershell
& .\client-work\mobile-dev\start-tailscale.ps1
```

請勿在現有服務仍執行時重複啟動。

防火牆新增因 Windows 權限不足而失敗。請以系統管理員身分開啟 PowerShell，執行：

```powershell
& 'D:\Documents\ChatGPT\逆向\client-work\mobile-dev\allow-tailscale-firewall.ps1'
```

手機連上同一個 tailnet 後，先以瀏覽器開啟 http://100.73.138.15:18080/health 。
應回傳 status 為 prototype 的 JSON；client_verified=false 是服務固定回傳的開發狀態。
此測試僅確認 HTTP，仍需 APK 登入確認遊戲 TCP 連線。

手機需安裝測試 APK、兩個 OBB，並將 client-work/mobile-dev/UrlList_Android.txt 放到
/sdcard/Android/data/com.tw99.no23.an/files/res/UrlList_Android.txt 。覆寫前先備份手機原檔。
本次僅更新 BlueStacks 的入口，沒有修改 APK 安裝包中的預設位址，也沒有操作實體手機。
BlueStacks 原入口備份：client-work/mobile-dev/UrlList.before-tailscale.txt。

已確認：此 IP 屬於本機 Tailscale、兩個服務埠監聽成功、本機 HTTP 健康檢查成功。
待確認：防火牆規則套用、手機跨裝置 HTTP 與 APK 登入。戰鬥尚未完成。
