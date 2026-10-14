# Desktop Pet 內部開發文件

本文件整理 Desktop Pet 的維護資訊。一般使用者若只想安裝與操作桌寵，請閱讀專案根目錄的 [README](../README.md)。

## 執行架構

`main.py` 將 `src` 加入模組搜尋路徑，實際的套件命令入口則是 `desktop_pet.app:main`。應用程式啟動後會建立 Qt 應用程式、桌寵視窗及 Hook 監聽器。

Codex Hook 由 `hook_bridge.py` 接收事件並轉換成桌寵事件，再透過本機 UDP `127.0.0.1:49377` 傳給 `hook_listener.py`。桌寵可在沒有 Hook 的情況下獨立執行。

其他工具也可以直接送出 UTF-8 JSON UDP 封包。共用格式如下：

```json
{
  "event": "turn.started",
  "title": "MyTool",
  "message": "正在產生影片",
  "status": "排程中",
  "session_id": "mytool:project-123",
  "turn_id": "job-456"
}
```

`title` 可以省略或留空；只有 `title` 與 `message` 皆有內容時，工作清單才會顯示為 `title > message`。不同工具應在 `session_id` 加入來源前綴，並讓同一回合的所有事件使用相同的 `session_id` 與 `turn_id`。

`status` 也可以省略或留空。提供時只覆蓋該事件的 Session 狀態標籤，未提供時使用 `EVENT_STATUSES` 的預設文字；動畫、完成狀態與顏色仍依事件名稱判定。

共用命令入口是 `bin/pet-hook.cmd`；不帶參數時會顯示使用說明並正常結束。它會呼叫同目錄的 `pet_hook.py`，優先使用專案 `.venv` 的 Python，否則使用 Windows `py -3`；Python 腳本只使用標準函式庫。事件參數為 `event`、`--title`、`--message`、`--status`、`--session-id` 與 `--turn-id`，其中 `session.ended` 可省略 `--turn-id`。封包以 UTF-8 編碼且不可超過 4096 bytes，對應接收端的緩衝區大小。

「Hook 設定」頁的 PATH 按鈕只在使用者點擊後更新 `HKEY_CURRENT_USER\Environment\Path`，保留原有值與型別，避免重複加入 `bin` 目錄，並通知 Windows 環境變數已變更。新啟動的工具會讀到新 PATH；已開啟的工具需重新啟動。測試這項功能時應模擬登錄檔，不要改寫真實使用者 PATH。

## Codex Hook 安裝

使用者可從設定面板的「Hook 設定」頁安裝，也可在專案根目錄執行：

```powershell
uv run python install_codex_hooks.py
```

安裝程式會使用目前的 Python 與 `hook_bridge.py` 絕對路徑，將桌寵 Hook 合併至 `~/.codex/hooks.json`；若設定了 `CODEX_HOME`，則改用該目錄。更新時會保留其他 Hook。原檔需要修改時，會先備份為同目錄下的 `hooks.json.bak.desktop_pet_v2`。

安裝後仍需由使用者在 Codex 的 `/hooks` 審閱並信任新增或更新的 Hook。修改 Hook 範本或安裝邏輯時，不要在驗證期間意外覆寫真實的使用者設定。

## 事件對應

| Codex 事件 | 桌寵事件與反應 |
| --- | --- |
| `UserPromptSubmit` | 開始回合並播放 Thinking；清理同一工作階段未正常結束的舊回合 |
| 一般工具的 `PreToolUse` / `PostToolUse` | 開始／結束工具執行並播放 Working |
| `PermissionRequest` | 播放 Asking，顯示「等待授權」 |
| `request_user_input` 或 `request_user_input_async` 的 `PreToolUse` | 播放 Asking，顯示「等待回覆」 |
| `Stop` | 播放 Success，顯示完成回覆，並結束該回合 |
| `Interrupt` | 播放 Cancelled，並結束該回合 |
| `SessionEnd` | 清理該工作階段的狀態 |

