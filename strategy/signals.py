"""
Детекторы сигналов.
MVP-1: bounce, breakout, trend_level.
Система критериев: A (структурные), B (индикаторные), D (контекст).

Шаг 1: сигналы обогащаются context, warnings, risk_reward, net_rr.
Логика score НЕ меняется.
"""

import pandas as pd
from datetime import datetime

from core.logger import get_logger
from core.models import AnalysisResult, Level, Signal
from core.instruments import commission_in_price
from strategy.strength import _compute_strength, _recalc_strength
from strategy.context import _build_context, _compute_session
from strategy.direction import _is_direction_allowed
from strategy.finalize import _finalize_signal
from strategy.stops import _compute_stops
from strategy.warnings import _build_warnings
from strategy.detectors import (
    detect_bounce,
    detect_breakout,
    detect_trend_level,
)
from strategy.patterns import (
    _is_rejection_candle,
    _is_engulfing,
    _has_volume_confirmation,
)

import config

log = get_logger(__name__)


def _nearest_level(
    levels: list[Level], price: float, direction: str = "any"
) -> Level | None:
    candidates = []
    for lv in levels:
        if direction == "above" and lv.price <= price:
            continue
        if direction == "below" and lv.price >= price:
            continue
        candidates.append(lv)
    if not candidates:
        return None
    return min(candidates, key=lambda lv: abs(lv.price - price))


def _trend_conflict(ind) -> dict:
    """
    Проверяет конфликты между источниками тренда.
    Возвращает dict:
        has_conflict: bool — есть ли конфликт
        double_conflict: bool — двойной конфликт (transition + day против)
    """
    # Одиночный конфликт: EMA против day_trend
    ema = (
        "up"
        if ind.ema_fast and ind.ema_slow and ind.ema_fast > ind.ema_slow
        else "down"
    )
    conflict = (ema == "down" and ind.day_trend == "bullish") or (
        ema == "up" and ind.day_trend == "bearish"
    )

    # Двойной: transition + day_trend против основного
    double = ind.trend == "transition" and ind.day_trend in ("bullish", "bearish")

    return {
        "has_conflict": conflict,
        "double_conflict": double,
    }


def _breakout_passes_filter(result: AnalysisResult, signal: Signal) -> bool:
    """
    Условные фильтры F1–F4 для breakout (config.BREAKOUT_FILTER).
    Возвращает True, если сигнал проходит фильтр (можно создавать).
    При BREAKOUT_FILTER == "none" — всегда True.
    """
    flt = getattr(config, "BREAKOUT_FILTER", "none")
    if flt == "none":
        return True

    ind = result.indicators
    adx = ind.adx
    direction = signal.direction

    if flt == "F1":  # ADX >= 25 (strong) только
        return adx is not None and adx >= config.ADX_STRONG
    if flt == "F2":  # ADX < 20 (flat) только
        return adx is not None and adx < config.ADX_THRESHOLD
    if flt == "F3":  # market_state == impulse только
        return ind.market_state == "impulse"
    if flt == "F4":  # week_trend не противоречит direction (neutral пропускаем)
        if ind.week_trend == "bullish" and direction == "short":
            return False
        if ind.week_trend == "bearish" and direction == "long":
            return False
        return True
    return True  # неизвестный фильтр — не блокируем


# ============================================================
# Агрегатор
# ============================================================


