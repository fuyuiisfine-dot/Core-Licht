# Windows 原生安裝包

Release 的 `CoreLicht-Windows-Setup.exe` 適用 Windows 10/11 x64、.NET Framework 4.8。以目前使用者安裝到 `%LOCALAPPDATA%\Programs\CoreLicht`，建立開始功能表捷徑與解除安裝項目。預留至少 4 GB 空間。

安裝後啟動「Core Licht」。啟動器會先檢查本機相容 Server；尚未啟動時，使用隨附 EXE 在背景啟動。不需要 Python 或 Android 模擬器。預設帳號 `windows-preview`。

新存檔在 `%LOCALAPPDATA%\CoreLicht\server-data\server.sqlite3`，與程式安裝位置分開。沿用已啟動的 Server 時則使用該服務的存檔。更新前關閉客戶端與對應 Server，備份存檔目錄，再執行新版安裝程式。解除安裝保留存檔。

目前客戶端連接本機 HTTP 18080／TCP 19090；手機的區網服務仍使用同一套 Server 程式，手機部署請下載 Server LAN ZIP。Windows 套件中的 Server 預設僅供本機連線。

包含 75 名角色相關資料、185 張立繪、介面素材與 3,905 段語音，不含私人 DB、測試畫面、記錄、簽署私鑰或原始 APK／OBB。完整原版戰鬥與 3D 動畫尚未還原；可玩的演習使用獨立原型規則。

## 建置

先依 `native-client/README.md` 準備客戶端資料、建置客戶端，並依 `SERVER_EXE.md` 建置 Server。從官方 NSIS 下載可攜版編譯器（本次使用 3.13），執行：

```powershell
.\tools\build_windows_installer.ps1 -ClientDirectory '<windows-client>' -ServerExecutable '<CoreLichtServer.exe>' -NsisCompiler '<NSIS>\makensis.exe' -OutputDirectory '<release-output>'
```

輸出安裝包、使用說明與 SHA-256 校驗檔。`native-client/installer.nsi` 管理安裝內容，`Launcher.cs` 管理本機 Server 啟動與使用者存檔位置。沒有把二進位資產加入 Git。

## 驗證

可用 `/S /TESTMODE /D=<隔離測試資料夾>` 靜默安裝；`/D` 必須最後且不加引號。TESTMODE 不建立捷徑或解除安裝登錄。將安裝後各檔案與輸入逐一比較 SHA-256，執行 `CoreLichtLauncher.exe --check` 檢查服務，再用 `CoreLicht.exe --smoke-test` 驗證登入、角色、語音、編隊、造型與重連。檢查 `data/smoke-result.json` 的 success。測試會更新測試角色造型／編隊，不應拿正式帳號做驗收。

發佈工具以串流上傳大檔；既有同名資產只有 SHA-256 相同才跳過，內容不同不覆寫。使用 `--update-notes` 明確更新 Release 說明。

2026-10-18 安裝驗證：5,256 個封裝輸入逐檔 SHA-256 一致，含 3,905 段 WAV；已安裝的客戶端通過 75 名角色、150 篇檔案、語音音訊、造型／編隊保存及重連測試。空白 Server 初始化為一個測試角色。安裝包未包含私人 DB。完整原版戰鬥不在本次驗證範圍。
