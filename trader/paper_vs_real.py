"""Сравнение paper entry_price vs market_price_at_open (лаг)."""

import sqlite3
from core.logger import get_logger

log = get_logger(__name__)


def paper_vs_real_stats(
    conn: sqlite3.Connection,
    since: str | None = None,
    until: str | None = None,
    symbol: str | None = None,
) -> dict:
    """
    Сравнивает entry_price (close) vs market_price_at_open (real).
    Возвращает:
        total, with_market,
        avg_lag_points, median_lag_points, max_lag_points,
        by_direction: {long: {...}, short: {...}},
        by_result: {win: {...}, loss: {...}},
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

    total = len(rows)
    with_market = 0
    lags = []  # в пунктах

    by_direction = {"long": [], "short": []}
    by_result = {"win": [], "loss": [], "open": []}

    for r in rows:
        market = r["market_price_at_open"]
        if market is None:
            continue

        with_market += 1

        # Лаг в пунктах: (market - entry) / price_step
        from core.instruments import get_instrument

        inst = get_instrument(r["symbol"])
        lag_points = (market - r["entry_price"]) / inst.price_step
        lag_points = round(lag_points, 1)
        lags.append(lag_points)

        # По направлению
        if r["direction"] in by_direction:
            by_direction[r["direction"]].append(lag_points)

        # По результату
        if r["result"] in by_result:
            by_result[r["result"]].append(lag_points)

    def _stats(values: list[float]) -> dict:
        if not values:
            return {"count": 0, "avg": None, "median": None, "min": None, "max": None}
        import statistics

        return {
            "count": len(values),
            "avg": round(statistics.mean(values), 1),
            "median": round(statistics.median(values), 1),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
        }

    return {
        "total": total,
        "with_market": with_market,
        "overall": _stats(lags),
        "by_direction": {
            "long": _stats(by_direction["long"]),
            "short": _stats(by_direction["short"]),
        },
        "by_result": {
            "win": _stats(by_result["win"]),
            "loss": _stats(by_result["loss"]),
            "open": _stats(by_result["open"]),
        },
    }
