"""程式進入點：`uv run sudoku` 或 `uv run python -m sudoku.app`。"""
from __future__ import annotations

import logging
import sys


def main() -> None:
    """建立主視窗並進入事件迴圈。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        from sudoku.ui.app_window import SudokuApp
    except ImportError as exc:
        print(f"錯誤：無法載入介面套件（{exc}），請先執行 uv sync", file=sys.stderr)
        sys.exit(1)
    app = SudokuApp()
    app.mainloop()


if __name__ == "__main__":
    main()
