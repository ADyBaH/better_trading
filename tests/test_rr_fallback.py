"""Проверка, что _finalize_signal всегда заполняет RR."""

import pytest
from strategy.signals import _finalize_signal
from core.models import Signal, IndicatorSnapshot, AnalysisResult
from datetime import datetime
import pandas as pd


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


def test_rr_computed_when_gross_risk_positive():
    """entry=12.41, stop=12.38579, take=12.45842 → RR=2.0."""
    sig = Signal(
        direction="long",
        kind="trend_level",
        strength="medium",
        strength_score=2.0,
        entry_price=12.41,
        stop_price=12.38579,
        take_price=12.45842,
    )
    result = _finalize_signal(sig, _make_result(), _make_df(), None, None, "CNYRUBF")
    assert result.risk_reward == 2.0
    assert result.net_rr is not None and result.net_rr > 0


def test_rr_zero_risk_logs_error():
    """entry == stop → gross_risk=0, RR остаётся None (не падает)."""
    sig = Signal(
        direction="long",
        kind="trend_level",
        strength="medium",
        strength_score=2.0,
        entry_price=12.41,
        stop_price=12.41,
        take_price=12.45842,
    )
    result = _finalize_signal(sig, _make_result(), _make_df(), None, None, "CNYRUBF")
    assert result.risk_reward is None
