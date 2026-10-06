"""數獨回溯解題核心：bitmask + MRV（最小剩餘值）啟發法。

盤面對外一律是 ``list[list[int]]``（9×9，0 = 空格）；內部轉成長度 81 的扁平 list，
並以 row / col / box 各 9 個 9-bit 遮罩記錄「已使用的數字」。數字 d 對應位元 ``1 << (d - 1)``。

為什麼用 bitmask：每個空格的候選集合 = ``~(row | col | box) & 0x1FF``，一次位元運算即可取得，
不需每步重掃 20 個同儕格，回溯搜尋因此快上一個數量級。
"""

from __future__ import annotations

import random

Board = list[list[int]]

FULL_MASK = 0x1FF

# 預先計算的查表：格子 → 列/行/宮索引、遮罩 → 候選數/位元清單
ROW_OF = [i // 9 for i in range(81)]
COL_OF = [i % 9 for i in range(81)]
BOX_OF = [(i // 27) * 3 + (i % 9) // 3 for i in range(81)]
POPCOUNT = [m.bit_count() for m in range(512)]
BITS_OF = [[1 << d for d in range(9) if m & (1 << d)] for m in range(512)]
DIGIT_OF_BIT = {1 << d: d + 1 for d in range(9)}


def validate_board(board: Board) -> None:
    """檢查盤面形狀與數值範圍；不合法時拋 ValueError（不檢查行列宮衝突）。"""
    if not isinstance(board, (list, tuple)) or len(board) != 9:
        raise ValueError("盤面必須是 9×9 的 list[list[int]]")
    for row in board:
        if not isinstance(row, (list, tuple)) or len(row) != 9:
            raise ValueError("盤面必須是 9×9 的 list[list[int]]")
        for v in row:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                raise ValueError(f"盤面數值必須是 0–9 的整數，收到 {v!r}")


def to_flat(board: Board) -> list[int]:
    """9×9 盤面轉成 81 長度扁平 list（會先驗證形狀）。"""
    validate_board(board)
    return [v for row in board for v in row]


def to_board(cells: list[int]) -> Board:
    """81 長度扁平 list 轉回 9×9 盤面（新物件）。"""
    return [list(cells[r * 9:(r + 1) * 9]) for r in range(9)]


def build_masks(cells: list[int]) -> tuple[list[int], list[int], list[int]] | None:
    """依已填數字建立 row/col/box 遮罩；若已填數字彼此衝突回 None。"""
    rows, cols, boxes = [0] * 9, [0] * 9, [0] * 9
    for i, v in enumerate(cells):
        if not v:
            continue
        bit = 1 << (v - 1)
        r, c, b = ROW_OF[i], COL_OF[i], BOX_OF[i]
        if rows[r] & bit or cols[c] & bit or boxes[b] & bit:
            return None
        rows[r] |= bit
        cols[c] |= bit
        boxes[b] |= bit
    return rows, cols, boxes


class _Search:
    """回溯搜尋器（MRV + bitmask）。

    以物件封裝狀態，避免遞迴時反覆傳遞大量參數；``solutions`` 只保留第一個找到的解。
    """

    __slots__ = ("boxes", "cells", "cols", "count", "empties", "first", "limit", "rng", "rows")

    def __init__(self, cells: list[int], masks, rng: random.Random | None, limit: int):
        self.cells = cells
        self.rows, self.cols, self.boxes = masks
        self.empties = [i for i, v in enumerate(cells) if v == 0]
        self.rng = rng
        self.limit = limit
        self.count = 0
        self.first: list[int] | None = None

    def run(self) -> int:
        self._dfs(len(self.empties))
        return self.count

    def _dfs(self, remaining: int) -> None:
        if remaining == 0:
            self.count += 1
            if self.first is None:
                self.first = list(self.cells)
            return
        cells, rows, cols, boxes = self.cells, self.rows, self.cols, self.boxes
        # MRV：挑候選數最少的空格；遇到 0 候選立即剪枝、1 候選直接採用
        best, best_mask, best_cnt = -1, 0, 10
        for i in self.empties:
            if cells[i]:
                continue
            m = ~(rows[ROW_OF[i]] | cols[COL_OF[i]] | boxes[BOX_OF[i]]) & FULL_MASK
            cnt = POPCOUNT[m]
            if cnt < best_cnt:
                best, best_mask, best_cnt = i, m, cnt
                if cnt <= 1:
                    break
        if best_cnt == 0:
            return
        bits = BITS_OF[best_mask]
        if self.rng is not None and len(bits) > 1:
            bits = list(bits)
            self.rng.shuffle(bits)  # 候選隨機排序 → 生成終盤多樣化
        r, c, b = ROW_OF[best], COL_OF[best], BOX_OF[best]
        for bit in bits:
            cells[best] = DIGIT_OF_BIT[bit]
            rows[r] |= bit
            cols[c] |= bit
            boxes[b] |= bit
            self._dfs(remaining - 1)
            rows[r] ^= bit
            cols[c] ^= bit
            boxes[b] ^= bit
            cells[best] = 0
            if self.count >= self.limit:
                return


def _run(cells: list[int], limit: int, rng: random.Random | None = None) -> _Search | None:
    masks = build_masks(cells)
    if masks is None:
        return None
    search = _Search(list(cells), masks, rng, limit)
    search.run()
    return search


def solve(board: Board) -> Board | None:
    """求出盤面的一個解（不修改輸入）。

    已填數字衝突或無解時回 None；形狀或數值不合法時拋 ValueError。
    若有多解，回傳搜尋順序下找到的第一個解。
    """
    search = _run(to_flat(board), limit=1)
    if search is None or search.first is None:
        return None
    return to_board(search.first)


def count_solutions(board: Board, limit: int = 2) -> int:
    """計算解的個數，數到 ``limit`` 即提前中止（預設 2，用於唯一解判定）。

    已填數字衝突回 0；``limit`` < 1 拋 ValueError。
    """
    if limit < 1:
        raise ValueError("limit 必須 >= 1")
    search = _run(to_flat(board), limit=limit)
    return 0 if search is None else search.count


def is_valid_placement(board: Board, row: int, col: int, value: int) -> bool:
    """只看行/列/宮是否已有相同數字（忽略 (row, col) 自身，不比對終盤）。

    座標需為 0–8、value 需為 1–9，否則拋 ValueError。
    """
    if not (0 <= row <= 8 and 0 <= col <= 8):
        raise ValueError(f"座標超出範圍：({row}, {col})")
    if not 1 <= value <= 9:
        raise ValueError(f"value 必須是 1–9，收到 {value!r}")
    br, bc = (row // 3) * 3, (col // 3) * 3
    for k in range(9):
        if k != col and board[row][k] == value:
            return False
        if k != row and board[k][col] == value:
            return False
        r, c = br + k // 3, bc + k % 3
        if (r, c) != (row, col) and board[r][c] == value:
            return False
    return True


def random_full_grid(rng: random.Random) -> list[int]:
    """以 rng 驅動的 MRV 回溯產生一個完整合法終盤（扁平 81 格）。"""
    search = _run([0] * 81, limit=1, rng=rng)
    assert search is not None and search.first is not None  # 空盤必有解
    return search.first


def has_other_solution(cells: list[int], index: int, value: int) -> bool:
    """假設 ``cells`` 目前唯一解中 index 格為 value：檢查若挖掉此格，是否存在 index ≠ value 的解。

    為什麼不直接 count_solutions(limit=2)：挖空前盤面已知唯一，只需找「另一個解」是否存在，
    把該格的 value 排除後找任一解即可（limit=1），搜尋量約減半。
    """
    trial = list(cells)
    trial[index] = 0
    masks = build_masks(trial)
    if masks is None:
        return False
    rows, cols, boxes = masks
    r, c, b = ROW_OF[index], COL_OF[index], BOX_OF[index]
    bit_v = 1 << (value - 1)
    cand = ~(rows[r] | cols[c] | boxes[b]) & FULL_MASK & ~bit_v
    for bit in BITS_OF[cand]:
        trial[index] = DIGIT_OF_BIT[bit]
        rows[r] |= bit
        cols[c] |= bit
        boxes[b] |= bit
        search = _Search(trial, (rows, cols, boxes), None, 1)
        found = search.run() > 0
        rows[r] ^= bit
        cols[c] ^= bit
        boxes[b] ^= bit
        if found:
            return True
    return False
