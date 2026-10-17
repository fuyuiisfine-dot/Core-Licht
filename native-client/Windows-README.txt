Core Licht Windows 原生預覽版

適用 Windows 10/11 x64，使用 Windows 內建 .NET Framework 4.8，不需要 Android 模擬器或 Python。
執行 CoreLicht-Windows-Setup.exe，以目前使用者安裝；請保留至少 4 GB 可用空間。
安裝後從開始功能表開啟 Core Licht。啟動器會連接本機的相容 Server；若尚未執行，會在背景啟動隨附 Server。
預設測試帳號：windows-preview。已執行的 Server 會沿用其帳號與進度。
本機服務使用 127.0.0.1 的 18080、19090 連接埠；與手機使用的區網 Server 為相同服務程式。

新建存檔位置：%LOCALAPPDATA%\CoreLicht\server-data\server.sqlite3
升級前請關閉原生客戶端與由此安裝包啟動的 CoreLichtServer.exe，備份上述目錄，再執行新版安裝程式。
解除安裝會保留該存檔目錄。關閉遊戲視窗後，Server 仍在背景執行；需要結束時可從工作管理員關閉 CoreLichtServer.exe。
若啟動器沿用先前已執行的 Server，存檔位置由該 Server 決定。

內容包含角色立繪、手機風格介面、角色檔案與 3,905 段語音，以及單檔 Server；不含私人帳號資料庫或簽署金鑰。
目前可測試登入、角色／好感檔案、語音、造型、編隊與演習原型。原手機版的完整戰鬥、3D 與技能邏輯仍在還原。
這是未簽署的開發預覽版；安裝前可使用 SHA256SUMS-Windows-Native.txt 校驗下載完整性。
