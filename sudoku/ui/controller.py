"""遊戲控制器：集中處理一局數獨的所有狀態變更，不依賴 tkinter / customtkinter。

UI 只負責把滑鼠 / 鍵盤事件轉成本類別的方法呼叫，再依查詢結果重繪；
因此所有規則（給定格不可改、錯誤計數、筆記、提示、undo、暫停、完成判定）
都能用 pytest 直接測試。

undo_stack 格式（存在 GameState.undo_stack，必須可 JSON 序列化）::

    {
        "kind": "fill" | "clear" | "note" | "hint",
        "changes": [
            {"r": 列, "c": 行, "value": 變更前數字, "notes": 變更前筆記, "hint": 變更前是否為提示格},
            ...
        ],
    }

undo 時把 changes 中每一格還原為「變更前」的值、筆記與提示標記，
因此「填數時被自動清掉的同行/列/宮筆記」也一併記錄在 changes 中，可完整回復。
設計取捨：undo 不退還錯誤次數與提示次數（避免以 undo 洗掉懲罰）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sudoku.data import GameRecord, GameState
from sudoku.logic import get_hint, is_complete

GRID = 9
MAX_HINTS = 3
# 限制 undo 深度，避免存檔無限長大（一局正常操作遠低於此值）
MAX_UNDO = 1000


class StorageLike(Protocol):
    """控制器需要的最小存檔介面（sudoku.data.Storage 或測試用假物件）。"""

    def save_game(self, state: GameState) -> None: ...

    def save_timer(self, state: GameState) -> None: ...

    def clear_game(self) -> None: ...


@dataclass(frozen=True)
class CellView:
    """單一格子的呈現資訊，供盤面繪製使用。"""

    row: int
    col: int
    value: int
    notes: tuple[int, ...]
    is_given: bool
    is_hint: bool
    is_error: bool
    is_selected: bool
    is_peer: bool
    is_same_number: bool


def peers_of(row: int, col: int) -> set[tuple[int, int]]:
    """回傳與 (row, col) 同列、同行、同宮的所有格子（不含自身）。"""
    cells: set[tuple[int, int]] = set()
    for i in range(GRID):
        cells.add((row, i))
        cells.add((i, col))
    br, bc = row // 3 * 3, col // 3 * 3
    for r in range(br, br + 3):
        for c in range(bc, bc + 3):
            cells.add((r, c))
    cells.discard((row, col))
    return cells


class GameController:
    """一局遊戲的狀態機。所有會改變 GameState 的操作都會呼叫 storage.save_game。

    完成時改為呼叫 storage.clear_game()，且之後 tick() 不再呼叫 save_timer，
    避免已清除的存檔被計時寫回。
    """

    def __init__(
        self,
        state: GameState,
        storage: StorageLike | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """以既有狀態（新局或讀檔）建立控制器；storage 為 None 時不存檔（測試/預覽用）。"""
        self.state = state
        self.storage = storage
        self.rng = rng if rng is not None else random.Random()
        self.notes_mode = False
        self.paused = False
        self.completed = is_complete(state.board, state.solution)
        self.selected: tuple[int, int] = self._first_empty_cell()

    # ------------------------------------------------------------------
    # 內部工具
    # ------------------------------------------------------------------
    def _first_empty_cell(self) -> tuple[int, int]:
        for r in range(GRID):
            for c in range(GRID):
                if self.state.board[r][c] == 0:
                    return (r, c)
        return (0, 0)

    def _save(self) -> None:
        if self.storage is not None and not self.completed:
            self.storage.save_game(self.state)

    def _blocked(self) -> bool:
        """暫停中或已完成時忽略所有盤面輸入。"""
        return self.paused or self.completed

    def _snapshot(self, r: int, c: int) -> dict:
        return {
            "r": r,
            "c": c,
            "value": self.state.board[r][c],
            "notes": list(self.state.notes[r][c]),
            "hint": [r, c] in self.state.hint_cells,
        }

    def _push_undo(self, kind: str, changes: list[dict]) -> None:
        self.state.undo_stack.append({"kind": kind, "changes": changes})
        if len(self.state.undo_stack) > MAX_UNDO:
            del self.state.undo_stack[: len(self.state.undo_stack) - MAX_UNDO]

    def _place(self, r: int, c: int, value: int) -> list[dict]:
        """填入正式數字並清除自身筆記與同行/列/宮的同數字筆記；回傳變更前快照。"""
        changes = [self._snapshot(r, c)]
        for pr, pc in sorted(peers_of(r, c)):
            if value in self.state.notes[pr][pc]:
                changes.append(self._snapshot(pr, pc))
                self.state.notes[pr][pc] = [n for n in self.state.notes[pr][pc] if n != value]
        self.state.board[r][c] = value
        self.state.notes[r][c] = []
        return changes

    def _check_complete(self) -> None:
        if is_complete(self.state.board, self.state.solution):
            self.completed = True
            if self.storage is not None:
                self.storage.clear_game()

    # ------------------------------------------------------------------
    # 查詢
    # ------------------------------------------------------------------
    def is_given(self, r: int, c: int) -> bool:
        """是否為題目給定格。"""
        return self.state.puzzle[r][c] != 0

    def is_hint(self, r: int, c: int) -> bool:
        """是否為提示填入的格子。"""
        return [r, c] in self.state.hint_cells

    def is_locked(self, r: int, c: int) -> bool:
        """給定格與提示格都不可再編輯。"""
        return self.is_given(r, c) or self.is_hint(r, c)

    def is_error(self, r: int, c: int) -> bool:
        """玩家填入的數字與終盤不符即為錯誤（直到被改掉前持續顯示）。"""
        value = self.state.board[r][c]
        return value != 0 and not self.is_given(r, c) and value != self.state.solution[r][c]

    def remaining_count(self, digit: int) -> int:
        """數字 digit 還需填幾個（只計正確的格子），供數字鍵盤顯示與停用。"""
        placed = sum(
            1
            for r in range(GRID)
            for c in range(GRID)
            if self.state.board[r][c] == digit and self.state.solution[r][c] == digit
        )
        return GRID - placed

    def cell_view(self, r: int, c: int) -> CellView:
        """取得單格的完整呈現資訊（含選取 / peer / 相同數字 / 錯誤 / 提示 / 給定）。"""
        sr, sc = self.selected
        value = self.state.board[r][c]
        selected_value = self.state.board[sr][sc]
        return CellView(
            row=r,
            col=c,
            value=value,
            notes=tuple(self.state.notes[r][c]),
            is_given=self.is_given(r, c),
            is_hint=self.is_hint(r, c),
            is_error=self.is_error(r, c),
            is_selected=(r, c) == (sr, sc),
            is_peer=(r, c) in peers_of(sr, sc),
            is_same_number=value != 0 and value == selected_value and (r, c) != (sr, sc),
        )

    @property
    def hints_left(self) -> int:
        """剩餘提示次數。"""
        return self.state.hints_left

    @property
    def can_undo(self) -> bool:
        """是否有可回復的操作。"""
        return bool(self.state.undo_stack)

    # ------------------------------------------------------------------
    # 選取
    # ------------------------------------------------------------------
    def select(self, r: int, c: int) -> bool:
        """選取指定格；座標越界或暫停中回 False。"""
        if self.paused or not (0 <= r < GRID and 0 <= c < GRID):
            return False
        self.selected = (r, c)
        return True

    def move(self, dr: int, dc: int) -> bool:
        """依方向移動選取格，碰到邊界停住不越界；有移動回 True。"""
        if self.paused:
            return False
        r, c = self.selected
        nr = min(max(r + dr, 0), GRID - 1)
        nc = min(max(c + dc, 0), GRID - 1)
        if (nr, nc) == (r, c):
            return False
        self.selected = (nr, nc)
        return True

    # ------------------------------------------------------------------
    # 編輯操作
    # ------------------------------------------------------------------
    def toggle_notes_mode(self) -> bool:
        """切換筆記模式，回傳切換後狀態；暫停或完成時不變。"""
        if not self._blocked():
            self.notes_mode = not self.notes_mode
        return self.notes_mode

    def input_digit(self, digit: int) -> bool:
        """依目前模式輸入數字：筆記模式切換候選，否則填入正式數字。"""
        if self.notes_mode:
            return self.toggle_note(digit)
        return self.fill(digit)

    def fill(self, digit: int) -> bool:
        """在選取格填入正式數字；給定格/提示格/相同數字不動作。填錯時錯誤次數 +1。"""
        if self._blocked() or not 1 <= digit <= 9:
            return False
        r, c = self.selected
        if self.is_locked(r, c) or self.state.board[r][c] == digit:
            return False
        changes = self._place(r, c, digit)
        self._push_undo("fill", changes)
        if digit != self.state.solution[r][c]:
            self.state.mistakes += 1
        self._check_complete()
        self._save()
        return True

    def toggle_note(self, digit: int) -> bool:
        """在選取格切換候選數字；已填數字的格子或鎖定格不動作。"""
        if self._blocked() or not 1 <= digit <= 9:
            return False
        r, c = self.selected
        if self.is_locked(r, c) or self.state.board[r][c] != 0:
            return False
        changes = [self._snapshot(r, c)]
        notes = set(self.state.notes[r][c])
        notes.symmetric_difference_update({digit})
        self.state.notes[r][c] = sorted(notes)
        self._push_undo("note", changes)
        self._save()
        return True

    def clear(self) -> bool:
        """清除選取格的數字與筆記；鎖定格或已是空白無筆記時不動作。"""
        if self._blocked():
            return False
        r, c = self.selected
        if self.is_locked(r, c):
            return False
        if self.state.board[r][c] == 0 and not self.state.notes[r][c]:
            return False
        changes = [self._snapshot(r, c)]
        self.state.board[r][c] = 0
        self.state.notes[r][c] = []
        self._push_undo("clear", changes)
        self._save()
        return True

    def hint(self) -> tuple[int, int, int] | None:
        """使用一次提示：隨機挑空格或錯填格填入正確值，記入 hint_cells 並選取該格。

        次數用完、暫停、完成或已無可提示格時回 None。
        """
        if self._blocked() or self.state.hints_left <= 0:
            return None
        result = get_hint(self.state.board, self.state.solution, self.rng)
        if result is None:
            return None
        r, c, value = result
        changes = self._place(r, c, value)
        self.state.hint_cells.append([r, c])
        self.state.hints_left -= 1
        self.selected = (r, c)
        self._push_undo("hint", changes)
        self._check_complete()
        self._save()
        return result

    def undo(self) -> bool:
        """回復上一步（填數 / 清除 / 筆記 / 提示，含被自動清除的筆記）。"""
        if self._blocked() or not self.state.undo_stack:
            return False
        entry = self.state.undo_stack.pop()
        for change in entry.get("changes", []):
            r, c = change["r"], change["c"]
            self.state.board[r][c] = change["value"]
            self.state.notes[r][c] = list(change["notes"])
            in_hints = [r, c] in self.state.hint_cells
            if change["hint"] and not in_hints:
                self.state.hint_cells.append([r, c])
            elif not change["hint"] and in_hints:
                self.state.hint_cells.remove([r, c])
        first = entry.get("changes", [])
        if first:
            self.selected = (first[0]["r"], first[0]["c"])
        self._save()
        return True

    # ------------------------------------------------------------------
    # 計時 / 暫停 / 結算
    # ------------------------------------------------------------------
    def toggle_pause(self) -> bool:
        """切換暫停，回傳切換後是否暫停；已完成時不動作。"""
        if self.completed:
            return False
        self.paused = not self.paused
        self._save()
        return self.paused

    def tick(self) -> bool:
        """每秒呼叫一次：未暫停且未完成時計時 +1 並呼叫 save_timer。"""
        if self.paused or self.completed:
            return False
        self.state.elapsed_seconds += 1
        if self.storage is not None:
            self.storage.save_timer(self.state)
        return True

    @property
    def hints_used(self) -> int:
        """本局已使用的提示次數。"""
        return max(0, MAX_HINTS - self.state.hints_left)

    def make_record(self, completed: bool) -> GameRecord:
        """依目前狀態產生遊玩紀錄（completed=False 表示放棄）。"""
        return GameRecord(
            finished_at=datetime.now().isoformat(timespec="seconds"),
            difficulty=self.state.difficulty,
            elapsed_seconds=self.state.elapsed_seconds,
            mistakes=self.state.mistakes,
            hints_used=self.hints_used,
            completed=completed,
            is_daily=self.state.is_daily,
        )


def format_time(seconds: int) -> str:
    """把秒數格式化為 mm:ss（超過一小時為 h:mm:ss）。"""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
