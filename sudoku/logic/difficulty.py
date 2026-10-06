"""難度評級：結合「人類技巧使用情形」與「挖空格數」。

評級 = max(技巧等級, 挖空等級)，兩者皆為 0–3（對應 easy / medium / hard / expert）：

技巧等級（只用 techniques.solve_with_techniques，不猜測）：
    0 easy    只需 naked / hidden single
    1 medium  用到進階刪減（naked/hidden pair、pointing、box-line）恰 1 次
    2 hard    用到 X-Wing 恰 1 次，或進階刪減 >= 2 次（「多次進階技巧」）
    3 expert  用到 Swordfish、X-Wing >= 2 次，或技巧解題器解不完

挖空等級（空格數）：<=40 → 0、41–46 → 1、47–52 → 2、>=53 → 3

為什麼取 max：挖空越多，即使只用唯一數技巧，人類掃描量也顯著增加；反之挖空少但需要
X-Wing 的盤面仍屬困難。取 max 讓兩個維度都只會「把難度往上推」，評級可單從盤面重現。

解不完（需要猜測）的策略：技巧解題器卡住代表需要 XY-Wing、鏈或試誤等本模組未實作的手法，
一律視為「專家」。產生器只會在目標為 expert 時接受這類盤面；其餘難度遇到會被淘汰或補回提示數。
"""

from __future__ import annotations

from .solver import Board, to_flat
from .techniques import TechniqueResult, solve_with_techniques

DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard", "expert")

# 各難度目標挖空範圍（產生器使用；評級用下方 hole_level）
HOLE_BANDS: dict[str, tuple[int, int]] = {
    "easy": (36, 40),
    "medium": (41, 46),
    "hard": (47, 52),
    "expert": (53, 58),
}

_ADVANCED = ("naked_pair", "hidden_pair", "pointing", "box_line")


def technique_level(result: TechniqueResult) -> int:
    """依技巧解題結果回傳 0–3 的技巧等級（定義見模組 docstring）。"""
    s = result.stats
    if not result.solved or s["swordfish"] >= 1 or s["x_wing"] >= 2:
        return 3
    advanced = sum(s[name] for name in _ADVANCED)
    if s["x_wing"] == 1 or advanced >= 2:
        return 2
    if advanced == 1:
        return 1
    return 0


def hole_level(holes: int) -> int:
    """依空格數回傳 0–3 的挖空等級。"""
    if holes <= 40:
        return 0
    if holes <= 46:
        return 1
    if holes <= 52:
        return 2
    return 3


def rate_cells(cells: list[int]) -> tuple[int, int, dict[str, int]]:
    """評估扁平盤面，回 (最終等級, 技巧等級, technique_stats)。供產生器內部重複使用。"""
    result = solve_with_techniques(cells)
    tech = technique_level(result)
    holes = cells.count(0)
    stats = dict(result.stats)
    # 卡住時記錄剩餘未解格數，讓 UI / 除錯能看出「需要猜測」
    stats["unsolved"] = result.cells.count(0) if not result.solved else 0
    return max(tech, hole_level(holes)), tech, stats


def rate_difficulty(puzzle: Board) -> tuple[str, dict[str, int]]:
    """用人類技巧解題器評級盤面，回 (difficulty, technique_stats)。

    technique_stats 含 TECHNIQUES 全部鍵（未使用為 0）以及 ``unsolved``（技巧解不完時剩餘空格數）。
    盤面形狀或數值不合法拋 ValueError；已填數字互相衝突的盤面視為解不完 → "expert"。
    不修改輸入。
    """
    level, _, stats = rate_cells(to_flat(puzzle))
    return DIFFICULTIES[level], stats
