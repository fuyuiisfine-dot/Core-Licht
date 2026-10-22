# 工作紀錄

## 2026-10-22：模擬器 APK 驗證

### 範圍
- 使用 BlueStacks 執行手機 APK；停止原生 Windows UI 開發。
- 原始備份與同步專案檔案保持不變；測試產物放在 `client-work/emulator-check-20261022/`。

### 已執行
1. 更新 `TODO_LOG.md`，新增 APK 安裝、啟動、OBB、Server、登入與主介面驗證。
2. 確認 BlueStacks 5.22.285.1013 Nougat32 已運作，已安裝遊戲。
3. APK ZIP CRC 檢查通過，含 ARM 32／64 位元程式庫。
4. 以 SQLite backup 複製原資料庫至獨立 `test.sqlite3`；啟動 loopback HTTP 18080／TCP 19090 Server，健康回覆正常，仍屬 prototype。
5. 初次 ADB shell 回報 `error: closed`；使用者手動開啟 ADB 後，已可讀取模擬器。遠端 ADB 保持關閉。
6. 核對已安裝 APK SHA-256：`ff4c2b44af175d7cd5fde99a93a552046535ea8f819d85d0cc016a9f0a4b7ca5`，與待測 APK 相同。
7. 發現 `/sdcard/Android/obb/com.tw99.no23.an` 為空；可用空間約 116 GB。
8. 備份既有入口至 `UrlList.before.txt`；其位址為舊區網 IP `192.168.0.124:18080`。保留本機測試登入設定。

### 正在處理
- 補入使用者原始 main／patch OBB，設定 ADB reverse 與本機入口，再實測 APK。
- 尚未宣稱 APK 主介面或原版戰鬥驗收成功。

### 傳輸與連線準備
- 已套用保留原 `versionCustomContent` 的入口副本，僅將 `192.168.0.124` 改為 `127.0.0.1`。
- main OBB 傳輸進行中，已確認檔案大小持續增加。
- 初次 ADB reverse 失敗：`more than one device/emulator`。同一 BlueStacks 同時列為 `127.0.0.1:5555` 和 `emulator-5554`，待傳輸完成再處理重複連線。
- 另核對 Server 的 12 個啟動資源，全部存在且 MD5 與 DriverVersion 清單相符；報告為 `fixture-check.json`。
- main OBB 已傳輸完成（1,538,811,147 bytes），patch OBB 傳輸中。
- 已斷開重複的 `127.0.0.1:5555` 連線，保留 `emulator-5554`；HTTP 18080 與 TCP 19090 的 ADB reverse 均已成功建立並列出。

### APK 實測結果
- main 與 patch OBB 傳輸完成，裝置與原始備份 MD5 分別一致：`1c788db1aaa77ec6f79fcb5c301bba1f`、`399c5021e654f067cffaf1c4d21598ae`。
- 重新啟動 APK 後，實際請求本機 `config.txt`、`DriverVersion.txt`，出現帳號輸入畫面；遊戲版本為 `0.1.38.237884`。
- 使用 `windows-preview` 測試帳號。第一次輸入因返回鍵取消，改用 Enter 完成輸入後成功。
- 實際收到 `/exe/login_auth`、`/client/role_region_list` 及遊戲協定流量，持續有 `1_0` 心跳往返。
- 內建保密協議的初次勾選被自動安全審查拒絕，未繞過；使用者明確授權「授權同意並繼續測試」後繼續。其後觀察到已進入主介面。
- 主介面顯示 `Windows Preview`、角色 ID 2、等級 100、伺服器 `Local test`。證據：`main-interface.png`。帳號沿用既有名稱，畫面是 Android APK，不是原生 Windows UI。
- APK 啟動、OBB 載入、本機登入及主介面：本輪通過。遊戲內操作、重啟保存、戰鬥完成與結算不在本輪通過範圍。

