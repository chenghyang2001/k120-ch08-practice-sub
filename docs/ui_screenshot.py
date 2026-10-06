"""程式化啟動數獨 App 並截圖驗證各畫面（輸出到 docs/screenshots/*.png）。

用法：PYTHONUTF8=1 uv run python docs/ui_screenshot.py
使用暫存目錄的 Storage，不會動到使用者真正的存檔。
"""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "docs" / "screenshots"


def make_dpi_aware() -> None:
    """Windows 上宣告 DPI 感知，讓視窗座標與 ImageGrab 的實體像素一致。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError) as exc:
            print(f"警告：無法設定 DPI 感知：{exc}", file=sys.stderr)


def seed_history(storage) -> None:
    """寫入幾筆假紀錄與每日挑戰打卡，讓紀錄 / 生涯畫面有內容。"""
    from sudoku.data import GameRecord

    now = datetime.now()
    samples = [
        ("easy", 312, 0, 0, True, False, 1),
        ("easy", 268, 1, 0, True, False, 2),
        ("medium", 655, 2, 1, True, True, 1),
        ("medium", 120, 1, 0, False, False, 3),
        ("hard", 1104, 0, 2, True, False, 4),
        ("expert", 1888, 3, 3, True, False, 5),
        ("medium", 702, 0, 0, True, True, 2),
    ]
    for diff, secs, mistakes, hints, done, daily, days_ago in samples:
        storage.add_record(GameRecord(
            finished_at=(now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
            difficulty=diff, elapsed_seconds=secs, mistakes=mistakes, hints_used=hints,
            completed=done, is_daily=daily))
    for days_ago in (1, 2, 3):
        storage.mark_daily_completed(date.today() - timedelta(days=days_ago))


class Shooter:
    """包住 App 的截圖小工具。"""

    def __init__(self, app) -> None:
        self.app = app

    def pump(self, seconds: float = 0.4) -> None:
        end = time.time() + seconds
        while time.time() < end:
            self.app.update()
            time.sleep(0.02)

    def wait_for(self, predicate, timeout: float = 30.0) -> None:
        end = time.time() + timeout
        while time.time() < end:
            self.app.update()
            if predicate():
                return
            time.sleep(0.03)
        raise TimeoutError("等待畫面逾時")

    def shot(self, name: str) -> Path:
        from PIL import ImageGrab

        self.app.lift()
        self.app.attributes("-topmost", True)
        self.pump(0.6)
        x, y = self.app.winfo_rootx(), self.app.winfo_rooty()
        w, h = self.app.winfo_width(), self.app.winfo_height()
        image = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        path = OUT_DIR / f"{name}.png"
        image.save(path)
        print(f"已截圖：{path}（{w}×{h}）")
        return path


def play_some_moves(view) -> None:
    """選格、填正確與錯誤數字、寫筆記、用一次提示。"""
    ctl = view.controller
    state = ctl.state
    empties = [(r, c) for r in range(9) for c in range(9) if state.board[r][c] == 0]
    # 兩個正確數字
    for r, c in empties[:2]:
        ctl.select(r, c)
        ctl.fill(state.solution[r][c])
    # 一個錯誤數字
    r, c = empties[2]
    ctl.select(r, c)
    ctl.fill(state.solution[r][c] % 9 + 1)
    # 兩格筆記
    ctl.toggle_notes_mode()
    for r, c in empties[5:7]:
        ctl.select(r, c)
        for digit in (1, 4, 5, 9):
            ctl.toggle_note(digit)
        ctl.toggle_note(state.solution[r][c])
    ctl.toggle_notes_mode()
    ctl.hint()
    # 最後選一個有數字的格子，展示相同數字高亮
    r, c = empties[0]
    ctl.select(r, c)
    view.refresh()


def finish_game(view) -> None:
    """把剩下的空格全部填上正確答案，觸發完成結算。"""
    ctl = view.controller
    state = ctl.state
    for r in range(9):
        for c in range(9):
            if state.board[r][c] != state.solution[r][c] and not ctl.is_locked(r, c):
                ctl.select(r, c)
                ctl.fill(state.solution[r][c])
    view._after_action()


def main() -> None:
    make_dpi_aware()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from sudoku.data import Storage
    from sudoku.ui.app_window import SudokuApp
    from sudoku.ui.game_view import GameView

    with tempfile.TemporaryDirectory() as tmp:
        storage = Storage(Path(tmp))
        seed_history(storage)
        app = SudokuApp(storage)
        app.geometry("+40+10")
        s = Shooter(app)
        try:
            s.pump(1.0)
            s.shot("01_menu")

            app.request_new_game("easy")
            s.wait_for(lambda: isinstance(app.view, GameView))
            play_some_moves(app.view)
            s.shot("02_game")

            app.view.toggle_pause()
            s.shot("03_paused")
            app.view.toggle_pause()

            app.apply_theme("dark")
            s.wait_for(lambda: isinstance(app.view, GameView))
            app.view.refresh()
            s.shot("04_game_dark")

            app.view.app_leave()
            s.shot("05_menu_dark_continue")

            app.show_career()
            s.shot("06_career")

            app.show_records()
            s.shot("07_records")

            app.show_theme_picker()
            s.shot("08_theme_picker")

            app.continue_game()
            s.wait_for(lambda: isinstance(app.view, GameView))
            finish_game(app.view)
            s.shot("09_result")

            app.apply_theme("warm")
            app.request_new_game("medium")
            s.pump(0.3)
            s.shot("10_confirm_new_game")
        finally:
            app.on_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        raise
