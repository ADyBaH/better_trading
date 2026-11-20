"""Проверка trader.paper.virtual_pnl."""

import pandas as pd
import pytest

from trader.paper import virtual_pnl

# ============================================================
# Фикстуры
# ============================================================


@pytest.fixture
def make_candles():
    """rows — список (high, low, close)."""

    def _make(rows):
        return pd.DataFrame(
            [
                {
                    "open": (h + l) / 2,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": 100,
                }
                for h, l, c in rows
            ]
        )

    return _make


# ============================================================
# Long
# ============================================================


class TestLong:
    def test_win(self, make_candles):
        df = make_candles(
            [
                (12.510, 12.500, 12.505),
                (12.535, 12.510, 12.530),  # high >= take
            ]
        )
        r = virtual_pnl(df, "long", 12.500, 12.470, 12.530)
        assert r["result"] == "win"
        assert r["exit_price"] == 12.530
        assert r["bars"] == 2
        assert r["ambiguous"] is False

    def test_loss(self, make_candles):
        df = make_candles(
            [
                (12.510, 12.500, 12.505),
                (12.510, 12.465, 12.470),  # low <= stop
            ]
        )
        r = virtual_pnl(df, "long", 12.500, 12.470, 12.530)
        assert r["result"] == "loss"
        assert r["exit_price"] == 12.470
        assert r["bars"] == 2


# ============================================================
# Short
# ============================================================


class TestShort:
    def test_win(self, make_candles):
        df = make_candles(
            [
                (12.535, 12.525, 12.530),
                (12.530, 12.495, 12.500),  # low <= take
            ]
        )
        r = virtual_pnl(df, "short", 12.530, 12.560, 12.500)
        assert r["result"] == "win"
        assert r["exit_price"] == 12.500

    def test_loss(self, make_candles):
        df = make_candles(
            [
                (12.535, 12.525, 12.530),
                (12.565, 12.530, 12.560),  # high >= stop
            ]
        )
        r = virtual_pnl(df, "short", 12.530, 12.560, 12.500)
        assert r["result"] == "loss"
        assert r["exit_price"] == 12.560


# ============================================================
# Ambiguous / timeout / open / no_data
# ============================================================


class TestEdgeCases:
    def test_ambiguous_is_loss(self, make_candles):
        df = make_candles([(12.540, 12.460, 12.500)])  # и take, и stop
        r = virtual_pnl(df, "long", 12.500, 12.470, 12.530)
        assert r["result"] == "loss"
        assert r["ambiguous"] is True

    def test_timeout(self, make_candles):
        df = make_candles(
            [
                (12.510, 12.490, 12.500),
                (12.515, 12.495, 12.505),
                (12.520, 12.500, 12.510),
            ]
        )
        r = virtual_pnl(df, "long", 12.500, 12.470, 12.530, max_bars=3)
        assert r["result"] == "timeout"
        assert r["exit_price"] == 12.510
        assert r["bars"] == 3

    def test_open(self, make_candles):
        df = make_candles(
            [
                (12.510, 12.490, 12.500),
                (12.515, 12.495, 12.505),
            ]
        )
        r = virtual_pnl(df, "long", 12.500, 12.470, 12.530, max_bars=10)
        assert r["result"] == "open"
        assert r["exit_price"] is None
        assert r["bars"] == 2

    def test_no_data(self):
        r = virtual_pnl(pd.DataFrame(), "long", 12.500, 12.470, 12.530)
        assert r["result"] == "no_data"
