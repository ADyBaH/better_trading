"""
Детектор: bounce (отбой от уровня).

Вынесено из strategy/signals.py (шаг 8.2 рефакторинга).
"""

import pandas as pd

import config
from core.logger import get_logger
from core.models import AnalysisResult, Signal
from strategy.direction import _is_direction_allowed
from strategy.patterns import (
    _has_volume_confirmation,
    _is_engulfing,
    _is_rejection_candle,
)
from strategy.stops import _compute_stops
from strategy.strength import _compute_strength

log = get_logger(__name__)


def detect_bounce(
    result: AnalysisResult, df: pd.DataFrame, day_range_atr: float = 0.0
) -> list[Signal]:
    signals = []
    price = result.current_price
    atr = result.atr
    tol = config.BOUNCE_TOLERANCE_ATR * atr

    for lv in result.levels:
        dist = abs(lv.price - price)

        if dist > tol:
            continue
        direction = "long" if lv.price <= price else "short"

        if not _is_direction_allowed(direction, result.indicators.trend, "bounce"):
            continue

        has_candle = _is_rejection_candle(df.iloc[-1], direction) or _is_engulfing(
            df, direction
        )

        if not has_candle:
            continue

        matched = ["A1", "A2"]
        reasons = [
            f"цена у уровня {lv.price:.3f} (d={dist/atr:.2f} ATR)",
            "свеча-разворот",
        ]

        rsi = result.indicators.rsi
        if rsi is not None:
            if direction == "long" and rsi < config.RSI_BOUNCE_LONG:
                matched.append("B1")
                reasons.append(f"RSI {rsi:.1f} < {config.RSI_BOUNCE_LONG}")
            elif direction == "short" and rsi > config.RSI_BOUNCE_SHORT:
                matched.append("B1")
                reasons.append(f"RSI {rsi:.1f} > {config.RSI_BOUNCE_SHORT}")

        if _has_volume_confirmation(df):
            matched.append("D3")
            reasons.append("объём выше среднего")

        score, strength = _compute_strength(matched)
        if strength == "none":
            continue

        # --- Штраф за transition ---
        if result.indicators.trend == "transition":
            penalty = config.PENALTY_BOUNCE_TRANSITION
            score = max(0.0, score - penalty)
            reasons.append(f"штраф за transition: -{penalty}")

            if score < 1.0:
                strength = "none"
            elif score < 2.0:
                strength = "weak"
            elif score < 3.0:
                strength = "medium"
            else:
                strength = "strong"

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
            kind="bounce",
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
