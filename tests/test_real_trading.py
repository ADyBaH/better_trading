"""Тесты на trader/real.py + core/risk.py (мок-режим)."""

import pytest

from core.models import Signal
from core.risk import calculate_position_size
from trader.real import close_real_trade, open_real_trade


@pytest.fixture
def make_signal():
    def _make(direction="short", entry=12.500, stop=12.530, take=12.440):
        return Signal(
            direction=direction,
            kind="breakout",
            strength="medium",
            strength_score=2.0,
            entry_price=entry,
            stop_price=stop,
            take_price=take,
            matched_criteria=["A1", "B2"],
            reasons=[],
            level_price=entry,
        )

    return _make


class TestCalculatePositionSize:
    def test_size_3(self):
        size = calculate_position_size(
            risk_rub=100.0,
            entry_price=12.500,
            stop_price=12.530,
            step_cost=1.0,
            price_step=0.001,
        )
        assert size == 3

    def test_size_10(self):
        size = calculate_position_size(
            risk_rub=100.0,
            entry_price=12.500,
            stop_price=12.510,
            step_cost=1.0,
            price_step=0.001,
        )
        assert size == 10

    def test_min_size_1(self):
        size = calculate_position_size(
            risk_rub=5.0,
            entry_price=12.500,
            stop_price=12.530,
            step_cost=1.0,
            price_step=0.001,
        )
        assert size == 1


class TestOpenRealTrade:
    def test_open_trade(self, make_signal):
        sig = make_signal(direction="short", entry=12.500, stop=12.530, take=12.440)
        result = open_real_trade(sig)
        assert result is not None
        assert result["status"] == "mock"
        assert result["direction"] == "short"
        assert result["size"] > 0
        assert result["trade_id"].startswith("real-")


class TestCloseRealTrade:
    def test_close_trade(self):
        ok = close_real_trade("real-123")
        assert ok is True
