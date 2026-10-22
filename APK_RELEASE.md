# APK 與單檔 Server 發布

發布檔案放在 GitHub Release，不將 APK、EXE 或遊戲資產直接加入 Git。

本次 APK 保留套件 `com.tw99.no23.an` 與原版本，修改內建 Unity `UrlList_Android` 文字資源為區網測試入口 `192.168.0.124:18080`，並使用既有的免 SDK 本機登入設定。其他 48 個 Unity 物件與 APK 中其他非簽章檔案逐一比對一致。

APK 已通過 zipalign 及 APK v1／v2／v3 簽章驗證；此重簽 APK 未安裝到目前手機測試，未宣稱裝置執行驗證。現有手機已另以相同連線設定完成區網登入驗證。

## 安裝與資料

- 重簽 APK 的憑證不同於原版，因此不能直接覆蓋原簽章安裝。現有手機未卸載、未清除資料、未改裝此 APK。
- APK 不包含約 3 GB 的原始 main／patch OBB；仍需使用者自己的既有 OBB，放在對應套件的 Android/obb 目錄。
- 內建伺服器 IP 是本次電腦的 192.168.0.124；不同電腦或網段需更改連線設定，或重新用工具指定 host 打包。已存在的外部 UrlList_Android.txt 可能優先於內建值。
- Server ZIP 僅含單檔 EXE、區網設定及說明，不包含玩家資料庫或憑證。新安裝自動建立 windows-preview 測試角色；如需目前進度，由使用者自行保管原有 server-data，不要公開上傳。
- 全新手機使用測試登入畫面時，可使用 windows-preview 帳號對應 Server 新建的全角色測試角色。手機版一般戰鬥仍在還原，Windows 演習擴充不代表原版關卡已可玩。

## 重建

`tools/repack_lan_apk.py` 只讀取原始備份，改寫唯一指定的 Unity 文字物件，保留其二進位容器格式，再重新封裝、對齊與簽署。需自備 UnityPy、Java 與 [uber-apk-signer](https://github.com/patrickfav/uber-apk-signer) JAR（使用其中的 Android apksigner 與 zipalign）。

```powershell
python tools/repack_lan_apk.py --source '<自己的原始 APK>' --output client-work/release/CoreLicht-Android-LAN.apk --work client-work/apk-build-001 --host 192.168.0.124 --unity-path '<UnityPy 安裝目錄>' --java '<Java bin/java.exe>' --signer '<uber-apk-signer.jar>' --private-key-dir '<私人簽署金鑰目錄>'
```

簽署工具會產生並重用私人簽章金鑰，密碼以環境變數交給 keytool／apksigner，不放在命令列或報告中。金鑰與密碼必須私下備份，後續更新 APK 需要使用同一把金鑰，不能上傳到倉庫或 Release。

`tools/publish_release.py` 僅上傳逐一明列的檔案，透過 Git 已設定的 GitHub credential helper 在記憶體取得授權，不輸出或保存憑證；既有不同內容的 Release 資產不會被覆蓋。上傳後核對 GitHub 回報的大小與 SHA-256（若可用）。
