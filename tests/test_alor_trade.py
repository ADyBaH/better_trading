"""Тесты на data/api_alor_trade.py (мок-режим)."""

import pytest

import config
from core.real_mode import RealModeError
from data.api_alor_trade import cancel_order, get_orders, place_order


class TestPlaceOrder:
    def test_place_market(self):
        result = place_order("CNYRUBF", "buy", 1)
        assert result["status"] == "mock"
        ...

    def test_place_limit(self):
        result = place_order("CNYRUBF", "sell", 1, order_type="limit", price=12.500)
        assert result["status"] == "mock"
        assert result["price"] == 12.500

    def test_live_without_env_raises(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "live")
        monkeypatch.delenv("CONFIRM_LIVE", raising=False)
        with pytest.raises(RealModeError):
            place_order("CNYRUBF", "buy", 1)


class TestCancelOrder:
    def test_cancel(self):
        assert cancel_order("mock-123") is True

    def test_cancel_live_without_env_raises(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "live")
        monkeypatch.delenv("CONFIRM_LIVE", raising=False)
        with pytest.raises(RealModeError):
            cancel_order("x")


class TestGetOrders:
    def test_empty(self):
        assert get_orders() == []
