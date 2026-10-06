"""資料模型：進行中遊戲狀態（GameState）與遊玩紀錄（GameRecord）。

設計重點：
- 兩者都能與 JSON 相容的 dict 互轉，`from_dict` 會嚴格驗證欄位與型別，
  任何缺漏或型別錯誤一律拋 ValueError，讓 Storage 可以據此判定壞檔並降級。
- 本模組刻意不 import sudoku.logic，難度字串在此自行定義（與合約一致）。
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

# 與 sudoku.logic.DIFFICULTIES 相同；為避免模組間耦合，此處獨立定義
DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard", "expert")
GRID_SIZE = 9
DEFAULT_HINTS = 3


# ---------------------------------------------------------------------------
# 驗證輔助函式（失敗一律拋 ValueError，訊息指出欄位名稱方便除錯）
# ---------------------------------------------------------------------------
def _is_int(value: Any) -> bool:
    """bool 是 int 的子類別，這裡要排除，避免 True 被當成 1 混進數值欄位。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _require_int(name: str, value: Any, minimum: int | None = None) -> int:
    if not _is_int(value):
        raise ValueError(f"欄位 {name} 必須是整數，實際為 {type(value).__name__}")
    if minimum is not None and value < minimum:
        raise ValueError(f"欄位 {name} 不可小於 {minimum}，實際為 {value}")
    return value


def _require_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"欄位 {name} 必須是布林值，實際為 {type(value).__name__}")
    return value


def _require_str(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"欄位 {name} 必須是字串，實際為 {type(value).__name__}")
    return value


def _require_difficulty(value: Any) -> str:
    _require_str("difficulty", value)
    if value not in DIFFICULTIES:
        raise ValueError(f"未知難度：{value!r}，可用值為 {DIFFICULTIES}")
    return value


def _require_grid(name: str, value: Any, allow_zero: bool = True) -> list[list[int]]:
    """驗證 9×9 整數盤面，值域 0–9（allow_zero=False 時為 1–9）。"""
    low = 0 if allow_zero else 1
    if not isinstance(value, list) or len(value) != GRID_SIZE:
        raise ValueError(f"欄位 {name} 必須是 9×9 盤面")
    for row in value:
        if not isinstance(row, list) or len(row) != GRID_SIZE:
            raise ValueError(f"欄位 {name} 必須是 9×9 盤面")
        for cell in row:
            if not _is_int(cell) or not low <= cell <= 9:
                raise ValueError(f"欄位 {name} 含非法數值：{cell!r}")
    return [list(row) for row in value]


def _require_notes(value: Any) -> list[list[list[int]]]:
    """驗證 9×9 筆記，每格為 1–9 的候選數字 list；回傳時排序並去重。"""
    if not isinstance(value, list) or len(value) != GRID_SIZE:
        raise ValueError("欄位 notes 必須是 9×9 結構")
    result: list[list[list[int]]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != GRID_SIZE:
            raise ValueError("欄位 notes 必須是 9×9 結構")
        new_row = []
        for cell in row:
            if not isinstance(cell, list):
                raise ValueError("欄位 notes 每格必須是 list")
            for digit in cell:
                if not _is_int(digit) or not 1 <= digit <= 9:
                    raise ValueError(f"欄位 notes 含非法候選數字：{digit!r}")
            new_row.append(sorted(set(cell)))
        result.append(new_row)
    return result


def _require_cells(value: Any) -> list[list[int]]:
    """驗證 [[r, c], ...] 座標清單。"""
    if not isinstance(value, list):
        raise ValueError("欄位 hint_cells 必須是 list")
    cells = []
    for item in value:
        if (
            not isinstance(item, list | tuple)
            or len(item) != 2
            or not all(_is_int(v) and 0 <= v < GRID_SIZE for v in item)
        ):
            raise ValueError(f"欄位 hint_cells 含非法座標：{item!r}")
        cells.append([item[0], item[1]])
    return cells


def _require_iso_date_or_none(name: str, value: Any) -> str | None:
    if value is None:
        return None
    _require_str(name, value)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"欄位 {name} 不是合法日期（YYYY-MM-DD）：{value!r}") from exc
    return value


def _require_iso_datetime(name: str, value: Any, allow_empty: bool = False) -> str:
    _require_str(name, value)
    if allow_empty and value == "":
        return value
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"欄位 {name} 不是合法 ISO 時間：{value!r}") from exc
    return value


def _require_keys(d: Any, keys: tuple[str, ...], kind: str) -> None:
    if not isinstance(d, dict):
        raise ValueError(f"{kind} 資料必須是 dict，實際為 {type(d).__name__}")
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"{kind} 缺少欄位：{missing}")


