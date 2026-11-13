"""Проверка, что фильтрованные сигналы не попадают в result.signals (RR=null)."""

from datetime import datetime

import pandas as pd
import pytest

from core.models import AnalysisResult, IndicatorSnapshot
from strategy.signals import detect_signals
import config


def _make_df(n=30, base=12.4):
    """DataFrame с достаточным объёмом для детекторов."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "begin": datetime(2026, 11, 13, 9, 0) + pd.Timedelta(minutes=15 * i),
                "open": base,
                "high": base + 0.005,
                "low": base - 0.005,
                "close": base,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


def _make_result(week_trend="bullish", market_state="normal", trend="up"):
    ind = IndicatorSnapshot(
        ema_fast=12.0,
        ema_slow=12.1,
        rsi=50.0,
        adx=20.0,
        trend=trend,
        adx_state="trend",
        rsi_state="neutral",
        market_state=market_state,
        week_trend=week_trend,
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


def test_no_rr_null_in_result(monkeypatch):
    """После detect_signals ни один сигнал не должен иметь RR=None."""
    monkeypatch.setattr(config, "PAPER_SKIP_BULLISH_LONG", True)
    monkeypatch.setattr(config, "PAPER_SKIP_NORMAL_BREAKOUT", True)

    result = _make_result(week_trend="bullish", market_state="normal")
    df = _make_df()
    signals = detect_signals(result, df)

    for s in signals:
        assert (
            s.risk_reward is not None
        ), f"{s.kind}/{s.direction}: RR=None — сигнал не должен попасть в result"
        assert s.net_rr is not None, f"{s.kind}/{s.direction}: net_rr=None"


def test_filters_disabled_no_rr_null(monkeypatch):
    """С выключенными фильтрами RR всё равно заполнен."""
    monkeypatch.setattr(config, "PAPER_SKIP_BULLISH_LONG", False)
    monkeypatch.setattr(config, "PAPER_SKIP_NORMAL_BREAKOUT", False)

    result = _make_result(week_trend="neutral", market_state="pullback")
    df = _make_df()
    signals = detect_signals(result, df)

    for s in signals:
        assert s.risk_reward is not None
        assert s.net_rr is not None
