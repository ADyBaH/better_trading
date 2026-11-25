"""
Детектор: trend_level (тренд + отбой от уровня).

Вынесено из strategy/signals.py (шаг 8.4 рефакторинга).
"""

import pandas as pd

import config
from core.logger import get_logger
from core.models import AnalysisResult, Signal
from strategy.patterns import (
    _has_volume_confirmation,
    _is_engulfing,
    _is_rejection_candle,
)
from strategy.stops import _compute_stops
from strategy.strength import _compute_strength

log = get_logger(__name__)


def detect_trend_level(
    result: AnalysisResult, df: pd.DataFrame, day_range_atr: float = 0.0
) -> list[Signal]:
    """
    Тренд + отбой от уровня.
    A1: цена у уровня.
    A2: свеча-подтверждение.
    A3: тренд по голосованию совпадает с направлением.

    ВАЖНО: при trend=transition/none сигнал НЕ создаётся (return []).
    """
    signals = []
    price = result.current_price
    atr = result.atr
    tol = config.TREND_LEVEL_TOLERANCE_ATR * atr
    ind = result.indicators

    # --- Направление по главному тренду ---
    if ind.trend in ("up", "strong_up"):
        direction = "long"
    elif ind.trend in ("down", "strong_down"):
        direction = "short"
    else:
        log.debug("trend_level пропущен: trend=%s", ind.trend)
        return []

    for lv in result.levels:
        if direction == "long" and lv.price > price:
            continue
        if direction == "short" and lv.price < price:
            continue

        dist = abs(lv.price - price)
        if dist > tol:
            continue

        has_candle = _is_rejection_candle(df.iloc[-1], direction) or _is_engulfing(
            df, direction
        )
        if not has_candle:
            continue

        matched = ["A1", "A2", "A3"]
        reasons = [
            f"тренд {ind.trend} (голосов {ind.vote_sum:+d})",
            f"отбой от уровня {lv.price:.3f}",
            "свеча-разворот",
        ]

        if _has_volume_confirmation(df):
            matched.append("D3")
            reasons.append("объём выше среднего")

        score, strength = _compute_strength(matched)
        if strength == "none":
            continue

        entry = price
        stop, take, stop_meta = _compute_stops(
            entry,
            direction,
            result.atr,
            day_range_atr=result.indicators.day_range_atr,
        )

        signal = Signal(
            direction=direction,
            kind="trend_level",
            strength=strength,
            strength_score=score,
            entry_price=entry,
            stop_price=stop,
            take_price=take,
            matched_criteria=matched,
            reasons=reasons,
            level_price=lv.price,
        )
        signal.take_source = stop_meta["take_source"]
        signal.take_atr_value = stop_meta["take_atr_value"]
        signal.day_range_atr_at_open = stop_meta["day_range_atr_at_open"]
        signals.append(signal)

    return signals
