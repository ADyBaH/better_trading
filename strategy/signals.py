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
from core.instruments import get_instrument
from strategy.strength import _compute_strength, _recalc_strength
from strategy.context import _build_context, _compute_session
from strategy.warnings import _build_warnings
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


def _commission_in_price(symbol: str) -> float:
    """Комиссия за круг в единицах цены (для net_rr)."""
    inst = get_instrument(symbol)
    if inst.step_cost == 0:
        return 0.0
    # commission_round в рублях, делим на step_cost → получаем пункты,
    # умножаем на price_step → получаем в цене
    commission_points = inst.commission_round / inst.step_cost
    return commission_points * inst.price_step


def _compute_stops(
    entry: float, direction: str, atr: float, day_range_atr: float | None = None
) -> tuple[float, float, dict]:
    """
    Возвращает (stop, take, meta).
    meta: take_source, take_atr_value, day_range_atr_at_open.
    """
    meta = {
        "take_source": "atr",
        "take_atr_value": None,
        "day_range_atr_at_open": day_range_atr,
    }

    if config.USE_ATR_STOPS:
        stop_dist = config.STOP_ATR_MULT * atr

        take_atr = config.TAKE_ATR_MULT * atr
        meta["take_atr_value"] = round(take_atr, 5)

        if getattr(config, "ADAPTIVE_TAKE_ENABLED", False):
            # --- Адаптивный take (Задача 1) ---
            if day_range_atr is not None and day_range_atr >= 0.5:
                take_day = config.TAKE_DAY_RANGE_FRAC * day_range_atr * atr
                take_dist = min(take_atr, take_day)
                take_dist = max(take_dist, config.MIN_TAKE_ATR * atr)
                meta["take_source"] = "day_range" if take_day < take_atr else "atr"
            else:
                # partial_day / day_range_atr = 0 -> baseline
                take_dist = take_atr
                meta["take_source"] = "atr"
        else:
            # --- baseline (2.0×ATR, но ≤ 0.6×day_range) ---
            if day_range_atr is not None and day_range_atr > 0:
                take_mult = min(config.TAKE_ATR_MULT, max(1.0, day_range_atr * 0.6))
                take_dist = take_mult * atr
                meta["take_source"] = (
                    "day_range" if take_mult < config.TAKE_ATR_MULT else "atr"
                )
            else:
                take_dist = take_atr
    else:
        stop_dist = config.STOP_POINTS * config.PRICE_STEP
        take_dist = config.TAKE_POINTS * config.PRICE_STEP

    if stop_dist <= 0:
        log.warning("_compute_stops: stop_dist=0 (atr=%.5f), fallback", atr)
        stop_dist = config.STOP_POINTS * config.PRICE_STEP
    if take_dist <= 0:
        take_dist = config.TAKE_POINTS * config.PRICE_STEP

    if direction == "long":
        return entry - stop_dist, entry + take_dist, meta
    else:
        return entry + stop_dist, entry - take_dist, meta


def _finalize_signal(
    signal: Signal,
    result: AnalysisResult,
    df: pd.DataFrame,
    level: Level | None,
    recent_signal: dict | None,
    symbol: str,
) -> Signal:
    """Заполняет context, warnings, R:R. Не бросает исключения наружу."""
    try:
        signal.context = _build_context(result, df, level, recent_signal)
    except Exception as e:
        log.exception(
            "_build_context упал (signal=%s %s): %s", signal.direction, signal.kind, e
        )
        signal.context = {}

    signal.market_state = result.indicators.market_state

    try:
        signal.warnings = _build_warnings(
            signal.direction, result, level, recent_signal, df
        )
    except Exception as e:
        log.exception(
            "_build_warnings упал (signal=%s %s): %s", signal.direction, signal.kind, e
        )
        signal.warnings = []

    # --- R:R — критично, всегда заполняем ---
    try:
        signal.compute_rr(commission_round=_commission_in_price(symbol))
    except Exception as e:
        log.exception(
            "compute_rr упал (signal=%s %s): %s", signal.direction, signal.kind, e
        )

    # --- Fallback: если RR всё ещё None — считаем вручную ---
    if signal.risk_reward is None or signal.net_rr is None:
        gross_risk = abs(signal.entry_price - signal.stop_price)
        gross_reward = abs(signal.take_price - signal.entry_price)
        if gross_risk > 0:
            comm = _commission_in_price(symbol)
            if signal.risk_reward is None:
                signal.risk_reward = round(gross_reward / gross_risk, 2)
            if signal.net_rr is None:
                net_risk = gross_risk + comm
                net_reward = gross_reward - comm
                if net_risk > 0:
                    signal.net_rr = round(net_reward / net_risk, 2)
            log.warning(
                "RR fallback: %s %s entry=%.3f stop=%.3f take=%.3f → RR=%.2f net=%.2f",
                signal.direction,
                signal.kind,
                signal.entry_price,
                signal.stop_price,
                signal.take_price,
                signal.risk_reward,
                signal.net_rr,
            )
        else:
            log.error(
                "RR невозможно посчитать: gross_risk=0 (entry=%.3f, stop=%.3f)",
                signal.entry_price,
                signal.stop_price,
            )
            signal._rr_invalid = True

    return signal


def _is_direction_allowed(direction: str, trend: str, kind: str) -> bool:
    """
    Проверяет, можно ли торговать в эту сторону при данном тренде.

    Правило:
    - trend_level — не трогаем (уже согласован).
    - bounce/breakout при up/strong_up → нет SHORT.
    - bounce/breakout при down/strong_down → нет LONG.
    - при transition — разрешено (штраф применяется отдельно).
    """
    if kind == "trend_level":
        return True

    if trend in ("up", "strong_up") and direction == "short":
        return False
    if trend in ("down", "strong_down") and direction == "long":
        return False

    return True


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
# Детектор: Bounce
# ============================================================


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
            entry, direction, result.atr, day_range_atr=result.indicators.day_range_atr
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


# ============================================================
# Детектор: Breakout
# ============================================================


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

        # 2. НОВОЕ: фильтр против тренда  ← ВСТАВЬ ЭТО
        if not _is_direction_allowed(direction, ind.trend, "breakout"):
            continue

        # 3. Блокировка двойного конфликта  ← ТВОЙ БЛОК, ОСТАВЛЯЙ
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

            # Пересчёт strength
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
            entry, direction, result.atr, day_range_atr=result.indicators.day_range_atr
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


# ============================================================
# Детектор: Trend + Level
# ============================================================


def detect_trend_level(
    result: AnalysisResult, df: pd.DataFrame, day_range_atr: float = 0.0
) -> list[Signal]:
    """
    Тренд + отбой от уровня.
    A1: цена у уровня.
    A2: свеча-подтверждение.
    A3: тренд по голосованию совпадает с направлением.

    ВАЖНО: при trend=transition/none сигнал НЕ создаётся (return []).
    Штраф PENALTY_TREND_TRANSITION здесь не применяется — transition
    отсекается раньше. Если позже понадобится разрешить trend_level
    при transition — вернуть блок штрафа (см. git history / NOTES).
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
        # transition или none — не создаём trend_level
        log.debug("trend_level пропущен: trend=%s", ind.trend)
        return []

    for lv in result.levels:
        # Для лонга — уровень ниже цены (поддержка), для шорта — выше (сопротивление)
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
            entry, direction, result.atr, day_range_atr=result.indicators.day_range_atr
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
