"""數獨介面模組：GameController（純邏輯，可測試）與 customtkinter 畫面。

注意：controller 不依賴 tkinter；畫面類別請從各子模組匯入（例如 sudoku.ui.app_window），
避免只用 controller 時也載入 GUI 套件。
"""
from .controller import CellView, GameController, format_time, peers_of

__all__ = ["CellView", "GameController", "format_time", "peers_of"]
