"""sudoku.data.Storage 測試：自動存檔、節流、壞檔降級、設定。"""
import json
import logging

import pytest

from sudoku.data import GameState, Storage

SOLUTION = [[(r * 3 + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
PUZZLE = [[v if (r + c) % 3 else 0 for c, v in enumerate(row)] for r, row in enumerate(SOLUTION)]


class FakeClock:
    """可手動推進的單調時鐘，讓節流測試不必真的 sleep。"""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def storage(tmp_path, clock):
    return Storage(tmp_path, timer_interval=5, clock=clock)


def new_state(elapsed=0):
    state = GameState.new(PUZZLE, SOLUTION, "medium")
    state.elapsed_seconds = elapsed
    return state


def disk_elapsed(storage):
    with storage.save_path.open(encoding="utf-8") as f:
        return json.load(f)["game"]["elapsed_seconds"]


def test_default_base_dir_uses_platformdirs(monkeypatch, tmp_path):
    import sudoku.data.storage as mod

    monkeypatch.setattr(mod.platformdirs, "user_data_dir", lambda *a, **k: str(tmp_path / "ud"))
    assert Storage().base_dir == tmp_path / "ud"
    assert (tmp_path / "ud").is_dir()


def test_save_load_roundtrip(storage):
    state = new_state(42)
    state.board[0][0] = 4
    state.notes[3][3] = [1, 2]
    state.undo_stack = [{"op": "note", "cell": [3, 3]}]
    storage.save_game(state)
    data = json.loads(storage.save_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert storage.load_game() == state


def test_load_without_file_returns_none(storage):
    assert storage.load_game() is None
    assert not storage.has_saved_game()


def test_atomic_write_leaves_no_tmp(storage, tmp_path):
    storage.save_game(new_state())
    storage.save_game(new_state(3))
    assert [p.name for p in tmp_path.iterdir()] == ["savegame.json"]


def test_atomic_write_failure_keeps_old_file(storage, tmp_path, monkeypatch):
    storage.save_game(new_state(10))
    import sudoku.data.storage as mod

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(mod.os, "replace", boom)
    storage.save_game(new_state(99))  # 不得拋例外
    monkeypatch.undo()
    assert disk_elapsed(storage) == 10
    assert not list(tmp_path.glob("*.tmp"))
    storage.flush()  # 失敗的狀態保留到 flush 再寫
    assert disk_elapsed(storage) == 99


def test_has_and_clear(storage):
    storage.save_game(new_state())
    assert storage.has_saved_game()
    storage.clear_game()
    assert not storage.has_saved_game()
    assert storage.load_game() is None
    storage.clear_game()  # 重複清除不報錯


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        json.dumps({"game": {}}),  # 缺 schema_version
        json.dumps({"schema_version": 999, "game": {}}),
        json.dumps({"schema_version": 1, "game": {"board": []}}),  # from_dict ValueError
        json.dumps({"schema_version": 1}),
    ],
)
def test_corrupt_save_backed_up(storage, tmp_path, caplog, content):
    storage.save_path.write_text(content, encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert storage.load_game() is None
    assert not storage.save_path.exists()
    backups = list(tmp_path.glob("savegame.json.*.corrupt"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == content
    assert any("損毀" in r.message for r in caplog.records)
    # 降級後可正常開新局
    storage.save_game(new_state(1))
    assert storage.load_game().elapsed_seconds == 1


def test_corrupt_binary_save(storage, tmp_path):
    storage.save_path.write_bytes(b"\xff\xfe\x00garbage")
    assert storage.load_game() is None
    assert list(tmp_path.glob("*.corrupt"))


def test_save_timer_throttles(storage, clock):
    state = new_state(0)
    storage.save_timer(state)  # 第一次立即寫
    assert disk_elapsed(storage) == 0
    for sec in range(1, 5):
        clock.advance(1)
        state.elapsed_seconds = sec
        storage.save_timer(state)
        assert disk_elapsed(storage) == 0  # 節流中
    clock.advance(1)
    state.elapsed_seconds = 5
    storage.save_timer(state)
    assert disk_elapsed(storage) == 5


def test_save_timer_write_count(storage, clock, monkeypatch):
    calls = []
    original = storage._atomic_write_json
    monkeypatch.setattr(storage, "_atomic_write_json", lambda *a: (calls.append(1), original(*a)))
    state = new_state()
    for sec in range(60):
        state.elapsed_seconds = sec
        storage.save_timer(state)
        clock.advance(1)
    assert len(calls) == 12  # 60 秒 / 5 秒


def test_flush_writes_pending(storage, clock):
    state = new_state(0)
    storage.save_timer(state)
    clock.advance(2)
    state.elapsed_seconds = 2
    storage.save_timer(state)
    assert disk_elapsed(storage) == 0
    storage.flush()
    assert disk_elapsed(storage) == 2
    storage.flush()  # 沒有 pending 時為 no-op


def test_reopen_error_within_interval(tmp_path, clock):
    """模擬每秒計時後直接關閉（未 flush）：重開誤差不超過節流間隔。"""
    s1 = Storage(tmp_path, timer_interval=5, clock=clock)
    state = new_state()
    for sec in range(1, 38):
        clock.advance(1)
        state.elapsed_seconds = sec
        s1.save_timer(state)
    loaded = Storage(tmp_path).load_game()
    assert 37 - loaded.elapsed_seconds <= 5


def test_save_game_resets_throttle(storage, clock):
    state = new_state(0)
    storage.save_timer(state)
    clock.advance(3)
    state.elapsed_seconds = 3
    storage.save_game(state)  # 填入立即寫
    assert disk_elapsed(storage) == 3
    clock.advance(1)
    state.elapsed_seconds = 4
    storage.save_timer(state)
    assert disk_elapsed(storage) == 3


def test_clear_discards_pending(storage, clock):
    state = new_state(0)
    storage.save_timer(state)
    clock.advance(1)
    storage.save_timer(state)
    storage.clear_game()
    storage.flush()
    assert not storage.save_path.exists()


def test_load_game_flushes_pending(storage, clock):
    state = new_state(0)
    storage.save_timer(state)
    clock.advance(1)
    state.elapsed_seconds = 1
    storage.save_timer(state)
    assert storage.load_game().elapsed_seconds == 1


def test_settings_roundtrip(tmp_path):
    storage = Storage(tmp_path)
    assert storage.get_setting("theme") is None
    assert storage.get_setting("theme", "light") == "light"
    storage.set_setting("theme", "暗夜")
    storage.set_setting("volume", 3)
    reopened = Storage(tmp_path)
    assert reopened.get_setting("theme") == "暗夜"
    assert reopened.get_setting("volume") == 3


def test_settings_not_serializable(tmp_path):
    with pytest.raises(TypeError):
        Storage(tmp_path).set_setting("x", object())


def test_settings_corrupt_falls_back(tmp_path):
    storage = Storage(tmp_path)
    storage.settings_path.write_text("{oops", encoding="utf-8")
    assert storage.get_setting("theme", "light") == "light"
    assert list(tmp_path.glob("settings.json.*.corrupt"))
    storage.set_setting("theme", "dark")
    assert storage.get_setting("theme") == "dark"
