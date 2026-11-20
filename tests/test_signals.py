"""Тесты на signals.py (pytest)."""

import pytest
from datetime import datetime, timedelta
import pandas as pd

from core.models import AnalysisResult, IndicatorSnapshot, Level, Signal
from strategy.signals import (
    detect_bounce,
    detect_signals,
    detect_breakout,
    detect_trend_level,
    _is_rejection_candle,
    _is_engulfing,
    _has_volume_confirmation,
    _compute_strength,
    _breakout_passes_filter,
)
import config

# --- Фикстуры ---


@pytest.fixture
def make_candles():
    def _make(rows):
        base = datetime(2026, 10, 23, 10, 0)
        return pd.DataFrame(
            [
                {
                    "begin": base + timedelta(minutes=15 * i),
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                }
                for i, (o, h, l, c, v) in enumerate(rows)
            ]
        )

    return _make


@pytest.fixture
def make_result():
    def _make(
        levels,
        trend="down",
        adx=30.0,
        rsi=50.0,
        day_trend="bearish",
        current_price=12.500,
    ):
        ind = IndicatorSnapshot(
            ema_fast=12.5,
            ema_slow=12.6,
            rsi=rsi,
            adx=adx,
            trend=trend,
            adx_state="strong",
            rsi_state="neutral",
            day_trend=day_trend,
            structure="bearish",
            price_direction="down",
            vote_sum=-3,
        )
        return AnalysisResult(
            symbol="CNYRUBF",
            timestamp=datetime(2026, 10, 23, 10, 0),
            current_price=current_price,
            atr=0.030,
            timeframe="M15",
            indicators=ind,
            levels=levels,
            references=[],
            signals=[],
        )

    return _make


@pytest.fixture
def reset_filters(monkeypatch):
    """Сбрасывает все PAPER_SKIP_* в False на время теста."""
    for k in (
        "PAPER_SKIP_BULLISH_LONG",
        "PAPER_SKIP_NORMAL_BREAKOUT",
        "PAPER_SKIP_BULLISH_SHORT",
        "PAPER_SKIP_ADX_FLAT_BREAKOUT",
        "PAPER_SKIP_ADX_TREND",
        "PAPER_SKIP_BID_HEAVY",
        "PAPER_SKIP_PULLBACK_BOUNCE",
        "PAPER_SKIP_BREAKOUT",
    ):
        if hasattr(config, k):
            monkeypatch.setattr(config, k, False)
    monkeypatch.setattr(config, "BREAKOUT_FILTER", "none")
    yield


# --- _is_rejection_candle ---


def test_rejection_candle_long():
    row = pd.Series({"open": 12.50, "high": 12.52, "low": 12.44, "close": 12.49})
    assert bool(_is_rejection_candle(row, "long")) is True
    assert bool(_is_rejection_candle(row, "short")) is False


def test_rejection_candle_short():
    row = pd.Series({"open": 12.49, "high": 12.58, "low": 12.48, "close": 12.50})
    assert bool(_is_rejection_candle(row, "short")) is True


# --- _is_engulfing ---


def test_engulfing_long(make_candles):
    df = make_candles(
        [
            (12.50, 12.51, 12.49, 12.49, 100),
            (12.48, 12.53, 12.47, 12.52, 200),
        ]
    )
    assert bool(_is_engulfing(df, "long")) is True


def test_engulfing_short(make_candles):
    df = make_candles(
        [
            (12.49, 12.52, 12.48, 12.52, 100),
            (12.53, 12.55, 12.47, 12.47, 200),
        ]
    )
    assert bool(_is_engulfing(df, "short")) is True


# --- _has_volume_confirmation ---


def test_volume_confirmation_high(make_candles):
    volumes = [100] * 20 + [200]
    df = make_candles([(12.5, 12.5, 12.5, 12.5, v) for v in volumes])
    assert bool(_has_volume_confirmation(df)) is True


def test_volume_confirmation_low(make_candles):
    volumes = [100] * 21
    df = make_candles([(12.5, 12.5, 12.5, 12.5, v) for v in volumes])
    assert bool(_has_volume_confirmation(df)) is False


# --- _compute_strength ---


@pytest.mark.parametrize(
    "matched, expected",
    [
        (["A1"], (1.0, "weak")),
        (["A1", "A2"], (2.0, "medium")),
        (["A1", "A2", "D3"], (3.0, "strong")),
        (["A1", "A2", "A3"], (3.0, "medium")),
        (["B2"], (0.0, "none")),
    ],
)
def test_compute_strength(matched, expected):
    assert _compute_strength(matched) == expected


# --- detect_breakout ---


def test_detect_breakout_short(make_candles, make_result):
    level = Level(price=12.500, type="down", weight=5)
    df = make_candles(
        [
            (12.52, 12.53, 12.51, 12.52, 100),
            (12.48, 12.52, 12.47, 12.48, 200),
        ]
    )
    result = make_result([level], trend="down", adx=30.0, current_price=12.480)
    signals = detect_breakout(result, df)
    assert len(signals) == 1
    assert signals[0].direction == "short"
    assert signals[0].kind == "breakout"
    assert "A1" in signals[0].matched_criteria


