"""🎨 主題選單：列出所有主題的色票縮圖，點選即時套用並存入設定。"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from sudoku.theme import Theme, list_themes

from .board_canvas import rounded_points
from .widgets import make_card, make_label, screen_header

if TYPE_CHECKING:
    from .app_window import SudokuApp

_SWATCH = 30
_GAP = 8


class ThemePicker(ctk.CTkFrame):
    """主題選擇畫面。"""

    def __init__(self, master, app: SudokuApp) -> None:
        """以 2 欄卡片列出主題；目前主題以主色外框標示。"""
        t = app.theme
        super().__init__(master, fg_color=t.bg, corner_radius=0)
        self.app = app
        self.theme = t
        screen_header(self, t, "🎨 背景主題", app.show_menu).pack(
            fill="x", padx=20, pady=(18, 6))
        make_label(self, t, "點選即可套用，設定會自動保存", muted=True).pack(
            anchor="w", padx=24, pady=(0, 10))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 20))
        for index, option in enumerate(list_themes()):
            grid.grid_columnconfigure(index % 2, weight=1, uniform="theme")
            self._theme_card(grid, option).grid(
                row=index // 2, column=index % 2, sticky="ew", padx=6, pady=6)

    def _theme_card(self, parent, option: Theme) -> ctk.CTkFrame:
        t = self.theme
        selected = option.key == t.key
        card = make_card(parent, t, border=t.accent if selected else t.surface)
        swatches = tk.Canvas(card, width=5 * _SWATCH + 4 * _GAP, height=_SWATCH,
                             highlightthickness=0, bd=0, bg=t.surface)
        for index, color in enumerate(option.swatches()):
            x = index * (_SWATCH + _GAP)
            swatches.create_polygon(rounded_points(x + 1, 1, x + _SWATCH - 1, _SWATCH - 1, 7),
                                    fill=color, outline=t.grid_line, width=1)
        swatches.pack(anchor="w", padx=16, pady=(16, 8))
        title = make_label(card, t, option.name, weight="bold", size=t.font_size_ui + 2)
        title.pack(anchor="w", padx=16)
        sub = make_label(card, t, "✓ 使用中" if selected else ("深色" if option.is_dark else "淺色"),
                         color=t.accent if selected else None, muted=not selected)
        sub.pack(anchor="w", padx=16, pady=(0, 14))

        def choose(_event=None, key=option.key) -> None:
            self.app.apply_theme(key)

        for widget in (card, swatches, title, sub):
            widget.bind("<Button-1>", choose)
            widget.configure(cursor="hand2")
        return card
