"""Проверка MFE/MAE в virtual_pnl + by_mfe_ratio."""

import pandas as pd
from datetime import datetime, timedelta
from trader.paper import virtual_pnl


def _make_candles(highs, lows, closes):
    """Строит DataFrame с заданными high/low/close."""
    n = len(highs)
    return pd.DataFrame(
        {
            "begin": [
                datetime(2026, 11, 17, 10, 0) + timedelta(minutes=15 * i)
                for i in range(n)
            ],
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000] * n,
        }
    )


def test_mfe_win_long():
    """Long: take сработал на свече 2 (high=12.50), MFE=100, MAE=10."""
    df = _make_candles(
        highs=[12.45, 12.50, 12.55],
        lows=[12.39, 12.42, 12.48],
        closes=[12.42, 12.48, 12.52],
    )
    pnl = virtual_pnl(df, "long", 12.40, 12.38, 12.50, price_step=0.001)
    assert pnl["result"] == "win"
    # MFE: до take high max = 12.50 → 100 пунктов
    assert pnl["mfe_points"] == 100.0
    # MAE: low min = 12.39 → 10 пунктов
    assert pnl["mae_points"] == 10.0


def test_mfe_loss_long():
    """Long: high не дошёл до тейка, low пробил стоп → MFE < take_dist, MAE ~ stop_dist."""
    df = _make_candles(
        highs=[12.42, 12.45],
        lows=[12.39, 12.37],
        closes=[12.41, 12.38],
    )
    pnl = virtual_pnl(df, "long", 12.40, 12.38, 12.50, price_step=0.001)
    assert pnl["result"] == "loss"
    # MFE: high max = 12.45 → 50 пунктов
    assert pnl["mfe_points"] == 50.0
    # MAE: low min = 12.37 → (12.40 - 12.37) / 0.001 = 30 пунктов
    assert pnl["mae_points"] == 30.0


def test_mfe_short_win():
    """Short: low уходит к тейку, high не доходит до стопа → win."""
    df = _make_candles(
        highs=[12.41, 12.40],   # ← 12.40 < stop 12.42
        lows=[12.38, 12.35],    # ← 12.35 <= take 12.35
        closes=[12.39, 12.36],
    )
    pnl = virtual_pnl(df, "short", 12.40, 12.42, 12.35, price_step=0.001)
    assert pnl["result"] == "win"
    assert pnl["mfe_points"] == 50.0   # (12.40 - 12.35) / 0.001
    assert pnl["mae_points"] == 10.0   # (12.41 - 12.40) / 0.001


def test_mfe_timeout():
    """Timeout: свечи кончились, stop/take не задеты."""
    df = _make_candles(
        highs=[12.41, 12.42],
        lows=[12.39, 12.39],   # ← 12.39 > stop 12.38
        closes=[12.40, 12.41],
    )
    pnl = virtual_pnl(df, "long", 12.40, 12.38, 12.50, max_bars=2, price_step=0.001)
    assert pnl["result"] == "timeout"
    assert pnl["mfe_points"] == 20.0   # (12.42 - 12.40) / 0.001
    assert pnl["mae_points"] == 10.0   # (12.40 - 12.39) / 0.001
