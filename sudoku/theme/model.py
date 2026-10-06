"""主題資料模型與 WCAG 對比度計算（純資料，不依賴任何 GUI 套件）。"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# 預設字型：Windows 內建的「微軟正黑體 UI」，對繁中與數字皆清晰。
# 其他平台若無此字型，Tk 會自動後備為系統預設 sans-serif；
# 建議 macOS 用 "PingFang TC"、Linux 用 "Noto Sans CJK TC"（見 FONT_FALLBACKS）。
DEFAULT_FONT_FAMILY = "Microsoft JhengHei UI"
FONT_FALLBACKS: tuple[str, ...] = (
    "Microsoft JhengHei UI",
    "Microsoft JhengHei",
    "PingFang TC",
    "Noto Sans CJK TC",
    "Noto Sans TC",
    "Segoe UI",
)


@dataclass(frozen=True)
class Theme:
    """一套完整的視覺主題（設計 token 集合）。

    所有顏色欄位皆為 "#RRGGBB" 字串；UI 層只能透過這些 token 取色，
    不可寫死色碼。尺寸欄位單位為像素（字級為 Tk 點數）。
    """

    key: str
    name: str
    is_dark: bool
    # 版面底色
    bg: str
    surface: str
    surface_alt: str
    # 文字
    text: str
    text_muted: str
    # 主要按鈕
    accent: str
    accent_hover: str
    accent_text: str
    # 次要按鈕
    button: str
    button_hover: str
    button_text: str
    button_disabled: str
    button_disabled_text: str
    # 盤面
    cell_bg: str
    given_text: str
    user_text: str
    note_text: str
    grid_line: str
    box_line: str
    sel_bg: str
    peer_bg: str
    same_num_bg: str
    error_text: str
    error_bg: str
    hint_text: str
    hint_bg: str
    # 尺寸
    radius: int = 12
    button_radius: int = 10
    grid_line_width: int = 1
    box_line_width: int = 3
    font_family: str = DEFAULT_FONT_FAMILY
    font_size_cell: int = 24
    font_size_note: int = 10
    font_size_ui: int = 13
    font_size_title: int = 26

    def __post_init__(self) -> None:
        """建立時驗證所有顏色欄位格式，避免壞色碼流入 UI 層。"""
        for name in color_field_names():
            value = getattr(self, name)
            if not isinstance(value, str) or not _HEX_RE.match(value):
                raise ValueError(f"主題 {self.key!r} 的 {name} 色碼格式錯誤：{value!r}")

    def colors(self) -> dict[str, str]:
        """回傳 {欄位名: 色碼} 的顏色 token 字典。"""
        return {name: getattr(self, name) for name in color_field_names()}

    def swatches(self) -> tuple[str, ...]:
        """回傳主題選單縮圖用的代表色票（背景、盤面、主色、選取、宮線）。"""
        return (self.bg, self.cell_bg, self.accent, self.sel_bg, self.box_line)


_NON_COLOR_FIELDS = {
    "key", "name", "is_dark", "radius", "button_radius", "grid_line_width",
    "box_line_width", "font_family", "font_size_cell", "font_size_note",
    "font_size_ui", "font_size_title",
}


def color_field_names() -> list[str]:
    """列出 Theme 中所有顏色欄位名稱（依宣告順序）。"""
    return [f.name for f in fields(Theme) if f.name not in _NON_COLOR_FIELDS]


def _channel(value: int) -> float:
    """sRGB 通道 (0–255) 轉線性值（WCAG 2.x 公式）。"""
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """計算 "#RRGGBB" 色碼的相對亮度（0 = 黑、1 = 白）。"""
    if not isinstance(color, str) or not _HEX_RE.match(color):
        raise ValueError(f"色碼格式錯誤（需為 #RRGGBB）：{color!r}")
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """依 WCAG 2.x 計算兩色對比度，回傳 1.0–21.0（與參數順序無關）。

    色碼格式錯誤時拋出 ValueError。
    """
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)
