# Core Licht — local compatibility server

本倉庫保存伺服器原始碼、分析工具、測試與還原流程。**不包含原始遊戲資產、APK/OBB、衍生資料表、手機記錄、憑證或私人角色存檔**。完整玩法仍在開發中。

## 從自己的本機備份建立執行資料

安裝 requirements.txt 與 requirements-analysis.txt 的依賴後，在倉庫根目錄執行分析工具。原始備份保持唯讀，輸出到被 Git 忽略的 analysis/。

```powershell
python -m pip install -r requirements.txt -r requirements-analysis.txt
python tools/inspect_protocol.py --assets '<exported-assets-directory>' --output analysis
python tools/inspect_backup.py --backup '<apk-obb-backup-directory>' --output analysis
python tools/extract_xor_table.py
python tools/extract_player_attributes.py
python tools/extract_config_tables.py lvl config open_func children children_awake children_sync children_lvl_attr children_skill_lvl children_skin children_favor_lvl children_doc children_doc_char children_doc_remember children_doc_voice hero hero_lvl hero_awake --source '<exported-assets-directory>/text_assets/Zero/Lua/lua.ab'
python -m unittest discover -s tests -v
```

extract_player_attributes.py 與手機啟動輔助工具目前仍含原開發環境路徑，換電腦需先調整。手機啟動資源透過 prepare_cdn_fixtures.py 從自己的備份準備；倉庫不配送這些資源。

## 已保存的開發紀錄

# 遊戲 server 相容性還原

目標：讓備份中的 Android 遊戲在電腦模擬器執行，連到自建 server，完成登入、角色建立、進入遊戲及核心遊玩流程。

目前為**已通過手機登入、創角與選角驗證的 server 原型，尚未完成主場景與玩法驗收**。不支援原生 Windows 客戶端。原始資產、APK、OBB 與 `sources/` 保持原樣；分析使用工作區副本。

## 已完成

- 解析 62 個 Protobuf descriptor 檔、1,319 個訊息結構。
- 以受限的 Lua 資料表解讀器還原 `ProtoMap`，取得 470 個 C2S、578 個 S2C ID。
- 依客戶端 `pbs` 清單載入 57 份協定；另外 5 份未啟用的舊協定引用缺失型別，保留作分析，不混入執行期。
- 從 APK ARM64 IL2CPP 定位 `SNPacketData`、`SNBuffer`、`SNTcpProtocol`，還原收發包頭與 XOR 表。
- 實作本機帳號、Protobuf 登入、心跳、角色建立、選角確認、重連與 SQLite 保存。
- HTTP 更新入口供應 12 個驗證過的原始啟動資源；內建免 SDK 測試帳號、服表與選服已接入。
- 25 項測試通過，包含 1,048 個訊息序列化往返、連線前綴、本機 TCP、CDN 白名單、角色屬性與新手進度保存。
- 手機已完成更新、本機帳號驗證、選服、TCP 登入、心跳、角色 dd 的建立與選角；部分初始化回覆已實測。主介面已顯示，編隊與一般關卡仍未完成，詳見 `DEVICE_VALIDATION.md`。

## 啟動

使用 Python 3.10 以上與 `requirements.txt` 的依賴。在本工作區執行：

```powershell
python -m game_server --port 19090 --http-port 18080 --issue-uid local-test
```

預設使用從 APK 還原的 SNPacket 格式。服務僅綁定 `127.0.0.1`。啟動時輸出的帳號資料僅供本機測試，與原遊戲帳號無關。角色保存在工作區 `server.sqlite3`。

`GET /health` 提供原型狀態。`POST /local/login` 接受 JSON `{"uid":"local-test"}`，回傳本機驗證資料。`/client/role_region_list` 與 `/client/select_region` 須附 `uid`、`token`、`p_key`。已支援原客戶端實際使用的表單編碼；手機啟動方式與更新資源設定見 `DEVICE_VALIDATION.md`。

`tests/synthetic_frame.json` **只供通用傳輸層測試**，不是原遊戲封包設定。正常啟動勿傳入此 profile。

```powershell
python -m unittest discover -s tests -v
```

測試會在隨機本機連接埠啟動短暫服務並自動結束。本機連線若被沙箱拒絕，需在允許 loopback 的執行環境測試。

## 封包格式的靜態證據

每條新客戶端連線先送一次未封裝的 `01 02`。之後所有整數包頭採 big endian。長度為 prefix 後的 body 大小，prefix 本身為 2 bytes。

| 方向 | Body | XOR 起始索引 |
|---|---|---|
| C2S | unique:u16、section:u8、method:u8、混淆後的 PB | unique & 255 |
| S2C | section:u8、method:u8、壓縮旗標:u8、混淆後的 PB | ((section << 4) + method) & 255 |