def detect_signals(
    result: AnalysisResult,
    df: pd.DataFrame,
    now: datetime | None = None,
    skip_age_check: bool = False,
    skip_filters: bool = False,
) -> list[Signal]:
    """
    Запускает детекторы, обогащает сигналы context/warnings/R:R,
    применяет фильтры (реестр strategy.filters), дедуплицирует, сортирует.
    """
    from strategy.filters import apply_filters
    from strategy.signal_history import get_recent_signal

    # --- Блокировка по свежести данных ---
    _now = now or datetime.now()

    if not skip_age_check and len(df) > 0:
        last = df["begin"].iloc[-1]
        if hasattr(last, "to_pydatetime"):
            last = last.to_pydatetime()
        age_min = int((_now - last).total_seconds() / 60)
        if age_min > config.DATA_MAX_AGE_BLOCK:
            log.warning(
                "Данные устарели на %d мин (> %d) — сигналы блокированы",
                age_min,
                config.DATA_MAX_AGE_BLOCK,
            )
            # T-05: записать причину
            result.skipped_signals.append(
                {
                    "direction": "any",
                    "kind": "data_age",
                    "entry_price": 0.0,
                    "strength_score": 0.0,
                    "reason": f"data_age:{age_min}",
                }
            )
            return []

    all_signals = []
    all_signals.extend(detect_bounce(result, df))
    all_signals.extend(detect_breakout(result, df))
    all_signals.extend(detect_trend_level(result, df))

    # Получаем последний сигнал из истории (для cooldown)
    recent = get_recent_signal(
        result.symbol,
        lookback_minutes=180,
        now=result.timestamp,
    )

    passed_signals: list[Signal] = []

    for s in all_signals:
        # --- 1. Реестр фильтров (7 bool + breakout + F1-F4) ---
        blocked_by = apply_filters(s, result)
        if blocked_by:
            log.info("%s заблокирован (фильтр %s)", s.kind, blocked_by)
            # T-05: записать в skipped_signals
            result.skipped_signals.append(
                {
                    "direction": s.direction,
                    "kind": s.kind,
                    "entry_price": s.entry_price,
                    "strength_score": s.strength_score,
                    "reason": f"filter:{blocked_by}",
                }
            )
            continue

        # --- 2. Найти уровень по level_price ---
        level = None
        if s.level_price is not None:
            for lv in result.levels:
                if abs(lv.price - s.level_price) < 0.0001:
                    level = lv
                    break

        # --- 3. Обогащение (context, warnings, R:R) ---
        _finalize_signal(s, result, df, level, recent, result.symbol)

        # --- 4. Штраф: EMA против direction (только если не replay) ---
        if not skip_filters:
            ema_against = (
                s.direction == "long" and s.context.get("ema_alignment") == "bearish"
            ) or (
                s.direction == "short" and s.context.get("ema_alignment") == "bullish"
            )
            if ema_against:
                penalty = 1.0
                s.strength_score = max(0.0, s.strength_score - penalty)
                s.reasons.append(f"штраф EMA-конфликт: -{penalty}")
                s.strength = _recalc_strength(s.strength_score)
                if s.strength == "none":
                    result.skipped_signals.append(
                        {
                            "direction": s.direction,
                            "kind": s.kind,
                            "entry_price": s.entry_price,
                            "strength_score": s.strength_score,
                            "reason": "penalty:ema_conflict",  # или "penalty:saw", "penalty:late_chase"
                        }
                    )
                    continue

        # --- 5. Штраф: пила (только если не replay) ---
        if not skip_filters:
            recent_dir = s.context.get("recent_signal_direction")
            recent_age = s.context.get("recent_signal_age_min")
            if (
                recent_dir
                and recent_dir != s.direction
                and recent_age is not None
                and recent_age < 30
            ):
                penalty = 1.5
                s.strength_score = max(0.0, s.strength_score - penalty)
                s.reasons.append(
                    f"штраф пила: -{penalty} ({recent_age} мин назад {recent_dir})"
                )
                s.strength = _recalc_strength(s.strength_score)
                if s.strength == "none":
                    result.skipped_signals.append(
                        {
                            "direction": s.direction,
                            "kind": s.kind,
                            "entry_price": s.entry_price,
                            "strength_score": s.strength_score,
                            "reason": "penalty:ema_conflict",  # или "penalty:saw", "penalty:late_chase"
                        }
                    )
                    continue

        # --- 6. RR invalid ---
        if getattr(s, "_rr_invalid", False):
            log.warning("Сигнал отброшен: RR не посчитан (%s)", s.kind)
            continue

        # --- 7. Штраф late/chase (только если не replay) ---
        if not skip_filters:
            if (
                level is not None
                and level.distance_atr is not None
                and level.distance_atr > 1.0
            ):
                penalty = 1.0
                s.strength_score = max(0.0, s.strength_score - penalty)
                s.reasons.append(
                    f"штраф late/chase: -{penalty} (distance={level.distance_atr:.1f} ATR)"
                )
                s.strength = _recalc_strength(s.strength_score)
                if s.strength == "none":
                    result.skipped_signals.append(
                        {
                            "direction": s.direction,
                            "kind": s.kind,
                            "entry_price": s.entry_price,
                            "strength_score": s.strength_score,
                            "reason": "penalty:ema_conflict",  # или "penalty:saw", "penalty:late_chase"
                        }
                    )
                    continue

        # --- 8. Прошёл все фильтры ---
        passed_signals.append(s)

    # --- Дедупликация — ТОЛЬКО по passed_signals ---
    dedup_window = 0.5 * result.atr if result.atr > 0 else 0.0
    best: list[Signal] = []
    for s in sorted(passed_signals, key=lambda x: x.strength_score, reverse=True):
        is_dup = False
        for b in best:
            if b.direction != s.direction:
                continue
            if abs(b.entry_price - s.entry_price) < dedup_window:
                is_dup = True
                break
            if abs((b.level_price or 0) - (s.level_price or 0)) < dedup_window:
                is_dup = True
                break
        if not is_dup:
            best.append(s)

    log.info(
        "Сигналов: %d (из %d, прошло фильтры %d)",
        len(best),
        len(all_signals),
        len(passed_signals),
    )
    return best
