"""人類技巧解題器：模擬玩家「不猜測」的邏輯推理，並記錄各技巧使用次數。

技巧依難度由淺至深嘗試，每成功一次就回到最簡單的技巧重新開始（貼近人類解題順序，
也讓統計的進階技巧次數代表「真的非用不可」的次數）：

    naked_single → hidden_single → naked_pair → hidden_pair
    → pointing → box_line → x_wing → swordfish

計數規則：
- 唯一數類（naked_single / hidden_single）：每填入一格計 1 次。
- 刪減類（pair / pointing / box_line / x_wing / swordfish）：每次「實際刪掉至少一個候選」計 1 次；
  沒有刪到任何候選的型態不計（避免把無效型態算成難度）。

候選以 81 格 9-bit 遮罩表示（已填格的遮罩為 0）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .solver import (
    BITS_OF,
    BOX_OF,
    COL_OF,
    DIGIT_OF_BIT,
    FULL_MASK,
    POPCOUNT,
    ROW_OF,
    build_masks,
)

TECHNIQUES: tuple[str, ...] = (
    "naked_single",
    "hidden_single",
    "naked_pair",
    "hidden_pair",
    "pointing",
    "box_line",
    "x_wing",
    "swordfish",
)

ROWS = [[r * 9 + c for c in range(9)] for r in range(9)]
COLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOXES = [[i for i in range(81) if BOX_OF[i] == b] for b in range(9)]
UNITS = ROWS + COLS + BOXES
PEERS = [
    sorted({j for j in ROWS[ROW_OF[i]] + COLS[COL_OF[i]] + BOXES[BOX_OF[i]] if j != i})
    for i in range(81)
]


@dataclass
class TechniqueResult:
    """技巧解題結果。

    solved: 是否只靠上述技巧就填滿盤面。
    stats: 各技巧使用次數（TECHNIQUES 全部鍵都會出現）。
    cells: 解題結束時的扁平盤面（未解完時含 0）。
    contradiction: 盤面本身矛盾（例如已填數字衝突、某格無候選）。
    """

    solved: bool
    stats: dict[str, int]
    cells: list[int]
    contradiction: bool = False
    cands: list[int] = field(default_factory=list)


def init_candidates(cells: list[int]) -> list[int] | None:
    """由已填數字推出每格候選遮罩；已填數字衝突時回 None。"""
    masks = build_masks(cells)
    if masks is None:
        return None
    rows, cols, boxes = masks
    return [
        0 if cells[i] else ~(rows[ROW_OF[i]] | cols[COL_OF[i]] | boxes[BOX_OF[i]]) & FULL_MASK
        for i in range(81)
    ]


def _place(cells: list[int], cands: list[int], i: int, bit: int) -> None:
    cells[i] = DIGIT_OF_BIT[bit]
    cands[i] = 0
    clear = ~bit
    for p in PEERS[i]:
        cands[p] &= clear


def _eliminate(cands: list[int], targets, mask: int) -> bool:
    """從 targets 各格刪除 mask 內的候選；有實際刪到才回 True。"""
    changed = False
    for j in targets:
        if cands[j] & mask:
            cands[j] &= ~mask
            changed = True
    return changed


# ---------------------------------------------------------------- 唯一數類

def find_naked_single(cells: list[int], cands: list[int]) -> int:
    """填入所有「只剩一個候選」的格子，回傳填入格數。"""
    placed = 0
    for i in range(81):
        if cells[i] == 0 and POPCOUNT[cands[i]] == 1:
            _place(cells, cands, i, cands[i])
            placed += 1
    return placed


def find_hidden_single(cells: list[int], cands: list[int]) -> int:
    """在某單位中，某數字只剩一個可放位置 → 填入；找到一個即回傳 1。"""
    for unit in UNITS:
        for bit in BITS_OF[FULL_MASK]:
            spot = -1
            for j in unit:
                if cands[j] & bit:
                    if spot != -1:
                        spot = -2
                        break
                    spot = j
            if spot >= 0:
                _place(cells, cands, spot, bit)
                return 1
    return 0


# ---------------------------------------------------------------- 數對類

def find_naked_pair(cands: list[int]) -> bool:
    """同單位兩格候選完全相同且只有 2 個 → 這兩數從單位其他格刪除。"""
    for unit in UNITS:
        seen: dict[int, int] = {}
        for j in unit:
            m = cands[j]
            if POPCOUNT[m] != 2:
                continue
            if m in seen:
                pair = (seen[m], j)
                if _eliminate(cands, (k for k in unit if k not in pair), m):
                    return True
            else:
                seen[m] = j
    return False


def find_hidden_pair(cands: list[int]) -> bool:
    """同單位兩個數字都只出現在相同兩格 → 這兩格的其他候選刪除。"""
    for unit in UNITS:
        where: dict[tuple[int, int], int] = {}
        for bit in BITS_OF[FULL_MASK]:
            spots = tuple(j for j in unit if cands[j] & bit)
            if len(spots) != 2:
                continue
            if spots in where:
                keep = where[spots] | bit
                changed = False
                for j in spots:
                    if cands[j] & ~keep:
                        cands[j] &= keep
                        changed = True
                if changed:
                    return True
            else:
                where[spots] = bit
    return False


# ---------------------------------------------------------------- 區塊刪減

def find_pointing(cands: list[int]) -> bool:
    """宮內某數字的候選全落在同一列（或行）→ 該列（行）宮外的此數字刪除。"""
    for b, box in enumerate(BOXES):
        for bit in BITS_OF[FULL_MASK]:
            spots = [j for j in box if cands[j] & bit]
            if len(spots) < 2:
                continue
            rows = {ROW_OF[j] for j in spots}
            if len(rows) == 1:
                r = rows.pop()
                if _eliminate(cands, (j for j in ROWS[r] if BOX_OF[j] != b), bit):
                    return True
            cols = {COL_OF[j] for j in spots}
            if len(cols) == 1:
                c = cols.pop()
                if _eliminate(cands, (j for j in COLS[c] if BOX_OF[j] != b), bit):
                    return True
    return False


def find_box_line(cands: list[int]) -> bool:
    """列（行）中某數字的候選全落在同一宮 → 該宮內、此列（行）以外的此數字刪除。"""
    for lines in (ROWS, COLS):
        for line in lines:
            line_set = set(line)
            for bit in BITS_OF[FULL_MASK]:
                spots = [j for j in line if cands[j] & bit]
                if len(spots) < 2:
                    continue
                boxes = {BOX_OF[j] for j in spots}
                if len(boxes) == 1:
                    b = boxes.pop()
                    if _eliminate(cands, (j for j in BOXES[b] if j not in line_set), bit):
                        return True
    return False


# ---------------------------------------------------------------- 魚類（X-Wing / Swordfish）

def _fish(cands: list[int], size: int) -> bool:
    """通用魚型：size=2 為 X-Wing、size=3 為 Swordfish。

    以「列為基準」：選 size 條列，數字 d 在這些列的候選位置都只落在同一組 size 個行內，
    則 d 必在這 size 行中被這些列佔滿 → 這些行其他列的 d 全部刪除。之後再以「行為基準」對稱處理。
    """
    for bit in BITS_OF[FULL_MASK]:
        for base_lines, cover_lines, cover_index in ((ROWS, COLS, COL_OF), (COLS, ROWS, ROW_OF)):
            # 每條基準線上 d 的位置，以「覆蓋線索引」的 9-bit 遮罩表示
            line_masks: list[tuple[int, int]] = []
            for li, line in enumerate(base_lines):
                m = 0
                for j in line:
                    if cands[j] & bit:
                        m |= 1 << cover_index[j]
                if 2 <= POPCOUNT[m] <= size:
                    line_masks.append((li, m))
            if len(line_masks) < size:
                continue
            for combo in combinations(line_masks, size):
                union = 0
                for _, m in combo:
                    union |= m
                if POPCOUNT[union] != size:
                    continue
                base_ids = {li for li, _ in combo}
                targets = []
                for ci in range(9):
                    if union & (1 << ci):
                        for j in cover_lines[ci]:
                            base_of_j = ROW_OF[j] if base_lines is ROWS else COL_OF[j]
                            if base_of_j not in base_ids:
                                targets.append(j)
                if _eliminate(cands, targets, bit):
                    return True
    return False


def find_x_wing(cands: list[int]) -> bool:
    """X-Wing：兩列中某數字都只剩相同兩行可放（或行列對調）→ 刪除這兩行其他列的該數字。"""
    return _fish(cands, 2)


def find_swordfish(cands: list[int]) -> bool:
    """Swordfish：三列中某數字的位置（各 2–3 個）合計只落在三行（或行列對調）→ 刪除這三行其他列的該數字。"""
    return _fish(cands, 3)


# ---------------------------------------------------------------- 主流程

_ELIMINATION_STEPS = (
    ("naked_pair", find_naked_pair),
    ("hidden_pair", find_hidden_pair),
    ("pointing", find_pointing),
    ("box_line", find_box_line),
    ("x_wing", find_x_wing),
    ("swordfish", find_swordfish),
)


def _has_contradiction(cells: list[int], cands: list[int]) -> bool:
    return any(cells[i] == 0 and cands[i] == 0 for i in range(81))


def solve_with_techniques(cells: list[int]) -> TechniqueResult:
    """只用人類技巧（不猜測）解扁平盤面，回傳是否解完與技巧統計。不修改輸入。"""
    cells = list(cells)
    stats = {name: 0 for name in TECHNIQUES}
    cands = init_candidates(cells)
    if cands is None:
        return TechniqueResult(False, stats, cells, contradiction=True)

    while True:
        if _has_contradiction(cells, cands):
            return TechniqueResult(False, stats, cells, contradiction=True, cands=cands)
        if all(cells):
            return TechniqueResult(True, stats, cells, cands=cands)
        n = find_naked_single(cells, cands)
        if n:
            stats["naked_single"] += n
            continue
        if find_hidden_single(cells, cands):
            stats["hidden_single"] += 1
            continue
        for name, step in _ELIMINATION_STEPS:
            if step(cands):
                stats[name] += 1
                break
        else:
            # 所有技巧都無進展 → 需要更高階技巧或猜測
            return TechniqueResult(False, stats, cells, cands=cands)