### 戰鬥排查結果與待辦
- 觀察到 0-1「因善之罪」與「戰鬥開始」畫面：`battle-entry.png`。
- 後續畫面為角色列表，出現「網路連線不暢，請求超體數據失敗」：`battle-start.png`。尚未觀察到戰鬥正式開始。
- Server 暫存未實作請求 `4_27`（`nf_agent_can_use_c2s`）及 `15_10`（`cost_cancel_assistant_c2s`），不能把這些請求直接回覆成功視為修復。
- 已核對 schema：`4_27` 回覆需 `map_id`、`have_agent`；`15_10` 回覆需 `result`、`event_id`。需追查客戶端呼叫與角色／隊伍狀態後實作，兩者尚未證明是唯一阻塞原因。
- 另有登入初始化未實作請求，完整證據見 `protocol_events.jsonl`。本次未改動同步 Server 原始碼。
- 後續：在可編輯的開發副本追查並補齊真實手機協定，再重測編隊、入場、戰鬥與結算。

### 本次結束時環境
- 測試 Server 保持運作，PID 存在 `client-work/emulator-check-20261022/server.pid`；使用隔離資料庫。
- BlueStacks 保留兩個 OBB 與本機入口；原入口備份為 `UrlList.before.txt`。
- 重開模擬器後可能需重新建立 ADB reverse；不要因此清除遊戲資料。

## 2026-10-22：角色資產、章節、瞳型態與陣營版面

- 使用者確認「鋼鐵機關／星辰製藥」是陣營卡片位置重疊，並非角色資料相同。
- 從原始 Lua 資產唯讀抽出 `char_relationship` 等配置，放在 `client-work/emulator-check-20261022/config/`。
- 十三人會議共 14 個圖鑑條目；目前缺少維穆爾（3011，非正式角色旗標為 1）與意識體・希爾（10005，NPC，條件為關卡 20005）。
- 維穆爾的 A03011 模型、動畫、貼圖、Spine 資產位於 main OBB；希爾的 `card_1000501` 立繪與 `headicon_10006` 頭像位於 patch OBB。清單：`client-work/unlock-audit-20261022/character-assets.json`。存在資產不等於完整可戰鬥角色，本次沒有擅自將非正式角色發放為可用卡片。
- 已備份角色 2 所在測試資料庫，開放 190 個非測試關卡，章節集合為 0–8、106、1001、2001–2003。以 access 記錄與客戶端需要的開放快照實現，沒有新增已賺取的通關記錄或發獎。
- 瞳 8 個型態原本已在資料庫；發現英雄 type 錯用 7，已按原客戶端 `HeroType.Common=0` 修正為 0。
- 原客戶端另有 `HeroDefine.FormLockList[3]=true`，會隱藏支援型態。已建立獨立 main OBB 副本，僅移除這一個 Lua 表賦值；沙箱執行驗證其餘 HeroDefine 值相同，其他 Unity 物件原始資料雜湊相同。正在傳至測試模擬器；原始備份不變。
- Lua 驗證首次斷言因空表被轉成 Python 空串列而失敗，修正斷言後通過；失敗版本未部署。

## 2026-10-22：內網與 Tailscale 連線條件確認

- 讀取目前測試啟動紀錄，Server 綁定 `127.0.0.1:19090`，HTTP 為 `18080`；BlueStacks 使用 ADB reverse，尚未驗證其他裝置直連。
- 原始啟動程式支援 `--listen-host` 與可重複指定的 `--allow-network`。改用內網／Tailscale 時需設定可達的監聽 IP、允許的用戶端 IPv4 網段，以及兩個 TCP 連接埠的防火牆／網路存取權限。
- APK 的入口亦須改為 Server 的內網／Tailscale IP；本次僅確認條件，尚未變更監聽設定、防火牆或 Tailscale 設定。

### 使用者提供 100.73.138.15 後的設定

- 已確認 100.73.138.15 屬於本機 Tailscale 介面；停止已核對命令列的測試程序 110336，使用相同資料庫重啟為 PID 102760。
- 新服務僅監聽 100.73.138.15 的 TCP 18080／19090，允許來源 100.64.0.0/10；本機 /health 成功回傳 prototype，兩埠監聽已確認。
- 建立 client-work/mobile-dev/start-tailscale.ps1 與新版 UrlList_Android.txt；備份 BlueStacks 原入口為 UrlList.before-tailscale.txt，再推送新版入口。
- 新增防火牆規則被 Windows 拒絕存取，未完成規則新增；提供需系統管理員執行的 allow-tailscale-firewall.ps1，規則只允許 Tailscale 位址與上述兩埠。
- 建立根目錄 TAILSCALE.md 操作與驗證說明。尚未驗證手機跨裝置連線或修改 APK 安裝包內的預設入口。
