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
from strategy.penalties import _apply_penalties
from strategy.dedup import _deduplicate_signals

# --- Реэкспорт для тестов (test_signals.py импортирует из strategy.signals) ---
from strategy.patterns import (
    _is_rejection_candle,
    _is_engulfing,
    _has_volume_confirmation,
)
from strategy.strength import _compute_strength, _recalc_strength
from strategy.context import _build_context, _compute_session
from strategy.warnings import _build_warnings
from strategy.stops import _compute_stops
from strategy.finalize import _finalize_signal
from strategy.direction import _is_direction_allowed
from strategy.detectors import (
    detect_bounce,
    detect_breakout,
    detect_trend_level,
)
from strategy.filters.breakout import _breakout_passes_filter

import config

log = get_logger(__name__)

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
    применяет фильтры (реестр strategy.filters), штрафы, дедуплицирует.
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

    recent = get_recent_signal(
        result.symbol,
        lookback_minutes=180,
        now=result.timestamp,
    )

    passed_signals: list[Signal] = []

    for s in all_signals:
        # --- 1. Реестр фильтров ---
        blocked_by = apply_filters(s, result)
        if blocked_by:
            log.info("%s заблокирован (фильтр %s)", s.kind, blocked_by)
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

        # --- 4. Штрафы (EMA, пила, late-chase) ---
        reason = _apply_penalties(s, result, level, skip_filters=skip_filters)
        if reason:
            result.skipped_signals.append(
                {
                    "direction": s.direction,
                    "kind": s.kind,
                    "entry_price": s.entry_price,
                    "strength_score": s.strength_score,
                    "reason": reason,
                }
            )
            continue

        # --- 5. RR invalid ---
        if getattr(s, "_rr_invalid", False):
            log.warning("Сигнал отброшен: RR не посчитан (%s)", s.kind)
            continue

        passed_signals.append(s)

    # --- Дедупликация ---
    best = _deduplicate_signals(passed_signals, result.atr)

    log.info(
        "Сигналов: %d (из %d, прошло фильтры %d)",
        len(best),
        len(all_signals),
        len(passed_signals),
    )
    return best
