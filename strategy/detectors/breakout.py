"""
Детектор: breakout (пробой уровня).

Вынесено из strategy/signals.py (шаг 8.3 рефакторинга).
"""

import pandas as pd

import config
from core.logger import get_logger
from core.models import AnalysisResult, Signal
from strategy.direction import _is_direction_allowed
from strategy.patterns import _has_volume_confirmation
from strategy.stops import _compute_stops
from strategy.strength import _compute_strength

log = get_logger(__name__)


def detect_breakout(
    result: AnalysisResult, df: pd.DataFrame, day_range_atr: float = 0.0
) -> list[Signal]:
    """
    Пробой уровня.
    A1: последняя свеча ЗАКРЫЛАСЬ за уровнем, предыдущая — нет.
    B2: ADX > ADX_BREAKOUT_THRESHOLD.
    D3: объём выше среднего.
    """
    if len(df) < 2:
        return []

    signals = []
    price = result.current_price
    atr = result.atr
    buffer = config.BREAKOUT_BUFFER_ATR * atr
    last = df.iloc[-1]
    prev = df.iloc[-2]
    ind = result.indicators

    for lv in result.levels:
        # 1. Определение direction
        if (
            prev["close"] <= lv.price
            and last["close"] > lv.price + buffer
            and price > lv.price
        ):
            direction = "long"
        elif (
            prev["close"] >= lv.price
            and last["close"] < lv.price - buffer
            and price < lv.price
        ):
            direction = "short"
        else:
            continue

        # 2. Фильтр против тренда
        if not _is_direction_allowed(direction, ind.trend, "breakout"):
            continue

        # 3. Блокировка двойного конфликта
        if ind.trend == "transition":
            if ind.day_trend == "bullish" and direction == "short":
                log.info("breakout SHORT заблокирован: transition + day bullish")
                continue
            if ind.day_trend == "bearish" and direction == "long":
                log.info("breakout LONG заблокирован: transition + day bearish")
                continue

        matched = ["A1"]
        reasons = [f"свежий пробой уровня {lv.price:.3f}"]

        adx = ind.adx
        if adx is not None and adx > config.ADX_BREAKOUT_THRESHOLD:
            matched.append("B2")
            reasons.append(f"ADX {adx:.1f} > {config.ADX_BREAKOUT_THRESHOLD}")

        if _has_volume_confirmation(df):
            matched.append("D3")
            reasons.append("объём выше среднего")

        score, strength = _compute_strength(matched)
        if strength == "none":
            continue

        # --- Штраф за transition ---
        if ind.trend == "transition":
            penalty = config.PENALTY_BREAKOUT_TRANSITION
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
            kind="breakout",
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


def detect_retest(
    result: AnalysisResult, df: pd.DataFrame, day_range_atr: float = 0.0
) -> list[Signal]:
    """
    T-29: вход от ретеста пробитого уровня.

    Условие:
    1. Пробой был: за последние RETEST_LOOKBACK_BARS свечей close > level + buffer
       (для long) или close < level - buffer (для short).
    2. Ретест: последняя свеча вернулась к level ± RETEST_TOLERANCE_ATR * ATR
       (low <= level + tol для long, high >= level - tol для short).
    3. Отскок: last.close > level + RETEST_BOUNCE_ATR * ATR (для long),
       last.close < level - RETEST_BOUNCE_ATR * ATR (для short).
    """
    if len(df) < config.RETEST_LOOKBACK_BARS + 1:
        return []

    signals = []
    price = result.current_price
    atr = result.atr
    if not atr or atr <= 0:
        return []

    buffer = config.BREAKOUT_BUFFER_ATR * atr
    tol = config.RETEST_TOLERANCE_ATR * atr
    bounce = config.RETEST_BOUNCE_ATR * atr
    last = df.iloc[-1]
    ind = result.indicators
    lookback = df.iloc[-(config.RETEST_LOOKBACK_BARS + 1) : -1]  # без последней

    for lv in result.levels:
        # --- 1. Пробой был? ---
        broke_up = (lookback["close"] > lv.price + buffer).any()
        broke_down = (lookback["close"] < lv.price - buffer).any()

        if broke_up and not broke_down:
            direction = "long"
            # --- 2. Ретест (low коснулся level ± tol) ---
            retested = last["low"] <= lv.price + tol
            # --- 3. Отскок (close > level + bounce) ---
            bounced = last["close"] > lv.price + bounce
        elif broke_down and not broke_up:
            direction = "short"
            retested = last["high"] >= lv.price - tol
            bounced = last["close"] < lv.price - bounce
        else:
            continue

        if not (retested and bounced):
            continue

        # 4. Фильтр против тренда
        if not _is_direction_allowed(direction, ind.trend, "breakout"):
            continue

        # 5. Блокировка двойного конфликта (как в direct)
        if ind.trend == "transition":
            if ind.day_trend == "bullish" and direction == "short":
                continue
            if ind.day_trend == "bearish" and direction == "long":
                continue

        matched = ["A1_retest"]
        reasons = [f"ретест уровня {lv.price:.3f} после пробоя"]

        adx = ind.adx
        if adx is not None and adx > config.ADX_BREAKOUT_THRESHOLD:
            matched.append("B2")
            reasons.append(f"ADX {adx:.1f} > {config.ADX_BREAKOUT_THRESHOLD}")

        if _has_volume_confirmation(df):
            matched.append("D3")
            reasons.append("объём выше среднего")

        score, strength = _compute_strength(matched)
        if strength == "none":
            continue

        # --- Штраф за transition (как в direct) ---
        if ind.trend == "transition":
            penalty = config.PENALTY_BREAKOUT_TRANSITION
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
            kind="retest",  # ← ВАЖНО: новый kind (для stats)
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
