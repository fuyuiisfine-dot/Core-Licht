# Windows 原生客戶端預覽

這是 C#／Windows Forms 的獨立 EXE，不使用 Android 模擬器，也不執行 APK。目標為 Windows x64、.NET Framework 4.8。現階段是可連線與保存資料的原生預覽，尚未完成原遊戲的戰鬥與動畫。

## 已實作與實測

- 直接使用原 SNPacket／Protobuf 格式連接本機 server，HTTP 取得獨立本機測試憑證。
- 登入、選角、心跳、重新連線、載入 75 名適格體。
- 顯示 server 的等級、好感、屬性與造型；原始立繪由本機備份匯出。
- 150 篇檔案、3960 筆語音台詞；檔案已讀狀態保存。
- 造型切換及 8 個編隊位置保存，重連後再次讀回驗證。
- 使用獨立 windows-preview 帳號／Windows Preview 角色。準備工具複製測試資料而不修改手機 dd 的角色與憑證。

## 尚未實作

- 即時戰鬥、關卡結算與原遊戲 3D／Live2D 動畫。
- 語音音訊播放；目前可瀏覽台詞。
- 超體形態操作、商城、空島等其他完整介面。
- 原始 UI 的一比一重製、跨電腦連線、正式帳號與正式安裝程式。

## 本機建立

倉庫不含原始遊戲資源、解出的資料、EXE、私人存檔或憑證。先依根目錄說明準備自己的 analysis/ 與本機 server。Windows 內建 Framework 編譯器可用時不必安裝 .NET SDK。

```powershell
python tools/prepare_windows_client.py --backup '<自己的 OBB 資料夾>'
python tools/prepare_windows_account.py --source-role 1
native-client/build.ps1
native-client/start.ps1
```

prepare_windows_client.py 讀取原始備份，將立繪和必要文字資料輸出至被忽略的 client-work/windows-client/data。prepare_windows_account.py 先建立一致 SQLite 備份，再建立獨立角色；已存在時保留其資料，不覆蓋。

原生程式為 client-work/windows-client/CoreLicht.exe，data/ 必須放在旁邊。start.ps1 在未偵測到本機 server 時，以隱藏程序啟動既有 Python server，不需要手機或 ADB；也不會停止不明的佔用程序。客戶端本身不需要 Python，server 仍需既有 Python 環境。

## 驗證

29 項 Python 測試通過。1,048 種協定訊息的基本測試向量已由 Python 產生，再由 C# 編解碼交叉比對通過；這不是所有遊戲功能均已實作的證明。

隱藏自動驗證模式實際連線 server，確認 75 名角色、150 篇檔案、3960 筆台詞與編隊；執行換裝、編隊修改、重新登入，再確認資料保留。這只操作獨立測試角色。

```powershell
native-client/test.ps1 -Smoke
```

本機驗證輸出位於 data/smoke-result.json、data/preview.png，不提交 Git。已匯出 185 張不同立繪；兩套造型（1440070003、1410090003）的對應圖片在目前備份中缺失，介面會顯示缺圖文字。
