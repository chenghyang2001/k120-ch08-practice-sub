"""sudoku.data 遊玩紀錄與生涯統計測試。"""
import json

import pytest

from sudoku.data import GameRecord, Storage


def rec(finished_at, difficulty="easy", elapsed=100, mistakes=0, hints=0, completed=True, daily=False):
    return GameRecord(finished_at, difficulty, elapsed, mistakes, hints, completed, daily)


@pytest.fixture
def storage(tmp_path):
    s = Storage(tmp_path)
    for r in [
        rec("2026-10-01T09:00:00", "easy", 300, 0, 0, True, False),
        rec("2026-10-03T21:30:00", "easy", 200, 2, 1, True, True),
        rec("2026-10-02T12:00:00", "medium", 500, 1, 3, False, False),
        rec("2026-10-06T23:59:59", "hard", 900, 0, 0, True, True),
        rec("2026-09-30T08:00:00", "easy", 250, 0, 2, False, False),
    ]:
        s.add_record(r)
    return s


def times(records):
    return [r.finished_at for r in records]


def test_query_all_sorted_new_to_old(storage):
    assert times(storage.query_records()) == [
        "2026-10-06T23:59:59", "2026-10-03T21:30:00", "2026-10-02T12:00:00",
        "2026-10-01T09:00:00", "2026-09-30T08:00:00",
    ]


def test_query_empty(tmp_path):
    assert Storage(tmp_path).query_records() == []


def test_filter_difficulty(storage):
    assert {r.difficulty for r in storage.query_records(difficulty="easy")} == {"easy"}
    assert len(storage.query_records(difficulty="easy")) == 3
    assert storage.query_records(difficulty="expert") == []


def test_filter_completed_and_daily(storage):
    assert len(storage.query_records(completed=True)) == 3
    assert len(storage.query_records(completed=False)) == 2
    assert times(storage.query_records(is_daily=True)) == ["2026-10-06T23:59:59", "2026-10-03T21:30:00"]
    assert len(storage.query_records(is_daily=False)) == 3


def test_filter_date_range_inclusive(storage):
    got = storage.query_records(since="2026-10-01", until="2026-10-06")
    assert times(got) == [
        "2026-10-06T23:59:59", "2026-10-03T21:30:00", "2026-10-02T12:00:00", "2026-10-01T09:00:00",
    ]
    assert times(storage.query_records(until="2026-09-30")) == ["2026-09-30T08:00:00"]
    assert times(storage.query_records(since="2026-10-03T21:30:00", until="2026-10-03T21:30:00")) == [
        "2026-10-03T21:30:00"
    ]


def test_filter_combined(storage):
    got = storage.query_records(difficulty="easy", completed=True, since="2026-10-02")
    assert times(got) == ["2026-10-03T21:30:00"]


def test_invalid_filters_raise(storage):
    with pytest.raises(ValueError):
        storage.query_records(difficulty="insane")
    with pytest.raises(ValueError):
        storage.query_records(since="10/06/2026")


def test_timezone_aware_records_comparable(tmp_path):
    s = Storage(tmp_path)
    s.add_record(rec("2026-10-05T10:00:00+08:00"))
    s.add_record(rec("2026-10-05T11:00:00"))
    assert len(s.query_records(since="2026-01-01")) == 2


def test_add_invalid_record_raises(tmp_path):
    with pytest.raises(ValueError):
        Storage(tmp_path).add_record(rec("not-a-date"))


def test_bad_lines_skipped(storage):
    with storage.records_path.open("a", encoding="utf-8") as f:
        f.write("{broken json\n")
        f.write("\n")
        f.write(json.dumps({"schema_version": 1, "difficulty": "easy"}) + "\n")
        f.write(json.dumps([1, 2]) + "\n")
        f.write('{"schema_version": 1, "finished_at": "2026-10-07T00:00:00", "diffic')  # 寫到一半
    assert len(storage.query_records()) == 5
    storage.add_record(rec("2026-10-08T00:00:00"))  # 壞尾行之後追加，新紀錄不可被黏進壞行
    records = storage.query_records()
    assert len(records) == 6 and records[0].finished_at == "2026-10-08T00:00:00"


def test_career_stats(storage):
    stats = storage.get_career_stats()
    assert set(stats) == {"easy", "medium", "hard", "expert"}
    assert stats["easy"] == {
        "played": 3, "completed": 2, "best_time": 200, "avg_time": 250.0, "zero_mistake_wins": 1,
    }
    assert stats["medium"] == {
        "played": 1, "completed": 0, "best_time": None, "avg_time": None, "zero_mistake_wins": 0,
    }
    assert stats["hard"]["best_time"] == 900 and stats["hard"]["zero_mistake_wins"] == 1
    assert stats["expert"] == {
        "played": 0, "completed": 0, "best_time": None, "avg_time": None, "zero_mistake_wins": 0,
    }


def test_career_stats_empty(tmp_path):
    stats = Storage(tmp_path).get_career_stats()
    assert len(stats) == 4
    assert all(v["best_time"] is None and v["avg_time"] is None and v["played"] == 0 for v in stats.values())
