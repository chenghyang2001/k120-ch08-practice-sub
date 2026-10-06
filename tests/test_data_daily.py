"""sudoku.data 每日挑戰測試：日期種子、完成標記、連續天數。"""
from datetime import date, timedelta

import pytest

from sudoku.data import DAILY_DIFFICULTY, Storage, compute_streak, daily_seed


def test_daily_seed():
    assert daily_seed(date(2026, 10, 6)) == 20261006
    assert daily_seed(date(2027, 1, 1)) == 20270101
    assert daily_seed(date(2026, 10, 6)) == daily_seed(date(2026, 10, 6))
    assert DAILY_DIFFICULTY == "medium"


def test_daily_seed_rejects_non_date():
    with pytest.raises(TypeError):
        daily_seed("2026-10-06")


def days_from(start, count):
    return [start + timedelta(days=i) for i in range(count)]


def test_streak_consecutive_including_today():
    assert compute_streak(days_from(date(2026, 10, 1), 6), date(2026, 10, 6)) == (6, 6)


def test_streak_today_not_done_counts_yesterday():
    assert compute_streak(days_from(date(2026, 10, 1), 5), date(2026, 10, 6)) == (5, 5)


def test_streak_broken():
    done = days_from(date(2026, 9, 1), 10) + days_from(date(2026, 10, 3), 2)  # 10/3, 10/4
    assert compute_streak(done, date(2026, 10, 6)) == (0, 10)
    assert compute_streak(done, date(2026, 10, 5)) == (2, 10)


def test_streak_cross_month():
    done = days_from(date(2026, 9, 28), 5)  # 9/28 ~ 10/2
    assert compute_streak(done, date(2026, 10, 2)) == (5, 5)


def test_streak_cross_year():
    done = days_from(date(2026, 12, 30), 4)  # 12/30 ~ 1/2
    assert compute_streak(done, date(2027, 1, 2)) == (4, 4)
    assert compute_streak(done, date(2027, 1, 3)) == (4, 4)
    assert compute_streak(done, date(2027, 1, 4)) == (0, 4)


def test_streak_leap_day():
    done = days_from(date(2028, 2, 27), 4)  # 2/27, 2/28, 2/29, 3/1
    assert compute_streak(done, date(2028, 3, 1)) == (4, 4)


def test_streak_empty():
    assert compute_streak([], date(2026, 10, 6)) == (0, 0)


def test_storage_mark_and_query(tmp_path):
    s = Storage(tmp_path)
    today = date(2026, 10, 6)
    assert not s.is_daily_completed(today)
    for d in days_from(date(2026, 10, 3), 4):
        s.mark_daily_completed(d)
    s.mark_daily_completed(today)  # 重複標記
    assert s.is_daily_completed(today)
    assert Storage(tmp_path).get_streak(today) == (4, 4)
    assert s.get_streak(date(2026, 10, 8)) == (0, 4)


def test_storage_get_streak_default_today(tmp_path):
    s = Storage(tmp_path)
    s.mark_daily_completed(date.today())
    assert s.get_streak() == (1, 1)


def test_storage_daily_corrupt(tmp_path):
    s = Storage(tmp_path)
    s.daily_path.write_text("garbage", encoding="utf-8")
    assert s.get_streak(date(2026, 10, 6)) == (0, 0)
    assert list(tmp_path.glob("daily.json.*.corrupt"))
    s.mark_daily_completed(date(2026, 10, 6))
    assert s.get_streak(date(2026, 10, 6)) == (1, 1)
