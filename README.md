# Desktop Pet

這是一個以 PySide6 製作的 Windows 桌寵。它會顯示在視窗最上層，並透過本機 Codex hook 事件播放工作、等待授權與完成等動畫。桌寵也能顯示 Codex 最後回覆的簡短預覽。

## 安裝與啟動

需要 Windows、Python 3.14 以上及 [uv](https://docs.astral.sh/uv/)。在專案根目錄執行：

```powershell
uv sync
uv run desktop-pet
```

如果已建立 `.venv`，也可執行 `.venv\Scripts\python.exe main.py`。桌寵可獨立啟動；若要接收 Codex 狀態，還需完成下方的 hook 設定。

## 操作

| 操作 | 功能 |
| --- | --- |
| 按住滑鼠左鍵拖曳 | 移動桌寵 |
| 雙擊桌寵 | 開啟設定面板 |
| 在桌寵上按右鍵 | 開啟退出選單 |

設定面板可切換「設定」、「Hook 測試」與「Hook 設定」。設定頁可即時調整角色大小（50–200%）與動畫速度（4–60 FPS），也可按「停止運行」結束程式。設定會保留到下次啟動；關閉面板只會收起面板，桌寵會繼續運行。

面板會顯示目前狀態與執行中的 Codex 工作數。工作數以桌寵啟動後收到的回合事件統計；同一回合的多次工具事件仍只算一個工作。Hook 測試頁可模擬回合開始、工具執行、等待授權、完成、失敗、中斷與工作階段結束，也可輸入測試回覆。測試事件會透過本機 UDP 傳給執行中的桌寵。

## 連接 Codex hook

桌寵在 `127.0.0.1:49377` 接收 UDP 事件。啟動桌寵後，在設定面板的「Hook 設定」頁按「設定／更新 Hook」。程式會自動使用目前的 Python 與 `hook_bridge.py` 路徑，不需要手動編輯路徑。也可以在專案根目錄執行：

```powershell
uv run python install_codex_hooks.py
```

按鈕與安裝腳本會將桌寵 Hook 合併至 `~/.codex/hooks.json`（若設定 `CODEX_HOME`，則使用該目錄）。更新時會保留其他 Hook；若原檔存在且需要修改，會先備份為同目錄下的 `hooks.json.bak.desktop_pet_v2`。安裝後，請在 Codex 的 `/hooks` 審閱並信任新增或更新的 Hook。

| Codex 事件 | 桌寵反應 |
| --- | --- |
| `UserPromptSubmit` | 開始回合，播放 Thinking；清理同一工作階段未正常結束的舊回合 |
| 一般工具的 `PreToolUse` / `PostToolUse` | 開始／結束工具執行，依仍在進行的工作切換 Working 或 Thinking |
| `PermissionRequest` | 播放 Asking，顯示「等待授權」 |
| `request_user_input` 或 `request_user_input_async` 的 `PreToolUse` | 播放 Asking，顯示「等待回覆」 |
| `Stop` / `Interrupt` | 播放 Success／Cancelled，並結束該回合 |
| `SessionEnd` | 清理該工作階段的狀態 |

同步提問工具的 `PostToolUse` 會結束等待回覆；非同步提問工具送出後會維持 Asking，直到後續工作事件或回合結束。不同回合同時工作時，狀態優先順序為結果動畫、Asking、Working、Thinking。同一工作階段較早回合的延遲事件不會覆蓋目前回合的狀態。

Codex 目前沒有專門的回合失敗 hook，因此單一工具錯誤不會觸發 Failed。若其他事件來源能確定整個回合失敗，可執行：

```powershell
uv run python src/desktop_pet/hook_bridge.py --event turn.failed
```

### 完成回覆預覽

收到 `Stop` 時，桌寵會將回覆轉為純文字，顯示前 100 字；超出時才附上 `...`。氣泡在六秒後自動收起。若回覆包含「變更 1 個檔案 +1 -1」或「更動 1 個檔案，新增 1 行，刪除 1 行」這類統計，桌寵會在回覆下方顯示灰色的「已變更 1 個檔案」、綠色的「+1」及紅色的「-1」，即使統計位於原回覆第 100 字以後也看得到。統計取自回覆文字，桌寵不掃描檔案。「Hook 測試」頁面的「變更統計測試」按鈕可直接檢查此畫面。

## 動畫與素材

執行時讀取 `assets/spritesheet.yaml` 與對應的 `assets/spritesheet.png`。`spritesheet_status.md` 記錄原始素材的列號與格數；狀態文件的列號從 0 起算，YAML 的 `row` 從 1 起算。

| 狀態 | 播放方式 |
| --- | --- |
| Idle | 隨機播放四種閒置片段 |
| Thinking | 循環播放兩段動畫 |
| Working、Asking | 各播放 intro 一次，再循環 repeat |
| Success、Failed | 各播放 intro 一次、repeat 三次 |
| Cancelled | 播放 intro 一次、repeat 一次 |

多個回合的結果動畫會依收到順序完整播放；播放期間工作數仍會更新。全部播完後，桌寵再依剩餘回合切回 Asking、Working、Thinking 或 Idle。Windows 上每秒會重新確認桌寵的最上層順序，不會因此搶走目前視窗的焦點。

## 專案結構

- `main.py`、`src/desktop_pet/app.py`：程式入口與 Qt 應用程式。
- `src/desktop_pet/desktop_pet.py`、`settings_panel.py`：桌寵動畫、互動與設定面板。
- `src/desktop_pet/hook_bridge.py`、`hook_listener.py`：Codex 事件轉換與 UDP 接收。
- `src/desktop_pet/config.py`、`assets/`：動畫設定與圖片素材。
- `src/desktop_pet/hook_install.py`、`install_codex_hooks.py`：Hook 設定邏輯與命令列入口。
- `tests/`：自動化測試。
