"""題目產生器測試：合法終盤、唯一解、決定性、難度評級、時間上限。"""

import time

import pytest

from sudoku.logic import (
    DIFFICULTIES,
    Puzzle,
    count_solutions,
    generate_puzzle,
    rate_difficulty,
)
from sudoku.logic.difficulty import HOLE_BANDS

SEEDS = (1, 20261006, 424242)


def is_valid_full(board) -> bool:
    want = set(range(1, 10))
    for i in range(9):
        if set(board[i]) != want or {board[r][i] for r in range(9)} != want:
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            if {board[br + r][bc + c] for r in range(3) for c in range(3)} != want:
                return False
    return True


@pytest.fixture(scope="module")
def puzzles() -> dict[tuple[str, int], Puzzle]:
    return {(d, s): generate_puzzle(d, s) for d in DIFFICULTIES for s in SEEDS}


def test_difficulties_constant():
    assert DIFFICULTIES == ("easy", "medium", "hard", "expert")


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_solution_is_valid_and_matches_givens(puzzles, difficulty):
    for s in SEEDS:
        p = puzzles[(difficulty, s)]
        assert is_valid_full(p.solution)
        for r in range(9):
            for c in range(9):
                assert p.puzzle[r][c] in (0, p.solution[r][c])


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_puzzle_has_unique_solution(puzzles, difficulty):
    for s in SEEDS:
        assert count_solutions(puzzles[(difficulty, s)].puzzle, limit=2) == 1


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_rating_matches_requested_difficulty(puzzles, difficulty):
    for s in SEEDS:
        p = puzzles[(difficulty, s)]
        assert p.difficulty == difficulty
        rated, stats = rate_difficulty(p.puzzle)
        assert rated == difficulty
        assert stats == p.technique_stats
        lo, hi = HOLE_BANDS[difficulty]
        holes = sum(row.count(0) for row in p.puzzle)
        assert lo <= holes <= hi


def test_easy_needs_only_singles(puzzles):
    advanced = ("naked_pair", "hidden_pair", "pointing", "box_line", "x_wing", "swordfish")
    for s in SEEDS:
        stats = puzzles[("easy", s)].technique_stats
        assert all(stats[k] == 0 for k in advanced)
        assert stats["unsolved"] == 0


def test_medium_and_hard_are_solvable_by_techniques(puzzles):
    for d in ("medium", "hard"):
        for s in SEEDS:
            stats = puzzles[(d, s)].technique_stats
            assert stats["unsolved"] == 0 and stats["swordfish"] == 0


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_same_seed_same_puzzle(puzzles, difficulty):
    again = generate_puzzle(difficulty, SEEDS[1])
    first = puzzles[(difficulty, SEEDS[1])]
    assert again.puzzle == first.puzzle
    assert again.solution == first.solution
    assert again.seed == SEEDS[1]


def test_different_seed_different_puzzle(puzzles):
    assert puzzles[("medium", SEEDS[0])].puzzle != puzzles[("medium", SEEDS[1])].puzzle


def test_seed_none_generates_random_puzzles():
    a = generate_puzzle("easy")
    b = generate_puzzle("easy")
    assert a.seed is None and a.difficulty == "easy"
    assert a.puzzle != b.puzzle  # 機率上幾乎不可能相同


@pytest.mark.parametrize("bad", ["", "EASY", "insane", None, 1])
def test_invalid_difficulty_raises(bad):
    with pytest.raises(ValueError):
        generate_puzzle(bad, 1)


def test_invalid_seed_type_raises():
    with pytest.raises(ValueError):
        generate_puzzle("easy", "abc")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "difficulty,limit", [("easy", 1.0), ("medium", 1.0), ("hard", 1.0), ("expert", 2.0)]
)
def test_generation_time_average_under_limit(difficulty, limit):
    seeds = range(100, 110)
    start = time.perf_counter()
    for s in seeds:
        generate_puzzle(difficulty, s)
    avg = (time.perf_counter() - start) / len(seeds)
    assert avg < limit, f"{difficulty} 平均 {avg:.3f}s 超過 {limit}s"


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_fallback_still_returns_requested_difficulty(monkeypatch, difficulty):
    """第一階段全部失敗時，降級策略仍須回傳目標難度、唯一解，且與評級一致。"""
    from sudoku.logic import generator

    monkeypatch.setattr(generator, "_PHASE1_ATTEMPTS", {d: 0 for d in DIFFICULTIES})
    p = generate_puzzle(difficulty, 99)
    assert p.difficulty == difficulty
    assert rate_difficulty(p.puzzle)[0] == difficulty
    assert count_solutions(p.puzzle) == 1
