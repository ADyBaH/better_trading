"""Проверка known_only + min_n + expectancy в paper_stats."""
import itertools
import sqlite3
from datetime import datetime

from trader.paper import init_paper_table, paper_stats


_counter = itertools.count()


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)
    return conn


def _insert(conn, **kwargs):
    defaults = {
        "signal_id": f"test-{next(_counter)}",  # ← уникальный
        "symbol": "CNYRUBF",
        "direction": "long",
        "kind": "bounce",
        "strength": "medium",
        "strength_score": 2.0,
        "entry_price": 12.4,
        "stop_price": 12.38,
        "take_price": 12.44,
        "created_at": f"2026-11-17T10:{next(_counter) % 60:02d}:00",  # ← уникальный
        "result": "win",
        "result_points": 40.0,
        "result_rub": 38.0,
        "week_trend_at_open": "bullish",
        "market_state_at_open": "normal",
        "rsi_at_open": 50.0,
        "atr_percentile_at_open": 0.5,
    }
    defaults.update(kwargs)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join(["?"] * len(defaults))
    conn.execute(
        f"INSERT INTO paper_trades ({cols}) VALUES ({placeholders})",
        tuple(defaults.values()),
    )
    conn.commit()


def test_known_only_filters_unknown():
    conn = _make_conn()
    _insert(conn, week_trend_at_open="bullish")
    _insert(conn, week_trend_at_open="unknown")  # должен быть отфильтрован
    _insert(conn, week_trend_at_open=None)  # тоже
    s = paper_stats(conn, known_only=True)
    assert s["total"] == 1


def test_min_n_filters_small_buckets():
    conn = _make_conn()
    for _ in range(5):
        _insert(conn, kind="bounce")
    for _ in range(2):
        _insert(conn, kind="breakout")
    s = paper_stats(conn, min_n=5)
    assert "bounce" in s["by_kind"]
    assert "breakout" not in s["by_kind"]


def test_expectancy_in_buckets():
    conn = _make_conn()
    _insert(conn, kind="bounce", result="win", result_points=40.0)
    _insert(conn, kind="bounce", result="loss", result_points=-20.0)
    s = paper_stats(conn)
    # expectancy = (40 + (-20)) / 2 = 10.0
    assert s["by_kind"]["bounce"]["expectancy"] == 10.0
