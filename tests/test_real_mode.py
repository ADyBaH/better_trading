"""Тесты на core/real_mode.py — единый источник истины режима."""

import pytest

import config
from core.real_mode import (
    RealModeError,
    check_real_mode,
    is_live,
    is_mock,
)


class TestMockMode:
    def test_default_is_mock(self):
        # В config.py по умолчанию "mock"
        assert config.REAL_TRADING_MODE == "mock"
        assert is_mock() is True
        assert is_live() is False
        assert check_real_mode() == "mock"


class TestLiveMode:
    def test_live_without_env_raises(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "live")
        monkeypatch.delenv("CONFIRM_LIVE", raising=False)
        with pytest.raises(RealModeError, match="CONFIRM_LIVE"):
            check_real_mode()

    def test_live_with_env_ok(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "live")
        monkeypatch.setenv("CONFIRM_LIVE", "1")
        assert check_real_mode() == "live"
        assert is_live() is True
        assert is_mock() is False

    def test_live_with_wrong_env_raises(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "live")
        monkeypatch.setenv("CONFIRM_LIVE", "0")
        with pytest.raises(RealModeError):
            check_real_mode()


class TestInvalidMode:
    def test_invalid_mode_raises(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "foo")
        with pytest.raises(RealModeError, match="ожидается одно из"):
            check_real_mode()

    def test_is_mock_raises_on_invalid(self, monkeypatch):
        monkeypatch.setattr(config, "REAL_TRADING_MODE", "foo")
        with pytest.raises(RealModeError):
            is_mock()