def now_iso() -> str:
    """回傳本機目前時間的 ISO 字串（秒精度）。"""
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------
_STATE_REQUIRED = ("puzzle", "solution", "board", "notes", "hint_cells", "difficulty")


@dataclass
class GameState:
    """進行中遊戲的完整狀態，可序列化為 JSON 存檔。"""

    puzzle: list[list[int]]
    solution: list[list[int]]
    board: list[list[int]]
    notes: list[list[list[int]]]
    hint_cells: list[list[int]]
    difficulty: str
    elapsed_seconds: int = 0
    mistakes: int = 0
    hints_left: int = DEFAULT_HINTS
    is_daily: bool = False
    daily_date: str | None = None
    undo_stack: list[dict] = field(default_factory=list)
    started_at: str = ""

    @classmethod
    def new(
        cls,
        puzzle: list[list[int]],
        solution: list[list[int]],
        difficulty: str,
        is_daily: bool = False,
        daily_date: str | None = None,
    ) -> GameState:
        """以題目與終盤建立一局全新狀態（盤面複製自題目、空筆記、計時歸零）。

        參數不合法（非 9×9、未知難度、日期格式錯）時拋 ValueError。
        """
        state = cls(
            puzzle=_require_grid("puzzle", puzzle),
            solution=_require_grid("solution", solution, allow_zero=False),
            board=[list(row) for row in puzzle],
            notes=[[[] for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)],
            hint_cells=[],
            difficulty=_require_difficulty(difficulty),
            is_daily=_require_bool("is_daily", is_daily),
            daily_date=_require_iso_date_or_none("daily_date", daily_date),
            started_at=now_iso(),
        )
        return state

    def to_dict(self) -> dict:
        """轉為可 JSON 序列化的 dict（深複製，修改回傳值不影響原物件）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> GameState:
        """由 dict 還原狀態；欄位缺漏或型別錯誤時拋 ValueError。

        有預設值的欄位（elapsed_seconds 等）缺漏時採預設值，
        核心欄位（盤面、難度等）缺漏則視為壞資料。
        """
        _require_keys(d, _STATE_REQUIRED, "GameState")
        undo_stack = d.get("undo_stack", [])
        if not isinstance(undo_stack, list) or not all(isinstance(x, dict) for x in undo_stack):
            raise ValueError("欄位 undo_stack 必須是 dict 的 list")
        return cls(
            puzzle=_require_grid("puzzle", d["puzzle"]),
            solution=_require_grid("solution", d["solution"], allow_zero=False),
            board=_require_grid("board", d["board"]),
            notes=_require_notes(d["notes"]),
            hint_cells=_require_cells(d["hint_cells"]),
            difficulty=_require_difficulty(d["difficulty"]),
            elapsed_seconds=_require_int("elapsed_seconds", d.get("elapsed_seconds", 0), 0),
            mistakes=_require_int("mistakes", d.get("mistakes", 0), 0),
            hints_left=_require_int("hints_left", d.get("hints_left", DEFAULT_HINTS), 0),
            is_daily=_require_bool("is_daily", d.get("is_daily", False)),
            daily_date=_require_iso_date_or_none("daily_date", d.get("daily_date")),
            undo_stack=copy.deepcopy(undo_stack),
            started_at=_require_iso_datetime("started_at", d.get("started_at", ""), allow_empty=True),
        )


# ---------------------------------------------------------------------------
# GameRecord
# ---------------------------------------------------------------------------
_RECORD_REQUIRED = (
    "finished_at", "difficulty", "elapsed_seconds", "mistakes",
    "hints_used", "completed", "is_daily",
)


@dataclass
class GameRecord:
    """一局結束（完成或放棄）後寫入的遊玩紀錄。"""

    finished_at: str
    difficulty: str
    elapsed_seconds: int
    mistakes: int
    hints_used: int
    completed: bool
    is_daily: bool

    def to_dict(self) -> dict:
        """轉為可 JSON 序列化的 dict。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> GameRecord:
        """由 dict 還原紀錄；欄位缺漏或型別錯誤時拋 ValueError。"""
        _require_keys(d, _RECORD_REQUIRED, "GameRecord")
        return cls(
            finished_at=_require_iso_datetime("finished_at", d["finished_at"]),
            difficulty=_require_difficulty(d["difficulty"]),
            elapsed_seconds=_require_int("elapsed_seconds", d["elapsed_seconds"], 0),
            mistakes=_require_int("mistakes", d["mistakes"], 0),
            hints_used=_require_int("hints_used", d["hints_used"], 0),
            completed=_require_bool("completed", d["completed"]),
            is_daily=_require_bool("is_daily", d["is_daily"]),
        )

    def validate(self) -> None:
        """檢查自身欄位是否合法（寫入前呼叫），不合法拋 ValueError。"""
        GameRecord.from_dict(self.to_dict())
