import sqlite3
import json
from typing import List, Dict, Any, Optional
from core.logger import get_logger

log = get_logger(__name__)

# Список всех колонок в правильном порядке для INSERT
# Это позволит нам не писать огромные строки SQL в основном коде
TRADE_COLUMNS = [
    "signal_id",
    "source_analysis_path",
    "symbol",
    "direction",
    "kind",
    "strength",
    "strength_score",
    "entry_price",
    "stop_price",
    "take_price",
    "level_price",
    "risk_reward",
    "net_rr",
    "trend_at_open",
    "adx_at_open",
    "day_trend_at_open",
    "structure_at_open",
    "partial_day_at_open",
    "week_trend_at_open",
    "market_state_at_open",
    "rsi_at_open",
    "atr_percentile_at_open",
    "created_at",
    "result",
    "warnings",
    "context",
    "bid_vol",
    "ask_vol",
    "market_price_at_open",
    "size",
    "balance_after",
    "mfe_source",
    "mae_source",
    "take_source",
    "take_atr_value",
    "day_range_atr_at_open",
]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE,
    source_analysis_path TEXT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    kind TEXT NOT NULL,
    strength TEXT,
    strength_score REAL,
    entry_price REAL NOT NULL,
    stop_price REAL NOT NULL,
    take_price REAL NOT NULL,
    level_price REAL,
    risk_reward REAL,
    net_rr REAL,
    trend_at_open TEXT,
    adx_at_open REAL,
    day_trend_at_open TEXT,
    structure_at_open TEXT,
    week_trend_at_open TEXT,
    market_state_at_open TEXT,
    rsi_at_open REAL,
    atr_percentile_at_open REAL,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    exit_price REAL,
    result TEXT DEFAULT 'open',
    result_points REAL,
    result_rub REAL,
    bars_to_close INTEGER,
    resolution_confidence TEXT,
    warnings TEXT,
    context TEXT,
    bid_vol REAL,
    ask_vol REAL,
    market_price_at_open REAL,
    size INTEGER DEFAULT 1,
    balance_after REAL
);
CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_trades(result);
CREATE INDEX IF NOT EXISTS idx_paper_created ON paper_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_paper_symbol ON paper_trades(symbol);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Инициализация схемы и миграции."""
    conn.row_factory = sqlite3.Row
    conn.executescript(CREATE_TABLE_SQL)

    existing = {row["name"] for row in conn.execute("PRAGMA table_info(paper_trades)")}

    # Список колонок для миграции
    migrations = [
        "market_price_at_open",
        "size",
        "balance_after",
        "week_trend_at_open",
        "market_state_at_open",
        "rsi_at_open",
        "atr_percentile_at_open",
        "mfe_points",
        "mae_points",
        "partial_day_at_open",
        "volume_ratio_at_open",
        "mfe_source",
        "mae_source",
        "take_source",
        "take_atr_value",
        "day_range_atr_at_open",
    ]

    for col in migrations:
        if col not in existing:
            # Определяем тип данных (упрощенно, можно расширить)
            dtype = "REAL"
            if "at_open" in col and "partial" not in col:
                dtype = "TEXT"
            if "partial" in col:
                dtype = "INTEGER"

            conn.execute(f"ALTER TABLE paper_trades ADD COLUMN {col} {dtype}")
    conn.commit()


def insert_trade(conn: sqlite3.Connection, data: Dict[str, Any]) -> bool:
    """
    Пытается вставить запись в таблицу paper_trades.

    Возвращает:
        True — если запись успешно вставлена.
        False — если запись уже существует (IntegrityError) или произошла другая ошибка.
    """
    columns = ", ".join(TRADE_COLUMNS)
    placeholders = ", ".join(["?"] * len(TRADE_COLUMNS))

    # Собираем значения в правильном порядке
    values = [data.get(col) for col in TRADE_COLUMNS]

    try:
        # Убрали "OR IGNORE", теперь используем обычный INSERT
        conn.execute(
            f"INSERT INTO paper_trades ({columns}) VALUES ({placeholders})", values
        )
        # Если выполнение дошло сюда без исключений — значит вставка успешна
        return True
    except sqlite3.IntegrityError:
        # Если возникла ошибка уникальности (signal_id уже есть)
        return False
    except Exception as e:
        log.error("Ошибка при вставке в БД: %s", e)
        return False


def get_open_trades_by_symbol(
    conn: sqlite3.Connection, symbol: str
) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM paper_trades WHERE symbol = ? AND result = 'open'",
        (symbol,),
    ).fetchall()


def update_trade_resolve(
    conn: sqlite3.Connection, trade_id: int, updates: Dict[str, Any]
) -> None:
    """Обновляет поля сделки по ID."""
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    sql = f"UPDATE paper_trades SET {set_clause} WHERE id = ?"
    conn.execute(sql, list(updates.values()) + [trade_id])


def get_stats_raw(
    conn: sqlite3.Connection, filters: Dict[str, Any]
) -> List[sqlite3.Row]:
    """Получает сырые данные для статистики с учетом фильтров."""
    where = []
    params = []

    if filters.get("since"):
        where.append("created_at >= ?")
        params.append(filters["since"])
    if filters.get("until"):
        where.append("created_at < ?")
        params.append(filters["until"])
    if filters.get("symbol"):
        where.append("symbol = ?")
        params.append(filters["symbol"])

    if filters.get("known_only"):
        where.append("""
            (week_trend_at_open IS NOT NULL AND week_trend_at_open != 'unknown')
            AND (market_state_at_open IS NOT NULL AND market_state_at_open != 'unknown')
            AND (rsi_at_open IS NOT NULL)
            AND (atr_percentile_at_open IS NOT NULL)
        """)

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return conn.execute(
        f"SELECT * FROM paper_trades {where_sql} ORDER BY created_at", params
    ).fetchall()


def get_prev_balance(conn: sqlite3.Connection, symbol: str, trade_id: int) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(result_rub), 0) FROM paper_trades "
        "WHERE symbol = ? AND result IN ('win', 'loss') AND id < ?",
        (symbol, trade_id),
    ).fetchone()
    return row[0] if row else 0.0
