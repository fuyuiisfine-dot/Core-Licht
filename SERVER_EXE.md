# 單檔 Windows 伺服器

`CoreLichtServer.exe` 已包含 Python 執行環境、伺服器程式、協定描述、必要設定表、全角色測試初始資料與已準備的 CDN 啟動檔。不需要另外安裝 Python、protobuf，或攜帶 analysis/。客戶端的圖片與語音仍由客戶端保管，不會重複塞進 server。

## 使用

1. 雙擊 `CoreLichtServer.exe`，保留視窗開啟。
2. 開啟原生客戶端 `CoreLicht.exe`，照常登入與遊玩。
3. 伺服器視窗按 Ctrl+C 可停止。

預設只監聽本機：HTTP 18080、遊戲 TCP 19090。若已有舊服務佔用連接埠，新程式會顯示錯誤，且不停止不明程序。建置工具不會自動替換已執行的服務。

存檔固定在 **EXE 旁的 `server-data/server.sqlite3`**，不依啟動時所在資料夾，也不放進單檔解壓暫存位置。更新 EXE 保留此資料夾即可；移機延續進度也要一起搬走此資料夾。只有 EXE 的全新安裝會建立獨立 `windows-preview` 全角色測試角色，沒有內嵌私人帳號、登入憑證、手機存檔或既有戰鬥進度。

本次開發機輸出至 `client-work/server/`，已另以 SQLite backup 建立現有進度的外部副本；原始 `client-work/device.sqlite3` 保留。切換到 EXE 之後的新進度寫入該外部副本，原先的 Python 服務不會自動使用它。

可選參數：

```powershell
.\CoreLichtServer.exe --check
.\CoreLichtServer.exe --database 'D:\LichtSave\server.sqlite3'
.\CoreLichtServer.exe --port 29090 --http-port 28080
```

改連接埠時客戶端也需對應調整；現有原生客戶端預設使用 18080／19090。`--check` 驗證資料並初始化空白安裝後結束，不啟動監聽。封裝版不提供來源熱重載，更新須重啟 EXE。

## 從自己的資源建置

在 Windows x64、Python 3.10 與已完成 analysis/、CDN fixtures 的環境執行。封裝選項參考 [PyInstaller 官方文件](https://pyinstaller.org/en/stable/usage.html)。

```powershell
python -m pip install -r requirements.txt -r requirements-packaging.txt
python tools/build_server_exe.py --analysis analysis --fixtures client-work/cdn-fixtures --output client-work/server --work client-work/server-build-001 --copy-database client-work/device.sqlite3
```

每次用新的空白 `--work` 目錄，避免夾帶過期資源。工具只納入明列的協定／設定與 CDN manifest 指向的檔案，初始全角色資料由設定重新建立，不從玩家存檔產生。`--copy-database` 是可選的外部存檔副本，已存在的輸出存檔不會被覆蓋。要做全新安裝則省略此參數。EXE、衍生設定、CDN 素材、建置輸出與私人存檔都不提交 Git。

## 已驗證

`tools/test_server_exe.py` 將單一 EXE 複製到新資料夾，移除 Python 的環境變數和 PATH 項目，以隱藏程序測試：全新角色、HTTP 登入、原 SNPacket 選角／75 角色、CDN fixture、實際演習勝利、重複結算及程序重啟保存。測試會使用新建存檔，不操作現有手機或 Windows 角色。

```powershell
python tools/test_server_exe.py --exe client-work/server/CoreLichtServer.exe --analysis analysis --output client-work/portable-test-001
```

本機也已用現有 Windows 客戶端連線 EXE，通過角色、檔案、語音資源檢查、換裝、編隊與重連測試。這項封裝不會增加尚未實作的原版玩法。

## 手機登入與轉接恢復

手機仍需要 ADB 的兩條 reverse 規則；無線偵錯中斷後可能消失。先啟動伺服器、確認手機已配對並連線，再執行：

```powershell
tools/connect_phone.ps1 -AdbPath '<platform-tools 資料夾>\adb.exe' -RestartGame
```

此工具只恢復 18080／19090 轉接並選擇性重啟遊戲，不清除遊戲資料。多台裝置時使用 `-Serial` 指定。開發機已在 EXE 旁另提供 `ReconnectPhone.cmd`，可雙擊恢復目前這台手機。

封裝版已修正手機初始化相容性：對已知 schema、尚未實作的請求沿用既有開發版的有界暫存行為，最多 128 筆，不回傳假的成功結果，也不因此中斷其他已實作的登入／心跳／角色請求。這不代表那些系統已完成；更換 EXE 後需要重新連線。來源版可用 `--defer-unimplemented` 獨立啟用，不需要熱重載。

封裝版會在存檔旁記錄 `http_requests.jsonl` 與 `protocol_events.jsonl`，只含路徑、欄位名稱、訊息 ID／長度，不記錄 payload 或登入憑證。手機登入失敗時先檢查這些新位置，舊開發服務的記錄不會繼續更新。

## 區網模式：不使用 ADB 轉接

可在 EXE 旁放置 `server-config.json`，啟動時自動載入：

```json
{
  "listen_host": "0.0.0.0",
  "allowed_networks": ["192.168.0.0/24"]
}
```

這個設定同時啟用 HTTP 與遊戲 TCP 的區網監聽，只接受指定網段及本機 IPv4 回環來源；其他實體網路、VPN 或外網來源仍會被應用程式拒絕。沒有此設定檔時維持本機模式。來源版也可使用 `--listen-host 0.0.0.0 --allow-network 192.168.0.0/24`。可多次指定 `--allow-network`。

目前電腦 Wi-Fi IP 為 `192.168.0.124`，手機已改用 `http://192.168.0.124:18080/`，並移除兩條 ADB reverse 規則，實測可進入 dd 主畫面。HTTP 服表／選服會根據連線實際到達的電腦 IP 回傳遊戲服務位址，不再固定回傳 127.0.0.1，也不信任客戶端 Host／轉送標頭。

手機日後只需連到相同網段並啟動遊戲，不需要開啟無線偵錯或執行 ReconnectPhone.cmd。ADB 僅用於本次一次性更改先前新增的 UrlList_Android.txt；原設定已備份，未清除應用資料。其他手機仍需先把遊戲入口指向此電腦 IP，僅連上 Wi-Fi 不會自動更改原遊戲位址。電腦 IP 改變時也需要同步更新入口；可在路由器為此電腦保留固定 IP。

本機已直接由手機連線驗證 HTTP，未新增防火牆規則。換電腦時若 Windows 防火牆阻擋，只需允許該程式的 TCP 18080／19090，來源限定自己的區網網段；不需路由器外網連接埠轉送。原生 Windows 客戶端的現有本機連線仍可用；其他電腦上的原生客戶端連線位址仍需另行調整，目前版本的預設為 127.0.0.1。
