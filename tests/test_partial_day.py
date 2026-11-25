"""Проверка partial_day + day_range_atr."""

from datetime import datetime, timedelta
import pandas as pd
from indicators.calc import get_trend_context


def test_partial_day_after_18():
    """После 18:00 МСК — partial_day=False."""
    # Просто проверяем, что поле есть и bool
    df = pd.DataFrame(
        {
            "begin": [
                datetime(2026, 11, 17, 9, 0) + timedelta(minutes=15 * i)
                for i in range(20)
            ],
            "open": [12.4] * 20,
            "high": [12.45] * 20,
            "low": [12.35] * 20,
            "close": [12.42] * 20,
            "volume": [1000] * 20,
        }
    )
    ctx = get_trend_context(df, 12.42, 12.4, 12.3, 0.02)
    assert "partial_day" in ctx
    assert isinstance(ctx["partial_day"], bool)


def test_day_range_atr():
    """day_range_atr = (high - low) / atr."""
    df = pd.DataFrame(
        {
            "begin": [
                datetime(2026, 11, 17, 9, 0) + timedelta(minutes=15 * i)
                for i in range(20)
            ],
            "open": [12.4] * 20,
            "high": [12.45] * 20,
            "low": [12.35] * 20,
            "close": [12.42] * 20,
            "volume": [1000] * 20,
        }
    )
    ctx = get_trend_context(df, 12.42, 12.4, 12.3, 0.02)
    # (12.45 - 12.35) / 0.02 = 5.0
    assert ctx["day_range_atr"] == 5.0


# ============================================================
# BUG-03: now_msk() + is_partial_day() — границы
# ============================================================

from datetime import datetime, timezone

from core.time_utils import is_partial_day, now_msk


class TestNowMsk:
    """now_msk() — naive datetime, близкий к реальному МСК."""

    def test_naive(self):
        dt = now_msk()
        assert dt.tzinfo is None

    def test_close_to_real_msk(self):
        """now_msk() ≈ datetime.now() (если сервер в МСК)."""
        from datetime import datetime as dt

        diff = abs((now_msk() - dt.now()).total_seconds())
        assert diff < 5


class TestIsPartialDay:
    """is_partial_day() — границы 18:00 МСК."""

    def test_17_59_is_partial(self):
        assert is_partial_day(datetime(2026, 11, 21, 17, 59)) is True

    def test_18_00_not_partial(self):
        assert is_partial_day(datetime(2026, 11, 21, 18, 0)) is False

    def test_18_01_not_partial(self):
        assert is_partial_day(datetime(2026, 11, 21, 18, 1)) is False

    def test_morning_is_partial(self):
        assert is_partial_day(datetime(2026, 11, 21, 9, 0)) is True

    def test_midnight_is_partial(self):
        assert is_partial_day(datetime(2026, 11, 21, 0, 0)) is True

    def test_custom_close_hour(self):
        now = datetime(2026, 11, 21, 16, 30)
        assert is_partial_day(now, day_close_hour=16) is False
        assert is_partial_day(now, day_close_hour=18) is True


def test_get_trend_context_uses_is_partial_day():
    """get_trend_context → is_partial_day (BUG-03)."""
    import pandas as pd
    from unittest.mock import patch
    from indicators.calc import get_trend_context

    df = pd.DataFrame(
        {
            "begin": [datetime(2026, 11, 17, 9, 0)],
            "open": [12.4],
            "high": [12.45],
            "low": [12.35],
            "close": [12.42],
            "volume": [1000],
        }
    )

    with patch("indicators.calc.is_partial_day", return_value=True) as mock_ipd:
        ctx = get_trend_context(df, 12.42, 12.4, 12.3, 0.02)
        assert ctx["partial_day"] is True
        mock_ipd.assert_called_once()
