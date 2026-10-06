"""數獨主題模組：集中式設計 token（顏色、圓角、線寬、字型），純資料、不依賴 GUI。

字型預設 "Microsoft JhengHei UI"（Windows）；其他平台若無此字型，
UI 層可依 FONT_FALLBACKS 順序挑選（macOS: PingFang TC、Linux: Noto Sans CJK TC）。
"""
from __future__ import annotations

from .model import (
    DEFAULT_FONT_FAMILY,
    FONT_FALLBACKS,
    Theme,
    color_field_names,
    contrast_ratio,
    relative_luminance,
)
from .palettes import ALL_THEMES

DEFAULT_THEME: str = "light"

_REGISTRY: dict[str, Theme] = {t.key: t for t in ALL_THEMES}


def list_themes() -> list[Theme]:
    """回傳所有內建主題（固定順序，淺色在前、深色在後），供 🎨 選單使用。"""
    return list(ALL_THEMES)


def get_theme(key: str) -> Theme:
    """依 key 取得主題；未知或非字串 key 一律回傳預設主題 "light"，不拋例外。"""
    if isinstance(key, str):
        theme = _REGISTRY.get(key.strip().lower())
        if theme is not None:
            return theme
    return _REGISTRY[DEFAULT_THEME]


__all__ = [
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_THEME",
    "FONT_FALLBACKS",
    "Theme",
    "color_field_names",
    "contrast_ratio",
    "get_theme",
    "list_themes",
    "relative_luminance",
]
