# 待辦與狀態紀錄

## 2026-10-22

依使用者本次確認，目前已有：

- Server。
- 角色檔案。
- 角色語音。

待辦：

- [x] 排查模擬器／下載問題：BlueStacks 已可用；本次補齊遊戲 OBB、修正入口並成功載入，無需重新下載模擬器。
- [x] 測試 APK 能否在模擬器運作：核對既有安裝、啟動、載入 OBB、連接 Server、登入與進入主介面，已保留畫面及日誌證據。
- [ ] 解決戰鬥功能。狀態：尚未解決；先完成模擬器與 APK 驗證，再追查戰鬥阻塞。

執行紀錄：使用者已要求開始執行待辦，目前正在盤點模擬器、APK／OBB 與 Server 環境。

### 第一輪執行結果

- BlueStacks 5.22.285.1013（Nougat 32-bit）已安裝並能顯示 Android 桌面；已有「核芯：利希特」圖示。目前無需重新下載模擬器，遊戲內下載問題仍待實測。
- 待測 APK：`client-work/release-20261018/CoreLicht-Android-LAN.apk`，66,102,068 bytes。ZIP CRC 檢查通過，包含 `armeabi-v7a` 與 `arm64-v8a`；尚未確認模擬器已安裝版本與此 APK 相同。
- 原始 main／patch OBB 均存在，分別為 1,538,811,147 與 1,684,642,455 bytes；尚未確認模擬器內的 OBB。
- 獨立測試 Server 已啟動：HTTP `127.0.0.1:18080`、TCP `127.0.0.1:19090`，健康回覆為 `status=prototype, client_verified=false`。
- 測試資料庫由原資料庫透過 SQLite backup 複製至 `client-work/emulator-check-20261022/test.sqlite3`，不使用原進度進行測試。
- 預檢報告、Server PID、日誌與待套用的入口設定位於 `client-work/emulator-check-20261022/`。
- 當前阻塞：BlueStacks 設定 `bst.enable_adb_access="0"`；ADB 曾列出裝置，但 shell 立即回報 `error: closed`，尚不能讀取遊戲日誌或檢查／傳入 OBB。已請使用者手動開啟 ADB。
- 下一步：ADB 開啟後，核對已安裝 APK、備份既有入口設定、檢查 OBB，再設定本機 Server 連線並實測啟動／登入／主介面。APK 執行與戰鬥目前均未驗收。

開發方向調整：

- 放棄原生 Windows 使用者介面，停止沿此方向開發。
- 後續改以 Android 模擬器執行手機版客戶端，連接現有 Server。
- 本次僅記錄方向調整，未刪除既有原生 Windows 客戶端程式或同步檔案。

完成判定：戰鬥仍未完成；既有演習或關卡開放不代表原版戰鬥已還原或通過驗收。

本檔為本地新增紀錄，既有同步專案檔案維持不變。

## 最新進度（2026-10-22，本輪實測）

- [x] 確認 BlueStacks 可運作；已補齊缺少的 OBB 並修正舊 IP 入口，APK 已越過資源載入。
- [x] 核對已安裝 APK，實測啟動、OBB、本機 Server 登入與主介面成功。上方原始 APK 待辦的基本驗收已完成。
- [ ] 原版戰鬥：仍未完成。已觀察 0-1 入口及資料請求失敗；`4_27`、`15_10` 等未實作請求待追查。
- 操作、備份、驗證證據、失敗嘗試與後續工作統一記錄於 `log.md`。
