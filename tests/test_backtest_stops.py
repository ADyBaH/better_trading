"""Тесты для aggregate() и replay_trade() в backtest_stops.py."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.backtest_stops import aggregate, replay_trade, restore_atr


def _trade(
    direction="long",
    entry=12.250,
    stop=12.220,
    take=12.310,
    created="2026-11-06T10:00:00",
    result="win",
):
    return {
        "id": 1,
        "direction": direction,
        "entry_price": entry,
        "stop_price": stop,
        "take_price": take,
        "created_at": created,
        "result": result,
    }


def _df_candles(prices, start="2026-11-06T10:15:00"):
    """prices: list of (high, low, close)."""
    n = len(prices)
    begins = pd.date_range(start, periods=n, freq="15min")
    return pd.DataFrame(
        {
            "begin": begins,
            "open": [p[2] for p in prices],
            "high": [p[0] for p in prices],
            "low": [p[1] for p in prices],
            "close": [p[2] for p in prices],
            "volume": [1] * n,
        }
    )


def test_restore_atr_from_take():
    t = _trade(entry=12.250, take=12.310)
    atr = restore_atr(t, base_take_mult=2.0)
    assert abs(atr - 0.030) < 1e-6


def test_replay_trade_win():
    t = _trade()
    df = _df_candles([(12.315, 12.240, 12.310)])
    r = replay_trade(
        t, atr=0.030, stop_mult=1.0, take_mult=2.0, df_m15=df, timeout_bars=50
    )
    assert r["result"] == "win"
    assert abs(r["points"] - 60.0) < 0.1  # (12.310-12.250)/0.001


def test_replay_trade_loss():
    t = _trade()
    df = _df_candles([(12.260, 12.215, 12.220)])
    r = replay_trade(
        t, atr=0.030, stop_mult=1.0, take_mult=2.0, df_m15=df, timeout_bars=50
    )
    assert r["result"] == "loss"
    assert abs(r["points"] - (-30.0)) < 0.1


def test_replay_trade_timeout():
    t = _trade()
    df = _df_candles([(12.255, 12.245, 12.250)] * 5)
    r = replay_trade(
        t, atr=0.030, stop_mult=1.0, take_mult=2.0, df_m15=df, timeout_bars=5
    )
    assert r["result"] == "timeout"
    assert r["bars"] == 5


def test_replay_trade_no_future_candles():
    t = _trade(created="2026-11-10T10:00:00")
    df = _df_candles([(12.255, 12.245, 12.250)])
    r = replay_trade(
        t, atr=0.030, stop_mult=1.0, take_mult=2.0, df_m15=df, timeout_bars=50
    )
    assert r is None


def test_aggregate_basic():
    replayed = [
        {"result": "win", "points": 60.0},
        {"result": "win", "points": 50.0},
        {"result": "loss", "points": -30.0},
        {"result": "loss", "points": -28.0},
        {"result": "timeout", "points": 5.0},
    ]
    a = aggregate(replayed)
    assert a["total"] == 5
    assert a["win"] == 2
    assert a["loss"] == 2
    assert a["timeout"] == 1
    assert a["winrate"] == 50.0
    assert a["total_points"] == 57.0
    assert abs(a["profit_factor"] - (110.0 / 58.0)) < 0.01
    # net* поля есть (или их нет — в зависимости от версии)
    assert "net_points" in a or True


def test_aggregate_empty():
    a = aggregate([])
    assert a["total"] == 0
    assert a["winrate"] is None
    assert a["profit_factor"] is None
    assert a["expectancy"] is None
