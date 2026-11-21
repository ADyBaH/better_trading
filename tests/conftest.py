"""Общие фикстуры для тестов фильтров (и не только)."""

from datetime import datetime

import pytest

import config
from core.models import AnalysisResult, IndicatorSnapshot, Signal

# ============================================================
# Конструкторы
# ============================================================


@pytest.fixture
def make_ind():
    """IndicatorSnapshot с дефолтами; переопределяется через kwargs."""

    def _make(**kwargs):
        defaults = dict(
            ema_fast=12.46,
            ema_slow=12.54,
            rsi=50.0,
            adx=22.0,
            trend="up",
            adx_state="trend",
            rsi_state="neutral",
            day_trend="bullish",
            day_change_atr=0.5,
            structure="bullish",
            price_direction="up",
            vote_sum=2,
            vote_breakdown={"ema": 1, "day": 1, "structure": 1, "price_direction": -1},
            week_trend="bearish",
            week_change_atr=-1.0,
            market_state="normal",
            impulse_atr=0.0,
            impulse_dir="none",
            volume_ratio=1.0,
        )
        defaults.update(kwargs)
        return IndicatorSnapshot(**defaults)

    return _make


@pytest.fixture
def make_result(make_ind):
    """AnalysisResult с дефолтами."""

    def _make(**kwargs):
        ind_kwargs = kwargs.pop("ind", {})
        defaults = dict(
            symbol="CNYRUBF",
            timestamp=datetime(2026, 11, 21, 12, 0),
            current_price=12.437,
            atr=0.024,
            timeframe="M15",
            indicators=make_ind(**ind_kwargs),
            levels=[],
            references=[],
            signals=[],
            order_book={},
        )
        defaults.update(kwargs)
        return AnalysisResult(**defaults)

    return _make


@pytest.fixture
def make_signal():
    """Signal с дефолтами."""

    def _make(**kwargs):
        defaults = dict(
            direction="long",
            kind="bounce",
            strength="medium",
            strength_score=2.0,
            entry_price=12.437,
            stop_price=12.413,
            take_price=12.485,
        )
        defaults.update(kwargs)
        return Signal(**defaults)

    return _make


# ============================================================
# Управление enabled
# ============================================================


ALL_SKIP_FLAGS = [
    "PAPER_SKIP_BULLISH_LONG",
    "PAPER_SKIP_NORMAL_BREAKOUT",
    "PAPER_SKIP_BULLISH_SHORT",
    "PAPER_SKIP_ADX_FLAT_BREAKOUT",
    "PAPER_SKIP_ADX_TREND",
    "PAPER_SKIP_BID_HEAVY",
    "PAPER_SKIP_PULLBACK_BOUNCE",
    "PAPER_SKIP_BREAKOUT",
]


@pytest.fixture
def only_filter(monkeypatch):
    """
    Выключает ВСЕ фильтры, потом включает только указанный.

    Использование:
        only_filter("bullish_long")           # PAPER_SKIP_BULLISH_LONG=True
        only_filter("breakout")               # PAPER_SKIP_BREAKOUT=True
        only_filter("breakout_filter", value="F1")  # BREAKOUT_FILTER="F1"
    """

    def _enable(name: str, value=True):
        # Сначала всё выключить
        for flag in ALL_SKIP_FLAGS:
            if hasattr(config, flag):
                monkeypatch.setattr(config, flag, False)
        monkeypatch.setattr(config, "BREAKOUT_FILTER", "none")

        # Потом включить нужный
        if name == "breakout_filter":
            monkeypatch.setattr(config, "BREAKOUT_FILTER", value)
        else:
            flag = f"PAPER_SKIP_{name.upper()}"
            monkeypatch.setattr(config, flag, True)

    return _enable


# Список всех PAPER_SKIP_* флагов для disable_all_filters
_ALL_SKIP_FLAGS = [
    "PAPER_SKIP_BULLISH_LONG",
    "PAPER_SKIP_NORMAL_BREAKOUT",
    "PAPER_SKIP_BULLISH_SHORT",
    "PAPER_SKIP_ADX_FLAT_BREAKOUT",
    "PAPER_SKIP_ADX_TREND",
    "PAPER_SKIP_BID_HEAVY",
    "PAPER_SKIP_PULLBACK_BOUNCE",
    "PAPER_SKIP_BREAKOUT",
]


@pytest.fixture
def disable_all_filters(monkeypatch):
    """Выключает все фильтры (PAPER_SKIP_*=False, BREAKOUT_FILTER='none')."""
    for flag in _ALL_SKIP_FLAGS:
        if hasattr(config, flag):
            monkeypatch.setattr(config, flag, False)
    monkeypatch.setattr(config, "BREAKOUT_FILTER", "none")
