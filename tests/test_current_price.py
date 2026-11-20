"""Тест get_current_price_sync (мок-режим)."""

import pytest

from data import api_alor


@pytest.fixture
def mock_current_price(monkeypatch):
    """Мок _get_current_price — возвращает bid/ask/mid."""

    async def _fake(symbol):
        return {"bid": 12.500, "ask": 12.510, "mid": 12.505}

    monkeypatch.setattr(api_alor, "_get_current_price", _fake)
    return _fake


@pytest.fixture
def mock_current_price_empty(monkeypatch):
    """Мок _get_current_price — пустой стакан (None)."""

    async def _fake(symbol):
        return {"bid": None, "ask": None, "mid": None}

    monkeypatch.setattr(api_alor, "_get_current_price", _fake)
    return _fake


class TestGetCurrentPrice:
    def test_keys_present(self, mock_current_price):
        result = api_alor.get_current_price_sync("CNYRUBF")
        assert "bid" in result
        assert "ask" in result
        assert "mid" in result

    def test_bid_less_than_ask(self, mock_current_price):
        result = api_alor.get_current_price_sync("CNYRUBF")
        assert result["bid"] < result["ask"]

    def test_mid_is_average(self, mock_current_price):
        result = api_alor.get_current_price_sync("CNYRUBF")
        expected = round((result["bid"] + result["ask"]) / 2, 5)
        assert result["mid"] == expected

    def test_empty_orderbook_returns_none(self, mock_current_price_empty):
        result = api_alor.get_current_price_sync("CNYRUBF")
        assert result["bid"] is None
        assert result["ask"] is None
        assert result["mid"] is None
