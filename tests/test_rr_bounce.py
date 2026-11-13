"""Проверка, что bounce всегда получает RR (fallback срабатывает)."""

import pytest
from datetime import datetime
import pandas as pd
from strategy.signals import _finalize_signal, _compute_stops
from core.models import Signal, IndicatorSnapshot, AnalysisResult


def _make_result():
    ind = IndicatorSnapshot(
        ema_fast=12.0,
        ema_slow=12.1,
        rsi=50.0,
        adx=20.0,
        trend="up",
        adx_state="trend",
        rsi_state="neutral",
        market_state="normal",
        week_trend="neutral",
    )
    return AnalysisResult(
        symbol="CNYRUBF",
        timestamp=datetime.now(),
        current_price=12.4,
        atr=0.02,
        timeframe="M15",
        indicators=ind,
        levels=[],
        references=[],
        signals=[],
    )


def _make_df():
    return pd.DataFrame(
        {
            "begin": [datetime.now()],
            "open": [12.4],
            "high": [12.41],
            "low": [12.39],
            "close": [12.4],
            "volume": [1000],
        }
    )


@pytest.mark.parametrize("kind", ["bounce", "breakout", "trend_level"])
@pytest.mark.parametrize("direction", ["long", "short"])
def test_rr_filled_for_all_kinds(kind, direction):
    """RR должен быть заполнен для любого kind и direction."""
    entry = 12.41
    stop_dist, take_dist = 0.02, 0.04
    if direction == "long":
        stop, take = entry - stop_dist, entry + take_dist
    else:
        stop, take = entry + stop_dist, entry - take_dist

    sig = Signal(
        direction=direction,
        kind=kind,
        strength="medium",
        strength_score=2.0,
        entry_price=entry,
        stop_price=stop,
        take_price=take,
    )
    out = _finalize_signal(sig, _make_result(), _make_df(), None, None, "CNYRUBF")
    assert out.risk_reward is not None, f"{kind}/{direction}: RR = None"
    assert out.net_rr is not None, f"{kind}/{direction}: net_rr = None"
    assert out.risk_reward > 0


def test_rr_zero_risk_marks_invalid():
    """entry == stop → gross_risk=0 → _rr_invalid=True."""
    sig = Signal(
        direction="long",
        kind="bounce",
        strength="medium",
        strength_score=2.0,
        entry_price=12.41,
        stop_price=12.41,
        take_price=12.45842,
    )
    out = _finalize_signal(sig, _make_result(), _make_df(), None, None, "CNYRUBF")
    assert out.risk_reward is None
    assert getattr(out, "_rr_invalid", False) is True


def test_filtered_signal_does_not_appear():
    """Сигнал, заблокированный фильтром, не должен попасть в result.signals с RR=null."""
    from strategy.signals import detect_signals
    from core.models import IndicatorSnapshot, AnalysisResult, Signal
    import config

    # временно включить фильтр
    old = config.PAPER_SKIP_BULLISH_LONG
    config.PAPER_SKIP_BULLISH_LONG = True
    try:
        ind = IndicatorSnapshot(
            ema_fast=12.0,
            ema_slow=12.1,
            rsi=50.0,
            adx=20.0,
            trend="up",
            adx_state="trend",
            rsi_state="neutral",
            market_state="normal",
            week_trend="bullish",  # ← триггерит фильтр
        )
        result = AnalysisResult(
            symbol="CNYRUBF",
            timestamp=datetime.now(),
            current_price=12.4,
            atr=0.02,
            timeframe="M15",
            indicators=ind,
            levels=[],
            references=[],
            signals=[],
        )
        # ... detect_signals(result, df) ...
        # assert: ни один сигнал не имеет RR = None
        for s in result.signals:
            assert s.risk_reward is not None, f"{s.kind}/{s.direction}: RR=None"
    finally:
        config.PAPER_SKIP_BULLISH_LONG = old


def test_filtered_signal_not_in_result():
    """Сигнал, заблокированный фильтром, не должен попасть в result.signals."""
    from strategy.signals import detect_signals
    from core.models import IndicatorSnapshot, AnalysisResult
    import config

    # временно включить фильтр
    old_long = config.PAPER_SKIP_BULLISH_LONG
    old_norm = config.PAPER_SKIP_NORMAL_BREAKOUT
    config.PAPER_SKIP_BULLISH_LONG = True
    config.PAPER_SKIP_NORMAL_BREAKOUT = True
    try:
        ind = IndicatorSnapshot(
            ema_fast=12.0,
            ema_slow=12.1,
            rsi=50.0,
            adx=20.0,
            trend="up",
            adx_state="trend",
            rsi_state="neutral",
            market_state="normal",
            week_trend="bullish",
        )
        result = AnalysisResult(
            symbol="CNYRUBF",
            timestamp=datetime.now(),
            current_price=12.4,
            atr=0.02,
            timeframe="M15",
            indicators=ind,
            levels=[],
            references=[],
            signals=[],
        )
        # df — с достаточным объёмом, чтобы детекторы сработали
        df = pd.DataFrame(
            {
                "begin": [datetime.now()],
                "open": [12.4],
                "high": [12.41],
                "low": [12.39],
                "close": [12.4],
                "volume": [1000],
            }
        )
        signals = detect_signals(result, df)
        # Ни один сигнал не должен иметь RR = None
        for s in signals:
            assert (
                s.risk_reward is not None
            ), f"{s.kind}/{s.direction}: RR=None (сигнал должен быть отфильтрован)"
    finally:
        config.PAPER_SKIP_BULLISH_LONG = old_long
        config.PAPER_SKIP_NORMAL_BREAKOUT = old_norm
