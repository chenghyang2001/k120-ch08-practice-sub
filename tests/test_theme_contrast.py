"""主題對比度規則測試：所有內建主題都必須通過，未達標即失敗。"""
from __future__ import annotations

import pytest

from sudoku.theme import contrast_ratio, list_themes

THEMES = list_themes()
IDS = [t.key for t in THEMES]

AA_TEXT = 4.5


def _assert_ratio(theme, fg_name, bg_name, minimum):
    """斷言 theme.fg_name 對 theme.bg_name 的對比度 ≥ minimum，失敗時附實際值。"""
    fg, bg = getattr(theme, fg_name), getattr(theme, bg_name)
    ratio = contrast_ratio(fg, bg)
    assert ratio >= minimum, (
        f"[{theme.key}] {fg_name}({fg}) 對 {bg_name}({bg}) = {ratio:.2f} < {minimum}"
    )


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
@pytest.mark.parametrize("fg", ["text", "given_text", "user_text"])
@pytest.mark.parametrize("bg", ["cell_bg", "bg"])
def test_main_text_contrast(theme, fg, bg):
    _assert_ratio(theme, fg, bg, AA_TEXT)


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_text_on_surfaces(theme):
    _assert_ratio(theme, "text", "surface", AA_TEXT)
    _assert_ratio(theme, "text", "surface_alt", AA_TEXT)


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_muted_and_note_text_readable(theme):
    # 次要文字與筆記小字也要達 AA，避免小字糊掉
    _assert_ratio(theme, "text_muted", "bg", AA_TEXT)
    _assert_ratio(theme, "note_text", "cell_bg", AA_TEXT)


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_error_and_hint_states(theme):
    _assert_ratio(theme, "error_text", "error_bg", AA_TEXT)
    _assert_ratio(theme, "hint_text", "hint_bg", AA_TEXT)
    assert theme.error_bg.upper() != theme.hint_bg.upper()


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_error_hint_distinct_from_cell(theme):
    # 狀態底色必須和一般格子不同，才不只依賴文字顏色辨識
    assert theme.error_bg.upper() != theme.cell_bg.upper()
    assert theme.hint_bg.upper() != theme.cell_bg.upper()


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_grid_lines(theme):
    box = contrast_ratio(theme.box_line, theme.cell_bg)
    grid = contrast_ratio(theme.grid_line, theme.cell_bg)
    assert box >= 3.0, f"[{theme.key}] box_line 對比 {box:.2f} < 3.0"
    assert grid >= 1.3, f"[{theme.key}] grid_line 對比 {grid:.2f} < 1.3"
    assert box > grid, f"[{theme.key}] 宮線({box:.2f}) 必須比格線({grid:.2f}) 明顯"
    assert theme.box_line_width > theme.grid_line_width


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_highlight_layers_distinct(theme):
    layers = {theme.sel_bg.upper(), theme.peer_bg.upper(), theme.same_num_bg.upper()}
    assert len(layers) == 3, f"[{theme.key}] sel/peer/same_num 底色重複"
    assert theme.cell_bg.upper() not in layers


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
@pytest.mark.parametrize("bg", ["sel_bg", "peer_bg", "same_num_bg"])
@pytest.mark.parametrize("fg", ["given_text", "user_text"])
def test_digits_readable_on_highlights(theme, fg, bg):
    _assert_ratio(theme, fg, bg, AA_TEXT)


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_highlight_hierarchy(theme):
    # 選取格 > 相同數字 > 同行列宮：與格子底色的差異應遞減
    sel = contrast_ratio(theme.sel_bg, theme.cell_bg)
    same = contrast_ratio(theme.same_num_bg, theme.cell_bg)
    peer = contrast_ratio(theme.peer_bg, theme.cell_bg)
    assert sel > same > peer, f"[{theme.key}] 高亮層級錯誤 sel={sel:.2f} same={same:.2f} peer={peer:.2f}"


@pytest.mark.parametrize("theme", THEMES, ids=IDS)
def test_button_contrast(theme):
    _assert_ratio(theme, "accent_text", "accent", AA_TEXT)
    _assert_ratio(theme, "accent_text", "accent_hover", AA_TEXT)
    _assert_ratio(theme, "button_text", "button", AA_TEXT)
    _assert_ratio(theme, "button_text", "button_hover", AA_TEXT)
    assert theme.button.upper() != theme.button_hover.upper()
    assert theme.accent.upper() != theme.accent_hover.upper()
