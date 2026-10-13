"""
Журнал сделок. CRUD для таблицы trades.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger
import config

log = get_logger(__name__)


# ============================================================
# Модель
# ============================================================


@dataclass
class Trade:
    """Одна сделка в журнале."""

    direction: str  # "long" / "short"
    entry_price: float
    datetime_open: datetime
    size: int = 1
    datetime_close: Optional[datetime] = None
    exit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_price: Optional[float] = None
    comment: str = ""
    tags: list[str] = field(default_factory=list)
    signal_kind: str = ""
    signal_strength: str = ""
    signal_score: float = 0.0
    result_points: Optional[float] = None
    result_rub: Optional[float] = None
    id: Optional[int] = None

    @property
    def is_closed(self) -> bool:
        return self.exit_price is not None and self.datetime_close is not None

    def compute_result(self) -> None:
        """Считает result_points и result_rub на основе exit_price."""
        if self.exit_price is None:
            self.result_points = None
            self.result_rub = None
            return

        if self.direction == "long":
            points = (self.exit_price - self.entry_price) / config.PRICE_STEP
        else:
            points = (self.entry_price - self.exit_price) / config.PRICE_STEP

        self.result_points = round(points, 1)
        self.result_rub = round(points * config.STEP_COST * self.size, 2)


# ============================================================
# Соединение
# ============================================================


def _journal_db_path() -> str:
    """Путь к БД журнала. Отдельно от market.db."""
    return str(Path(config.DB_PATH).parent / "journal.db")


@contextmanager
def _connect():
    db_path = _journal_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Создаёт таблицу trades, если её нет."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime_open   TEXT NOT NULL,
                datetime_close  TEXT,
                direction       TEXT NOT NULL,
                entry_price     REAL NOT NULL,
                exit_price      REAL,
                size            INTEGER DEFAULT 1,
                stop_price      REAL,
                take_price      REAL,
                comment         TEXT DEFAULT '',
                tags            TEXT DEFAULT '',
                signal_kind     TEXT DEFAULT '',
                signal_strength TEXT DEFAULT '',
                signal_score    REAL DEFAULT 0,
                result_points   REAL,
                result_rub      REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_open
            ON trades (datetime_open)
        """)
    log.debug("Журнал инициализирован: %s", _journal_db_path())


# ============================================================
# CRUD
# ============================================================


def add_trade(trade: Trade) -> int:
    """Добавляет сделку в журнал. Возвращает id."""
    trade.compute_result()

    tags_str = ",".join(trade.tags) if trade.tags else ""

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO trades (
                datetime_open, datetime_close, direction, entry_price, exit_price,
                size, stop_price, take_price, comment, tags,
                signal_kind, signal_strength, signal_score,
                result_points, result_rub
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                trade.datetime_open.isoformat(),
                trade.datetime_close.isoformat() if trade.datetime_close else None,
                trade.direction,
                trade.entry_price,
                trade.exit_price,
                trade.size,
                trade.stop_price,
                trade.take_price,
                trade.comment,
                tags_str,
                trade.signal_kind,
                trade.signal_strength,
                trade.signal_score,
                trade.result_points,
                trade.result_rub,
            ),
        )
        trade_id = cur.lastrowid

    log.info(
        "Сделка #%d добавлена: %s %s @ %.3f",
        trade_id,
        trade.direction,
        trade.signal_kind or "manual",
        trade.entry_price,
    )
    return trade_id


def close_trade(trade_id: int, exit_price: float, comment: str = "") -> None:
    """Закрывает сделку: устанавливает exit_price и пересчитывает результат."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if row is None:
            log.warning("Сделка #%d не найдена", trade_id)
            return

        trade = _row_to_trade(row)
        trade.exit_price = exit_price
        trade.datetime_close = datetime.now()
        if comment:
            trade.comment = (trade.comment + " | " + comment).strip(" |")
        trade.compute_result()

        conn.execute(
            """
            UPDATE trades
            SET exit_price = ?, datetime_close = ?, comment = ?,
                result_points = ?, result_rub = ?
            WHERE id = ?
        """,
            (
                trade.exit_price,
                trade.datetime_close.isoformat(),
                trade.comment,
                trade.result_points,
                trade.result_rub,
                trade_id,
            ),
        )

    log.info(
        "Сделка #%d закрыта @ %.3f → %.1f пунктов",
        trade_id,
        exit_price,
        trade.result_points or 0,
    )


def list_trades(limit: int = 20, only_open: bool = False) -> list[Trade]:
    """Возвращает последние сделки."""
    query = "SELECT * FROM trades"
    if only_open:
        query += " WHERE exit_price IS NULL"
    query += " ORDER BY datetime_open DESC LIMIT ?"

    with _connect() as conn:
        rows = conn.execute(query, (limit,)).fetchall()

    return [_row_to_trade(r) for r in rows]


def get_trade(trade_id: int) -> Trade | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    return _row_to_trade(row) if row else None


def _row_to_trade(row: sqlite3.Row) -> Trade:
    tags_str = row["tags"] or ""
    tags = [t for t in tags_str.split(",") if t] if tags_str else []

    def _parse_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    return Trade(
        id=row["id"],
        datetime_open=_parse_dt(row["datetime_open"]),
        datetime_close=_parse_dt(row["datetime_close"]),
        direction=row["direction"],
        entry_price=row["entry_price"],
        exit_price=row["exit_price"],
        size=row["size"],
        stop_price=row["stop_price"],
        take_price=row["take_price"],
        comment=row["comment"] or "",
        tags=tags,
        signal_kind=row["signal_kind"] or "",
        signal_strength=row["signal_strength"] or "",
        signal_score=row["signal_score"] or 0.0,
        result_points=row["result_points"],
        result_rub=row["result_rub"],
    )
