"""sudoku.logic 解題核心測試：solve / count_solutions / is_valid_placement。"""

import copy

import pytest

from sudoku.logic import count_solutions, is_valid_placement, solve

# 以本模組產生器搜出、唯一解的盤面（57 空格）
PUZZLE_STR = "000010700002084005000000840004930010200000000960000057090007002700000100000608000"


def parse(s: str) -> list[list[int]]:
    return [[int(ch) for ch in s[r * 9:(r + 1) * 9]] for r in range(9)]


def is_valid_full(board) -> bool:
    """獨立於被測程式的終盤合法性檢查。"""
    want = set(range(1, 10))
    for i in range(9):
        if set(board[i]) != want or {board[r][i] for r in range(9)} != want:
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            if {board[br + r][bc + c] for r in range(3) for c in range(3)} != want:
                return False
    return True


def test_solve_returns_valid_solution_consistent_with_givens():
    puzzle = parse(PUZZLE_STR)
    original = copy.deepcopy(puzzle)
    sol = solve(puzzle)
    assert sol is not None and is_valid_full(sol)
    assert all(puzzle[r][c] in (0, sol[r][c]) for r in range(9) for c in range(9))
    assert puzzle == original  # 不修改輸入


def test_solve_conflicting_board_returns_none():
    board = [[0] * 9 for _ in range(9)]
    board[0][0] = board[0][5] = 7
    assert solve(board) is None
    assert count_solutions(board) == 0


def test_solve_unsolvable_without_direct_conflict_returns_none():
    # (0,0) 的列含 1–8、行含 9 → 無候選但已填數字不直接衝突
    board = [[0] * 9 for _ in range(9)]
    board[0][1:9] = [1, 2, 3, 4, 5, 6, 7, 8]
    board[4][0] = 9
    assert solve(board) is None


def test_count_solutions_unique_and_multiple():
    assert count_solutions(parse(PUZZLE_STR)) == 1
    empty = [[0] * 9 for _ in range(9)]
    assert count_solutions(empty, limit=2) == 2
    assert count_solutions(empty, limit=5) == 5


def test_count_solutions_full_board_is_one():
    sol = solve(parse(PUZZLE_STR))
    assert count_solutions(sol) == 1


@pytest.mark.parametrize(
    "bad",
    [
        [[0] * 9 for _ in range(8)],
        [[0] * 8 for _ in range(9)],
        [[10] + [0] * 8] + [[0] * 9 for _ in range(8)],
        [[-1] + [0] * 8] + [[0] * 9 for _ in range(8)],
        None,
    ],
)
def test_malformed_board_raises_value_error(bad):
    with pytest.raises(ValueError):
        solve(bad)
    with pytest.raises(ValueError):
        count_solutions(bad)


def test_count_solutions_invalid_limit():
    with pytest.raises(ValueError):
        count_solutions(parse(PUZZLE_STR), limit=0)


def test_is_valid_placement_row_col_box_conflicts():
    board = [[0] * 9 for _ in range(9)]
    board[0][8] = 5  # 同列
    board[8][1] = 6  # 同行
    board[2][2] = 7  # 同宮
    assert not is_valid_placement(board, 0, 1, 5)
    assert not is_valid_placement(board, 4, 1, 6)
    assert not is_valid_placement(board, 1, 1, 7)
    assert is_valid_placement(board, 1, 1, 4)


def test_is_valid_placement_ignores_own_cell():
    board = [[0] * 9 for _ in range(9)]
    board[3][3] = 9
    assert is_valid_placement(board, 3, 3, 9)


@pytest.mark.parametrize("args", [(9, 0, 1), (0, -1, 1), (0, 0, 0), (0, 0, 10)])
def test_is_valid_placement_out_of_range(args):
    with pytest.raises(ValueError):
        is_valid_placement([[0] * 9 for _ in range(9)], *args)
