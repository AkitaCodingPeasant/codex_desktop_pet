# Desktop Pet

Desktop Pet 是一款給 Codex 使用者的 Windows 桌面夥伴。它會常駐在桌面最上層，用動畫呈現 Codex 正在思考、執行工具、等待授權或已完成工作，也會短暫顯示 Codex 的最後回覆。

![桌寵開場動畫](assets/Intro.gif)

## 主要功能

- 一眼看出 Codex 目前是思考中、工作中、等待回覆，還是已完成。
- 同時追蹤多個 Codex 工作，點一下桌寵即可展開工作清單。
- 工作完成時顯示回覆摘要與檔案變更統計。
- 可調整角色大小、動畫速度、工作清單位置與透明度。
- 所有事件只透過本機連線傳送，不需要額外的雲端服務。

## 系統需求

- Windows
- Python 3.14 以上
- [uv](https://docs.astral.sh/uv/)
- Codex（只有接收 Codex 狀態時才需要）

## 快速開始

在專案根目錄執行：

```powershell
uv sync
uv run desktop-pet
```

桌寵現在已可獨立使用。若要讓它顯示 Codex 的即時狀態，請繼續完成下一節的 Hook 設定。

> 已建立 `.venv` 時，也可以執行 `.venv\Scripts\python.exe main.py`。

## 連接 Codex

1. 啟動桌寵。
2. 在桌寵上按右鍵，選擇「設定」。
3. 切換到「Hook 設定」，按下「設定／更新 Codex Hook」。
4. 回到 Codex 輸入 `/hooks`，審閱並信任新增或更新的 Hook。

設定完成後，Codex 開始工作、執行工具、要求授權及結束回合時，桌寵會自動切換狀態。若偏好命令列，也可以執行：

```powershell
uv run python install_codex_hooks.py
```

安裝程式會保留既有 Hook；需要修改現有設定時，會先在同一目錄建立 `hooks.json.bak.desktop_pet_v2` 備份。

## 連接 Claude Code

1. 啟動桌寵。
2. 在桌寵上按右鍵，選擇「設定」。
3. 切換到「Hook 設定」，按下「設定／更新 Claude Code Hook」。
4. 重新開啟 Claude Code 工作階段，可輸入 `/hooks` 確認已載入。

Hook 會寫入 `~/.claude/settings.json`（有設定 `CLAUDE_CONFIG_DIR` 時改用該目錄），保留既有設定與 Hook；修改前會先建立 `settings.json.bak.desktop_pet` 備份。Claude Code 送出提示、執行工具、要求授權、透過 `AskUserQuestion` 提問及結束回合時，桌寵都會切換狀態。命令列可執行：

```powershell
uv run python install_codex_hooks.py --claude
```

## 連接其他工具

桌寵啟動後，可以讓其他專案的 Hook 呼叫共用的 `pet-hook` 指令。在「設定 → Hook 設定」按「將 pet-hook 加入使用者 PATH」，重新開啟要呼叫它的工具，再執行 `pet-hook` 或 `pet-hook --help` 查看使用說明。此按鈕只更新目前使用者的 PATH，不會改動其他工具的設定。

例如在工具開始工作時呼叫：

```cmd
pet-hook turn.started --title "MyTool" --subtitle "專案 123" --message "正在產生影片" --status "排程中" --session-id "mytool:project-123" --turn-id "job-456"
```

完成時沿用同一組 ID：

```cmd
pet-hook turn.completed --message "影片處理完成" --session-id "mytool:project-123" --turn-id "job-456"
```

`--title`、`--subtitle` 與 `--status` 都可省略。工作清單會顯示 `標題 > 副標題`，標題以粗體呈現；任何事件帶有 `--title` 或 `--subtitle` 都會更新該工作階段的名稱。`turn.started` 未提供 `--subtitle` 時，會改用 `--message` 當副標題；都沒有時只顯示 `Session N`。`--status` 只取代這次事件在工作清單上的預設狀態文字，例如 `思考中` 或 `調用工具中`，不改變動畫；下個事件未提供時會回到該事件的預設文字。每項新工作應使用新的 `turn-id`；同一工作階段可重複使用 `session-id`。工具開始與結束一項子工作時，分別送出 `tool.started` 與 `turn.in_progress`。失敗、取消或結束工作階段時可送出 `turn.failed`、`turn.cancelled` 或 `session.ended`。除 `session.ended` 外，每個事件都要提供兩個 ID。

不想修改 PATH，也可以在專案 Hook 設定中直接使用 `D:\codex_desktop_pet\bin\pet-hook.cmd` 的絕對路徑。桌寵若未啟動，UDP 訊息不會保留待送；指令無法確認桌寵是否已收到。

## 日常操作

| 操作 | 功能 |
| --- | --- |
| 點一下桌寵 | 顯示或收起 Codex 工作清單 |
| 按住滑鼠左鍵拖曳 | 移動桌寵 |
| 在桌寵上按右鍵 | 開啟設定、在 VS Code 開啟本專案 repo、對調工作狀態面板的水平位置、重播開機動畫或結束程式 |
| 開場動畫播放時點一下 | 跳過動畫，直接顯示桌寵 |

設定面板包含五個頁面：

- **設定**：調整角色大小、動畫速度、工作清單位置與透明度，並決定下次啟動時是否播放開場動畫。
- **Hook 測試**：不必真的執行 Codex 工作，也能預覽各種狀態與完成回覆。
- **Hook 設定**：安裝或更新 Codex 或 Claude Code Hook，並可將其他工具使用的共用 CLI 加入使用者 PATH。
- **隱藏的 Session**：查看及恢復被隱藏的工作階段。
- **呼叫紀錄**：查看本次啟動後收到的最近 200 筆 Hook 事件；關閉桌寵後會清除。

所有偏好都會自動保存。關閉設定面板不會結束桌寵；若要退出，請從右鍵選單選擇「Exit」，或在設定頁按「停止運行」。

右鍵選單的「工作狀態面板位置對調」會將工作狀態面板的水平位移 X 變成相反數，讓面板移到桌寵中心的另一側；X 以兩個視窗的中心計算。靠近螢幕邊緣時仍會自動換邊。

![桌寵Demo](assets/Demo.gif)

## 狀態說明

| 畫面狀態 | 代表意義 |
| --- | --- |
| Idle | 目前沒有進行中的工作 |
| Thinking | Codex 正在思考或準備下一步 |
| Working | Codex 正在執行工具 |
| Asking | Codex 正等待你的授權或回覆 |
| Success | 工作已完成 |
| Failed | 工作失敗 |
| Cancelled | 工作已中斷 |

完成工作時，桌寵會顯示回覆的前 100 個字，並在六秒後自動收起。若回覆內含檔案變更統計，也會一併顯示。

## 常見問題

### 桌寵有出現，但沒有跟著 Codex 切換狀態

請確認已在「Hook 設定」完成安裝，並在 Codex 的 `/hooks` 頁面信任該 Hook。你也可以先到「Hook 測試」確認桌寵本身能正常切換動畫。

### 關閉設定面板後，桌寵仍在執行

這是正常行為。設定面板只負責調整選項；請使用右鍵選單的「Exit」或設定頁的「停止運行」結束桌寵。

### 不想每次啟動都播放開場動畫

在「設定」頁關閉「啟動時播放開場動畫」。之後仍可從右鍵選單手動重播。

## 開發與維護

事件對應、動畫播放規則、專案結構與驗證方式已整理至 [內部開發文件](docs/INTERNALS.md)。
