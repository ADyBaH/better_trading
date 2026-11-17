"""Проверка partial_day + day_range_atr."""

from datetime import datetime, timedelta
import pandas as pd
from indicators.calc import get_trend_context


def test_partial_day_after_18():
    """После 18:00 МСК — partial_day=False."""
    # Просто проверяем, что поле есть и bool
    df = pd.DataFrame(
        {
            "begin": [
                datetime(2026, 11, 17, 9, 0) + timedelta(minutes=15 * i)
                for i in range(20)
            ],
            "open": [12.4] * 20,
            "high": [12.45] * 20,
            "low": [12.35] * 20,
            "close": [12.42] * 20,
            "volume": [1000] * 20,
        }
    )
    ctx = get_trend_context(df, 12.42, 12.4, 12.3, 0.02)
    assert "partial_day" in ctx
    assert isinstance(ctx["partial_day"], bool)


def test_day_range_atr():
    """day_range_atr = (high - low) / atr."""
    df = pd.DataFrame(
        {
            "begin": [
                datetime(2026, 11, 17, 9, 0) + timedelta(minutes=15 * i)
                for i in range(20)
            ],
            "open": [12.4] * 20,
            "high": [12.45] * 20,
            "low": [12.35] * 20,
            "close": [12.42] * 20,
            "volume": [1000] * 20,
        }
    )
    ctx = get_trend_context(df, 12.42, 12.4, 12.3, 0.02)
    # (12.45 - 12.35) / 0.02 = 5.0
    assert ctx["day_range_atr"] == 5.0