XOR 表長度 256，逐位元組遞增並以 256 循環。Server 目前發送未壓縮回覆。接收端旗標非零會解壓縮的行為已由靜態程式碼確認，壓縮分支尚未用真實客戶端測試。

| 函式 | APK ARM64 RVA | 衍生證據 |
|---|---|---|
| SNPacketData.GenC2SPacket | `0x1585D1C` | `analysis/packet_disassembly.txt` |
| SNPacketData.ProcessS2CPacket | `0x1585EE4` | `analysis/packet_disassembly.txt` |
| SNBuffer.EndPacket | `0x1585344` | `analysis/buffer_packet.txt` |
| SNBuffer.WritePacketUInt16 | `0x1585410` | `analysis/buffer_uint16.txt` |
| SNTcpProtocol.ProcessBuffer | `0x158A10C` | `analysis/tcp_buffer.txt` |
| SNPacketData..cctor | `0x1586334` | `analysis/packet_init.txt` |

XOR 資料的 SHA-1 為 `AFDB694BFA892BC872A116B516A86C3A8C1C83EE`，與 IL2CPP 私有常數欄位名稱吻合，來源 metadata offset 為 `0x39A069`。

## 重新產生分析

```powershell
python tools/inspect_protocol.py --assets 'C:\Users\USER\Desktop\assets_images_20260927_193401' --output analysis
python tools/inspect_backup.py --backup 'D:\tool\platform-tools-latest-windows\platform-tools\game_backup' --output analysis
python tools/extract_xor_table.py
```

原始備份含 APK 與 main/patch OBB。Lua 與 PB bundle 位於 main OBB，patch OBB 沒有覆寫這兩個 bundle。APK 只有 ARM64、ARMv7 原生程式庫，因此電腦端須使用支援相應 ARM 程式的 Android 執行環境。

靜態分析工具：官方 [Il2CppDumper v6.7.46](https://github.com/Perfare/Il2CppDumper/releases/tag/v6.7.46)、Capstone 5.0.9、pyelftools 0.33。Lua 指令欄位參考 [Lua 官方 lopcodes.h](https://www.lua.org/source/5.4/lopcodes.h.html)。工具下載來源與 SHA-256 記錄於 `.dependencies/Il2CppDumper/download-source.json`。不需這些分析工具也可執行 server 與測試。

## 尚未完成

- 手機已連接並使用新增的可移除設定改接本機；模擬器尚未測試。
- CDN 啟動、免 SDK 本機帳號、遊戲 TCP 登入、心跳、創角與選角已實測，場景與玩法仍需完成。
- HTTP 服表、帳號驗證、區域清單與選服已收到真實請求；後續欄位仍需依實測補齊。
- 選角回覆之後的角色資料、背包、地圖、任務等初始化推送。`1_3` 回覆成功只代表 server 核心接受選角，**不表示遊戲已載入**。
- 戰鬥、獎勵、商城、任務等遊戲系統；未實作訊息會明確拒絕並關閉測試連線。
- 重連封包歷史補送與 `proto_num` 同步。
- 完整部署、安全強化、多人容量與長時間穩定性。

詳細執行順序與驗收標準見 `PLAN.md`。

## 滿等全角色測試模式

已依使用者要求對本機 dd 套用等級 100、75 名正式適格體各自滿等、8 種超體形態、233 套適格體造型與全部功能開放旗標。角色清單、詳情與換裝已在手機實測；系統玩法仍未全部實作。26 項測試通過。備份與限制見 `SANDBOX_GM.md`。

## 滿好感與角色檔案

75 名角色好感度 5、150 篇文字檔案及 3960 筆語音資料已補齊解鎖與已讀保存。備份工具與完整性檢查見 [DOCUMENTS.md](DOCUMENTS.md)。27 項測試通過；一般關卡玩法仍在還原。

## Windows 原生客戶端預覽

已新增不使用模擬器的 C# Windows Forms 客戶端，可實際登入、瀏覽角色與檔案、換裝、保存編隊。原生端已完成 1048 種基本訊息交叉測試與實際連線驗證，Python 測試共 29 項。戰鬥、動畫與語音播放尚未接入。建立與限制見 [native-client/README.md](native-client/README.md)。原始資源、EXE 與私人存檔不提交 Git。

介面已改為參照手機版的橫向配置，使用原始大廳背景、圖示與角色卡片素材，支援六個主要頁面、等比縮放與 F11 全螢幕。這是手機介面的首版還原，所有頁面與動畫仍需逐步補齊。
