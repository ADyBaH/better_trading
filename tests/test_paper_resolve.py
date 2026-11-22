"""Проверка resolve_open_trades."""

import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest

from core.models import Signal
from trader.paper import init_paper_table, resolve_open_trades, save_signal_as_paper
import config


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_paper_table(c)
    yield c
    c.close()


@pytest.fixture
def make_signal():
    def _make(direction="long", kind="bounce", entry=12.500):
        return Signal(
            direction=direction,
            kind=kind,
            strength="medium",
            strength_score=2.0,
            entry_price=entry,
            stop_price=entry - 0.03 if direction == "long" else entry + 0.03,
            take_price=entry + 0.06 if direction == "long" else entry - 0.06,
            matched_criteria=["A1"],
            reasons=[],
            level_price=None,
            warnings=[],
            context={},
        )

    return _make


@pytest.fixture
def make_result():
    def _make(signals, timestamp, symbol="CNYRUBF", atr=0.025):
        class MockIndicator:
            trend = "up"
            adx = 25.0
            day_trend = "bullish"
            structure = "bullish"
            partial_day = False
            market_state = "normal"
            week_trend = "bearish"
            rsi = 50.0
            volume_ratio = 1.0
            day_range_atr_at_open = 2.0

        class MockResult:
            pass

        r = MockResult()
        r.symbol = symbol
        r.atr = atr
        r.timestamp = timestamp
        r.indicators = MockIndicator()
        r.signals = signals
        return r

    return _make


@pytest.fixture
def make_candles():
    def _make(start_time, rows):
        return pd.DataFrame(
            [
                {
                    "begin": start_time + timedelta(minutes=15 * i),
                    "open": (h + l) / 2,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": 100,
                }
                for i, (h, l, c) in enumerate(rows)
            ]
        )

    return _make


class TestResolveOpenTrades:
    def test_long_take(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 10, 0)
        sig = make_signal("long", entry=12.500)
        save_signal_as_paper(conn, [sig], make_result([sig], ts_open))
        df = make_candles(
            ts_open + timedelta(minutes=15),
            [(12.510, 12.500, 12.505), (12.570, 12.510, 12.560)],
        )
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 10, 35), df_m15=df
        )
        assert closed == 1
        row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
        assert row["result"] == "win"
        assert row["exit_price"] == 12.560
        assert row["bars_to_close"] == 2
        assert row["result_points"] == 60.0

    def test_long_stop(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 10, 0)
        sig = make_signal("long", entry=12.510)
        save_signal_as_paper(
            conn, [sig], make_result([sig], ts_open + timedelta(minutes=1))
        )
        df = make_candles(
            ts_open + timedelta(minutes=15),
            [(12.505, 12.460, 12.470)],
        )
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 10, 30), df_m15=df
        )
        assert closed == 1
        row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
        assert row["result"] == "loss"
        assert row["exit_price"] == 12.480
        assert row["result_points"] == -30.0

    def test_short_take(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 10, 0)
        sig = make_signal("short", entry=12.560)
        save_signal_as_paper(
            conn, [sig], make_result([sig], ts_open + timedelta(minutes=2))
        )
        df = make_candles(
            ts_open + timedelta(minutes=15),
            [(12.570, 12.490, 12.500)],
        )
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 10, 30), df_m15=df
        )
        assert closed == 1
        row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
        assert row["result"] == "win"
        assert row["result_points"] == 60.0

    def test_timeout(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 10, 0)
        sig = make_signal("long", entry=12.600)
        save_signal_as_paper(
            conn, [sig], make_result([sig], ts_open + timedelta(minutes=3))
        )
        timeout_candles = [(12.610, 12.595, 12.605) for _ in range(50)]  # ← 50
        df = make_candles(ts_open + timedelta(minutes=15), timeout_candles)
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 23, 0), df_m15=df
        )
        assert closed == 1
        row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
        assert row["result"] == "timeout"
        assert row["bars_to_close"] == config.PAPER_TIMEOUT_BARS
        assert row["result_points"] == 5.0

    def test_open(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 10, 0)
        sig = make_signal("long", entry=12.700)
        save_signal_as_paper(
            conn, [sig], make_result([sig], ts_open + timedelta(minutes=4))
        )
        df = make_candles(
            ts_open + timedelta(minutes=15),
            [(12.710, 12.695, 12.705), (12.715, 12.700, 12.710)],
        )
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 10, 45), df_m15=df
        )
        assert closed == 0
        row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
        assert row["result"] == "open"

    def test_open_bar_ignored(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 12, 0)
        sig = make_signal("long", entry=12.800)
        save_signal_as_paper(conn, [sig], make_result([sig], ts_open))
        df = make_candles(
            ts_open,
            [
                (12.870, 12.790, 12.800),  # свеча открытия — take, но не считается
                (12.810, 12.795, 12.805),
                (12.815, 12.795, 12.810),
            ],
        )
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 12, 45), df_m15=df
        )
        assert closed == 0

    def test_ambiguous(self, conn, make_signal, make_result, make_candles):
        ts_open = datetime(2026, 10, 17, 13, 0)
        sig = make_signal("long", entry=12.900)
        save_signal_as_paper(conn, [sig], make_result([sig], ts_open))
        df = make_candles(
            ts_open + timedelta(minutes=15),
            [(12.970, 12.870, 12.900)],  # и take, и stop
        )
        closed = resolve_open_trades(
            conn, "CNYRUBF", datetime(2026, 10, 17, 13, 30), df_m15=df
        )
        assert closed == 1
        row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
        assert row["result"] == "loss"
        assert row["resolution_confidence"] == "auto_ambiguous"
