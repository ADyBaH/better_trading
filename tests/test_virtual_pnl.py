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


# ============================================================
# T-24: вход по market_price_at_open
# ============================================================


class TestMarketEntry:
    """T-24: _resolve_entry_price + virtual_pnl от нового entry."""

    def test_uses_market_price_when_present(self, monkeypatch):
        import config
        from trader.paper import _resolve_entry_price

        monkeypatch.setattr(config, "PAPER_USE_MARKET_PRICE", True)
        trade = {"entry_price": 12.400, "market_price_at_open": 12.410}
        assert _resolve_entry_price(trade) == 12.410

    def test_fallback_to_close_when_missing(self, monkeypatch):
        import config
        from trader.paper import _resolve_entry_price

        monkeypatch.setattr(config, "PAPER_USE_MARKET_PRICE", True)
        trade = {"entry_price": 12.400, "market_price_at_open": None}
        assert _resolve_entry_price(trade) == 12.400

    def test_flag_disabled_uses_close(self, monkeypatch):
        import config
        from trader.paper import _resolve_entry_price

        monkeypatch.setattr(config, "PAPER_USE_MARKET_PRICE", False)
        trade = {"entry_price": 12.400, "market_price_at_open": 12.410}
        assert _resolve_entry_price(trade) == 12.400

    def test_mfe_mae_from_market_entry(self, make_candles):
        """MFE/MAE считаются от нового entry (market), а не от close."""
        df = make_candles(
            [
                (12.520, 12.400, 12.500),  # high 12.520, low 12.400
            ]
        )
        # long, entry=12.410 (market), take=12.530, stop=12.380
        r = virtual_pnl(df, "long", 12.410, 12.380, 12.530)
        # MFE = (12.520 - 12.410) / 0.001 = 110
        # MAE = (12.410 - 12.400) / 0.001 = 10
        assert r["mfe_points"] == 110.0
        assert r["mae_points"] == 10.0

    def test_pnl_differs_with_and_without_market(self, make_candles):
        """PnL с market entry ≠ PnL с close entry (при разных ценах)."""
        df = make_candles(
            [
                (12.520, 12.400, 12.500),
            ]
        )
        # close entry=12.400, market entry=12.410
        r_close = virtual_pnl(df, "long", 12.400, 12.380, 12.530)
        r_market = virtual_pnl(df, "long", 12.410, 12.380, 12.530)
        assert r_close["mfe_points"] == 120.0  # (12.520-12.400)
        assert r_market["mfe_points"] == 110.0  # (12.520-12.410)
        assert r_close["mfe_points"] != r_market["mfe_points"]
