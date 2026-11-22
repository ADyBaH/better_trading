import sqlite3
import json
from typing import List, Dict, Any, Callable
from core.logger import get_logger

log = get_logger(__name__)

# --- БАЗОВАЯ СХЕМА (Только обязательные поля первой версии) ---
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
    ask_vol REAL
);
CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_trades(result);
CREATE INDEX IF NOT EXISTS idx_paper_created ON paper_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_paper_symbol ON paper_trades(symbol);
"""

# --- Система миграций (Обновленная для защиты от дублей) ---


def _get_columns(conn: sqlite3.Connection) -> List[str]:
    """Вспомогательная функция для получения списка колонок."""
    return [
        row["name"]
        for row in conn.execute("PRAGMA table_info(paper_trades)").fetchall()
    ]


def _m_add_market_price(conn):
    cols = _get_columns(conn)
    if "market_price_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN market_price_at_open REAL")


def _m_add_size(conn):
    cols = _get_columns(conn)
    if "size" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN size INTEGER DEFAULT 1")


def _m_add_balance(conn):
    cols = _get_columns(conn)
    if "balance_after" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN balance_after REAL")


def _m_add_week_trend(conn):
    cols = _get_columns(conn)
    if "week_trend_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN week_trend_at_open TEXT")


def _m_add_market_state(conn):
    cols = _get_columns(conn)
    if "market_state_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN market_state_at_open TEXT")


def _m_add_rsi(conn):
    cols = _get_columns(conn)
    if "rsi_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN rsi_at_open REAL")


def _m_add_atr_pct(conn):
    cols = _get_columns(conn)
    if "atr_percentile_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN atr_percentile_at_open REAL")


def _m_add_mfe(conn):
    cols = _get_columns(conn)
    if "mfe_points" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN mfe_points REAL")


def _m_add_mae(conn):
    cols = _get_columns(conn)
    if "mae_points" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN mae_points REAL")


def _m_add_partial(conn):
    cols = _get_columns(conn)
    if "partial_day_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN partial_day_at_open INTEGER")


def _m_add_vol_ratio(conn):
    cols = _get_columns(conn)
    if "volume_ratio_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN volume_ratio_at_open REAL")


def _m_add_mfe_src(conn):
    cols = _get_columns(conn)
    if "mfe_source" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN mfe_source TEXT")


def _m_add_mae_src(conn):
    cols = _get_columns(conn)
    if "mae_source" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN mae_source TEXT")


def _m_add_take_src(conn):
    cols = _get_columns(conn)
    if "take_source" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN take_source TEXT")


def _m_add_take_atr(conn):
    cols = _get_columns(conn)
    if "take_atr_value" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN take_atr_value REAL")


def _m_add_day_range(conn):
    cols = _get_columns(conn)
    if "day_range_atr_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN day_range_atr_at_open REAL")


def _m_add_trend_at_open(conn):
    cols = _get_columns(conn)
    if "trend_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN trend_at_open TEXT")


def _m_add_adx_at_open(conn):
    cols = _get_columns(conn)
    if "adx_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN adx_at_open REAL")


def _m_add_day_trend_at_open(conn):
    cols = _get_columns(conn)
    if "day_trend_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN day_trend_at_open TEXT")


def _m_add_structure_at_open(conn):
    cols = _get_columns(conn)
    if "structure_at_open" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN structure_at_open TEXT")


def _m_add_closed_at(conn):
    cols = _get_columns(conn)
    if "closed_at" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN closed_at TEXT")


def _m_add_exit_price(conn):
    cols = _get_columns(conn)
    if "exit_price" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN exit_price REAL")


def _m_add_result_points(conn):
    cols = _get_columns(conn)
    if "result_points" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN result_points REAL")


def _m_add_result_rub(conn):
    cols = _get_columns(conn)
    if "result_rub" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN result_rub REAL")


def _m_add_bars_to_close(conn):
    cols = _get_columns(conn)
    if "bars_to_close" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN bars_to_close INTEGER")


def _m_add_resolution_confidence(conn):
    cols = _get_columns(conn)
    if "resolution_confidence" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN resolution_confidence TEXT")


def _m_add_bid_vol(conn):
    cols = _get_columns(conn)
    if "bid_vol" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN bid_vol REAL")


def _m_add_ask_vol(conn):
    cols = _get_columns(conn)
    if "ask_vol" not in cols:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN ask_vol REAL")


# Список миграций (остается прежним)
MIGRATIONS: List[tuple[int, Callable]] = [
    (1, _m_add_market_price),
    (2, _m_add_size),
    (3, _m_add_balance),
    (4, _m_add_week_trend),
    (5, _m_add_market_state),
    (6, _m_add_rsi),
    (7, _m_add_atr_pct),
    (8, _m_add_mfe),
    (9, _m_add_mae),
    (10, _m_add_partial),
    (11, _m_add_vol_ratio),
    (12, _m_add_mfe_src),
    (13, _m_add_mae_src),
    (14, _m_add_take_src),
    (15, _m_add_take_atr),
    (16, _m_add_day_range),
    (17, _m_add_trend_at_open),
    (18, _m_add_adx_at_open),
    (19, _m_add_day_trend_at_open),
    (20, _m_add_structure_at_open),
    (21, _m_add_closed_at),
    (22, _m_add_exit_price),
    (23, _m_add_result_points),
    (24, _m_add_result_rub),
    (25, _m_add_bars_to_close),
    (26, _m_add_resolution_confidence),
    (27, _m_add_bid_vol),
    (28, _m_add_ask_vol),
]


def init_db(conn: sqlite3.Connection) -> None:
    """Инициализация схемы с поддержкой версии и автоматических миграций."""
    conn.row_factory = sqlite3.Row

    # 1. Создаем базовую таблицу
    conn.executescript(CREATE_TABLE_SQL)

    # 2. Обрабатываем миграции в транзакции
    try:
        current_version = conn.execute("PRAGMA user_version").fetchone()[0]

        for version, func in MIGRATIONS:
            if version > current_version:
                func(conn)
                conn.execute(f"PRAGMA user_version = {version}")

        conn.commit()
        log.info(f"DB initialized. Current schema version: {current_version}")
    except Exception as e:
        conn.rollback()
        log.error(f"Failed to apply migrations: {e}")
        raise


# --- Динамическое получение колонок ---


def get_columns(conn: sqlite3.Connection) -> List[str]:
    """Возвращает список всех колонок таблицы в порядке их создания в БД."""
    cursor = conn.execute("PRAGMA table_info(paper_trades)")
    return [row["name"] for row in cursor.fetchall()]


# --- Основные операции ---


def insert_trade(conn: sqlite3.Connection, data: Dict[str, Any]) -> bool:
    columns = get_columns(conn)
    placeholders = ", ".join(["?"] * len(columns))
    values = [data.get(col) for col in columns]

    try:
        conn.execute(
            f"INSERT INTO paper_trades ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        log.error(f"DB Insert Error: {e}")
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
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    sql = f"UPDATE paper_trades SET {set_clause} WHERE id = ?"
    conn.execute(sql, list(updates.values()) + [trade_id])


def get_stats_raw(
    conn: sqlite3.Connection, filters: Dict[str, Any]
) -> List[sqlite3.Row]:
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
