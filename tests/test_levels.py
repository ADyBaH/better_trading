"""
Тесты на strategy/levels.py: find_fractals, cluster_levels.
"""

from datetime import datetime

import pandas as pd
import pytest

from strategy.levels import build_levels, cluster_levels, find_fractals

# ============================================================
# Фикстуры
# ============================================================


@pytest.fixture
def make_candles():
    """rows — список (high, low)."""

    def _make(rows):
        base = datetime(2026, 10, 23, 10, 0)
        return pd.DataFrame(
            [
                {
                    "begin": base + pd.Timedelta(minutes=15 * i),
                    "open": (h + l) / 2,
                    "high": h,
                    "low": l,
                    "close": (h + l) / 2,
                    "volume": 100,
                }
                for i, (h, l) in enumerate(rows)
            ]
        )

    return _make


@pytest.fixture
def make_fractal():
    def _make(price, type_="up", tf="H1", dt=None):
        return {
            "price": price,
            "type": type_,
            "tf": tf,
            "begin": dt or datetime(2026, 10, 23, 10, 0),
        }

    return _make


# ============================================================
# find_fractals
# ============================================================


class TestFindFractals:
    def test_up_fractal(self, make_candles):
        df = make_candles(
            [
                (12.50, 12.45),
                (12.52, 12.47),
                (12.60, 12.55),  # фрактал вверх
                (12.53, 12.48),
                (12.51, 12.46),
            ]
        )
        fractals = find_fractals(df, period=2)
        assert len(fractals) == 1
        assert fractals[0]["type"] == "up"
        assert fractals[0]["price"] == 12.60

    def test_down_fractal(self, make_candles):
        df_down = make_candles(
            [
                (12.55, 12.50),
                (12.53, 12.48),
                (12.50, 12.40),  # фрактал вниз
                (12.52, 12.47),
                (12.54, 12.49),
            ]
        )
        fractals = find_fractals(df_down, period=2)
        assert len(fractals) == 1
        assert fractals[0]["type"] == "down"
        assert fractals[0]["price"] == 12.40

    def test_monotonic_no_fractals(self, make_candles):
        df_mono = make_candles(
            [
                (12.50, 12.45),
                (12.52, 12.47),
                (12.54, 12.49),
                (12.56, 12.51),
                (12.58, 12.53),
            ]
        )
        fractals = find_fractals(df_mono, period=2)
        assert len(fractals) == 0


# ============================================================
# cluster_levels
# ============================================================


class TestClusterLevels:
    def test_two_close_merge(self, make_fractal):
        fractals = [
            make_fractal(12.500),
            make_fractal(12.502, dt=datetime(2026, 10, 23, 10, 15)),
        ]
        levels = cluster_levels(fractals, tolerance=0.005)
        assert len(levels) == 1
        assert round(levels[0]["price"], 4) == 12.501
        assert levels[0]["weight"] == 2

    def test_two_far_split(self, make_fractal):
        fractals = [
            make_fractal(12.500),
            make_fractal(12.520, dt=datetime(2026, 10, 23, 10, 15)),
        ]
        levels = cluster_levels(fractals, tolerance=0.005)
        assert len(levels) == 2

    def test_mixed_type(self, make_fractal):
        fractals = [
            make_fractal(12.500, type_="up"),
            make_fractal(12.502, type_="down", dt=datetime(2026, 10, 23, 10, 15)),
        ]
        levels = cluster_levels(fractals, tolerance=0.005)
        assert len(levels) == 1
        assert levels[0]["type"] == "mixed"


# ============================================================
# build_levels (интеграционный — только импорт)
# ============================================================


class TestBuildLevels:
    def test_callable(self):
        assert callable(build_levels)
