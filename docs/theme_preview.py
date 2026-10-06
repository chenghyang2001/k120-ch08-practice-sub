"""主題視覺預覽：用 tkinter Canvas 為每套主題畫迷你數獨盤面與圓角按鈕，並截圖存成 PNG。

執行：PYTHONUTF8=1 uv run python docs/theme_preview.py [輸出路徑]
預設輸出 docs/theme_preview.png。需要 Pillow（dev 相依）。
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sudoku.theme import Theme, list_themes

CELL = 30
BOARD = CELL * 9
PAD = 22
PANEL_W = BOARD + PAD * 2
PANEL_H = BOARD + 190
COLS = 3

# 示範盤面：0 = 空格；GIVEN 標記題目給定格
PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]
USER = {(4, 4): 5, (0, 3): 6, (2, 0): 1, (6, 4): 3}   # 玩家填入
ERROR = {(1, 7): 3}                                     # 填錯
HINT = {(7, 2): 2}                                      # 提示填入
NOTES = {(0, 2): [1, 2, 4], (1, 1): [2, 4, 7], (3, 1): [1, 2, 5]}
SELECTED = (4, 4)


def rounded_rect(cv: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    """在 Canvas 上畫圓角矩形（以平滑多邊形近似）。"""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def cell_value(r: int, c: int) -> int:
    """取得示範盤面某格目前顯示的數字（0 = 空）。"""
    return PUZZLE[r][c] or USER.get((r, c)) or ERROR.get((r, c)) or HINT.get((r, c)) or 0


def cell_colors(t: Theme, r: int, c: int) -> tuple[str, str]:
    """依狀態優先序（錯誤/提示 > 選取 > 相同數字 > 同行列宮）決定 (底色, 字色)。"""
    sr, sc = SELECTED
    sel_val = cell_value(sr, sc)
    fg = t.given_text if PUZZLE[r][c] else t.user_text
    if (r, c) in ERROR:
        return t.error_bg, t.error_text
    if (r, c) in HINT:
        return t.hint_bg, t.hint_text
    if (r, c) == SELECTED:
        return t.sel_bg, fg
    if sel_val and cell_value(r, c) == sel_val:
        return t.same_num_bg, fg
    if r == sr or c == sc or (r // 3 == sr // 3 and c // 3 == sc // 3):
        return t.peer_bg, fg
    return t.cell_bg, fg


def draw_board(cv: tk.Canvas, t: Theme, ox: int, oy: int) -> None:
    """畫 9×9 盤面：圓角外框、狀態底色、數字、筆記、細格線與粗宮線。"""
    f = t.font_family
    rounded_rect(cv, ox - 4, oy - 4, ox + BOARD + 4, oy + BOARD + 4, t.radius,
                 fill=t.box_line, outline="")
    rounded_rect(cv, ox - 1, oy - 1, ox + BOARD + 1, oy + BOARD + 1, t.radius - 3,
                 fill=t.cell_bg, outline="")
    for r in range(9):
        for c in range(9):
            x, y = ox + c * CELL, oy + r * CELL
            bg, fg = cell_colors(t, r, c)
            if bg != t.cell_bg:
                cv.create_rectangle(x, y, x + CELL, y + CELL, fill=bg, outline="")
            val = cell_value(r, c)
            if val:
                # 給定數字用粗體、玩家/錯誤/提示用一般字重，不只靠顏色區分
                weight = "bold" if PUZZLE[r][c] or (r, c) in ERROR else "normal"
                cv.create_text(x + CELL / 2, y + CELL / 2 + 1, text=str(val), fill=fg,
                               font=(f, int(t.font_size_cell * 0.62), weight))
            for n in NOTES.get((r, c), []):
                nx = x + 5 + ((n - 1) % 3) * 10
                ny = y + 5 + ((n - 1) // 3) * 10
                cv.create_text(nx, ny, text=str(n), fill=t.note_text,
                               font=(f, max(6, t.font_size_note - 4)))
    for i in range(1, 9):
        if i % 3:
            p = i * CELL
            cv.create_line(ox + p, oy, ox + p, oy + BOARD, fill=t.grid_line, width=t.grid_line_width)
            cv.create_line(ox, oy + p, ox + BOARD, oy + p, fill=t.grid_line, width=t.grid_line_width)
    for i in (3, 6):
        p = i * CELL
        cv.create_line(ox + p, oy, ox + p, oy + BOARD, fill=t.box_line, width=t.box_line_width)
        cv.create_line(ox, oy + p, ox + BOARD, oy + p, fill=t.box_line, width=t.box_line_width)


def draw_button(cv, t: Theme, x, y, w, h, label, fill, fg) -> None:
    """畫一顆圓角扁平按鈕。"""
    rounded_rect(cv, x, y, x + w, y + h, t.button_radius, fill=fill, outline="")
    cv.create_text(x + w / 2, y + h / 2, text=label, fill=fg, font=(t.font_family, 10, "bold"))


def draw_panel(cv: tk.Canvas, t: Theme, px: int, py: int) -> None:
    """畫單一主題的預覽面板（標題、色票、盤面、按鈕列）。"""
    rounded_rect(cv, px, py, px + PANEL_W, py + PANEL_H, 16, fill=t.bg, outline="")
    cv.create_text(px + PAD, py + 24, text=t.name, anchor="w", fill=t.text,
                   font=(t.font_family, 14, "bold"))
    cv.create_text(px + PAD, py + 46, text=f"{t.key} · {'深色' if t.is_dark else '淺色'}",
                   anchor="w", fill=t.text_muted, font=(t.font_family, 9))
    for i, color in enumerate(t.swatches()):
        sx = px + PANEL_W - PAD - (5 - i) * 20
        rounded_rect(cv, sx, py + 18, sx + 16, py + 34, 6, fill=color, outline=t.text_muted)
    draw_board(cv, t, px + PAD, py + 66)
    by = py + 66 + BOARD + 18
    rounded_rect(cv, px + PAD - 6, by - 6, px + PANEL_W - PAD + 6, by + 98, t.radius,
                 fill=t.surface, outline="")
    bw = (BOARD - 16) // 3
    draw_button(cv, t, px + PAD, by + 4, bw, 34, "開始", t.accent, t.accent_text)
    draw_button(cv, t, px + PAD + bw + 8, by + 4, bw, 34, "筆記 N", t.button, t.button_text)
    draw_button(cv, t, px + PAD + 2 * (bw + 8), by + 4, bw, 34, "↩ 復原",
                t.button_disabled, t.button_disabled_text)
    cv.create_text(px + PAD, by + 62, anchor="w", fill=t.error_text, font=(t.font_family, 10, "bold"),
                   text="✕ 錯誤 1")
    cv.create_text(px + PAD + 100, by + 62, anchor="w", fill=t.hint_text,
                   font=(t.font_family, 10, "bold"), text="✓ 提示 2/3")
    cv.create_text(px + PANEL_W - PAD, by + 62, anchor="e", fill=t.text_muted,
                   font=(t.font_family, 10), text="03:42")


def capture(root: tk.Tk, cv: tk.Canvas, out: Path) -> None:
    """以 PIL.ImageGrab 擷取 Canvas 所在的螢幕區域並存檔。"""
    try:
        from PIL import ImageGrab
    except ImportError:
        print("錯誤：需要 Pillow，請執行 uv add --dev pillow", file=sys.stderr)
        root.destroy()
        sys.exit(1)
    root.update()
    x, y = cv.winfo_rootx(), cv.winfo_rooty()
    img = ImageGrab.grab(bbox=(x, y, x + cv.winfo_width(), y + cv.winfo_height()))
    img.save(out)
    print(f"已輸出預覽圖：{out}（{img.width}×{img.height}）")
    root.destroy()


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "theme_preview.png"
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 避免高 DPI 縮放造成截圖座標偏移
    except (AttributeError, OSError):
        pass
    themes = list_themes()
    rows = (len(themes) + COLS - 1) // COLS
    gap = 18
    width = COLS * PANEL_W + (COLS + 1) * gap
    height = rows * PANEL_H + (rows + 1) * gap
    root = tk.Tk()
    root.title("主題預覽")
    root.attributes("-topmost", True)
    root.geometry("+20+20")
    cv = tk.Canvas(root, width=width, height=height, bg="#8A8F98", highlightthickness=0)
    cv.pack()
    for i, theme in enumerate(themes):
        r, c = divmod(i, COLS)
        draw_panel(cv, theme, gap + c * (PANEL_W + gap), gap + r * (PANEL_H + gap))
    root.after(800, lambda: capture(root, cv, out))
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        print(f"錯誤：無法建立 Tk 視窗：{exc}", file=sys.stderr)
        sys.exit(1)
