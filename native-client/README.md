# Windows 原生客戶端預覽

這是 C#／Windows Forms 的獨立 EXE，不使用 Android 模擬器，也不執行 APK。目標為 Windows x64、.NET Framework 4.8。現階段是可連線與保存資料的原生預覽，尚未完成原遊戲的戰鬥與動畫。

## 已實作與實測

- 直接使用原 SNPacket／Protobuf 格式連接本機 server，HTTP 取得獨立本機測試憑證。
- 登入、選角、心跳、重新連線、載入 75 名適格體。
- 顯示 server 的等級、好感、屬性與造型；原始立繪由本機備份匯出。
- 150 篇檔案、3960 筆語音台詞；檔案已讀狀態保存。
- 造型切換及 8 個編隊位置保存，重連後再次讀回驗證。
- 以手機 2340×1080 畫面配置重做主頁、七欄角色卡片、屬性、檔案、時裝與編隊頁。使用原始大廳背景、圖示、按鈕與卡片裁圖，視窗縮放時等比留邊。
- 滑鼠點擊導覽與角色卡片、滾輪瀏覽角色／檔案、F11 全螢幕、Esc 返回。時裝選擇可先預覽，再按「穿戴」保存。
- 使用獨立 windows-preview 帳號／Windows Preview 角色。準備工具複製測試資料而不修改手機 dd 的角色與憑證。
- 作戰演習：三個關卡、編隊、格子部署、移動與攻擊、血量、勝敗、星級、精神力消耗、一次性結算與逐關解鎖。
- 由 server 固定步長計算戰鬥，關閉客戶端後重連可讀回戰局／結算；不是客戶端自報勝利。

演習使用原角色生命／攻擊／防禦與關卡名稱／消耗。敵人、AI、射程、移速、波次、解鎖順序與演習點數為獨立原型規則，不代表原版戰鬥已還原，也不寫入原版通關紀錄。詳見 [GAMEPLAY.md](../GAMEPLAY.md)。

## 尚未實作

- 原版戰鬥觸發、技能、敵人／波次、掉落、任務與原遊戲 3D／Live2D 動畫；目前僅有獨立演習戰鬥。
- 語音音訊播放；目前可瀏覽台詞。
- 超體形態操作、商城、空島等其他完整介面。
- 所有頁面與細節的一比一重製：目前為手機版風格的首版還原，部分構圖、字體、頁面仍有差異。
- 跨電腦連線、正式帳號與正式安裝程式。

## 本機建立

倉庫不含原始遊戲資源、解出的資料、EXE、私人存檔或憑證。先依根目錄說明準備自己的 analysis/ 與本機 server。Windows 內建 Framework 編譯器可用時不必安裝 .NET SDK。

```powershell
python tools/prepare_windows_client.py --backup '<自己的 OBB 資料夾>'
python tools/extract_config_tables.py children_fightjob dungeon
python tools/prepare_mobile_ui.py '<自己的 OBB 資料夾>' client-work/windows-client/data/ui
python tools/prepare_windows_account.py --source-role 1
native-client/build.ps1
native-client/start.ps1
```

prepare_windows_client.py 讀取原始備份，將立繪和必要文字資料輸出至被忽略的 client-work/windows-client/data。prepare_windows_account.py 先建立一致 SQLite 備份，再建立獨立角色；已存在時保留其資料，不覆蓋。

prepare_mobile_ui.py 另將 UI 與角色卡片素材匯出至 data/ui，記錄來源 bundle 與雜湊；它還會從 analysis/config 讀取 children 與 children_fightjob。所有遊戲美術與匯出資料只留在私人輸出目錄，不加入 Git。

原生程式為 client-work/windows-client/CoreLicht.exe，data/ 必須放在旁邊。start.ps1 在未偵測到本機 server 時，以隱藏程序啟動既有 Python server，不需要手機或 ADB；也不會停止不明的佔用程序。客戶端本身不需要 Python，server 仍需既有 Python 環境。

## 驗證

39 項 Python 測試通過。1,048 種協定訊息的基本測試向量已由 Python 產生，再由 C# 編解碼交叉比對通過；這不是所有遊戲功能均已實作的證明。

隱藏自動驗證模式實際連線 server，確認 75 名角色、150 篇檔案、3960 筆台詞與編隊；執行換裝、編隊修改、重新登入，再確認資料保留。另驗證主頁→角色→屬性→檔案／時裝與編隊選人等點擊路徑，以及提示視窗不會穿透點擊。這只操作獨立測試角色。

```powershell
native-client/test.ps1 -Smoke
native-client/test.ps1 -GameSmoke
```

本機驗證輸出位於 data/smoke-result.json、data/preview.png 以及六頁 data/preview-*.png，不提交 Git。已匯出 185 張不同立繪；兩套造型（1440070003、1410090003）的對應圖片在目前備份中缺失，介面會顯示缺圖文字。

GameSmoke 實際進入演習、部署三名隊員、等待 server 判定勝利，重複請求結算確認僅加一次點數，再登入讀回保存結果。它會使用測試角色的精神力並保存演習進度；輸出 data/gameplay-smoke-result.json、preview-stages*.png、preview-battle.png、preview-result.png。既有 server 程序在更新 bootstrap.py 後需重啟。
