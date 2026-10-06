# 模組介面合約（四位 agent 共同遵守）

> 本檔是 logic / data / theme / ui 四個模組之間的唯一合約。
> **簽名不可擅自更改**；若確有必要，於回報中列出新舊簽名差異。

## 專案結構

```
sudoku/
  __init__.py          # 空（或版本號）
  app.py               # main() 進入點（ui-engineer）
  logic/               # game-logic-engineer
  data/                # data-engineer
  theme/               # visual-designer
  ui/                  # ui-engineer
tests/
  test_logic_*.py / test_data_*.py / test_theme_*.py / test_ui_state.py
```

- Python 3.12、uv 管理。執行：`uv run python -m sudoku.app` 或 `uv run sudoku`。測試：`uv run pytest`。
- 相依：`customtkinter`、`platformdirs`（已安裝）。logic / data / theme 不得 import customtkinter。
- 盤面：`Board = list[list[int]]`，9×9，0 = 空格。座標 `(row, col)`，皆 0–8。
- 難度字串：`"easy" | "medium" | "hard" | "expert"`，顯示名稱：簡單 / 中等 / 困難 / 專家。

---

## 1. `sudoku.logic`（game-logic-engineer）

`sudoku/logic/__init__.py` 必須 re-export 以下名稱：

```python
DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard", "expert")

@dataclass
class Puzzle:
    puzzle: list[list[int]]          # 題目（0 = 空格）
    solution: list[list[int]]        # 唯一終盤
    difficulty: str
    seed: int | None
    technique_stats: dict[str, int]  # 例如 {"naked_single": 30, "x_wing": 1}

def generate_puzzle(difficulty: str, seed: int | None = None) -> Puzzle
    # 同 difficulty + 同 seed 必須回傳完全相同的題目。非法 difficulty → ValueError。

def solve(board: Board) -> Board | None            # 不修改輸入；無解回 None
def count_solutions(board: Board, limit: int = 2) -> int
def is_valid_placement(board: Board, row: int, col: int, value: int) -> bool
    # 不看終盤，只看行/列/宮是否衝突（忽略 (row,col) 自身）
def get_hint(board: Board, solution: Board, rng: random.Random | None = None) -> tuple[int, int, int] | None
    # 從 board 中「為 0 或與 solution 不同」的格子隨機選一格，回 (row, col, value)；全部正確回 None
def rate_difficulty(puzzle: Board) -> tuple[str, dict[str, int]]
    # 用人類技巧解題器評級，回 (difficulty, technique_stats)
def is_complete(board: Board, solution: Board) -> bool
```

## 2. `sudoku.data`（data-engineer）

`sudoku/data/__init__.py` 必須 re-export：

