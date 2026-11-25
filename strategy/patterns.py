"""
Свечи-паттерны: rejection, engulfing, volume confirmation.

Вынесено из strategy/signals.py (шаг 1 рефакторинга).
Возвращают Python bool (не numpy), чтобы тесты `is True` работали.
"""

import pandas as pd

import config
from core.logger import get_logger

log = get_logger(__name__)


def _is_rejection_candle(row: pd.Series, direction: str) -> bool:
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    body = abs(c - o)
    total_range = h - l
    if total_range == 0:
        return False
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    if direction == "long":
        return bool(lower_shadow > 2 * body and lower_shadow > total_range * 0.5)
    else:
        return bool(upper_shadow > 2 * body and upper_shadow > total_range * 0.5)


def _is_engulfing(df: pd.DataFrame, direction: str) -> bool:
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    cur = df.iloc[-1]
    if direction == "long":
        return bool(
            cur["close"] > cur["open"]
            and prev["close"] < prev["open"]
            and cur["close"] > prev["open"]
            and cur["open"] < prev["close"]
        )
    else:
        return bool(
            cur["close"] < cur["open"]
            and prev["close"] > prev["open"]
            and cur["close"] < prev["open"]
            and cur["open"] > prev["close"]
        )


def _has_volume_confirmation(df: pd.DataFrame) -> bool:
    if len(df) < config.VOLUME_LOOKBACK + 1:
        return False
    avg_volume = df["volume"].iloc[-config.VOLUME_LOOKBACK - 1 : -1].mean()
    if avg_volume <= 0:
        return False
    ratio = min(df["volume"].iloc[-1] / avg_volume, config.VOLUME_RATIO_CAP)
    return bool(ratio > config.VOLUME_MULTIPLIER)
