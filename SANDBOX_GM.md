# 本機滿等與全角色測試設定

僅套用本機 SQLite 角色 1「dd」，由使用者於 2026-10-17 明確要求。原始 APK、OBB、匯出資產均未修改。

- 帳號等級：原始 lvl 表上限 100；體力 140/140。
- 正式適格體：75 名。排除 `is_informal` 測試單位與另列的超體。
- 每名適格體依原始 children_awake 表取得最高突破及等級，依 children_sync 表取得最高同調；保留原始星數。
- 超體：1001，共 8 種形態，按 hero_lvl 表取得各形態最高等級。
- 適格體造型：233 套；超體造型另隨各形態提供。
- 好感度：依各角色 children_favor_lvl 表上限設定，不自動領取獎勵。
- `24_1` 功能開放旗標全部開啟，共 85 項。不代表對應系統、關卡通關、獎勵與戰鬥已實作；客戶端自身隱藏的入口也不因此改寫。
- 新手階段設為原始 Finished=29，避免重新進入創角流程。
- 提供全角色查詢、數量、角色造型切換與保存、超體造型查詢與切換、個人資料、每個 event 的一組持久測試編隊。

角色屬性包含原始等級基礎值、突破加值與同調修正欄位。目前不宣稱已還原完整戰鬥計算、裝備、羈絆、技能附加效果或戰力公式。

## 備份

最初套用 GM 前的一致 SQLite 備份：

`client-work/device.before-gm-1792229949783068100.sqlite3`

此檔中的 dd 仍為等級 1。之後修正好感度前的第二份備份為 `client-work/device.before-gm-1792230116070815700.sqlite3`，第二份已含 GM 設定。不要將兩份的用途混淆。備份與 DB 均位於被忽略的 client-work，不應公開憑證。

## 實測

手機重新連線後顯示 dd 等級 100、體力 140/140。適格體清單收到並顯示 75 名角色；詳情已見 110/110，清單亦已見多名等級 150。原客戶端兩次送出 `11_20` 換裝，server 成功回覆並保存。

畫面證據：`analysis/device/gm-roster-verified.png`、`analysis/device/gm-character-detail-verified.png`。

26 項測試通過，涵蓋套用前備份、重開後保存、其他角色不受影響、原始等級上限、編隊引用已擁有角色、換裝保存與拒絕未擁有造型。編隊與超體介面的完整手機操作尚未驗證。

## 工具

`tools/enable_sandbox_profile.py --database client-work/device.sqlite3 --role 1` 會先建立新的備份，再重建該角色的 GM 資料；重跑會重設這份 GM 角色／造型資料，不應當作日常啟動指令。

資料產生邏輯：`game_server/sandbox_profile.py`。依賴 analysis/config 內的 lvl、children、children_awake、children_sync、children_lvl_attr、children_skill_lvl、children_skin、children_favor_lvl、hero、hero_lvl、hero_awake；它們皆由原始 Lua 資料表解讀產生。
