"""Тесты на data/api_alor_trade.py (мок-режим)."""

from data.api_alor_trade import cancel_order, get_orders, place_order


class TestPlaceOrder:
    def test_place_market(self):
        result = place_order("CNYRUBF", "buy", 1)
        assert result["status"] == "mock"
        assert result["symbol"] == "CNYRUBF"
        assert result["side"] == "buy"
        assert result["quantity"] == 1
        assert result["order_id"].startswith("mock-")

    def test_place_limit(self):
        result = place_order("CNYRUBF", "sell", 1, order_type="limit", price=12.500)
        assert result["status"] == "mock"
        assert result["price"] == 12.500


class TestCancelOrder:
    def test_cancel(self):
        ok = cancel_order("mock-123")
        assert ok is True


class TestGetOrders:
    def test_empty(self):
        orders = get_orders()
        assert orders == []