同步提問工具的 `PostToolUse` 會結束等待回覆；非同步提問工具送出後會維持 Asking，直到後續工作事件或回合結束。

Codex 目前沒有專門的回合失敗 Hook，因此單一工具錯誤不可視為整個回合失敗。若其他事件來源能確認整個回合失敗，可手動發送：

```powershell
uv run python src/desktop_pet/hook_bridge.py --event turn.failed
```

## 狀態與動畫規則

執行時會讀取 `assets/spritesheet.yaml` 與 `assets/spritesheet.png`。`spritesheet_status.md` 記錄原始素材的列號與格數；該文件的列號從 0 起算，而 YAML 的 `row` 從 1 起算。

| 狀態 | 播放方式 |
| --- | --- |
| Idle | 隨機播放四種閒置片段 |
| Thinking | 循環播放兩段動畫 |
| Working、Asking | 各播放 intro 一次，再循環 repeat |
| Success、Failed | 各播放 intro 一次、repeat 三次 |
| Cancelled | 播放 intro 一次、repeat 一次 |

Working 從每次工具開始調用起至少播放兩秒。若工具提早完成，會播放到期限後才切回 Thinking；期間開始另一項工具時，會從新工具的開始時間重新計算兩秒，動畫不中斷。完成、失敗或取消會立即播放結果動畫，不等待 Working 的期限，工作階段結束也會立即清理狀態。

多個回合同時存在時，顯示優先順序為：結果動畫、Asking、Working、Thinking。結果動畫會依接收順序完整播放，期間工作數仍會更新；全部播完後，再依剩餘回合切換狀態。同一工作階段較早回合的延遲事件不可覆蓋目前回合。

Windows 上每秒會重新確認桌寵的最上層順序，但不應搶走目前視窗的焦點。

## 完成回覆預覽

收到 `Stop` 時，`hook_bridge.py` 會將回覆轉為純文字，截取前 100 個字；只有超出長度時才附加 `...`。氣泡顯示六秒後自動收起。

若回覆含有「變更 1 個檔案 +1 -1」或「更動 1 個檔案，新增 1 行，刪除 1 行」形式的統計，桌寵會另外顯示灰色檔案數、綠色新增行數與紅色刪除行數。統計取自回覆文字，桌寵不會掃描檔案，而且即使統計出現在第 100 個字之後仍會顯示。設定面板的「Hook 測試」頁提供「變更統計測試」按鈕。

## 主要模組

- `main.py`、`src/desktop_pet/app.py`：程式入口與 Qt 應用程式生命週期。
- `src/desktop_pet/desktop_pet.py`：桌寵動畫、狀態協調與滑鼠互動。
- `src/desktop_pet/settings_panel.py`：設定、Hook 測試、Hook 設定、隱藏的 Session 與呼叫紀錄介面。呼叫紀錄由 `DesktopPet.handle_event` 收集，僅保留本次執行最近 200 筆事件，不寫入磁碟。
- `src/desktop_pet/session_panel.py`：Codex 工作清單。
- `src/desktop_pet/startup_animation.py`：開場動畫。
- `src/desktop_pet/hook_bridge.py`、`hook_listener.py`：Codex 事件轉換與 UDP 接收。
- `src/desktop_pet/hook_install.py`、`install_codex_hooks.py`：Hook 設定邏輯與命令列入口。
- `src/desktop_pet/config.py`、`assets/`：動畫設定與圖片素材。
- `src/desktop_pet/topmost.py`：Windows 最上層視窗維護。
- `tests/`：自動化測試。

## 開發與驗證

安裝開發環境：

```powershell
uv sync
```

執行自動化測試：

```powershell
uv run python -m unittest discover -s tests
```

程式碼變更至少要檢查受影響模組的語法、匯入及相關測試。動畫或視窗行為變更還需啟動桌寵實際觀察。Hook 變更應分開驗證事件對應與執行中桌寵的接收結果，且不可把單一工具失敗誤報為整個回合失敗。
