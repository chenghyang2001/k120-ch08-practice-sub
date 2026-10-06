"""主選單：標題、每日挑戰卡片、繼續遊戲、四個難度、紀錄 / 生涯 / 主題入口。"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import customtkinter as ctk

from sudoku.data import GameState
from sudoku.logic import DIFFICULTIES

from .controller import format_time
from .widgets import DIFFICULTY_NAMES, make_button, make_card, make_label, style_button

if TYPE_CHECKING:
    from .app_window import SudokuApp

DIFFICULTY_DESC = {
    "easy": "基礎排除，適合暖身",
    "medium": "需要區塊與數對",
    "hard": "會用到進階技巧",
    "expert": "X-Wing、Swordfish 等",
}


class MenuView(ctk.CTkFrame):
    """主選單畫面。saved 為目前存檔（None 表示沒有可繼續的遊戲）。"""

    def __init__(self, master, app: SudokuApp, saved: GameState | None) -> None:
        """建立主選單；saved 由 app 讀取後傳入，避免畫面自行碰存檔。"""
        t = app.theme
        super().__init__(master, fg_color=t.bg, corner_radius=0)
        self.app = app
        self.theme = t
        self.saved = saved

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=(26, 18))
        make_label(body, t, "數獨", size=t.font_size_title + 14, weight="bold").pack(pady=(4, 0))
        make_label(body, t, "SUDOKU · 動動腦，一天一題", muted=True).pack(pady=(0, 18))

        self._build_daily(body)
        if saved is not None:
            self._build_continue(body)
        self._build_difficulties(body)
        self._build_bottom(body)

    def _build_daily(self, parent) -> None:
        t = self.theme
        app = self.app
        today = date.today()
        done = app.storage.is_daily_completed(today)
        current, longest = app.storage.get_streak(today)
        card = make_card(parent, t)
        card.pack(fill="x", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        make_label(card, t, "📅 每日挑戰", size=t.font_size_ui + 3, weight="bold").grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 0))
        make_label(card, t, f"{today:%Y-%m-%d} · {DIFFICULTY_NAMES['medium']}", muted=True).grid(
            row=1, column=0, sticky="w", padx=18)
        streak_text = f"🔥 連續 {current} 天　最長 {longest} 天"
        make_label(card, t, streak_text, color=t.accent, weight="bold").grid(
            row=2, column=0, sticky="w", padx=18, pady=(2, 14))

        is_saved_daily = (
            self.saved is not None and self.saved.is_daily
            and self.saved.daily_date == today.isoformat()
        )
        if done:
            text = "✓ 今日已完成"
        elif is_saved_daily:
            text = "繼續挑戰"
        else:
            text = "開始挑戰"
        btn = make_button(card, t, text, app.request_daily, primary=not done, width=130,
                          height=42, weight="bold")
        btn.grid(row=0, column=1, rowspan=3, padx=18)
        if done:
            style_button(btn, t, enabled=False)

    def _build_continue(self, parent) -> None:
        t = self.theme
        saved = self.saved
        label = "每日挑戰" if saved.is_daily else DIFFICULTY_NAMES.get(saved.difficulty, "")
        text = f"▶ 繼續遊戲　{label} · {format_time(saved.elapsed_seconds)}"
        make_button(parent, t, text, self.app.continue_game, primary=True, height=48,
                    weight="bold").pack(fill="x", pady=(0, 12))

    def _build_difficulties(self, parent) -> None:
        t = self.theme
        make_label(parent, t, "新遊戲", muted=True, weight="bold").pack(anchor="w", pady=(4, 6))
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x")
        for index, level in enumerate(DIFFICULTIES):
            grid.grid_columnconfigure(index % 2, weight=1, uniform="diff")
            text = f"{DIFFICULTY_NAMES[level]}\n{DIFFICULTY_DESC[level]}"
            btn = make_button(grid, t, text, lambda lv=level: self.app.request_new_game(lv),
                              height=64, weight="bold")
            btn.grid(row=index // 2, column=index % 2, sticky="ew", padx=5, pady=5)

    def _build_bottom(self, parent) -> None:
        t = self.theme
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(16, 0))
        specs = (
            ("📋 遊玩紀錄", self.app.show_records),
            ("🏆 生涯總覽", self.app.show_career),
            ("🎨 主題", self.app.show_theme_picker),
        )
        for index, (text, command) in enumerate(specs):
            row.grid_columnconfigure(index, weight=1, uniform="bottom")
            make_button(row, t, text, command, height=46).grid(
                row=0, column=index, sticky="ew", padx=5)
        make_label(parent, t, f"目前主題：{t.name}", muted=True,
                   size=max(t.font_size_ui - 2, 9)).pack(side="bottom", pady=(8, 0))
