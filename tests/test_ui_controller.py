"""GameController 單元測試（不依賴視窗，使用記錄呼叫的假 storage）。"""
from __future__ import annotations

import json
import random

import pytest

from sudoku.data import GameState
from sudoku.ui.controller import GameController, format_time, peers_of

# 以公式產生合法終盤：每列平移，保證行/列/宮皆不重複
SOLUTION = [[(r * 3 + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]


class FakeStorage:
    """記錄每次呼叫的假存檔物件。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def save_game(self, state: GameState) -> None:
        self.calls.append("save_game")

    def save_timer(self, state: GameState) -> None:
        self.calls.append("save_timer")

    def clear_game(self) -> None:
        self.calls.append("clear_game")


def make_controller(blanks: list[tuple[int, int]] | None = None, seed: int = 0):
    """建立測試用控制器；blanks 為挖空的格子，預設挖空第 0 列與 (1,0)。"""
    if blanks is None:
        blanks = [(0, c) for c in range(9)] + [(1, 0)]
    puzzle = [row[:] for row in SOLUTION]
    for r, c in blanks:
        puzzle[r][c] = 0
    state = GameState.new(puzzle, [row[:] for row in SOLUTION], "easy")
    storage = FakeStorage()
    return GameController(state, storage, rng=random.Random(seed)), storage


def wrong_digit(r: int, c: int) -> int:
    return SOLUTION[r][c] % 9 + 1


# ---------------------------------------------------------------- 選取
def test_initial_selection_is_first_empty_cell():
    ctl, _ = make_controller()
    assert ctl.selected == (0, 0)


def test_move_stops_at_boundaries():
    ctl, _ = make_controller()
    ctl.select(0, 0)
    assert ctl.move(-1, 0) is False
    assert ctl.move(0, -1) is False
    assert ctl.selected == (0, 0)
    ctl.select(8, 8)
    assert ctl.move(1, 0) is False and ctl.move(0, 1) is False
    assert ctl.move(-1, -1) is True and ctl.selected == (7, 7)


def test_select_out_of_range_rejected():
    ctl, _ = make_controller()
    assert ctl.select(9, 0) is False
    assert ctl.select(-1, 3) is False
    assert ctl.selected == (0, 0)


# ---------------------------------------------------------------- 填數
def test_fill_correct_value_saves_without_mistake():
    ctl, storage = make_controller()
    ctl.select(0, 0)
    assert ctl.fill(SOLUTION[0][0]) is True
    assert ctl.state.board[0][0] == SOLUTION[0][0]
    assert ctl.state.mistakes == 0
    assert storage.calls[-1] == "save_game"


def test_given_cell_cannot_be_modified():
    ctl, storage = make_controller()
    ctl.select(5, 5)
    assert ctl.fill(wrong_digit(5, 5)) is False
    assert ctl.clear() is False
    assert ctl.toggle_note(1) is False
    assert ctl.state.board[5][5] == SOLUTION[5][5]
    assert storage.calls == []


def test_wrong_fill_counts_mistake_and_marks_error_until_changed():
    ctl, _ = make_controller()
    ctl.select(0, 1)
    bad = wrong_digit(0, 1)
    ctl.fill(bad)
    assert ctl.state.mistakes == 1
    assert ctl.cell_view(0, 1).is_error
    ctl.fill(SOLUTION[0][1])
    assert not ctl.cell_view(0, 1).is_error
    assert ctl.state.mistakes == 1


def test_refilling_same_digit_is_noop():
    ctl, storage = make_controller()
    ctl.select(0, 2)
    ctl.fill(wrong_digit(0, 2))
    count = len(storage.calls)
    assert ctl.fill(wrong_digit(0, 2)) is False
    assert ctl.state.mistakes == 1
    assert len(storage.calls) == count


def test_invalid_digit_rejected():
    ctl, _ = make_controller()
    assert ctl.fill(0) is False
    assert ctl.fill(10) is False


# ---------------------------------------------------------------- 筆記
def test_notes_mode_toggles_candidates():
    ctl, _ = make_controller()
    assert ctl.toggle_notes_mode() is True
    ctl.select(0, 3)
    ctl.input_digit(2)
    ctl.input_digit(7)
    assert ctl.state.notes[0][3] == [2, 7]
    ctl.input_digit(2)
    assert ctl.state.notes[0][3] == [7]
    assert ctl.state.board[0][3] == 0


def test_fill_removes_related_notes_in_row_col_box():
    ctl, _ = make_controller()
    digit = SOLUTION[0][0]
    ctl.toggle_notes_mode()
    for c in (1, 4):
        ctl.select(0, c)
        ctl.toggle_note(digit)
        ctl.toggle_note(9 if digit != 9 else 8)
    ctl.select(1, 0)
    ctl.toggle_note(digit)
    ctl.toggle_notes_mode()
    ctl.select(0, 0)
    ctl.fill(digit)
    assert digit not in ctl.state.notes[0][1]
    assert digit not in ctl.state.notes[0][4]
    assert digit not in ctl.state.notes[1][0]
    assert ctl.state.notes[0][1]  # 其他候選保留


def test_note_on_filled_cell_ignored():
    ctl, _ = make_controller()
    ctl.select(0, 0)
    ctl.fill(SOLUTION[0][0])
    assert ctl.toggle_note(3) is False


# ---------------------------------------------------------------- 清除
def test_clear_removes_value_and_notes():
    ctl, _ = make_controller()
    ctl.select(0, 4)
    ctl.fill(wrong_digit(0, 4))
    assert ctl.clear() is True
    assert ctl.state.board[0][4] == 0
    assert ctl.clear() is False  # 已空白


# ---------------------------------------------------------------- 提示
def test_hint_fills_correct_value_and_records_hint_cell():
    ctl, storage = make_controller()
    result = ctl.hint()
    assert result is not None
    r, c, v = result
    assert v == SOLUTION[r][c] and ctl.state.board[r][c] == v
    assert [r, c] in ctl.state.hint_cells
    assert ctl.hints_left == 2 and ctl.selected == (r, c)
    assert ctl.cell_view(r, c).is_hint
    assert storage.calls[-1] == "save_game"


def test_hints_exhausted_after_three():
    ctl, _ = make_controller()
    for _ in range(3):
        assert ctl.hint() is not None
    assert ctl.hints_left == 0
    assert ctl.hint() is None
    assert ctl.hints_used == 3


def test_hint_cell_locked():
    ctl, _ = make_controller()
    r, c, _v = ctl.hint()
    ctl.select(r, c)
    assert ctl.fill(wrong_digit(r, c)) is False
    assert ctl.clear() is False


# ---------------------------------------------------------------- undo
def test_undo_fill_restores_value():
    ctl, _ = make_controller()
    ctl.select(0, 5)
    ctl.fill(wrong_digit(0, 5))
    assert ctl.undo() is True
    assert ctl.state.board[0][5] == 0
    assert ctl.state.mistakes == 1  # 錯誤次數不退還
    assert ctl.undo() is False


def test_undo_restores_auto_removed_notes():
    ctl, _ = make_controller()
    digit = SOLUTION[0][0]
    ctl.select(0, 6)
    ctl.toggle_note(digit)
    ctl.select(0, 0)
    ctl.toggle_note(digit)
    ctl.toggle_note(wrong_digit(0, 0))
    ctl.fill(digit)
    assert ctl.state.notes[0][6] == [] and ctl.state.notes[0][0] == []
    ctl.undo()
    assert ctl.state.notes[0][6] == [digit]
    assert ctl.state.notes[0][0] == sorted([digit, wrong_digit(0, 0)])
    assert ctl.state.board[0][0] == 0


def test_undo_clear_and_note():
    ctl, _ = make_controller()
    ctl.select(0, 7)
    ctl.toggle_note(4)
    ctl.clear()
    assert ctl.state.notes[0][7] == []
    ctl.undo()
    assert ctl.state.notes[0][7] == [4]
    ctl.undo()
    assert ctl.state.notes[0][7] == []


def test_undo_hint_removes_hint_cell_but_keeps_count():
    ctl, _ = make_controller()
    r, c, _v = ctl.hint()
    ctl.undo()
    assert ctl.state.board[r][c] == 0
    assert [r, c] not in ctl.state.hint_cells
    assert ctl.hints_left == 2


def test_undo_stack_survives_json_round_trip():
    ctl, _ = make_controller()
    digit = SOLUTION[0][0]
    ctl.select(0, 8)
    ctl.toggle_note(digit)
    ctl.select(0, 0)
    ctl.fill(digit)
    ctl.hint()
    data = json.loads(json.dumps(ctl.state.to_dict()))
    restored = GameController(GameState.from_dict(data), FakeStorage())
    assert restored.undo() is True  # 回復提示
    assert restored.undo() is True  # 回復填數（含筆記）
    assert restored.state.board[0][0] == 0
    assert restored.state.notes[0][8] == [digit]


# ---------------------------------------------------------------- 暫停 / 計時
def test_paused_ignores_input_and_timer():
    ctl, storage = make_controller()
    assert ctl.toggle_pause() is True
    calls = len(storage.calls)
    assert ctl.fill(SOLUTION[0][0]) is False
    assert ctl.move(0, 1) is False
    assert ctl.hint() is None
    assert ctl.undo() is False
    assert ctl.toggle_notes_mode() is False
    assert ctl.tick() is False
    assert len(storage.calls) == calls
    assert ctl.toggle_pause() is False
    assert ctl.tick() is True
    assert ctl.state.elapsed_seconds == 1 and storage.calls[-1] == "save_timer"


# ---------------------------------------------------------------- 完成
def test_completion_clears_save_and_stops_timer():
    ctl, storage = make_controller(blanks=[(4, 4), (8, 8)])
    ctl.select(4, 4)
    ctl.fill(SOLUTION[4][4])
    assert not ctl.completed
    ctl.select(8, 8)
    ctl.fill(SOLUTION[8][8])
    assert ctl.completed
    assert storage.calls[-1] == "clear_game"
    assert ctl.tick() is False
    assert "save_timer" not in storage.calls
    assert ctl.fill(1) is False and ctl.toggle_pause() is False
    assert storage.calls[-1] == "clear_game"  # 完成後不再寫回存檔
    record = ctl.make_record(completed=True)
    assert record.completed and record.difficulty == "easy" and record.hints_used == 0


def test_completion_by_hint():
    ctl, storage = make_controller(blanks=[(2, 2)])
    assert ctl.hint() == (2, 2, SOLUTION[2][2])
    assert ctl.completed and storage.calls[-1] == "clear_game"


# ---------------------------------------------------------------- 高亮 / 其他查詢
def test_cell_view_highlights():
    ctl, _ = make_controller()
    ctl.select(4, 4)
    value = SOLUTION[4][4]
    assert ctl.cell_view(4, 4).is_selected
    assert ctl.cell_view(4, 0).is_peer and ctl.cell_view(0, 4).is_peer
    assert ctl.cell_view(3, 3).is_peer
    assert not ctl.cell_view(0, 0).is_peer
    same = [(r, c) for r in range(9) for c in range(9)
            if ctl.state.board[r][c] == value and (r, c) != (4, 4)]
    assert same and all(ctl.cell_view(r, c).is_same_number for r, c in same)
    assert ctl.cell_view(4, 4).is_given


def test_remaining_count():
    ctl, _ = make_controller()
    digit = SOLUTION[0][0]
    before = ctl.remaining_count(digit)
    assert before >= 1
    ctl.select(0, 0)
    ctl.fill(digit)
    assert ctl.remaining_count(digit) == before - 1
    full = SOLUTION[5][5]
    if all(SOLUTION[0][c] != full for c in range(9)) and SOLUTION[1][0] != full:
        assert ctl.remaining_count(full) == 0


def test_peers_count_and_format_time():
    assert len(peers_of(0, 0)) == 20
    assert format_time(0) == "00:00"
    assert format_time(125) == "02:05"
    assert format_time(3725) == "1:02:05"


@pytest.mark.parametrize("completed", [True, False])
def test_make_record_abandon_flag(completed):
    ctl, _ = make_controller()
    ctl.hint()
    rec = ctl.make_record(completed=completed)
    assert rec.completed is completed and rec.hints_used == 1
    rec.validate()


def test_key_to_digit_mapping():
    from sudoku.ui.game_view import key_to_digit

    assert key_to_digit("5", "5") == 5
    assert key_to_digit("KP_7", "") == 7
    assert key_to_digit("KP_End", "") == 1  # NumLock 關閉時的數字鍵台
    assert key_to_digit("KP_0", "") is None
    assert key_to_digit("a", "a") is None
    assert key_to_digit("0", "0") is None
