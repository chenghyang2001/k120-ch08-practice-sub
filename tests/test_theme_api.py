"""主題模組公開介面測試（docs/interfaces.md 第 3 節合約）。"""
from __future__ import annotations

import dataclasses
import pathlib
import re

import pytest

import sudoku.theme as theme_mod
from sudoku.theme import (
    DEFAULT_THEME,
    Theme,
    color_field_names,
    contrast_ratio,
    get_theme,
    list_themes,
)

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

CONTRACT_FIELDS = [
    "key", "name", "is_dark",
    "bg", "surface", "surface_alt", "text", "text_muted",
    "accent", "accent_hover", "accent_text",
    "button", "button_hover", "button_text", "button_disabled", "button_disabled_text",
    "cell_bg", "given_text", "user_text", "note_text", "grid_line", "box_line",
    "sel_bg", "peer_bg", "same_num_bg", "error_text", "error_bg", "hint_text", "hint_bg",
    "radius", "button_radius", "grid_line_width", "box_line_width", "font_family",
    "font_size_cell", "font_size_note", "font_size_ui", "font_size_title",
]


def test_theme_fields_match_contract():
    assert [f.name for f in dataclasses.fields(Theme)] == CONTRACT_FIELDS


def test_theme_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        get_theme("light").bg = "#000000"  # type: ignore[misc]


def test_list_themes_count_and_dark():
    themes = list_themes()
    assert len(themes) >= 5
    assert any(t.is_dark for t in themes)
    assert any(not t.is_dark for t in themes)
    keys = [t.key for t in themes]
    assert len(keys) == len(set(keys))
    for required in ("light", "warm", "forest", "ocean", "dark"):
        assert required in keys


def test_list_themes_returns_copy():
    themes = list_themes()
    themes.clear()
    assert len(list_themes()) >= 5


@pytest.mark.parametrize("theme", list_themes(), ids=lambda t: t.key)
def test_all_colors_are_hex(theme):
    for name in color_field_names():
        assert HEX.match(getattr(theme, name)), f"{theme.key}.{name}"


@pytest.mark.parametrize("theme", list_themes(), ids=lambda t: t.key)
def test_sizes_in_recommended_range(theme):
    assert 22 <= theme.font_size_cell <= 26
    assert 9 <= theme.font_size_note <= 10
    assert 10 <= theme.radius <= 14
    assert theme.button_radius > 0
    assert theme.box_line_width == 3 and theme.grid_line_width == 1
    assert theme.font_family == "Microsoft JhengHei UI"
    assert theme.name and theme.name.strip()


@pytest.mark.parametrize("theme", list_themes(), ids=lambda t: t.key)
def test_swatches(theme):
    sw = theme.swatches()
    assert len(sw) >= 3 and all(HEX.match(c) for c in sw)


def test_get_theme_known_and_default():
    assert DEFAULT_THEME == "light"
    for t in list_themes():
        assert get_theme(t.key) is t
    assert get_theme("DARK").key == "dark"


@pytest.mark.parametrize("bad", ["", "nope", "  ", None, 123])
def test_get_theme_unknown_falls_back(bad):
    assert get_theme(bad).key == "light"  # type: ignore[arg-type]


def test_contrast_ratio_known_values():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    # 對稱性
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(contrast_ratio("#FFFFFF", "#777777"))
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)
    assert contrast_ratio("#abcdef", "#ABCDEF") == pytest.approx(1.0)


@pytest.mark.parametrize("bad", ["#FFF", "FFFFFF", "#GGGGGG", "", None, "#1234567"])
def test_contrast_ratio_rejects_bad_hex(bad):
    with pytest.raises(ValueError):
        contrast_ratio(bad, "#FFFFFF")  # type: ignore[arg-type]


def test_theme_rejects_bad_color():
    base = dataclasses.asdict(get_theme("light"))
    base["bg"] = "red"
    with pytest.raises(ValueError):
        Theme(**base)


def test_theme_module_has_no_gui_import():
    # theme 為純資料模組，不得引入 customtkinter / tkinter
    pkg = pathlib.Path(theme_mod.__file__).parent
    for py in pkg.glob("*.py"):
        content = py.read_text(encoding="utf-8")
        assert "tkinter" not in content, f"{py.name} 不可引用 tkinter/customtkinter"
