"""檔案儲存層：自動存檔、遊玩紀錄、每日挑戰、設定。

檔案配置（皆位於 base_dir，UTF-8 編碼）：
- savegame.json  進行中存檔  {"schema_version": 1, "game": {...}}
- records.jsonl  遊玩紀錄，一行一筆 JSON（append-only，壞行略過）
- daily.json     每日挑戰完成日期 {"schema_version": 1, "completed": ["YYYY-MM-DD", ...]}
- settings.json  使用者設定 {"schema_version": 1, "settings": {...}}

所有整檔覆寫都走「同目錄暫存檔 → fsync → os.replace」原子寫入，
寫到一半斷電也只會留下舊檔或新檔，不會出現半截 JSON。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import platformdirs

from .daily import compute_streak
from .models import DIFFICULTIES, GameRecord, GameState

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
SAVE_FILE = "savegame.json"
RECORDS_FILE = "records.jsonl"
DAILY_FILE = "daily.json"
SETTINGS_FILE = "settings.json"

# 計時存檔節流間隔：PRD 要求「重開程式誤差最多數秒」，5 秒在誤差與磁碟寫入量間取平衡
DEFAULT_TIMER_INTERVAL = 5.0
# Windows 上防毒軟體或索引服務可能短暫鎖住目標檔，os.replace 會丟 PermissionError，稍等重試即可
_REPLACE_RETRIES = 5
_REPLACE_RETRY_DELAY = 0.05


class Storage:
    """數獨遊戲的本機資料存取入口（存檔 / 紀錄 / 每日挑戰 / 設定）。"""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        timer_interval: float = DEFAULT_TIMER_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """建立儲存物件。

        base_dir 為 None 時使用 platformdirs 的使用者資料目錄；測試請傳 tmp_path。
        timer_interval：save_timer 兩次實際寫檔的最短間隔秒數（合約外的選用參數）。
        clock：單調時鐘，供測試注入假時間（合約外的選用參數）。
        """
        if base_dir is None:
            base_dir = Path(platformdirs.user_data_dir("sudoku", appauthor=False))
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.timer_interval = float(timer_interval)
        self._clock = clock
        self._lock = threading.RLock()
        self._pending: GameState | None = None   # 尚未寫出的計時狀態
        self._last_write: float | None = None    # 上次實際寫存檔的時鐘值

    # ------------------------------------------------------------------
    # 路徑
    # ------------------------------------------------------------------
    @property
    def save_path(self) -> Path:
        return self.base_dir / SAVE_FILE

    @property
    def records_path(self) -> Path:
        return self.base_dir / RECORDS_FILE

    @property
    def daily_path(self) -> Path:
        return self.base_dir / DAILY_FILE

    @property
    def settings_path(self) -> Path:
        return self.base_dir / SETTINGS_FILE

    # ------------------------------------------------------------------
    # 低階檔案工具
    # ------------------------------------------------------------------
    def _atomic_write_json(self, path: Path, payload: dict) -> None:
        """以同目錄暫存檔 + os.replace 原子寫入 JSON；失敗時清掉暫存檔並往上拋。"""
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        fd, tmp_name = tempfile.mkstemp(dir=self.base_dir, prefix=f".{path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(_REPLACE_RETRIES):
                try:
                    os.replace(tmp_path, path)
                    break
                except PermissionError:
                    if attempt == _REPLACE_RETRIES - 1:
                        raise
                    time.sleep(_REPLACE_RETRY_DELAY)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    def _backup_corrupt(self, path: Path, reason: str) -> None:
        """把壞檔改名為 <檔名>.<時間戳>.corrupt 保留現場，並記錄警告。"""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = path.with_name(f"{path.name}.{stamp}.corrupt")
        try:
            os.replace(path, target)
            logger.warning("偵測到損毀檔案 %s（%s），已備份為 %s", path, reason, target)
        except OSError as exc:
            logger.error("損毀檔案 %s 備份失敗：%s", path, exc)

    def _read_versioned(self, path: Path) -> dict | None:
        """讀取帶 schema_version 的 JSON 檔。

        無檔回 None；解析失敗或版本不支援 → 備份為 .corrupt 並回 None。
        """
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("最外層不是物件")
            data = self._migrate(data)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._backup_corrupt(path, str(exc))
            return None
        except OSError as exc:
            logger.error("讀取 %s 失敗：%s", path, exc)
            return None
        return data

    @staticmethod
    def _migrate(data: dict) -> dict:
        """依 schema_version 遷移資料；目前只有 v1，未來改版在此補遷移步驟。"""
        version = data.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError(f"缺少或非法 schema_version：{version!r}")
        if version > SCHEMA_VERSION:
            raise ValueError(f"不支援的 schema_version：{version}（程式僅支援到 {SCHEMA_VERSION}）")
        if version < 1:
            raise ValueError(f"非法 schema_version：{version}")
        return data

    # ------------------------------------------------------------------
    # 自動存檔
    # ------------------------------------------------------------------
    def _write_game(self, state: GameState) -> None:
        self._atomic_write_json(
            self.save_path, {"schema_version": SCHEMA_VERSION, "game": state.to_dict()}
        )
        self._last_write = self._clock()
        self._pending = None

    def save_game(self, state: GameState) -> None:
        """立即原子寫入存檔（每次填入、清除、筆記、提示、undo 時呼叫）。

        寫檔失敗只記錄錯誤不拋例外，避免自動存檔失敗讓遊戲崩潰。
        """
        with self._lock:
            try:
                self._write_game(state)
            except OSError as exc:
                self._pending = state  # 保留給下次 flush 再試
                logger.error("存檔失敗（%s）：%s", self.save_path, exc)

    def save_timer(self, state: GameState) -> None:
        """每秒計時觸發的輕量存檔：記下最新狀態，距上次寫檔滿 timer_interval 秒才真正寫出。

        未寫出的狀態由下一次節流到期、save_game 或 flush() 寫出。
        """
        with self._lock:
            self._pending = state
            now = self._clock()
            if self._last_write is not None and now - self._last_write < self.timer_interval:
                return
            try:
                self._write_game(state)
            except OSError as exc:
                # 失敗也更新時間，避免磁碟有問題時每秒狂寫狂失敗
                self._last_write = now
                logger.error("計時存檔失敗（%s）：%s", self.save_path, exc)

    def flush(self) -> None:
        """強制寫出尚未寫入的計時狀態（關閉程式、暫停、切換畫面前呼叫）。"""
        with self._lock:
            if self._pending is None:
                return
            try:
                self._write_game(self._pending)
            except OSError as exc:
                logger.error("flush 存檔失敗（%s）：%s", self.save_path, exc)

    def load_game(self) -> GameState | None:
        """讀取進行中存檔；無檔回 None；壞檔備份為 .corrupt 並回 None（不拋例外）。"""
        with self._lock:
            self.flush()
            data = self._read_versioned(self.save_path)
            if data is None:
                return None
            try:
                return GameState.from_dict(data.get("game"))
            except ValueError as exc:
                self._backup_corrupt(self.save_path, str(exc))
                return None

    def has_saved_game(self) -> bool:
        """是否有可繼續的存檔（磁碟上有檔，或記憶體中有尚未寫出的計時狀態）。"""
        with self._lock:
            return self._pending is not None or self.save_path.exists()

    def clear_game(self) -> None:
        """清除進行中存檔（遊戲完成或放棄後呼叫），連同未寫出的計時狀態一併丟棄。"""
        with self._lock:
            self._pending = None
            self._last_write = None
            try:
                self.save_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.error("刪除存檔失敗（%s）：%s", self.save_path, exc)

    # ------------------------------------------------------------------
    # 遊玩紀錄
    # ------------------------------------------------------------------
    def add_record(self, record: GameRecord) -> None:
        """追加一筆遊玩紀錄（JSON lines）。紀錄欄位不合法時拋 ValueError。"""
        record.validate()
        line = json.dumps(
            {"schema_version": SCHEMA_VERSION, **record.to_dict()}, ensure_ascii=False
        )
        with self._lock:
            # 上次若當機留下沒換行的半截尾行，先補換行，避免新紀錄黏在壞行後面一起被丟棄
            if self._records_tail_missing_newline():
                line = "\n" + line
            with self.records_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def _records_tail_missing_newline(self) -> bool:
        try:
            with self.records_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    return False
                handle.seek(-1, os.SEEK_END)
                return handle.read(1) != b"\n"
        except FileNotFoundError:
            return False

    def _load_records(self) -> list[GameRecord]:
        """讀出所有合法紀錄；壞行（含寫到一半的最後一行）記錄警告後略過。"""
        if not self.records_path.exists():
            return []
        records: list[GameRecord] = []
        try:
            with self.records_path.open("r", encoding="utf-8", errors="replace") as handle:
                for lineno, raw in enumerate(handle, start=1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        if not isinstance(data, dict):
                            raise ValueError("紀錄不是物件")
                        self._migrate(data)
                        records.append(GameRecord.from_dict(data))
                    except (json.JSONDecodeError, ValueError) as exc:
                        logger.warning("略過 %s 第 %d 行壞紀錄：%s", self.records_path, lineno, exc)
        except OSError as exc:
            logger.error("讀取紀錄失敗（%s）：%s", self.records_path, exc)
        return records

    def query_records(
        self,
        difficulty: str | None = None,
        completed: bool | None = None,
        is_daily: bool | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[GameRecord]:
        """依條件篩選紀錄，依 finished_at 由新到舊排序。

        - 各條件為 None 表示不篩選。
        - since / until 接受 "YYYY-MM-DD" 或 ISO 時間字串，皆為「含」端點；
          until 只給日期時涵蓋當天整天。
        - 非法難度或日期字串拋 ValueError。
        """
        if difficulty is not None and difficulty not in DIFFICULTIES:
            raise ValueError(f"未知難度：{difficulty!r}")
        lower = _parse_bound(since, is_upper=False)
        upper = _parse_bound(until, is_upper=True)

        with self._lock:
            records = self._load_records()

        result: list[tuple[datetime, GameRecord]] = []
        for record in records:
            if difficulty is not None and record.difficulty != difficulty:
                continue
            if completed is not None and record.completed != completed:
                continue
            if is_daily is not None and record.is_daily != is_daily:
                continue
            finished = _to_naive(datetime.fromisoformat(record.finished_at))
            if lower is not None and finished < lower:
                continue
            if upper is not None and finished >= upper:
                continue
            result.append((finished, record))
        result.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _, record in result]

    def get_career_stats(self) -> dict[str, dict]:
        """計算各難度生涯統計；四個難度一定都有 key，無資料時時間欄位為 None。

        played 含放棄局；best_time / avg_time / zero_mistake_wins 只看完成局。
        """
        stats: dict[str, dict] = {}
        records = self.query_records()
        for level in DIFFICULTIES:
            level_records = [r for r in records if r.difficulty == level]
            wins = [r for r in level_records if r.completed]
            times = [r.elapsed_seconds for r in wins]
            stats[level] = {
                "played": len(level_records),
                "completed": len(wins),
                "best_time": min(times) if times else None,
                "avg_time": sum(times) / len(times) if times else None,
                "zero_mistake_wins": sum(1 for r in wins if r.mistakes == 0),
            }
        return stats

    # ------------------------------------------------------------------
    # 每日挑戰
    # ------------------------------------------------------------------
    def _load_daily_days(self) -> set[date]:
        data = self._read_versioned(self.daily_path)
        if data is None:
            return set()
        raw_days = data.get("completed")
        if not isinstance(raw_days, list):
            self._backup_corrupt(self.daily_path, "completed 欄位不是 list")
            return set()
        days: set[date] = set()
        for item in raw_days:
            try:
                days.add(date.fromisoformat(item))
            except (TypeError, ValueError):
                logger.warning("略過非法每日完成日期：%r", item)
        return days

    def mark_daily_completed(self, day: date) -> None:
        """記錄某天的每日挑戰已完成（重複標記無副作用）。"""
        if not isinstance(day, date):
            raise TypeError(f"day 必須是 datetime.date，實際為 {type(day).__name__}")
        if isinstance(day, datetime):
            day = day.date()
        with self._lock:
            days = self._load_daily_days()
            if day in days:
                return
            days.add(day)
            payload = {
                "schema_version": SCHEMA_VERSION,
                "completed": [d.isoformat() for d in sorted(days)],
            }
            self._atomic_write_json(self.daily_path, payload)

    def is_daily_completed(self, day: date) -> bool:
        """查詢某天的每日挑戰是否已完成。"""
        if isinstance(day, datetime):
            day = day.date()
        with self._lock:
            return day in self._load_daily_days()

    def get_streak(self, today: date | None = None) -> tuple[int, int]:
        """回傳 (目前連續天數, 最長連續天數)；today 預設為本機今天。

        今天尚未完成但昨天有完成時，目前連續仍算到昨天。
        """
        if today is None:
            today = date.today()
        elif isinstance(today, datetime):
            today = today.date()
        with self._lock:
            days = self._load_daily_days()
        return compute_streak(days, today)

    # ------------------------------------------------------------------
    # 設定
    # ------------------------------------------------------------------
    def _load_settings(self) -> dict:
        data = self._read_versioned(self.settings_path)
        if data is None:
            return {}
        settings = data.get("settings")
        if not isinstance(settings, dict):
            self._backup_corrupt(self.settings_path, "settings 欄位不是物件")
            return {}
        return settings

    def get_setting(self, key: str, default: Any = None) -> Any:
        """讀取設定值，不存在或設定檔損毀時回 default。"""
        with self._lock:
            return self._load_settings().get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """寫入設定值（例如 "theme"）；value 必須可 JSON 序列化，否則拋 TypeError。"""
        if not isinstance(key, str):
            raise TypeError("設定 key 必須是字串")
        json.dumps(value)  # 提前檢查可序列化，避免寫出半套設定
        with self._lock:
            settings = self._load_settings()
            settings[key] = value
            self._atomic_write_json(
                self.settings_path, {"schema_version": SCHEMA_VERSION, "settings": settings}
            )


# ----------------------------------------------------------------------
# 時間區間工具
# ----------------------------------------------------------------------
def _to_naive(moment: datetime) -> datetime:
    """帶時區的時間轉成本機時間並去掉 tzinfo，讓新舊紀錄可以互相比較。"""
    if moment.tzinfo is not None:
        return moment.astimezone().replace(tzinfo=None)
    return moment


def _parse_bound(value: str | None, is_upper: bool) -> datetime | None:
    """把 since/until 轉成 datetime 邊界。

    回傳值語意：下界為「>=」，上界為「<」。
    純日期的上界轉成隔天 00:00，使當天整天都包含在內；
    含時間的上界加 1 微秒，使該時間點本身也包含在內。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"日期條件必須是字串：{value!r}")
    try:
        if len(value) == 10:
            day = date.fromisoformat(value)
            start = datetime(day.year, day.month, day.day)
            return start + timedelta(days=1) if is_upper else start
        moment = _to_naive(datetime.fromisoformat(value))
    except ValueError as exc:
        raise ValueError(f"非法日期條件：{value!r}") from exc
    return moment + timedelta(microseconds=1) if is_upper else moment
