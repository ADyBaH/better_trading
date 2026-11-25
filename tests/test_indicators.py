"""
Тесты на indicators/calc.py: add_indicators, get_atr, get_trend_context, get_main_trend.
"""

from datetime import datetime

import pandas as pd
import pytest

from indicators.calc import (
    add_indicators,
    get_atr,
    get_main_trend,
    get_trend_context,
)

# ============================================================
# Фикстуры
# ============================================================


@pytest.fixture
def make_candles():
    """prices — список close. high/low — ±0.01."""

    def _make(prices):
        base = datetime(2026, 10, 23, 10, 0)
        return pd.DataFrame(
            [
                {
                    "begin": base + pd.Timedelta(minutes=15 * i),
                    "open": p,
                    "high": p + 0.01,
                    "low": p - 0.01,
                    "close": p,
                    "volume": 100,
                }
                for i, p in enumerate(prices)
            ]
        )

    return _make


@pytest.fixture
def prices_bull():
    """Зигзаг с HH/HL для structure='bullish'."""
    prices = []
    base = 12.5
    for i in range(50):
        for j in range(5):
            prices.append(base + 0.001 * j)
        base += 0.005
        for j in range(3):
            prices.append(base - 0.001 * j)
        base += 0.002
    while len(prices) < 250:
        prices.append(prices[-1] + 0.0001)
    return prices[:250]


@pytest.fixture
def prices_down():
    """Монотонное падение."""
    return [12.5 - 0.001 * i for i in range(250)]


@pytest.fixture
def df_bull(make_candles, prices_bull):
    return add_indicators(make_candles(prices_bull))


@pytest.fixture
def df_down(make_candles, prices_down):
    return add_indicators(make_candles(prices_down))


@pytest.fixture
def ctx_bull(df_bull):
    last = df_bull.iloc[-1]
    atr = get_atr(df_bull, period=14)
    return get_trend_context(
        df=df_bull,
        current_price=float(last["close"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"]),
        atr=atr,
    )


@pytest.fixture
def ctx_down(df_down):
    last = df_down.iloc[-1]
    atr = get_atr(df_down, period=14)
    return get_trend_context(
        df=df_down,
        current_price=float(last["close"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"]),
        atr=atr,
    )


# ============================================================
# add_indicators
# ============================================================


class TestAddIndicators:
    @pytest.mark.parametrize("col", ["ema_fast", "ema_slow", "rsi", "adx"])
    def test_column_present(self, df_bull, col):
        assert col in df_bull.columns

    @pytest.mark.parametrize("col", ["ema_fast", "ema_slow", "rsi", "adx"])
    def test_last_value_not_nan(self, df_bull, col):
        assert pd.notna(df_bull[col].iloc[-1])

    def test_ema_fast_above_slow_on_uptrend(self, df_bull):
        assert df_bull["ema_fast"].iloc[-1] > df_bull["ema_slow"].iloc[-1]


# ============================================================
# get_atr
# ============================================================


class TestGetAtr:
    def test_atr_not_none(self, df_bull):
        atr = get_atr(df_bull, period=14)
        assert atr is not None

    def test_atr_approx(self, df_bull):
        atr = get_atr(df_bull, period=14)
        assert atr == pytest.approx(0.02, abs=0.005)

    def test_atr_short_df_none(self, make_candles):
        df_short = make_candles([12.5] * 5)
        atr_short = get_atr(df_short, period=14)
        assert atr_short is None


# ============================================================
# get_trend_context
# ============================================================


class TestGetTrendContext:
    def test_day_change_positive_on_uptrend(self, ctx_bull):
        assert ctx_bull["day_change_atr"] > 0

    def test_price_direction_up(self, ctx_bull):
        assert ctx_bull["price_direction"] == "up"

    def test_structure_valid(self, ctx_bull):
        assert ctx_bull["structure"] in ("bullish", "bearish", "mixed")

    def test_day_change_negative_on_downtrend(self, ctx_down):
        assert ctx_down["day_change_atr"] < 0

    def test_price_direction_down(self, ctx_down):
        assert ctx_down["price_direction"] == "down"


# ============================================================
# get_main_trend
# ============================================================


class TestGetMainTrend:
    def test_trend_up_on_uptrend(self, ctx_bull):
        main = get_main_trend(ctx_bull)
        assert main["trend"] in ("up", "strong_up")

    def test_vote_sum_positive(self, ctx_bull):
        main = get_main_trend(ctx_bull)
        assert main["vote_sum"] > 0

    def test_vote_breakdown_is_dict(self, ctx_bull):
        main = get_main_trend(ctx_bull)
        assert isinstance(main["vote_breakdown"], dict)

    def test_trend_down_on_downtrend(self, ctx_down):
        main = get_main_trend(ctx_down)
        assert main["trend"] in ("down", "strong_down")

    def test_vote_sum_negative(self, ctx_down):
        main = get_main_trend(ctx_down)
        assert main["vote_sum"] < 0
