"""共用 UI 元件與輔助函式：依 Theme 建立按鈕 / 標籤 / 卡片、字型後備、確認對話框。

所有顏色、圓角、字型都從 sudoku.theme.Theme 取得，本模組不寫死任何色碼。
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable

import customtkinter as ctk

from sudoku.theme import FONT_FALLBACKS, Theme

DIFFICULTY_NAMES: dict[str, str] = {
    "easy": "簡單",
    "medium": "中等",
    "hard": "困難",
    "expert": "專家",
}

_family_cache: dict[str, str] = {}


def resolve_family(preferred: str) -> str:
    """回傳系統上可用的字型名稱：優先主題指定字型，否則依 FONT_FALLBACKS 後備。"""
    if preferred in _family_cache:
        return _family_cache[preferred]
    try:
        available = {name.lower() for name in tkfont.families()}
    except tk.TclError:
        # 尚未建立 Tk root 時無法查字型，先直接用主題字型（Tk 會自行後備）
        return preferred
    chosen = preferred
    for name in (preferred, *FONT_FALLBACKS):
        if name.lower() in available:
            chosen = name
            break
    _family_cache[preferred] = chosen
    return chosen


def font(theme: Theme, size: int | None = None, weight: str = "normal") -> tuple:
    """產生 customtkinter 用的字型 tuple（size 預設為主題 UI 字級）。"""
    return (resolve_family(theme.font_family), size or theme.font_size_ui, weight)


def make_button(
    parent,
    theme: Theme,
    text: str,
    command: Callable[[], None] | None,
    *,
    primary: bool = False,
    size: int | None = None,
    weight: str = "normal",
    height: int = 40,
    width: int = 120,
) -> ctk.CTkButton:
    """建立圓角扁平按鈕；primary=True 用主色，否則用次要按鈕色。"""
    btn = ctk.CTkButton(
        parent,
        text=text,
        command=command,
        height=height,
        width=width,
        corner_radius=theme.button_radius,
        border_width=0,
        font=font(theme, size, weight),
    )
    style_button(btn, theme, primary=primary, enabled=True)
    return btn


def style_button(btn: ctk.CTkButton, theme: Theme, *, primary: bool = False,
                 enabled: bool = True) -> None:
    """依啟用狀態與主/次要樣式套用按鈕顏色（停用時改用 disabled token）。"""
    if not enabled:
        btn.configure(
            state="disabled",
            fg_color=theme.button_disabled,
            hover_color=theme.button_disabled,
            text_color=theme.button_disabled_text,
            text_color_disabled=theme.button_disabled_text,
        )
        return
    if primary:
        btn.configure(state="normal", fg_color=theme.accent, hover_color=theme.accent_hover,
                      text_color=theme.accent_text)
    else:
        btn.configure(state="normal", fg_color=theme.button, hover_color=theme.button_hover,
                      text_color=theme.button_text)


def make_label(parent, theme: Theme, text: str = "", *, size: int | None = None,
               weight: str = "normal", muted: bool = False, color: str | None = None,
               **kwargs) -> ctk.CTkLabel:
    """建立透明背景文字標籤；muted=True 用次要文字色，color 可指定其他 token 色。"""
    text_color = color or (theme.text_muted if muted else theme.text)
    return ctk.CTkLabel(parent, text=text, text_color=text_color,
                        font=font(theme, size, weight), fg_color="transparent", **kwargs)


def make_card(parent, theme: Theme, *, alt: bool = False, border: str | None = None,
              **kwargs) -> ctk.CTkFrame:
    """建立圓角卡片容器（surface 底色，可選外框色）。"""
    return ctk.CTkFrame(
        parent,
        fg_color=theme.surface_alt if alt else theme.surface,
        corner_radius=theme.radius,
        border_width=2 if border else 0,
        border_color=border or theme.surface,
        **kwargs,
    )


def screen_header(parent, theme: Theme, title: str, on_back: Callable[[], None]) -> ctk.CTkFrame:
    """子畫面共用標頭：左側「← 主選單」按鈕 + 標題。"""
    bar = ctk.CTkFrame(parent, fg_color="transparent")
    make_button(bar, theme, "← 主選單", on_back, width=96, height=34).pack(side="left")
    make_label(bar, theme, title, size=theme.font_size_title - 6, weight="bold").pack(
        side="left", padx=14)
    return bar


def show_confirm(
    parent,
    theme: Theme,
    title: str,
    message: str,
    on_yes: Callable[[], None],
    *,
    yes_text: str = "確定",
    no_text: str = "取消",
    on_no: Callable[[], None] | None = None,
) -> ctk.CTkFrame:
    """在 parent 上方覆蓋一個主題化的確認卡片（同視窗內，不另開系統對話框）。"""
    shade = ctk.CTkFrame(parent, fg_color=theme.bg, corner_radius=0)
    shade.place(relx=0, rely=0, relwidth=1, relheight=1)
    card = make_card(shade, theme, border=theme.box_line)
    card.place(relx=0.5, rely=0.45, anchor="center")
    make_label(card, theme, title, size=theme.font_size_title - 8, weight="bold").pack(
        padx=28, pady=(24, 8))
    make_label(card, theme, message, muted=True, justify="center", wraplength=360).pack(
        padx=28, pady=(0, 18))
    row = ctk.CTkFrame(card, fg_color="transparent")
    row.pack(padx=24, pady=(0, 22))

    def close_then(callback: Callable[[], None] | None) -> None:
        shade.destroy()
        if callback is not None:
            callback()

    make_button(row, theme, no_text, lambda: close_then(on_no), width=120).pack(
        side="left", padx=6)
    make_button(row, theme, yes_text, lambda: close_then(on_yes), primary=True,
                width=120).pack(side="left", padx=6)
    shade.lift()
    return shade


def rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float,
                 **kwargs) -> int:
    """在 tk.Canvas 上畫圓角矩形（以 smooth 多邊形近似），回傳物件 id。"""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)