# --- detect_bounce ---


def test_detect_bounce_short(make_candles, make_result):
    level = Level(price=12.515, type="down", weight=5)
    df = make_candles(
        [
            (12.52, 12.53, 12.51, 12.52, 100),
            (12.51, 12.54, 12.49, 12.51, 200),
        ]
    )
    result = make_result([level], trend="down", adx=30.0, current_price=12.510)
    signals = detect_bounce(result, df)
    assert len(signals) == 1
    assert signals[0].direction == "short"


# --- detect_trend_level ---


def test_detect_trend_level_short(make_candles, make_result):
    level = Level(price=12.510, type="down", weight=5)
    df = make_candles(
        [
            (12.51, 12.52, 12.49, 12.50, 100),
            (12.50, 12.54, 12.49, 12.50, 200),
        ]
    )
    result = make_result([level], trend="down", adx=30.0, current_price=12.500)
    signals = detect_trend_level(result, df)
    assert len(signals) == 1
    assert signals[0].direction == "short"
    assert "A3" in signals[0].matched_criteria


def test_detect_trend_level_transition_blocked(make_candles, make_result):
    level = Level(price=12.510, type="down", weight=5)
    df = make_candles(
        [
            (12.51, 12.52, 12.49, 12.50, 100),
            (12.50, 12.54, 12.49, 12.50, 200),
        ]
    )
    result = make_result([level], trend="transition", adx=15.0)
    signals = detect_trend_level(result, df)
    assert len(signals) == 0


# --- F1–F4 ---


@pytest.fixture
def breakout_signal():
    return Signal(
        direction="short",
        kind="breakout",
        strength="medium",
        strength_score=2.0,
        entry_price=12.500,
        stop_price=12.530,
        take_price=12.440,
    )


@pytest.mark.parametrize(
    "filter_name, adx, expected",
    [
        ("F1", 30.0, True),
        ("F1", 22.0, False),
        ("F2", 15.0, True),
        ("F2", 22.0, False),
    ],
)
def test_breakout_filter_adx(
    monkeypatch, make_result, breakout_signal, filter_name, adx, expected
):
    monkeypatch.setattr(config, "BREAKOUT_FILTER", filter_name)
    result = make_result([], adx=adx)
    assert _breakout_passes_filter(result, breakout_signal) is expected


def test_breakout_filter_f3_impulse(monkeypatch, make_result, breakout_signal):
    monkeypatch.setattr(config, "BREAKOUT_FILTER", "F3")
    result = make_result([], adx=30.0)
    result.indicators.market_state = "impulse"
    assert bool(_breakout_passes_filter(result, breakout_signal)) is True
    result.indicators.market_state = "normal"
    assert bool(_breakout_passes_filter(result, breakout_signal)) is False


@pytest.mark.parametrize(
    "week, direction, expected",
    [
        ("bullish", "short", False),
        ("bullish", "long", True),
        ("bearish", "long", False),
        ("bearish", "short", True),
        ("neutral", "long", True),
    ],
)
def test_breakout_filter_f4(monkeypatch, make_result, week, direction, expected):
    monkeypatch.setattr(config, "BREAKOUT_FILTER", "F4")
    sig = Signal(
        direction=direction,
        kind="breakout",
        strength="medium",
        strength_score=2.0,
        entry_price=12.500,
        stop_price=12.530,
        take_price=12.440,
    )
    result = make_result([], adx=30.0)
    result.indicators.week_trend = week
    assert _breakout_passes_filter(result, sig) is expected


def test_breakout_filter_none(monkeypatch, make_result, breakout_signal):
    monkeypatch.setattr(config, "BREAKOUT_FILTER", "none")
    result = make_result([], adx=15.0)
    assert bool(_breakout_passes_filter(result, breakout_signal)) is True


# --- kill-switch (PAPER_SKIP_BREAKOUT) через detect_signals ---


def test_kill_switch_breakout(monkeypatch, make_candles, make_result):
    """PAPER_SKIP_BREAKOUT=True → breakout не создаётся."""
    monkeypatch.setattr(config, "PAPER_SKIP_BREAKOUT", True)
    monkeypatch.setattr(config, "BREAKOUT_FILTER", "none")

    level = Level(price=12.500, type="down", weight=5)
    df = make_candles(
        [
            (12.52, 12.53, 12.51, 12.52, 100),
            (12.48, 12.52, 12.47, 12.48, 200),
        ]
    )
    result = make_result([level], trend="down", adx=30.0, current_price=12.480)

    # Без kill-switch: breakout есть
    signals = detect_signals(result, df, skip_age_check=True)
    kinds = [s.kind for s in signals]
    assert "breakout" not in kinds
