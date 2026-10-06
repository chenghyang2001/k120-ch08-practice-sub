"""題目產生器：MRV 回溯產生終盤 → 唯一解挖空 → 依技巧評級命中目標難度。

流程（每次嘗試 = 一個新終盤）：

第一階段「技巧命中」（最多 ``_PHASE1_ATTEMPTS[difficulty]`` 次）：
- easy：直接挖到 36–40 格，評級為 easy 即採用。
- medium / hard / expert：先盡量挖深（最多 58 格），此時盤面最難；若技巧等級低於目標就放棄此終盤。
  否則隨機把空格「補回」正解，每補一格就重新評級，補完若技巧等級跌破目標就撤回該格；
  直到空格數落入目標範圍且技巧等級恰為目標。
  為什麼先挖深再補回：直接挖到 41–52 格的盤面 95% 以上只需唯一數技巧，
  幾乎不可能隨機命中需要 Pair / X-Wing 的題目；從難的盤面往回補，命中率高一個數量級。

第二階段「降級」（第一階段用盡仍未命中時，最多 ``_PHASE2_ATTEMPTS`` 次）：
- 只要求空格數落在目標範圍、且技巧等級不高於目標；此時評級由挖空格數決定
  （評級 = max(技巧, 挖空)，見 difficulty.py），故回傳的 difficulty 仍與 rate_difficulty 一致。

最後保險：兩階段都失敗（實務上不會發生）時，回傳最後一個候選盤面並標上其實際評級，
保證函式一定結束、絕不無窮迴圈。

決定性：所有隨機都來自 ``random.Random(f"sudoku:{difficulty}:{seed}")``，重試上限以「次數」
而非「秒數」控制（以時間控制會讓不同機器產生不同題目），因此同 difficulty + 同 seed 必得同題。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .difficulty import DIFFICULTIES, HOLE_BANDS, rate_cells
from .solver import has_other_solution, random_full_grid, to_board

# 第一階段嘗試上限：依實測平均命中次數（medium≈4、hard≈5、expert≈2.5）抓足餘裕，
# 同時讓最壞情況仍在時間預算內（easy/medium/hard < 1 s、expert < 2 s）。
_PHASE1_ATTEMPTS: dict[str, int] = {"easy": 20, "medium": 20, "hard": 20, "expert": 40}
_PHASE2_ATTEMPTS = 30
_MAX_DIG = 58


@dataclass
class Puzzle:
    """產生結果。puzzle 為題目（0 = 空格），solution 為唯一終盤。"""

    puzzle: list[list[int]]
    solution: list[list[int]]
    difficulty: str
    seed: int | None
    technique_stats: dict[str, int] = field(default_factory=dict)


def _dig(rng: random.Random, cells: list[int], max_holes: int) -> int:
    """依隨機順序挖空，每挖一格都確認仍為唯一解；回傳最終空格數（就地修改 cells）。"""
    order = list(range(81))
    rng.shuffle(order)
    holes = cells.count(0)
    for i in order:
        if holes >= max_holes:
            break
        value = cells[i]
        if value and not has_other_solution(cells, i, value):
            cells[i] = 0
            holes += 1
    return holes


def _attempt_easy(rng: random.Random, solution: list[int]) -> list[int] | None:
    lo, hi = HOLE_BANDS["easy"]
    cells = list(solution)
    holes = _dig(rng, cells, rng.randint(lo, hi))
    if holes < lo:
        return None
    level, _, _ = rate_cells(cells)
    return cells if level == 0 else None


def _attempt_by_add_back(rng: random.Random, solution: list[int], target: int) -> list[int] | None:
    """先挖深再補回提示，使技巧等級恰為 target 且空格數落在目標範圍（見模組說明）。"""
    lo, hi = HOLE_BANDS[DIFFICULTIES[target]]
    cells = list(solution)
    holes = _dig(rng, cells, _MAX_DIG)
    _, tech, _ = rate_cells(cells)
    if tech < target:
        return None
    blanks = [i for i in range(81) if cells[i] == 0]
    rng.shuffle(blanks)
    for i in blanks:
        if holes <= hi and tech == target:
            break
        cells[i] = solution[i]  # 補回一格（補提示不會破壞唯一解）
        _, new_tech, _ = rate_cells(cells)
        if new_tech < target:
            cells[i] = 0  # 補了這格會變太簡單 → 撤回
        else:
            tech = new_tech
            holes -= 1
    if lo <= holes <= hi and tech == target:
        return cells
    return None


def _attempt_fallback(rng: random.Random, solution: list[int], target: int) -> list[int]:
    """降級：只挖到目標範圍，回傳挖好的盤面（是否符合由呼叫端以評級判斷）。"""
    lo, hi = HOLE_BANDS[DIFFICULTIES[target]]
    cells = list(solution)
    _dig(rng, cells, rng.randint(lo, hi))
    return cells


def generate_puzzle(difficulty: str, seed: int | None = None) -> Puzzle:
    """產生指定難度、唯一解的題目。

    difficulty 必須是 DIFFICULTIES 之一，否則拋 ValueError。
    同 difficulty + 同 seed 必回傳完全相同的題目；seed 為 None 時以系統亂數取種子
    （回傳的 Puzzle.seed 維持呼叫端傳入的值）。
    """
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"未知難度 {difficulty!r}，可用：{', '.join(DIFFICULTIES)}")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ValueError(f"seed 必須是整數或 None，收到 {seed!r}")
    actual_seed = seed if seed is not None else random.SystemRandom().randrange(2**63)
    # 字串種子在 Python 3 的 random 中是決定性的（以 SHA-512 雜湊，不受 PYTHONHASHSEED 影響）
    rng = random.Random(f"sudoku:{difficulty}:{actual_seed}")
    target = DIFFICULTIES.index(difficulty)

    def build(solution: list[int], cells: list[int]) -> Puzzle:
        level, _, stats = rate_cells(cells)
        return Puzzle(
            puzzle=to_board(cells),
            solution=to_board(solution),
            difficulty=DIFFICULTIES[level],
            seed=seed,
            technique_stats=stats,
        )

    # 第一階段：技巧命中
    for _ in range(_PHASE1_ATTEMPTS[difficulty]):
        solution = random_full_grid(rng)
        if target == 0:
            cells = _attempt_easy(rng, solution)
        else:
            cells = _attempt_by_add_back(rng, solution, target)
        if cells is not None:
            return build(solution, cells)

    # 第二階段：降級為「挖空格數決定難度」
    last: tuple[list[int], list[int]] | None = None
    for _ in range(_PHASE2_ATTEMPTS):
        solution = random_full_grid(rng)
        cells = _attempt_fallback(rng, solution, target)
        last = (solution, cells)
        lo, hi = HOLE_BANDS[difficulty]
        if lo <= cells.count(0) <= hi and rate_cells(cells)[0] == target:
            return build(solution, cells)

    # 最後保險：回傳最後一個候選並標上實際評級（不拋例外、不無窮迴圈）
    assert last is not None
    return build(*last)
