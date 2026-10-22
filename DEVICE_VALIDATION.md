# 手機實測紀錄

測試日期：2026-10-17（Asia/Taipei）。套件 `com.tw99.no23.an`，版本 `0.1.38`、versionCode 138，遊戲初始化顯示 `0.1.38.237884`。裝置為 Samsung SM-A1760、Android 16，透過使用者已配對的無線 ADB 連線。

## 已確認

1. 原客戶端卡在 CDN `config.txt` 下載，主／備網域皆回報無法解析。
2. 原手機 `res/SHASD_local.txt` 已備份，SHA-256 為 `0b64b0fb096b97d096e41dfb7b86da2b9b63a273054b7b432935de9d6e26ed51`。
3. 新增原本不存在的 `res/UrlList_Android.txt`。未修改 APK、OBB 或原始 SHASD 設定；`gameReleaseVersion` 保留 `X202308261705`。
4. 手機經 ADB reverse 存取電腦 `127.0.0.1:18080` 與 `127.0.0.1:19090`。Server 仍僅綁定電腦 loopback。
5. 真實客戶端成功要求本機 `config.txt`、`DriverVersion.txt`，並進入 SDK 登入介面。
6. 12 個啟動資源取自 main／patch OBB，大小與 MD5 均吻合客戶端產生的原始版本清單。來源見 `analysis/device/cdn_fixture_provenance.json`。
7. 使用客戶端現有 `versionCustomContent` 設定：`isRelease=false`、`server='tw_debug_888'`、`isDisabledSdk=true`，成功進入內建測試帳號介面。沒有使用或登入官方／社群帳號。
8. 真實客戶端以表單 POST `/exe/login_auth`，接受本機帳號回覆；之後成功取得 `/client/role_region_list`，實際畫面顯示 `Local test`。
9. 真實客戶端送出 `/client/select_region` 並建立到自建遊戲 TCP 服務的連線。
10. 發現每條新 TCP 連線先送未封裝的 `01 02` 前綴，之後才是長度包頭；由真實流量及 `SNTCPClient.OnConnectedCB`（RVA `0xF4458C`）交叉確認。已加入 server 及測試。
11. 原客戶端 `1_1` 登入 payload（326 bytes）已成功解碼並通過 required 欄位驗證；已回覆 `1_1`，原客戶端隨後持續送出 `1_0`，server 持續正確回覆。非敏感驗證摘要見 `analysis/device/validation.json`。
12. 原客戶端已進入新帳號開場流程。這個流程包含客戶端本地的新手引導，尚不代表角色建立或進入線上場景完成。
13. 已依真實請求補上創角前的新手戰鬥上報 `47_3`、怪物歷史查詢 `4_26`，並實測 `4_26` 回覆成功。另加入引導次數 `4_29/4_30`、視角保存 `4_31` 與連線檢查 `4_20`，目前測試共 24 項通過。

14. 真實客戶端已建立角色 dd，創角與選角往返成功，角色保存於本機 SQLite。
15. 重連已推送角色屬性與新手階段。原始等級表確認等級 1 體力 30/30、經驗上限 720、技能槽 3。
16. 新手階段 23（AfterCreateRole）推送後，手機已從黑畫面恢復到創角後劇情。這是客戶端本地劇情與新手戰鬥，尚未驗證主基地與 server 戰鬥。

## 尚未確認

- 一般關卡戰鬥、編隊、獎勵與可持續操作的核心玩法。
- 電腦 Android 模擬器重現測試。

## 啟動目前的手機測試服務

```powershell
python -m game_server --port 19090 --http-port 18080 --database client-work/device.sqlite3 --cdn-fixtures client-work/cdn-fixtures --request-log analysis/device/http_requests.jsonl --protocol-log analysis/device/protocol_events.jsonl --allow-local-client-login
```

`--allow-local-client-login` 只對免 SDK 測試設定使用。它發行獨立的本機憑證，不驗證或模擬原發行商的真實帳號。預設不開啟這些相容登入路徑。

目前背景 server 的程序編號記錄於 `analysis/device/server.pid`；標準輸出與錯誤記錄位於同目錄。HTTP 記錄只保留路徑和欄位名稱；協定記錄只保留訊息 ID 與長度。私有測試封包（如啟用擷取）放在忽略的 `client-work/`，不應作為公開測試素材。

可使用 `tools/start_device_server.ps1 -Restart` 重啟這個本機測試服務；加上 `-RestartGame` 會重啟手機遊戲。腳本只會停止記錄中且命令列符合 `-m game_server` 的程序，並以隱藏視窗啟動新服務。此開發用腳本啟用 `--reload-core`：未實作但已知 schema 的請求可暫存最多 128 筆，後續修改核心後重試，期間不偽造成功回覆。一般啟動不啟用此模式。

ADB reverse 在連線中斷或裝置重啟後可能需要重新建立。

## 還原入口

移除本次新增的單一檔案 `/sdcard/Android/data/com.tw99.no23.an/files/res/UrlList_Android.txt` 並重啟遊戲，即回到原本的封裝入口。不要刪除整個 `files/` 或 `res/` 目錄，不要清除遊戲資料。原始 APK、OBB 與 `SHASD_local.txt` 均保留。

目前成功到達本機選服、TCP 登入、創角、選角、重連與創角後劇情，尚未達成可完整遊玩的 server 驗收。

## 最新主介面驗證

新手戰鬥結束上報與進度更新已收到。主介面最初因 `selectedGameServer.name` 缺失而在 `RefreshTestInfos` 中止；補齊選服 HTTP 名稱後，重新登入已顯示 dd、等級 1、創角貨幣 200、體力 30/30 與作戰等入口。貨幣取自原始 `config.role_born_item`，以一次性 grant 保存，重連不重複發放。

已按原始 open_func 表回覆無條件與等級條件的開放功能，副本與房間條件仍保持未達成。原始 config 指定預設適格體 3008、超體 1001；這些角色、編隊與正常關卡初始化仍需實作。不可將目前空集合回覆當成完整系統。

畫面證據：`analysis/device/main-interface-verified.png`。一般關卡與模擬器驗收尚未完成。
