"""盤面畫布：以 tk.Canvas 自繪 9×9 盤面（圓角外框、細格線 / 粗宮線、筆記、高亮、暫停遮罩）。

只負責繪圖與把滑鼠點擊換算成 (row, col)；狀態一律從 GameController 查詢。
盤面隨畫布大小等比縮放，字級依格子大小與主題字級比例計算。
"""
from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable

from sudoku.theme import Theme

from .controller import CellView, GameController
from .widgets import resolve_family

# 主題字級（點數）對應到格寬的比例基準：格寬 44px 時格內數字即為 font_size_cell
_CELL_FONT_BASE = 44.0
_NOTE_FONT_BASE = 34.0
_PADDING = 6


def rounded_points(x1: float, y1: float, x2: float, y2: float, r: float,
                   steps: int = 10) -> list[float]:
    """產生真正圓弧的圓角矩形頂點（順時針），供填色、外框與角落遮罩共用。"""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    corners = (
        (x2 - r, y1 + r, -90.0),   # 右上：從 -90° 到 0°
        (x2 - r, y2 - r, 0.0),     # 右下
        (x1 + r, y2 - r, 90.0),    # 左下
        (x1 + r, y1 + r, 180.0),   # 左上
    )
    points: list[float] = []
    for cx, cy, start in corners:
        for i in range(steps + 1):
            angle = math.radians(start + 90.0 * i / steps)
            points.extend((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


class BoardCanvas(tk.Canvas):
    """數獨盤面畫布。呼叫 redraw() 依控制器狀態重繪。"""

    def __init__(self, master, theme: Theme, controller: GameController,
                 on_cell_click: Callable[[int, int], None]) -> None:
        """建立畫布；on_cell_click(row, col) 於滑鼠點到格子時呼叫。"""
        super().__init__(master, highlightthickness=0, bd=0, bg=theme.bg,
                         width=480, height=480)
        self.theme = theme
        self.controller = controller
        self.on_cell_click = on_cell_click
        self.family = resolve_family(theme.font_family)
        self._origin = (0.0, 0.0)
        self._cell = 0.0
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Button-1>", self._on_click)

    # ------------------------------------------------------------------
    def _geometry(self) -> tuple[float, float, float]:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        size = max(min(width, height) - 2 * _PADDING, 90)
        x0 = (width - size) / 2
        y0 = (height - size) / 2
        return x0, y0, size

    def _on_click(self, event: tk.Event) -> None:
        if self._cell <= 0:
            return
        x0, y0 = self._origin
        col = int((event.x - x0) // self._cell)
        row = int((event.y - y0) // self._cell)
        if 0 <= row < 9 and 0 <= col < 9:
            self.on_cell_click(row, col)

    def _cell_bg(self, view: CellView) -> str:
        t = self.theme
        if view.is_selected:
            return t.sel_bg
        if view.is_error:
            return t.error_bg
        if view.is_hint:
            return t.hint_bg
        if view.is_same_number:
            return t.same_num_bg
        if view.is_peer:
            return t.peer_bg
        return t.cell_bg

    def _cell_fg(self, view: CellView) -> str:
        t = self.theme
        if view.is_given:
            return t.given_text
        if view.is_error:
            return t.error_text
        if view.is_hint:
            return t.hint_text
        return t.user_text

    # ------------------------------------------------------------------
    def redraw(self) -> None:
        """依控制器目前狀態完整重繪盤面。"""
        self.delete("all")
        t = self.theme
        x0, y0, size = self._geometry()
        cell = size / 9
        self._origin = (x0, y0)
        self._cell = cell
        x1, y1 = x0 + size, y0 + size
        radius = t.radius

        outline = rounded_points(x0, y0, x1, y1, radius)
        self.create_polygon(outline, fill=t.cell_bg, outline="")

        paused = self.controller.paused
        views = [[self.controller.cell_view(r, c) for c in range(9)] for r in range(9)]
        if not paused:
            for r in range(9):
                for c in range(9):
                    color = self._cell_bg(views[r][c])
                    if color != t.cell_bg:
                        self.create_rectangle(x0 + c * cell, y0 + r * cell,
                                              x0 + (c + 1) * cell, y0 + (r + 1) * cell,
                                              fill=color, outline="")
        self._draw_corner_masks(x0, y0, x1, y1, radius)
        if paused:
            self._draw_pause_cover(x0, y0, x1, y1)
            self.create_polygon(outline, fill="", outline=t.box_line, width=t.box_line_width)
            return
        self._draw_lines(x0, y0, x1, y1, cell)
        self.create_polygon(outline, fill="", outline=t.box_line, width=t.box_line_width)
        selected_value = self.controller.state.board[self.controller.selected[0]][
            self.controller.selected[1]]
        for r in range(9):
            for c in range(9):
                self._draw_cell_content(views[r][c], x0 + c * cell, y0 + r * cell, cell,
                                        selected_value)

    def _draw_corner_masks(self, x0: float, y0: float, x1: float, y1: float, r: float) -> None:
        """把高亮格超出圓角的部分以背景色蓋掉，讓四角保持圓弧。"""
        if r <= 0:
            return
        pts = rounded_points(x0, y0, x1, y1, r)
        steps = len(pts) // 8  # 每個角有 steps 個點（=10+1）
        corner_points = [pts[i * steps * 2:(i + 1) * steps * 2] for i in range(4)]
        squares = ((x1, y0), (x1, y1), (x0, y1), (x0, y0))
        for arc, (sx, sy) in zip(corner_points, squares, strict=True):
            self.create_polygon([sx, sy, *arc], fill=self.theme.bg, outline="")

    def _draw_lines(self, x0: float, y0: float, x1: float, y1: float, cell: float) -> None:
        t = self.theme
        for i in range(1, 9):
            if i % 3 == 0:
                continue
            pos_x = x0 + i * cell
            pos_y = y0 + i * cell
            self.create_line(pos_x, y0, pos_x, y1, fill=t.grid_line, width=t.grid_line_width)
            self.create_line(x0, pos_y, x1, pos_y, fill=t.grid_line, width=t.grid_line_width)
        for i in (3, 6):
            pos_x = x0 + i * cell
            pos_y = y0 + i * cell
            self.create_line(pos_x, y0, pos_x, y1, fill=t.box_line, width=t.box_line_width)
            self.create_line(x0, pos_y, x1, pos_y, fill=t.box_line, width=t.box_line_width)

    def _draw_cell_content(self, view: CellView, x: float, y: float, cell: float,
                           selected_value: int) -> None:
        t = self.theme
        if view.value:
            px = max(10, round(cell * t.font_size_cell / _CELL_FONT_BASE))
            weight = "bold" if view.is_given else "normal"
            self.create_text(x + cell / 2, y + cell / 2 + 1, text=str(view.value),
                             fill=self._cell_fg(view), font=(self.family, -px, weight))
            return
        if not view.notes:
            return
        px = max(7, round(cell * t.font_size_note / _NOTE_FONT_BASE))
        sub = cell / 3
        for digit in view.notes:
            nr, nc = divmod(digit - 1, 3)
            emphasize = digit == selected_value
            self.create_text(x + sub * (nc + 0.5), y + sub * (nr + 0.5) + 0.5, text=str(digit),
                             fill=t.user_text if emphasize else t.note_text,
                             font=(self.family, -px, "bold" if emphasize else "normal"))

    def _draw_pause_cover(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """暫停時以 surface 色遮蔽盤面內容，避免偷看。"""
        t = self.theme
        self.create_polygon(rounded_points(x0, y0, x1, y1, t.radius),
                            fill=t.surface_alt, outline="")
        size = x1 - x0
        title_px = max(14, round(size * 0.07))
        self.create_text((x0 + x1) / 2, y0 + size * 0.38, text="⏸ 已暫停", fill=t.text,
                         font=(self.family, -title_px, "bold"))
        self.create_text((x0 + x1) / 2, y0 + size * 0.47,
                         text="計時已停止，按 Esc 或「繼續」回到遊戲",
                         fill=t.text_muted, font=(self.family, -max(11, round(size * 0.032))))
