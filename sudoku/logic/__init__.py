"""數獨遊戲邏輯：題目生成、解題、難度評級、提示。純 Python，不依賴任何 UI / 存檔模組。"""

from .difficulty import DIFFICULTIES, rate_difficulty
from .generator import Puzzle, generate_puzzle
from .hints import get_hint, is_complete
from .solver import Board, count_solutions, is_valid_placement, solve
from .techniques import TECHNIQUES

__all__ = [
    "DIFFICULTIES",
    "TECHNIQUES",
    "Board",
    "Puzzle",
    "count_solutions",
    "generate_puzzle",
    "get_hint",
    "is_complete",
    "is_valid_placement",
    "rate_difficulty",
    "solve",
]
