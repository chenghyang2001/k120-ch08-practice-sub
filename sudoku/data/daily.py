"""每日挑戰：日期種子與連續天數計算（純函式，不碰檔案，方便單元測試）。"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

# 每日挑戰固定使用的難度（合約規定）
DAILY_DIFFICULTY: str = "medium"


def daily_seed(day: date) -> int:
    """以日期產生每日挑戰種子，例如 2026-10-06 → 20261006。

    同一天必定得到同一個整數，交給 logic.generate_puzzle 即可得到同一題。
    """
    if not isinstance(day, date):
        raise TypeError(f"day 必須是 datetime.date，實際為 {type(day).__name__}")
    return day.year * 10000 + day.month * 100 + day.day


def compute_streak(completed_days: Iterable[date], today: date) -> tuple[int, int]:
    """由已完成日期集合計算 (目前連續天數, 最長連續天數)。

    規則：
    - 今天已完成 → 從今天往回數。
    - 今天未完成但昨天完成 → 連續仍有效，從昨天往回數（今天還有機會接上）。
    - 昨天也沒完成 → 目前連續為 0。
    - 用 timedelta 逐日回推，跨月、跨年、閏年都自然正確。
    - 晚於 today 的日期（例如系統時鐘被調回）不計入目前連續，但計入最長連續。
    """
    days = set(completed_days)

    anchor = today if today in days else today - timedelta(days=1)
    current = 0
    while anchor in days:
        current += 1
        anchor -= timedelta(days=1)

    longest = 0
    run = 0
    previous: date | None = None
    for day in sorted(days):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    return current, max(longest, current)
