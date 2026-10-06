"""sudoku.data 模型測試：GameState / GameRecord 的序列化與驗證。"""
import json

import pytest

from sudoku.data import GameRecord, GameState

# 合法終盤（標準移位構造），題目為挖掉部分格子
SOLUTION = [[(r * 3 + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
PUZZLE = [[v if (r + c) % 3 else 0 for c, v in enumerate(row)] for r, row in enumerate(SOLUTION)]


def make_state(**overrides) -> GameState:
    state = GameState.new(PUZZLE, SOLUTION, "hard")
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def test_new_initial_values():
    state = GameState.new(PUZZLE, SOLUTION, "easy", is_daily=True, daily_date="2026-10-06")
    assert state.board == PUZZLE and state.board is not PUZZLE
    assert state.notes == [[[] for _ in range(9)] for _ in range(9)]
    assert state.hints_left == 3 and state.mistakes == 0 and state.elapsed_seconds == 0
    assert state.is_daily and state.daily_date == "2026-10-06"
    assert state.started_at  # ISO 時間字串


def test_new_rejects_bad_difficulty():
    with pytest.raises(ValueError):
        GameState.new(PUZZLE, SOLUTION, "nightmare")


def test_roundtrip_through_json():
    state = make_state(elapsed_seconds=123, mistakes=2, hints_left=1)
    state.board[0][0] = 5
    state.notes[1][2] = [3, 7]
    state.hint_cells = [[0, 0]]
    state.undo_stack = [{"op": "set", "r": 0, "c": 0, "old": 0, "new": 5, "中文": "ok"}]
    restored = GameState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored == state


def test_to_dict_is_deep_copy():
    state = make_state()
    d = state.to_dict()
    d["board"][0][0] = 9
    assert state.board[0][0] == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("board"),
        lambda d: d.__setitem__("difficulty", 3),
        lambda d: d.__setitem__("board", [[0] * 9] * 8),
        lambda d: d.__setitem__("elapsed_seconds", "12"),
        lambda d: d.__setitem__("elapsed_seconds", True),
        lambda d: d.__setitem__("mistakes", -1),
        lambda d: d.__setitem__("notes", [[[10]] * 9] * 9),
        lambda d: d.__setitem__("hint_cells", [[9, 0]]),
        lambda d: d.__setitem__("daily_date", "2026/10/06"),
        lambda d: d.__setitem__("undo_stack", ["x"]),
        lambda d: d.__setitem__("is_daily", "yes"),
    ],
)
def test_from_dict_invalid_raises_value_error(mutate):
    d = make_state().to_dict()
    mutate(d)
    with pytest.raises(ValueError):
        GameState.from_dict(d)


def test_from_dict_non_dict_raises_value_error():
    with pytest.raises(ValueError):
        GameState.from_dict(None)


def test_from_dict_optional_fields_default():
    d = make_state().to_dict()
    for key in ("elapsed_seconds", "mistakes", "hints_left", "undo_stack", "started_at"):
        d.pop(key)
    state = GameState.from_dict(d)
    assert state.hints_left == 3 and state.undo_stack == [] and state.started_at == ""


def test_record_roundtrip_and_validation():
    record = GameRecord("2026-10-06T10:00:00", "easy", 300, 0, 1, True, False)
    assert GameRecord.from_dict(record.to_dict()) == record
    bad = record.to_dict()
    bad["completed"] = 1
    with pytest.raises(ValueError):
        GameRecord.from_dict(bad)
