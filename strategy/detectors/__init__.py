"""Детекторы сигналов: bounce, breakout, trend_level."""

from strategy.detectors.bounce import detect_bounce
from strategy.detectors.breakout import detect_breakout
from strategy.detectors.trend_level import detect_trend_level

__all__ = [
    "detect_bounce",
    "detect_breakout",
    "detect_trend_level",
]
