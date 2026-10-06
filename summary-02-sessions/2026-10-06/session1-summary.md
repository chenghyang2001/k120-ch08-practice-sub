# Session 1 Summary — 四 agent 協作開發數獨桌面遊戲

- 日期：2026-10-06
- 機器：DESKTOP-6LST1BR
- Repo：<https://github.com/chenghyang2001/k120-ch08-practice-sub>（commit `fb1bf18`）

## 完成事項

### Agent 定義

- 在專案層 `.claude/agents/` 建立四個 subagent（不放全域）：`game-logic-engineer`、`ui-engineer`、`data-engineer`、`visual-designer`，各自定義職責、模組邊界（`sudoku/logic|ui|data|theme`）與品質要求。

### 專案骨架與合約（主 Claude）

- `uv init` 建 Python 3.12 專案，改為平面套件結構（`[tool.uv.build-backend] module-root = ""`），入口 `sudoku = "sudoku.app:main"`。
- 相依：customtkinter 6、platformdirs；dev：pytest、pillow。
- 撰寫 `docs/interfaces.md` 介面合約，讓 logic / data / theme 三模組可並行開發。

### 四 agent 協作（3 phase）

- Phase 1 並行：logic（75 測試）、data（65 測試）、theme（157 測試）。
- Phase 2：ui-engineer 串接三模組，controller 30 測試、實際啟動截 10 張圖並修 4 個排版問題。
- Phase 3：code-qa 五層驗證 OVERALL PASS — 全專案 326 pytest 通過 + 54 個獨立案例 + PRD 16 項逐項對照全 OK。
- 依使用者選擇：UI 框架用 CustomTkinter；只做 QA、不派 code-reviewer。
- 四個角色皆由 general-purpose 讀取對應 `.claude/agents/<name>.md` 扮演（同 session 新建的專案 agent 尚未註冊，`subagent_type` 呼叫回報 not found）。
- 以 `gh repo create --public` 新建公開 repo `chenghyang2001/k120-ch08-practice-sub`，commit `fb1bf18` 已 push。

## 關鍵技術筆記

- 生成器：MRV + bitmask 回溯；medium/hard/expert 採「挖到最深再逐格補回、每補一格重新評級」，命中率高一個數量級。重試以次數而非時間控制 → 同 seed 跨機器同題。實測最慢 0.66 秒。
- 難度 = max(技巧等級, 挖空等級)；技巧解不完（需猜測）一律評 expert；`technique_stats` 含 `"unsolved"` 鍵。
- 存檔：mkstemp → fsync → os.replace 原子寫入；`save_timer` 節流 5 秒、`flush()` 於關窗補寫；壞檔改名 `.corrupt` 回 None。
- **完成一局後須先 `clear_game()`，之後不可再呼叫 `save_timer`**，否則存檔會被寫回（controller 已處理）。
- UI 設計取捨：undo 不退還錯誤／提示次數；提示格鎖定不可改；每日挑戰已完成時按鈕停用。
- 題目生成在背景執行緒，以 `after` 輪詢回主執行緒（tk 不可跨執行緒）。
- 視窗高度依螢幕自動縮放（1080p + 150% 縮放下 780 高會超出螢幕）。

## 產出檔案

| 路徑 | 說明 |
| --- | --- |
| `.claude/agents/*.md`（4 檔） | 四位專案 subagent 定義 |
| `docs/interfaces.md` | 模組介面合約 |
| `sudoku/logic/`（6 檔） | 生成、解題、技巧、難度、提示 |
| `sudoku/data/`（4 檔） | GameState / GameRecord、Storage、每日挑戰 |
| `sudoku/theme/`（3 檔） | Theme dataclass、6 套色盤、對比度 |
| `sudoku/ui/`（9 檔）+ `sudoku/app.py` | CustomTkinter 介面與 GameController |
| `tests/`（11 檔） | 326 項 pytest |
| `docs/theme_preview.py/.png`、`docs/ui_screenshot.py`、`docs/screenshots/*.png`（10 張） | 視覺驗證 |
| `README.md`、`pyproject.toml`、`uv.lock`、`.gitignore` | 專案設定與說明 |

## HANDOFF（下次 session 優先處理）

### 立即行動

- [ ] 重開 session 後用 `/agents` 確認四個專案 agent 已註冊，之後可直接以 `subagent_type` 呼叫
- [ ] 實際手動玩一局（`uv run sudoku`），確認滑鼠點擊與真實鍵盤體驗（QA 只以程式模擬事件測試）
- [ ] 視需要補派 code-reviewer 做 adversarial review（本次依使用者選擇略過）

### 進行中（需接續）

- 無未完成工作；PRD 16 項功能皆已實作並通過 QA，已 push 至 GitHub。

### 注意事項

- 本 session 新建的專案 agent 當下未註冊，改由 general-purpose 讀 `.claude/agents/<name>.md` 扮演角色。
- ruff 剩 20 條風格警告（DTZ 時區、TRY004），屬刻意保留：每日挑戰以本機日期計算、合約規定拋 ValueError；專案尚無 `[tool.ruff]` 設定。
- `app.destroy()` 後 stderr 有 customtkinter after 回呼噪音，不影響功能。
- 專案用 uv 管理，執行 Python 前加 `PYTHONUTF8=1`。
