# Windows 劇情回顧與第一關驗證

Windows 主頁右側新增「劇情回顧」。章節列表與逐句對話取自使用者自己的遊戲備份，放在私人 `client-work/windows-client/data/story.json`；倉庫只保存匯出工具和閱讀介面，不包含劇情資料。已讀狀態由本機伺服器的 `26_4` 劇情紀錄讀取。回顧可閱讀現有文字，沒有重播原版過場動畫、配音或選項。

目前匯出圖鑑章節的 76 個條目，以及其餘 135 段帶對話的正式劇情腳本，共 8,845 句。另有 34 個圖鑑條目在這份備份中沒有對話腳本，畫面會標示「無對話」。標題明確為「測試」或「示例」的內部腳本不列入回顧。

## 資料與流程

1. `tools/prepare_story_replay.py` 從個人備份的 Lua 設定與劇情腳本整理章節、場景、說話者和對話；未列於圖鑑的正式對話列在「其他劇情」，輸出 `story.json`。
2. `native-client/StoryReplay.cs` 載入私人資料，提供章節切換、場景列表、逐句閱讀與已讀提示。
3. `native-client/Client.cs` 登入後向本機伺服器讀取劇情已讀紀錄。`native-client/MobileView.cs` 提供主頁入口與返回操作。
4. `native-client/test-first-stage.ps1` 複製測試資料庫，在 18081／19091 啟動隔離服務，透過實際 Windows 畫面完成劇情閱讀及第一關演習、獎勵與重新登入驗證。正式手機服務的 18080／19090 不會被此測試佔用。

## 本次修改點

- `tools/prepare_story_replay.py`：原始劇情文字匯出。
- `native-client/StoryReplay.cs`、`MobileView.cs`、`Client.cs`：入口、閱讀畫面與已讀紀錄。
- `native-client/Protocol.cs`：測試時可指定服務連接埠；預設連接埠維持 18080／19090。
- `native-client/Gameplay.cs`、`test-first-stage.ps1`：完整介面驗證。
- `native-client/build.ps1`、`CoreLicht.csproj`：編入新畫面。
- `tools/start_device_server.ps1`：依此工作區的私人資料路徑啟動手機測試服務，接受 192.168.0.0/24 的區網連線。

## 驗證

在 `repository` 執行 `native-client/test-first-stage.ps1`。成功時會輸出 `story_replay_verified`、`first_stage_cleared`、`reward_once` 與 `reconnect_verified`。截圖在回報的私人 `first-stage-check-*` 目錄。測試的第一關是本機伺服器計算的獨立演習；原版手機戰鬥尚須另行依手機協定實測與實作。

完成測試後，執行 `native-client/build.ps1 -OutputDirectory '..\client-work\windows-client'` 更新私人 Windows 程式。劇情資料需放在 EXE 旁的 `data/story.json`。
