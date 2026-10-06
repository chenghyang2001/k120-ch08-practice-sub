"""主視窗 SudokuApp：管理畫面切換、主題、存檔流程、背景生成題目與鍵盤分派。"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import date

import customtkinter as ctk

from sudoku.data import DAILY_DIFFICULTY, GameState, Storage, daily_seed
from sudoku.logic import generate_puzzle
from sudoku.theme import DEFAULT_THEME, get_theme

from .career_view import CareerView
from .controller import GameController
from .game_view import GameView
from .menu_view import MenuView
from .records_view import RecordsView
from .theme_picker import ThemePicker
from .widgets import DIFFICULTY_NAMES, make_label, show_confirm

logger = logging.getLogger(__name__)

_POLL_MS = 50
DEFAULT_WIDTH = 560
DEFAULT_HEIGHT = 780


class LoadingView(ctk.CTkFrame):
    """題目生成中的等待畫面（文字動畫，主執行緒不被阻塞）。"""

    def __init__(self, master, app: SudokuApp, title: str) -> None:
        """顯示「生成中…」與難度名稱。"""
        t = app.theme
        super().__init__(master, fg_color=t.bg, corner_radius=0)
        self._dots = 0
        self._anim_id: str | None = None
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.place(relx=0.5, rely=0.42, anchor="center")
        make_label(box, t, "🧩", size=t.font_size_title + 20).pack()
        self.label = make_label(box, t, "生成中…", size=t.font_size_title - 4, weight="bold")
        self.label.pack(pady=(8, 2))
        make_label(box, t, title, muted=True).pack()
        self._animate()

    def _animate(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.label.configure(text="生成中" + "．" * self._dots)
        self._anim_id = self.after(350, self._animate)

    def destroy(self) -> None:
        """停止動畫後銷毀。"""
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except tk.TclError:
                pass
        super().destroy()


class SudokuApp(ctk.CTk):
    """數獨主視窗。storage 可注入（測試 / 截圖用暫存目錄）。"""

    def __init__(self, storage: Storage | None = None) -> None:
        """建立視窗、讀取主題設定並顯示主選單。"""
        super().__init__()
        self.storage = storage if storage is not None else Storage()
        self.theme = get_theme(self.storage.get_setting("theme", DEFAULT_THEME))
        ctk.set_appearance_mode("dark" if self.theme.is_dark else "light")
        self.title("數獨")
        self._fit_to_screen()
        self.configure(fg_color=self.theme.bg)

        self.view: ctk.CTkFrame | None = None
        self._factory: Callable[[], ctk.CTkFrame] | None = None
        self._gen_token = 0

        self.bind_all("<KeyPress>", self._on_key)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_menu()

    def _fit_to_screen(self) -> None:
        """預設 560×780；螢幕較矮（例如 1080p + 150% 縮放）時縮到可完整顯示的高度。"""
        try:
            scaling = self._get_window_scaling()
        except AttributeError:
            scaling = 1.0
        # 預留標題列與工作列的高度
        available = int(self.winfo_screenheight() / max(scaling, 0.1)) - 100
        height = max(560, min(DEFAULT_HEIGHT, available))
        self.geometry(f"{DEFAULT_WIDTH}x{height}")
        self.minsize(460, min(600, height))

    # ------------------------------------------------------------------
    # 畫面切換
    # ------------------------------------------------------------------
    def _set_view(self, factory: Callable[[], ctk.CTkFrame]) -> None:
        if self.view is not None:
            self.view.destroy()
        self._factory = factory
        self.view = factory()
        self.view.pack(fill="both", expand=True)
        self.focus_set()

    def show_menu(self) -> None:
        """顯示主選單（重新讀取存檔資訊）。"""
        self._gen_token += 1  # 讓進行中的生成結果失效
        self._set_view(lambda: MenuView(self, self, self.storage.load_game()))

    def show_records(self) -> None:
        """顯示遊玩紀錄。"""
        self._set_view(lambda: RecordsView(self, self))

    def show_career(self) -> None:
        """顯示生涯總覽。"""
        self._set_view(lambda: CareerView(self, self))

    def show_theme_picker(self) -> None:
        """顯示主題選單。"""
        self._set_view(lambda: ThemePicker(self, self))

    def apply_theme(self, key: str) -> None:
        """套用主題、保存設定並以新主題重建目前畫面。"""
        self.theme = get_theme(key)
        self.storage.set_setting("theme", self.theme.key)
        ctk.set_appearance_mode("dark" if self.theme.is_dark else "light")
        self.configure(fg_color=self.theme.bg)
        if self._factory is not None:
            self._set_view(self._factory)

    # ------------------------------------------------------------------
    # 開局流程
    # ------------------------------------------------------------------
    def _abandon_saved(self) -> None:
        """把目前存檔記為放棄（completed=False）並清除。"""
        state = self.storage.load_game()
        self.storage.clear_game()
        if state is None:
            return
        try:
            self.storage.add_record(GameController(state).make_record(completed=False))
        except ValueError as exc:
            logger.error("寫入放棄紀錄失敗：%s", exc)

    def request_new_game(self, difficulty: str, daily: bool = False) -> None:
        """開新局；已有存檔時先詢問是否放棄舊局。"""
        def start() -> None:
            self._abandon_saved()
            self._generate(difficulty, daily)

        if self.storage.has_saved_game():
            saved = self.storage.load_game()
            if saved is not None:
                name = "每日挑戰" if saved.is_daily else DIFFICULTY_NAMES.get(saved.difficulty, "")
                show_confirm(self.view, self.theme, "開始新的一局？",
                             f"目前有一局「{name}」尚未完成，\n開新局會把它記為放棄。",
                             start, yes_text="放棄並開新局")
                return
        self._generate(difficulty, daily)

    def request_daily(self) -> None:
        """每日挑戰：今日存檔則續玩，已完成則不動作，否則開今日題目。"""
        today = date.today()
        if self.storage.is_daily_completed(today):
            return
        saved = self.storage.load_game()
        if saved is not None and saved.is_daily and saved.daily_date == today.isoformat():
            self._show_game(saved)
            return
        self.request_new_game(DAILY_DIFFICULTY, daily=True)

    def continue_game(self) -> None:
        """讀取存檔繼續遊戲；存檔遺失或損毀時回主選單。"""
        state = self.storage.load_game()
        if state is None:
            self.show_menu()
            return
        self._show_game(state)

    def _generate(self, difficulty: str, daily: bool) -> None:
        """在背景執行緒生成題目，以 after 輪詢結果回主執行緒。"""
        today = date.today()
        seed = daily_seed(today) if daily else None
        title = f"每日挑戰 · {DIFFICULTY_NAMES[difficulty]}" if daily else DIFFICULTY_NAMES[difficulty]
        self._gen_token += 1
        token = self._gen_token
        self._set_view(lambda: LoadingView(self, self, title))
        result_queue: queue.Queue = queue.Queue()

        def worker() -> None:
            try:
                result_queue.put(("ok", generate_puzzle(difficulty, seed)))
            except Exception as exc:
                logger.exception("生成題目失敗")
                result_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

        def poll() -> None:
            if token != self._gen_token:
                return
            try:
                status, payload = result_queue.get_nowait()
            except queue.Empty:
                self.after(_POLL_MS, poll)
                return
            if status == "error":
                self._show_error(f"生成題目失敗：{payload}")
                return
            state = GameState.new(payload.puzzle, payload.solution, difficulty,
                                  is_daily=daily, daily_date=today.isoformat() if daily else None)
            self.storage.save_game(state)
            self._show_game(state)

        self.after(_POLL_MS, poll)

    def _show_error(self, message: str) -> None:
        self.show_menu()
        show_confirm(self.view, self.theme, "發生錯誤", message, lambda: None,
                     yes_text="知道了", no_text="關閉")

    def _show_game(self, state: GameState) -> None:
        controller = GameController(state, self.storage)
        self._set_view(lambda: GameView(self, self, controller))

    # ------------------------------------------------------------------
    # 遊戲結束 / 離開
    # ------------------------------------------------------------------
    def leave_game(self, controller: GameController) -> None:
        """從遊戲返回主選單：未完成則存檔保留（不算放棄）。"""
        if not controller.completed:
            self.storage.save_game(controller.state)
        self.show_menu()

    def complete_game(self, controller: GameController) -> dict:
        """完成一局：清存檔 → 寫紀錄 → 每日挑戰打卡；回傳結算資訊（是否新最佳等）。"""
        state = controller.state
        best_before = self.storage.get_career_stats().get(state.difficulty, {}).get("best_time")
        self.storage.clear_game()
        try:
            self.storage.add_record(controller.make_record(completed=True))
        except ValueError as exc:
            logger.error("寫入完成紀錄失敗：%s", exc)
        summary: dict = {
            "new_best": best_before is None or state.elapsed_seconds < best_before,
            "streak": 0,
        }
        if state.is_daily and state.daily_date:
            day = date.fromisoformat(state.daily_date)
            self.storage.mark_daily_completed(day)
            summary["streak"] = self.storage.get_streak(date.today())[0]
        return summary

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _on_key(self, event: tk.Event) -> None:
        handler = getattr(self.view, "handle_key", None)
        if handler is not None:
            handler(event)

    def on_close(self) -> None:
        """關閉視窗：讓遊戲畫面存檔、flush 計時後銷毀。"""
        closer = getattr(self.view, "on_app_close", None)
        if closer is not None:
            closer()
        self.storage.flush()
        self.destroy()

