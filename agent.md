# 專案代理工作指引

## 基本規則

- 回答與新增文件預設使用繁體中文，不使用簡體中文。
- 讀寫 Python 與其他文字檔時明確使用 UTF-8 編碼。
- 先確認現有程式的入口、設定與事件流程，再修改相關檔案；維持既有名稱與設定鍵，避免無關的重構。
- 修改後說明實際驗證範圍；未執行的 GUI 或 hook 測試不可宣稱通過。

## 專案結構與啟動

- 專案使用 Python 3.14 以上、PySide6 與 `uv`；套件設定與命令入口位於 `pyproject.toml`。
- 從專案根目錄執行 `uv run desktop-pet`，或使用 `.venv\Scripts\python.exe main.py` 啟動桌寵。
- `main.py` 將 `src` 加入模組路徑；`src/desktop_pet/app.py` 建立 Qt 應用程式、桌寵與 hook 監聽器。
- `src/desktop_pet/desktop_pet.py` 負責動畫狀態、畫格播放、拖曳、雙擊開啟設定與右鍵退出；`settings_panel.py` 負責設定面板介面；`topmost.py` 負責 Windows 最上層視窗位置。

## 動畫與圖片

- `spritesheet_status.md` 記錄原始圖片的第 0 起算列號與各動畫格數；`spritesheet.yaml` 的 `row` 則從 1 起算。
- `src/desktop_pet/config.py` 讀取 `spritesheet.yaml`。這是專案內的簡易 YAML 解析器，修改設定格式前須確認它能解析。
- 調整圖片、格數或播放順序時，同步檢查 `spritesheet.png`、`spritesheet.yaml`、`spritesheet_status.md` 與 `desktop_pet.py` 的動畫名稱。
- Idle 隨機選擇四種片段；Thinking 循環兩段；Asking 播放 intro 後循環 repeat；Success、Failed 播放 intro 一次、repeat 三次；Cancelled 播放 intro 一次、repeat 一次，再返回 Idle。
- 多回合同時存在時，結果動畫優先於 Asking 與 Thinking；結果依收到順序完整播放，結束後才依仍在工作的回合恢復 Asking、Thinking 或 Idle。

## Codex hook

- `hook_bridge.py` 將 Codex hook 事件轉為桌寵事件，透過本機 UDP `127.0.0.1:49377` 傳送；`hook_listener.py` 在 Qt 事件迴圈中接收。
- 事件對應：`UserPromptSubmit` → `turn.started`；使用者輸入工具的 `PreToolUse` → `user_input_requested`（Asking）；一般 `PostToolUse` → `turn.in_progress`；`PermissionRequest` → `action_required`；`Stop` → `turn.completed`；`Interrupt` → `turn.cancelled`；`SessionEnd` → `session.ended`。非同步使用者輸入工具的 `PostToolUse` 不應立即取消 Asking。
- `turn.failed` 目前只有手動事件入口，不能把單次工具錯誤視為整個回合失敗。
- `codex_hooks.template.json` 是 hook 範本。`install_codex_hooks.py` 會修改使用者的 `~/.codex/hooks.json` 並備份原檔；只有在任務需要安裝 hook 時才執行。修改範本時須檢查其中的絕對路徑是否仍指向本專案。

## 驗證

- 程式碼變更至少檢查受影響模組的語法與匯入；動畫或視窗行為變更再啟動桌寵實際觀察。
- hook 變更須分開檢查事件對應與執行中桌寵的接收結果；安裝腳本的檢查不要意外改寫使用者設定。
- 若環境無法啟動 PowerShell，可改用 `cmd.exe` 執行檢查，並如實記錄阻礙。
