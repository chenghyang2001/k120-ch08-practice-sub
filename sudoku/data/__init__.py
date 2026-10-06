"""資料模組：自動存檔、遊玩紀錄、生涯統計、每日挑戰、使用者設定。

公開介面見 docs/interfaces.md 第 2 節。
"""
from .daily import DAILY_DIFFICULTY, compute_streak, daily_seed
from .models import GameRecord, GameState
from .storage import Storage

__all__ = [
    "DAILY_DIFFICULTY",
    "GameRecord",
    "GameState",
    "Storage",
    "compute_streak",
    "daily_seed",
]
