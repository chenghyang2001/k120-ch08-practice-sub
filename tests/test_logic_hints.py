"""get_hint / is_complete 測試。"""

import random

import pytest

from sudoku.logic import generate_puzzle, get_hint, is_complete


@pytest.fixture(scope="module")
def game():
    return generate_puzzle("easy", 7)


def test_hint_returns_empty_cell_with_correct_value(game):
    r, c, v = get_hint(game.puzzle, game.solution, random.Random(0))
    assert game.puzzle[r][c] == 0
    assert v == game.solution[r][c]


def test_hint_none_when_all_correct(game):
    board = [row[:] for row in game.solution]
    assert get_hint(board, game.solution) is None


def test_hint_picks_wrong_cell(game):
    board = [row[:] for row in game.solution]
    correct = board[4][4]
    board[4][4] = correct % 9 + 1  # 唯一錯填格
    assert get_hint(board, game.solution) == (4, 4, correct)


def test_hint_deterministic_with_rng_and_covers_wrong_and_empty(game):
    board = [row[:] for row in game.puzzle]
    # 把一個給定格改錯，候選 = 空格 + 錯格
    gr, gc = next((r, c) for r in range(9) for c in range(9) if board[r][c])
    board[gr][gc] = board[gr][gc] % 9 + 1
    a = get_hint(board, game.solution, random.Random(5))
    b = get_hint(board, game.solution, random.Random(5))
    assert a == b
    seen = {get_hint(board, game.solution, random.Random(i))[:2] for i in range(300)}
    assert (gr, gc) in seen
    assert all(board[r][c] == 0 or (r, c) == (gr, gc) for r, c in seen)


def test_hint_does_not_mutate(game):
    board = [row[:] for row in game.puzzle]
    get_hint(board, game.solution)
    assert board == game.puzzle


def test_is_complete(game):
    assert is_complete(game.solution, game.solution)
    assert not is_complete(game.puzzle, game.solution)
    wrong = [row[:] for row in game.solution]
    wrong[0][0] = wrong[0][0] % 9 + 1
    assert not is_complete(wrong, game.solution)


def test_hint_bad_shape_raises(game):
    with pytest.raises(ValueError):
        get_hint([[0] * 9], game.solution)