```python
@dataclass
class GameState:
    puzzle: list[list[int]]              # 原始題目（給定格 = 非 0）
    solution: list[list[int]]
    board: list[list[int]]               # 目前盤面（含玩家填入）
    notes: list[list[list[int]]]         # 9×9，每格為排序後的候選數字 list
    hint_cells: list[list[int]]          # 被提示填入的格子 [[r, c], ...]
    difficulty: str
    elapsed_seconds: int = 0
    mistakes: int = 0
    hints_left: int = 3
    is_daily: bool = False
    daily_date: str | None = None        # "YYYY-MM-DD"
    undo_stack: list[dict] = field(default_factory=list)   # 內容由 ui 定義，需可 JSON 序列化
    started_at: str = ""                 # ISO 時間字串

    @classmethod
    def new(cls, puzzle, solution, difficulty, is_daily=False, daily_date=None) -> "GameState"
    def to_dict(self) -> dict
    @classmethod
    def from_dict(cls, d: dict) -> "GameState"   # 欄位缺漏/型別錯 → ValueError

@dataclass
class GameRecord:
    finished_at: str        # ISO 時間
    difficulty: str
    elapsed_seconds: int
    mistakes: int
    hints_used: int
    completed: bool         # False = 放棄
    is_daily: bool

class Storage:
    def __init__(self, base_dir: Path | None = None)
        # None → platformdirs.user_data_dir("sudoku", appauthor=False)；測試時傳 tmp_path
    # --- 自動存檔 ---
    def save_game(self, state: GameState) -> None          # 原子寫入（tmp + os.replace）
    def save_timer(self, state: GameState) -> None         # 每秒呼叫，必須輕量（可節流）
    def load_game(self) -> GameState | None                # 無檔 → None；壞檔 → 備份為 .corrupt 並回 None
    def has_saved_game(self) -> bool
    def clear_game(self) -> None
    def flush(self) -> None                                # 關閉程式前強制寫出未寫入的計時
    # --- 紀錄 ---
    def add_record(self, record: GameRecord) -> None
    def query_records(self, difficulty: str | None = None, completed: bool | None = None,
                      is_daily: bool | None = None, since: str | None = None,
                      until: str | None = None) -> list[GameRecord]   # 依 finished_at 新到舊
    def get_career_stats(self) -> dict[str, dict]
        # {"easy": {"played": int, "completed": int, "best_time": int | None,
        #           "avg_time": float | None, "zero_mistake_wins": int}, ...四個難度都要有}
    # --- 每日挑戰 ---
    def mark_daily_completed(self, day: date) -> None
    def is_daily_completed(self, day: date) -> bool
    def get_streak(self, today: date | None = None) -> tuple[int, int]   # (目前連續, 最長連續)
    # --- 設定 ---
    def get_setting(self, key: str, default=None)
    def set_setting(self, key: str, value) -> None          # 例如 "theme"

def daily_seed(day: date) -> int          # 20261006 這種整數
DAILY_DIFFICULTY: str = "medium"
```

## 3. `sudoku.theme`（visual-designer）

`sudoku/theme/__init__.py` 必須 re-export：

```python
@dataclass(frozen=True)
class Theme:
    key: str                 # "light" / "warm" / "forest" / "ocean" / "dark" ...
    name: str                # 顯示名稱（繁中），例如「清新淺色」
    is_dark: bool
    # 顏色皆為 "#RRGGBB"
    bg: str; surface: str; surface_alt: str
    text: str; text_muted: str
    accent: str; accent_hover: str; accent_text: str      # 主要按鈕
    button: str; button_hover: str; button_text: str      # 次要按鈕
    button_disabled: str; button_disabled_text: str
    cell_bg: str; given_text: str; user_text: str; note_text: str
    grid_line: str           # 細格線
    box_line: str            # 宮線（粗）
    sel_bg: str              # 選取格
    peer_bg: str             # 同行/列/宮
    same_num_bg: str         # 相同數字
    error_text: str; error_bg: str
    hint_text: str; hint_bg: str
    # 尺寸
    radius: int; button_radius: int
    grid_line_width: int; box_line_width: int
    font_family: str
    font_size_cell: int; font_size_note: int; font_size_ui: int; font_size_title: int

def list_themes() -> list[Theme]          # 至少 5 個，其中至少 1 個 is_dark=True
def get_theme(key: str) -> Theme          # 未知 key → 回預設 "light"（不拋例外）
DEFAULT_THEME: str = "light"
def contrast_ratio(fg: str, bg: str) -> float   # WCAG 對比度
```

## 4. `sudoku.ui` + `sudoku/app.py`（ui-engineer）

- `sudoku/app.py`：`main()` 建立 `customtkinter.CTk` 視窗並啟動。
- 遊戲狀態變更邏輯（填數、清除、筆記、提示、undo、錯誤計數、完成判定）放在 **不依賴 tk 的** `sudoku/ui/controller.py`（`GameController`），以 pytest 測試。
- 主選單：每日挑戰（顯示連續天數）、繼續遊戲（有存檔時）、四個難度、遊玩紀錄、生涯總覽、🎨 主題。
- 所有顏色/字型/圓角從 `sudoku.theme` 取，**不寫死色碼**；主題切換後即時重繪並存到 `Storage.set_setting("theme", key)`。
