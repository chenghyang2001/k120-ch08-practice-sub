"""生涯總覽：每日挑戰連續天數 + 四難度統計卡片（局數、完成、最佳 / 平均時間、零錯誤）。"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import customtkinter as ctk

from sudoku.logic import DIFFICULTIES

from .controller import format_time
from .widgets import DIFFICULTY_NAMES, make_card, make_label, screen_header

if TYPE_CHECKING:
    from .app_window import SudokuApp


def _fmt_time(value: float | None) -> str:
    return "—" if value is None else format_time(round(value))


class CareerView(ctk.CTkFrame):
    """生涯總覽畫面。"""

    def __init__(self, master, app: SudokuApp) -> None:
        """讀取生涯統計與連續天數並排版。"""
        t = app.theme
        super().__init__(master, fg_color=t.bg, corner_radius=0)
        self.app = app
        self.theme = t
        screen_header(self, t, "🏆 生涯總覽", app.show_menu).pack(
            fill="x", padx=20, pady=(18, 12))

        stats = app.storage.get_career_stats()
        current, longest = app.storage.get_streak(date.today())
        self._build_overview(stats, current, longest)

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=14, pady=(4, 20))
        for index, level in enumerate(DIFFICULTIES):
            grid.grid_columnconfigure(index % 2, weight=1, uniform="career")
            grid.grid_rowconfigure(index // 2, weight=1)
            self._difficulty_card(grid, level, stats.get(level, {})).grid(
                row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)

    def _build_overview(self, stats: dict, current: int, longest: int) -> None:
        t = self.theme
        card = make_card(self, t)
        card.pack(fill="x", padx=20, pady=(0, 6))
        played = sum(s.get("played", 0) for s in stats.values())
        wins = sum(s.get("completed", 0) for s in stats.values())
        items = (
            ("🔥 目前連續", f"{current} 天", t.accent),
            ("最長連續", f"{longest} 天", t.text),
            ("總局數", str(played), t.text),
            ("完成", str(wins), t.hint_text),
        )
        for index, (name, value, color) in enumerate(items):
            card.grid_columnconfigure(index, weight=1, uniform="ov")
            make_label(card, t, value, size=t.font_size_title - 4, weight="bold",
                       color=color).grid(row=0, column=index, pady=(14, 0))
            make_label(card, t, name, muted=True).grid(row=1, column=index, pady=(0, 14))

    def _difficulty_card(self, parent, level: str, data: dict) -> ctk.CTkFrame:
        t = self.theme
        card = make_card(parent, t)
        make_label(card, t, DIFFICULTY_NAMES[level], size=t.font_size_ui + 5,
                   weight="bold").pack(anchor="w", padx=18, pady=(14, 8))
        played = data.get("played", 0)
        wins = data.get("completed", 0)
        rate = f"{wins / played:.0%}" if played else "—"
        rows = (
            ("局數", str(played)),
            ("完成", f"{wins}（{rate}）"),
            ("最佳時間", _fmt_time(data.get("best_time"))),
            ("平均時間", _fmt_time(data.get("avg_time"))),
            ("零錯誤完成", str(data.get("zero_mistake_wins", 0))),
        )
        table = ctk.CTkFrame(card, fg_color="transparent")
        table.pack(fill="x", padx=18, pady=(0, 14))
        table.grid_columnconfigure(1, weight=1)
        for index, (name, value) in enumerate(rows):
            make_label(table, t, name, muted=True).grid(row=index, column=0, sticky="w", pady=1)
            color = t.hint_text if name == "最佳時間" and value != "—" else None
            make_label(table, t, value, weight="bold", color=color).grid(
                row=index, column=1, sticky="e", pady=1)
        return card
