"""遊戲畫面：頂部資訊列、盤面、功能列、數字鍵盤、暫停遮罩、結算卡片。

本畫面只轉發事件給 GameController 並依其狀態重繪；存檔與紀錄寫入由 SudokuApp 負責。
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from .board_canvas import BoardCanvas
from .controller import GameController, format_time
from .widgets import (
    DIFFICULTY_NAMES,
    make_button,
    make_card,
    make_label,
    style_button,
)

if TYPE_CHECKING:
    from .app_window import SudokuApp

# 數字鍵台在 NumLock 關閉時送出的 keysym 對應
_KEYPAD_NAV = {
    "KP_End": 1, "KP_Down": 2, "KP_Next": 3, "KP_Left": 4, "KP_Begin": 5,
    "KP_Right": 6, "KP_Home": 7, "KP_Up": 8, "KP_Prior": 9,
}
_ARROWS = {"Up": (-1, 0), "Down": (1, 0), "Left": (0, -1), "Right": (0, 1)}
_CTRL_MASK = 0x0004


def key_to_digit(keysym: str, char: str) -> int | None:
    """把按鍵事件轉成 1–9（支援主鍵盤與數字鍵台），其他回 None。"""
    if char and char in "123456789" and len(char) == 1:
        return int(char)
    if keysym.startswith("KP_") and keysym[3:].isdigit():
        value = int(keysym[3:])
        return value if 1 <= value <= 9 else None
    return _KEYPAD_NAV.get(keysym)


class GameView(ctk.CTkFrame):
    """一局遊戲的主畫面。"""

    def __init__(self, master, app: SudokuApp, controller: GameController) -> None:
        """建立遊戲畫面並開始計時（若遊戲尚未完成）。"""
        theme = app.theme
        super().__init__(master, fg_color=theme.bg, corner_radius=0)
        self.app = app
        self.theme = theme
        self.controller = controller
        self._timer_id: str | None = None
        self._finished = controller.completed
        self._result_overlay: ctk.CTkFrame | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_top_bar()
        self.board = BoardCanvas(self, theme, controller, self._on_cell_click)
        self.board.grid(row=1, column=0, sticky="nsew", padx=14, pady=(4, 6))
        self._build_toolbar()
        self._build_numpad()
        self._build_footer()
        self.resume_button = make_button(self.board, theme, "▶ 繼續", self.toggle_pause,
                                         primary=True, width=140, height=42, weight="bold")
        # 按鈕疊在暫停遮罩上，四角背景色需與遮罩一致
        self.resume_button.configure(bg_color=theme.surface_alt)
        self.refresh()
        if not self._finished:
            self._schedule_tick()

    # ------------------------------------------------------------------
    # 版面
    # ------------------------------------------------------------------
    def _build_top_bar(self) -> None:
        t = self.theme
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        make_button(bar, t, "← 主選單", self.app_leave, width=92, height=34).pack(side="left")
        title = DIFFICULTY_NAMES.get(self.controller.state.difficulty, "")
        if self.controller.state.is_daily:
            title = f"📅 每日挑戰 · {title}"
        make_label(bar, t, title, size=t.font_size_ui + 3, weight="bold").pack(
            side="left", padx=12)
        stats = make_card(bar, t, alt=True)
        stats.pack(side="right")
        self.timer_label = make_label(stats, t, "00:00", size=t.font_size_ui + 3, weight="bold")
        self.timer_label.pack(side="right", padx=(6, 14), pady=4)
        make_label(stats, t, "⏱", muted=True).pack(side="right")
        self.mistake_label = make_label(stats, t, "錯誤 0", muted=True)
        self.mistake_label.pack(side="right", padx=(14, 12), pady=4)

    def _build_toolbar(self) -> None:
        t = self.theme
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(2, 6))
        specs = (
            ("undo", "↩ 返回", self.undo),
            ("notes", "✏ 筆記", self.toggle_notes),
            ("hint", "💡 提示", self.use_hint),
            ("clear", "⌫ 清除", self.clear),
            ("pause", "⏸ 暫停", self.toggle_pause),
        )
        self.tool_buttons: dict[str, ctk.CTkButton] = {}
        for index, (key, text, command) in enumerate(specs):
            bar.grid_columnconfigure(index, weight=1, uniform="tool")
            btn = make_button(bar, t, text, command, height=42, width=60)
            btn.grid(row=0, column=index, sticky="ew", padx=3)
            self.tool_buttons[key] = btn

    def _build_numpad(self) -> None:
        t = self.theme
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.grid(row=3, column=0, sticky="ew", padx=16, pady=(2, 2))
        self.num_buttons: dict[int, ctk.CTkButton] = {}
        self.num_counts: dict[int, ctk.CTkLabel] = {}
        for digit in range(1, 10):
            pad.grid_columnconfigure(digit - 1, weight=1, uniform="num")
            btn = make_button(pad, t, str(digit), lambda d=digit: self.input_digit(d),
                              size=t.font_size_cell - 2, weight="bold", height=52, width=40)
            btn.grid(row=0, column=digit - 1, sticky="ew", padx=3)
            count = make_label(pad, t, "", muted=True, size=max(t.font_size_ui - 2, 9))
            count.grid(row=1, column=digit - 1, pady=(1, 0))
            self.num_buttons[digit] = btn
            self.num_counts[digit] = count

    def _build_footer(self) -> None:
        t = self.theme
        make_label(self, t, "方向鍵移動 · 1–9 填數 · N 筆記 · Del 清除 · Ctrl+Z 返回 · Esc 暫停",
                   muted=True, size=max(t.font_size_ui - 2, 9)).grid(
            row=4, column=0, pady=(2, 10))

    # ------------------------------------------------------------------
    # 狀態同步
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """依控制器狀態更新盤面、計時、錯誤數與所有按鈕的啟用狀態。"""
        t = self.theme
        ctl = self.controller
        state = ctl.state
        self.board.redraw()
        self.timer_label.configure(text=format_time(state.elapsed_seconds))
        self.mistake_label.configure(
            text=f"錯誤 {state.mistakes}",
            text_color=t.error_text if state.mistakes else t.text_muted)
        active = not ctl.paused and not ctl.completed

        notes_btn = self.tool_buttons["notes"]
        notes_btn.configure(text="✏ 筆記 開" if ctl.notes_mode else "✏ 筆記 關")
        style_button(notes_btn, t, primary=ctl.notes_mode, enabled=active)
        hint_btn = self.tool_buttons["hint"]
        hint_btn.configure(text=f"💡 提示 {ctl.hints_left}")
        style_button(hint_btn, t, enabled=active and ctl.hints_left > 0)
        style_button(self.tool_buttons["undo"], t, enabled=active and ctl.can_undo)
        style_button(self.tool_buttons["clear"], t, enabled=active)
        pause_btn = self.tool_buttons["pause"]
        pause_btn.configure(text="▶ 繼續" if ctl.paused else "⏸ 暫停")
        style_button(pause_btn, t, primary=ctl.paused, enabled=not ctl.completed)

        for digit, btn in self.num_buttons.items():
            remaining = ctl.remaining_count(digit)
            self.num_counts[digit].configure(text=str(remaining) if remaining else "✓")
            style_button(btn, t, enabled=active and remaining > 0)

        if ctl.paused:
            self.resume_button.place(relx=0.5, rely=0.6, anchor="center")
        else:
            self.resume_button.place_forget()

    def _after_action(self) -> None:
        self.refresh()
        if self.controller.completed and not self._finished:
            self._finished = True
            self._cancel_tick()
            summary = self.app.complete_game(self.controller)
            self._show_result(summary)

    # ------------------------------------------------------------------
    # 計時
    # ------------------------------------------------------------------
    def _schedule_tick(self) -> None:
        self._timer_id = self.after(1000, self._tick)

    def _cancel_tick(self) -> None:
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None

    def _tick(self) -> None:
        self._timer_id = None
        if self._finished:
            return
        if self.controller.tick():
            self.timer_label.configure(text=format_time(self.controller.state.elapsed_seconds))
        self._schedule_tick()

    def destroy(self) -> None:
        """銷毀前停止計時，避免 after 回呼打到已銷毀的元件。"""
        self._cancel_tick()
        super().destroy()

    # ------------------------------------------------------------------
    # 使用者操作
    # ------------------------------------------------------------------
    def _on_cell_click(self, row: int, col: int) -> None:
        if self.controller.select(row, col):
            self.refresh()

    def input_digit(self, digit: int) -> None:
        """數字鍵盤或鍵盤 1–9。"""
        if self.controller.input_digit(digit):
            self._after_action()

    def toggle_notes(self) -> None:
        """切換筆記模式（✏ 按鈕或 N）。"""
        self.controller.toggle_notes_mode()
        self.refresh()

    def use_hint(self) -> None:
        """使用提示（💡 按鈕）。"""
        if self.controller.hint() is not None:
            self._after_action()

    def clear(self) -> None:
        """清除選取格（⌫ 按鈕或 Delete / Backspace）。"""
        if self.controller.clear():
            self._after_action()

    def undo(self) -> None:
        """返回上一步（↩ 按鈕或 Ctrl+Z）。"""
        if self.controller.undo():
            self._after_action()

    def toggle_pause(self) -> None:
        """暫停 / 繼續（⏸ 按鈕或 Escape）。"""
        if self._finished:
            return
        self.controller.toggle_pause()
        if self.controller.paused:
            self.app.storage.flush()
        self.refresh()

    def app_leave(self) -> None:
        """返回主選單（存檔保留，不算放棄）。"""
        self._cancel_tick()
        self.app.leave_game(self.controller)

    def on_app_close(self) -> None:
        """視窗關閉時呼叫：停止計時並寫出存檔。"""
        self._cancel_tick()
        if not self.controller.completed:
            self.app.storage.save_game(self.controller.state)

    def handle_key(self, event: tk.Event) -> bool:
        """處理鍵盤事件；有處理回 True。"""
        if self._result_overlay is not None:
            return False
        keysym = event.keysym
        ctrl = bool(event.state & _CTRL_MASK)
        if ctrl and keysym.lower() == "z":
            self.undo()
            return True
        if ctrl:
            return False
        if keysym == "Escape":
            self.toggle_pause()
            return True
        if keysym in _ARROWS:
            if self.controller.move(*_ARROWS[keysym]):
                self.refresh()
            return True
        if keysym in ("Delete", "BackSpace", "KP_Delete"):
            self.clear()
            return True
        if keysym.lower() == "n":
            self.toggle_notes()
            return True
        digit = key_to_digit(keysym, event.char)
        if digit is not None:
            self.input_digit(digit)
            return True
        return False

    # ------------------------------------------------------------------
    # 結算
    # ------------------------------------------------------------------
    def _show_result(self, summary: dict) -> None:
        t = self.theme
        state = self.controller.state
        shade = ctk.CTkFrame(self, fg_color=t.bg, corner_radius=0)
        shade.place(relx=0, rely=0, relwidth=1, relheight=1)
        card = make_card(shade, t, border=t.accent)
        card.place(relx=0.5, rely=0.45, anchor="center")
        make_label(card, t, "🎉 完成！", size=t.font_size_title + 4, weight="bold").pack(
            padx=48, pady=(28, 4))
        subtitle = DIFFICULTY_NAMES.get(state.difficulty, "")
        if state.is_daily:
            subtitle = f"每日挑戰 · {subtitle}"
        make_label(card, t, subtitle, muted=True).pack(pady=(0, 16))

        rows = ctk.CTkFrame(card, fg_color="transparent")
        rows.pack(padx=36, pady=(0, 8), fill="x")
        time_text = format_time(state.elapsed_seconds)
        items = [
            ("難度", DIFFICULTY_NAMES.get(state.difficulty, "")),
            ("時間", time_text),
            ("錯誤", f"{state.mistakes} 次"),
            ("提示使用", f"{self.controller.hints_used} / 3"),
        ]
        for index, (name, value) in enumerate(items):
            make_label(rows, t, name, muted=True).grid(row=index, column=0, sticky="w", pady=3)
            make_label(rows, t, value, weight="bold").grid(row=index, column=1, sticky="e",
                                                           pady=3, padx=(40, 0))
        rows.grid_columnconfigure(1, weight=1)
        if summary.get("new_best"):
            make_label(card, t, "🏆 新的最佳時間！", color=t.hint_text, weight="bold").pack(
                pady=(6, 0))
        if summary.get("streak"):
            make_label(card, t, f"🔥 每日挑戰連續 {summary['streak']} 天", color=t.accent,
                       weight="bold").pack(pady=(4, 0))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(padx=28, pady=(18, 26))
        make_button(buttons, t, "主選單", self.app.show_menu, width=120).pack(
            side="left", padx=6)
        make_button(buttons, t, "再來一局", lambda: self.app.request_new_game(state.difficulty),
                    primary=True, width=120).pack(side="left", padx=6)
        self._result_overlay = shade
