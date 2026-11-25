"""
Хранилище свечей в SQLite.
Таблица candles: (symbol, interval, begin) — уникальный ключ.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from trader.db import migrate, get_version
from typing import Callable

import pandas as pd

from core.logger import get_logger
import config

log = get_logger(__name__)

MIGRATIONS_CANDLES: list[tuple[int, Callable]] = [
    # version 1 — базовая схема (CREATE TABLE уже в init_db)
    (1, lambda conn: None),
    # При добавлении колонки:
    # (2, _m_add_candles_column_xxx),
]


@contextmanager
def _connect():
    """Контекстный менеджер для соединения с БД."""
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Создаёт таблицу candles и применяет миграции (T-06: schema_versions)."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                symbol   TEXT    NOT NULL,
                interval INTEGER NOT NULL,
                begin    TEXT    NOT NULL,
                open     REAL,
                high     REAL,
                low      REAL,
                close    REAL,
                volume   INTEGER,
                PRIMARY KEY (symbol, interval, begin)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_begin
            ON candles (symbol, interval, begin)
        """)
        # T-06: миграции через schema_versions
        version = migrate(conn, "candles", MIGRATIONS_CANDLES)
    log.debug("БД инициализирована: %s (candles schema=%d)", config.DB_PATH, version)


def save_candles(symbol: str, interval: int, df: pd.DataFrame) -> int:
    """
    Сохраняет свечи в БД. Дубликаты (symbol, interval, begin) перезаписываются.
    Возвращает число вставленных/обновлённых строк.
    """
    if df.empty:
        return 0

    rows = [
        (
            symbol,
            interval,
            (
                row["begin"].isoformat()
                if hasattr(row["begin"], "isoformat")
                else str(row["begin"])
            ),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            int(row["volume"]) if pd.notna(row["volume"]) else 0,
        )
        for _, row in df.iterrows()
    ]

    with _connect() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO candles
            (symbol, interval, begin, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            rows,
        )

    log.info("Сохранено свечей: %d (%s interval=%s)", len(rows), symbol, interval)
    return len(rows)


def load_candles(
    symbol: str,
    interval: int,
    count: int = 500,
) -> pd.DataFrame:
    """
    Загружает последние `count` свечей из БД.
    Возвращает DataFrame с колонками begin, open, high, low, close, volume.
    """
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT begin, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND interval = ?
            ORDER BY begin DESC
            LIMIT ?
        """,
            conn,
            params=(symbol, interval, count),
        )

    if df.empty:
        return df

    df["begin"] = pd.to_datetime(df["begin"])
    df = df.sort_values("begin").reset_index(drop=True)
    return df


def get_last_begin(symbol: str, interval: int) -> str | None:
    """Возвращает время последней свечи в БД (ISO-строку) или None."""
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT MAX(begin) FROM candles
            WHERE symbol = ? AND interval = ?
        """,
            (symbol, interval),
        )
        result = cur.fetchone()[0]
    return result
