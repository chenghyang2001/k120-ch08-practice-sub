"""內建主題色盤。

設計原則：低飽和、帶灰階的現代扁平配色；高亮層級為
選取格（最深） > 相同數字 > 同行列宮（最淡）；錯誤用暖紅底 + 紅字、
提示用綠底 + 綠字，兩者皆搭配底色以免只依賴文字顏色辨識。
"""
from __future__ import annotations

from .model import Theme

LIGHT = Theme(
    key="light", name="清新淺色", is_dark=False,
    bg="#F3F5F9", surface="#FFFFFF", surface_alt="#E9EDF4",
    text="#1F2633", text_muted="#5A6372",
    accent="#4A63D8", accent_hover="#3D54BF", accent_text="#FFFFFF",
    button="#E4E8F0", button_hover="#D6DCE7", button_text="#1F2633",
    button_disabled="#ECEEF2", button_disabled_text="#A3A9B4",
    cell_bg="#FFFFFF", given_text="#1F2633", user_text="#334BBA", note_text="#6B7383",
    grid_line="#D3D9E3", box_line="#4B5466",
    sel_bg="#C8D4FA", peer_bg="#EEF1F8", same_num_bg="#DDE4FB",
    error_text="#B42318", error_bg="#FDE4E1",
    hint_text="#17693F", hint_bg="#DCF3E5",
)

WARM = Theme(
    key="warm", name="溫暖米色", is_dark=False,
    bg="#F5EFE6", surface="#FFFBF5", surface_alt="#EDE4D6",
    text="#3A2E25", text_muted="#6C5F52",
    accent="#A8552E", accent_hover="#924726", accent_text="#FFFFFF",
    button="#E9DFD0", button_hover="#DED1BE", button_text="#3A2E25",
    button_disabled="#EFE9DF", button_disabled_text="#AFA394",
    cell_bg="#FFFCF7", given_text="#3A2E25", user_text="#954620", note_text="#7A6B5B",
    grid_line="#E2D6C4", box_line="#76604C",
    sel_bg="#F2D2B6", peer_bg="#F7EEE2", same_num_bg="#F3E1CB",
    error_text="#B0261D", error_bg="#FBE1DC",
    hint_text="#2D6A37", hint_bg="#E0F0DA",
)

FOREST = Theme(
    key="forest", name="森林綠", is_dark=False,
    bg="#EDF2EE", surface="#FFFFFF", surface_alt="#E1EAE3",
    text="#1D2C23", text_muted="#55665B",
    accent="#2E7553", accent_hover="#266346", accent_text="#FFFFFF",
    button="#DAE5DC", button_hover="#CCDACF", button_text="#1D2C23",
    button_disabled="#E7EDE8", button_disabled_text="#9CA9A0",
    cell_bg="#FBFDFB", given_text="#1D2C23", user_text="#1A615A", note_text="#617166",
    grid_line="#D1DDD4", box_line="#4C6354",
    sel_bg="#BCDEC9", peer_bg="#E7F0E9", same_num_bg="#D3E9DB",
    error_text="#B0261D", error_bg="#FBE1DE",
    hint_text="#1B6438", hint_bg="#D5F0DC",
)

OCEAN = Theme(
    key="ocean", name="海洋藍", is_dark=False,
    bg="#ECF3F8", surface="#FFFFFF", surface_alt="#E0EAF3",
    text="#13283A", text_muted="#4E6276",
    accent="#1F6AA0", accent_hover="#195A88", accent_text="#FFFFFF",
    button="#DAE5EF", button_hover="#CAD9E7", button_text="#13283A",
    button_disabled="#E6ECF2", button_disabled_text="#99A8B7",
    cell_bg="#FBFDFF", given_text="#13283A", user_text="#14619E", note_text="#5C7185",
    grid_line="#D0DCE7", box_line="#46607A",
    sel_bg="#BDDBF3", peer_bg="#E5EFF7", same_num_bg="#D1E5F5",
    error_text="#B42318", error_bg="#FCE4E1",
    hint_text="#196A44", hint_bg="#D8F1E3",
)

DARK = Theme(
    key="dark", name="深色模式", is_dark=True,
    bg="#14171D", surface="#1D2129", surface_alt="#262B35",
    text="#E6E9EF", text_muted="#9AA3B2",
    accent="#7D9BFF", accent_hover="#93ADFF", accent_text="#0E1220",
    button="#2C323D", button_hover="#363D4A", button_text="#E6E9EF",
    button_disabled="#22262E", button_disabled_text="#5F6674",
    cell_bg="#1B1F27", given_text="#EEF1F6", user_text="#93B1FF", note_text="#9AA3B2",
    grid_line="#3A414E", box_line="#9AA4B6",
    sel_bg="#33436C", peer_bg="#242A36", same_num_bg="#2C3A5A",
    error_text="#FF9F98", error_bg="#4A2125",
    hint_text="#8EE0AD", hint_bg="#1D3D2B",
)

MIDNIGHT = Theme(
    key="midnight", name="午夜深藍", is_dark=True,
    bg="#0D1322", surface="#151C2F", surface_alt="#1C253D",
    text="#E3E8F4", text_muted="#95A0BB",
    accent="#5CC3C6", accent_hover="#74D0D2", accent_text="#0A1A1D",
    button="#222C47", button_hover="#2B3756", button_text="#E3E8F4",
    button_disabled="#1A2135", button_disabled_text="#57617A",
    cell_bg="#121A2C", given_text="#EAF0FA", user_text="#7DD6D9", note_text="#95A0BB",
    grid_line="#2F3A58", box_line="#8A95B6",
    sel_bg="#26475F", peer_bg="#1B2440", same_num_bg="#233656",
    error_text="#FF9C9C", error_bg="#4A1E2A",
    hint_text="#8EE3B0", hint_bg="#173D30",
)

ALL_THEMES: tuple[Theme, ...] = (LIGHT, WARM, FOREST, OCEAN, DARK, MIDNIGHT)
