# Licht Windows 語音與本機伺服器

已另提供免安裝 Python 的 [單檔 Server 與區網模式](SERVER_EXE.md)；APK／Server 安裝檔見 [Release](https://github.com/fuyuiisfine-dot/Core-Licht/releases/tag/v0.1.38-lan.20261018)。下方 Python 指令保留供原始碼開發使用。

## 目前功能

Windows 客戶端的「檔案 → 語音台詞」可播放與停止已解鎖的角色語音。切換台詞、角色或離開頁面會停止前一段聲音。音檔從你自己的 OBB 備份匯出，儲存在 `client-work/windows-client/data/voices/`；此目錄、EXE 與私人存檔都不進 Git。

本次本機資料有 3,960 筆語音台詞，其中 3,905 筆提供音檔名稱，並已從備份匯出 3,905 個 WAV。另 55 筆在設定中沒有 `voice_name`，會維持文字顯示。

## 從備份重建語音（換電腦時）

在專案根目錄開 PowerShell，先完成 `README.md` 的分析資料及 Windows 客戶端資料準備，再執行：

```powershell
python -m pip install -r requirements.txt -r requirements-analysis.txt
python tools/prepare_voice_audio.py --backup 'D:\tool\platform-tools-latest-windows\platform-tools\game_backup\obb'
native-client/build.ps1
```

`--backup` 指向放有 `main.*.obb` 和 `patch.*.obb` 的資料夾。工具只匯出 Windows 目錄裡的角色語音；重跑時會略過已存在的 WAV。若只想驗證一個音效庫，可以加 `--bank Gabi`。匯出結果會列出 `available`、`wanted` 與失敗的 bank。

## 開本機伺服器與遊戲

在**含 `game_server/`、`analysis/` 與 `client-work/` 的專案根目錄**開 PowerShell：

```powershell
python -m pip install -r requirements.txt
native-client/start.ps1
```

`start.ps1` 會先檢查 `http://127.0.0.1:18080/health`，需要時在背景啟動本機伺服器，然後開啟 `client-work/windows-client/CoreLicht.exe`。現成安裝也可雙擊 `client-work/windows-client/StartClient.cmd`。登入帳號是 `windows-preview`。不需要 Android 模擬器或 ADB。

要只開伺服器並查看其輸出，可在上述根目錄執行：

```powershell
python -u -m game_server --port 19090 --http-port 18080 --database client-work/device.sqlite3 --analysis analysis --cdn-fixtures client-work/cdn-fixtures --allow-local-client-login --reload-core
```

保留這個 PowerShell 視窗開著，再啟動 `client-work/windows-client/CoreLicht.exe`。關閉前景伺服器時在同一視窗按 `Ctrl+C`。

檢查伺服器：

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
```

應看到 `status` 為 `prototype`。若 `start.ps1` 無法啟動，查看 `client-work/windows-client/server.stderr.log`；18080 或 19090 已被其他程式占用時，先確認該程式來源。此設定只供同一部電腦的本機預覽使用。
