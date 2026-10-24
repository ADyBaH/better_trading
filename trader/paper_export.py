"""Экспорт paper_trades в CSV."""

import csv
import sqlite3
from pathlib import Path
from core.logger import get_logger

log = get_logger(__name__)


def export_paper_trades(
    conn: sqlite3.Connection,
    output_path: str,
    since: str | None = None,
    until: str | None = None,
    symbol: str | None = None,
) -> int:
    """
    Экспортирует paper_trades в CSV.
    Возвращает количество записей.
    """
    where = []
    params = []

    if since:
        where.append("created_at >= ?")
        params.append(since)
    if until:
        where.append("created_at < ?")
        params.append(until)
    if symbol:
        where.append("symbol = ?")
        params.append(symbol)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"SELECT * FROM paper_trades {where_sql} ORDER BY created_at",
        params,
    ).fetchall()

    if not rows:
        log.warning("paper_export: нет данных для экспорта")
        return 0

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Колонки — все поля paper_trades
    columns = [
        "id",
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
        "created_at",
        "closed_at",
        "exit_price",
        "result",
        "result_points",
        "result_rub",
        "bars_to_close",
        "resolution_confidence",
        "bid_vol",
        "ask_vol",
    ]

    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for r in rows:
            writer.writerow([r[col] for col in columns])

    log.info("paper_export: %d записей → %s", len(rows), output)
    return len(rows)
