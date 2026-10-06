"""提示與完成判定。"""

from __future__ import annotations

import random

from .solver import Board, validate_board


def get_hint(
    board: Board, solution: Board, rng: random.Random | None = None
) -> tuple[int, int, int] | None:
    """從「空格或與終盤不同」的格子中隨機挑一格，回 (row, col, 正確值)；全部正確回 None。

    錯填格也列入候選，讓提示能順便修正玩家的錯誤。rng 為 None 時使用新的 random.Random()。
    盤面形狀不合法拋 ValueError。不修改輸入。
    """
    validate_board(board)
    validate_board(solution)
    wrong = [
        (r, c)
        for r in range(9)
        for c in range(9)
        if board[r][c] == 0 or board[r][c] != solution[r][c]
    ]
    if not wrong:
        return None
    rng = rng if rng is not None else random.Random()
    r, c = rng.choice(wrong)
    return r, c, solution[r][c]


def is_complete(board: Board, solution: Board) -> bool:
    """盤面是否已全部填滿且與終盤完全一致。盤面形狀不合法拋 ValueError。"""
    validate_board(board)
    validate_board(solution)
    return all(
        board[r][c] != 0 and board[r][c] == solution[r][c] for r in range(9) for c in range(9)
    )
