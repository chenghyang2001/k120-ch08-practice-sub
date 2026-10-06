"""人類技巧解題器測試：X-Wing / Swordfish 專門測資、其他技巧、評級。"""

import pytest

from sudoku.logic import rate_difficulty
from sudoku.logic import techniques as tq
from sudoku.logic.solver import FULL_MASK

# 由產生器搜出的盤面，需要 X-Wing / Swordfish 才能以技巧解完（測試中另以「停用該技巧就解不完」交叉驗證）
X_WING_PUZZLE = "000010700002084005000000840004930010200000000960000057090007002700000100000608000"
SWORDFISH_PUZZLE = "009000000060000502300000860000009080007425010010000029500800007082500000003010000"


def flat(s: str) -> list[int]:
    return [int(ch) for ch in s]


def parse(s: str) -> list[list[int]]:
    return [[int(ch) for ch in s[r * 9:(r + 1) * 9]] for r in range(9)]


def full_cands() -> list[int]:
    return [FULL_MASK] * 81


def keep_digit_only_at(cands, bit, row, cols):
    """讓 bit 在指定列只出現在 cols。"""
    for c in range(9):
        if c not in cols:
            cands[row * 9 + c] &= ~bit


# ---------------------------------------------------------------- X-Wing

def test_x_wing_row_based_eliminates_from_columns():
    bit = 1 << 4  # 數字 5
    cands = full_cands()
    keep_digit_only_at(cands, bit, 1, {2, 7})
    keep_digit_only_at(cands, bit, 5, {2, 7})
    assert tq.find_x_wing(cands) is True
    for r in range(9):
        for c in (2, 7):
            has = bool(cands[r * 9 + c] & bit)
            assert has == (r in (1, 5)), (r, c)
    # 其他行不受影響
    assert cands[0 * 9 + 0] & bit
    # 再找一次已無可刪 → False
    assert tq.find_x_wing(cands) is False


def test_x_wing_column_based():
    bit = 1 << 0  # 數字 1
    cands = full_cands()
    for c in (3, 6):
        for r in range(9):
            if r not in (0, 8):
                cands[r * 9 + c] &= ~bit
    assert tq.find_x_wing(cands) is True
    for c in range(9):
        for r in (0, 8):
            assert bool(cands[r * 9 + c] & bit) == (c in (3, 6))


def test_x_wing_absent_on_full_candidates():
    assert tq.find_x_wing(full_cands()) is False


def test_x_wing_puzzle_needs_x_wing():
    result = tq.solve_with_techniques(flat(X_WING_PUZZLE))
    assert result.solved
    assert result.stats["x_wing"] >= 1
    assert result.stats["swordfish"] == 0


def test_x_wing_puzzle_unsolvable_without_x_wing(monkeypatch):
    steps = tuple(s for s in tq._ELIMINATION_STEPS if s[0] not in ("x_wing", "swordfish"))
    monkeypatch.setattr(tq, "_ELIMINATION_STEPS", steps)
    assert tq.solve_with_techniques(flat(X_WING_PUZZLE)).solved is False


# ---------------------------------------------------------------- Swordfish

def _swordfish_cands():
    bit = 1 << 2  # 數字 3
    cands = full_cands()
    keep_digit_only_at(cands, bit, 0, {1, 4})
    keep_digit_only_at(cands, bit, 4, {4, 7})
    keep_digit_only_at(cands, bit, 8, {1, 7})
    return cands, bit


def test_swordfish_pattern_is_not_x_wing():
    cands, _ = _swordfish_cands()
    assert tq.find_x_wing(cands) is False


def test_swordfish_row_based_eliminates_from_columns():
    cands, bit = _swordfish_cands()
    assert tq.find_swordfish(cands) is True
    for r in range(9):
        for c in (1, 4, 7):
            has = bool(cands[r * 9 + c] & bit)
            if r in (0, 4, 8):
                # 基準列原本的位置保留
                assert has == (c in {0: {1, 4}, 4: {4, 7}, 8: {1, 7}}[r])
            else:
                assert not has, (r, c)
    assert cands[3 * 9 + 0] & bit  # 非覆蓋行不受影響
    assert tq.find_swordfish(cands) is False


def test_swordfish_puzzle_needs_swordfish(monkeypatch):
    result = tq.solve_with_techniques(flat(SWORDFISH_PUZZLE))
    assert result.solved
    assert result.stats["swordfish"] >= 1
    steps = tuple(s for s in tq._ELIMINATION_STEPS if s[0] != "swordfish")
    monkeypatch.setattr(tq, "_ELIMINATION_STEPS", steps)
    assert tq.solve_with_techniques(flat(SWORDFISH_PUZZLE)).solved is False


def test_swordfish_puzzle_rated_expert():
    difficulty, stats = rate_difficulty(parse(SWORDFISH_PUZZLE))
    assert difficulty == "expert"
    assert stats["swordfish"] >= 1 and stats["unsolved"] == 0


# ---------------------------------------------------------------- 其他技巧

def test_naked_pair_eliminates_in_unit():
    cands = full_cands()
    pair = (1 << 0) | (1 << 1)
    cands[0] = cands[1] = pair
    assert tq.find_naked_pair(cands) is True
    # 同列（亦同宮）其他格的 1、2 皆被刪除
    assert all(not cands[c] & pair for c in range(2, 9))


def test_hidden_pair_restricts_cells():
    cands = full_cands()
    pair = (1 << 5) | (1 << 6)  # 數字 6、7
    for c in range(2, 9):
        cands[c] &= ~pair  # 第 0 列中 6、7 只剩 (0,0)、(0,1)
    assert tq.find_hidden_pair(cands) is True
    assert cands[0] == pair and cands[1] == pair


def test_pointing_eliminates_outside_box():
    bit = 1 << 8
    cands = full_cands()
    for i in (9, 10, 11, 18, 19, 20):  # 第 0 宮的第 1、2 列移除 9
        cands[i] &= ~bit
    assert tq.find_pointing(cands) is True
    assert all(not cands[c] & bit for c in range(3, 9))


def test_box_line_eliminates_inside_box():
    bit = 1 << 3
    cands = full_cands()
    for c in range(3, 9):  # 第 0 列的 4 只能在第 0 宮
        cands[c] &= ~bit
    # 先讓 pointing 不先觸發不影響本函式；直接呼叫 box_line
    assert tq.find_box_line(cands) is True
    assert all(not cands[i] & bit for i in (9, 10, 11, 18, 19, 20))


def test_stats_contain_all_technique_keys():
    result = tq.solve_with_techniques(flat(X_WING_PUZZLE))
    assert set(result.stats) == set(tq.TECHNIQUES)


def test_contradictory_board_is_flagged():
    cells = [0] * 81
    cells[0] = cells[1] = 4
    result = tq.solve_with_techniques(cells)
    assert not result.solved and result.contradiction


def test_rate_difficulty_does_not_mutate_and_rejects_bad_shape():
    board = parse(X_WING_PUZZLE)
    before = [row[:] for row in board]
    rate_difficulty(board)
    assert board == before
    with pytest.raises(ValueError):
        rate_difficulty([[0] * 9])
