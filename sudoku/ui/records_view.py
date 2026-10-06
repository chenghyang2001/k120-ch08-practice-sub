"""遊玩紀錄：歷史清單 + 篩選（難度、完成 / 放棄、每日挑戰 / 一般）。"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from sudoku.data import GameRecord
from sudoku.logic import DIFFICULTIES
from sudoku.theme import Theme

from .controller import format_time
from .widgets import (
    DIFFICULTY_NAMES,
    make_button,
    make_card,
    make_label,
    screen_header,
    style_button,
)

if TYPE_CHECKING:
    from .app_window import SudokuApp

# 清單最多顯示筆數，避免紀錄很多時建立過多元件拖慢畫面
MAX_ROWS = 200


class ChipGroup(ctk.CTkFrame):
    """一列單選篩選膠囊（選中者用主色）。"""

    def __init__(self, master, theme: Theme, title: str, options: list[tuple[str, Any]],
                 on_change: Callable[[], None]) -> None:
        """options 為 (顯示文字, 值)；第一個選項預設選中。"""
        super().__init__(master, fg_color="transparent")
        self.theme = theme
        self.options = options
        self.value = options[0][1]
        self.on_change = on_change
        make_label(self, theme, title, muted=True, width=44, anchor="w").pack(side="left")
        self.buttons: list[ctk.CTkButton] = []
        for text, value in options:
            btn = make_button(self, theme, text, lambda v=value: self._select(v), width=62,
                              height=30, size=max(theme.font_size_ui - 1, 9))
            btn.pack(side="left", padx=3)
            self.buttons.append(btn)
        self._restyle()

    def _select(self, value: Any) -> None:
        self.value = value
        self._restyle()
        self.on_change()

    def _restyle(self) -> None:
        for btn, (_text, value) in zip(self.buttons, self.options, strict=True):
            style_button(btn, self.theme, primary=value == self.value)


class RecordsView(ctk.CTkFrame):
    """遊玩紀錄畫面。"""

    def __init__(self, master, app: SudokuApp) -> None:
        """建立篩選列與紀錄清單。"""
        t = app.theme
        super().__init__(master, fg_color=t.bg, corner_radius=0)
        self.app = app
        self.theme = t
        screen_header(self, t, "📋 遊玩紀錄", app.show_menu).pack(
            fill="x", padx=20, pady=(18, 10))

        filters = make_card(self, t)
        filters.pack(fill="x", padx=20, pady=(0, 10))
        self.diff_chips = ChipGroup(
            filters, t, "難度",
            [("全部", None), *[(DIFFICULTY_NAMES[d], d) for d in DIFFICULTIES]], self.reload)
        self.diff_chips.pack(anchor="w", padx=12, pady=(10, 4))
        self.status_chips = ChipGroup(
            filters, t, "結果", [("全部", None), ("完成", True), ("放棄", False)], self.reload)
        self.status_chips.pack(anchor="w", padx=12, pady=4)
        self.type_chips = ChipGroup(
            filters, t, "類型", [("全部", None), ("每日挑戰", True), ("一般", False)],
            self.reload)
        self.type_chips.pack(anchor="w", padx=12, pady=(4, 10))

        self.summary = make_label(self, t, "", muted=True)
        self.summary.pack(anchor="w", padx=24)
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=t.surface, corner_radius=t.radius,
            scrollbar_button_color=t.button, scrollbar_button_hover_color=t.button_hover)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(6, 20))
        self.reload()

    def reload(self) -> None:
        """依目前篩選條件重新查詢並重建清單。"""
        for child in self.list_frame.winfo_children():
            child.destroy()
        try:
            records = self.app.storage.query_records(
                difficulty=self.diff_chips.value,
                completed=self.status_chips.value,
                is_daily=self.type_chips.value,
            )
        except ValueError as exc:
            self.summary.configure(text=f"讀取紀錄失敗：{exc}")
            return
        self.summary.configure(text=f"共 {len(records)} 筆")
        if not records:
            make_label(self.list_frame, self.theme, "還沒有符合條件的紀錄，來玩一局吧！",
                       muted=True).pack(pady=40)
            return
        for record in records[:MAX_ROWS]:
            self._add_row(record)

    def _add_row(self, record: GameRecord) -> None:
        t = self.theme
        row = make_card(self.list_frame, t, alt=True)
        row.pack(fill="x", padx=6, pady=4)
        row.grid_columnconfigure(1, weight=1)
        try:
            when = datetime.fromisoformat(record.finished_at).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            when = record.finished_at
        name = DIFFICULTY_NAMES.get(record.difficulty, record.difficulty)
        if record.is_daily:
            name = f"📅 {name}"
        make_label(row, t, name, weight="bold", width=86, anchor="w").grid(
            row=0, column=0, rowspan=2, padx=(14, 6), pady=8, sticky="w")
        make_label(row, t, when, muted=True, size=max(t.font_size_ui - 1, 9)).grid(
            row=0, column=1, sticky="w", pady=(8, 0))
        detail = (f"⏱ {format_time(record.elapsed_seconds)}　錯誤 {record.mistakes}"
                  f"　提示 {record.hints_used}")
        make_label(row, t, detail).grid(row=1, column=1, sticky="w", pady=(0, 8))
        status, color = ("完成", t.hint_text) if record.completed else ("放棄", t.error_text)
        make_label(row, t, status, color=color, weight="bold").grid(
            row=0, column=2, rowspan=2, padx=14)
