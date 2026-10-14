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

import config

log = get_logger(__name__)


# ============================================================
# Вспомогательные: свечи-паттерны
# ============================================================


def _is_rejection_candle(row: pd.Series, direction: str) -> bool:
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    body = abs(c - o)
    total_range = h - l
    if total_range == 0:
        return False
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    if direction == "long":
        return lower_shadow > 2 * body and lower_shadow > total_range * 0.5
    else:
        return upper_shadow > 2 * body and upper_shadow > total_range * 0.5


def _is_engulfing(df: pd.DataFrame, direction: str) -> bool:
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    cur = df.iloc[-1]
    if direction == "long":
        return (
            cur["close"] > cur["open"]
            and prev["close"] < prev["open"]
            and cur["close"] > prev["open"]
            and cur["open"] < prev["close"]
        )
    else:
        return (
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
    return df["volume"].iloc[-1] > avg_volume * config.VOLUME_MULTIPLIER


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


# ============================================================
# Контекст и предупреждения
# ============================================================


def _compute_session(hour_msk: int) -> str:
    """Сессия по МСК."""
    if 9 <= hour_msk < 12:
        return "morning"
    elif 12 <= hour_msk < 17:
        return "day"
    elif 17 <= hour_msk < 20:
        return "evening"
    return "night"


def _build_context(
    result: AnalysisResult,
    df: pd.DataFrame,
    level: Level | None,
    recent_signal: dict | None,
) -> dict:
    """
    Собирает context сигнала — 19 полей.
    """
    ind = result.indicators

    # Цена vs EMA
    price = result.current_price
    price_vs_fast = "above" if (ind.ema_fast and price > ind.ema_fast) else "below"
    price_vs_slow = "above" if (ind.ema_slow and price > ind.ema_slow) else "below"

    # EMA alignment
    if ind.ema_fast and ind.ema_slow:
        ema_alignment = "bullish" if ind.ema_fast > ind.ema_slow else "bearish"
    else:
        ema_alignment = "unknown"

    # ATR percentile (относительно последних 200 свечей H1 — считаем здесь упрощённо)
    atr_percentile = None
    volatility_state = "unknown"
    # Считаем процентиль по последним 200 свечам того же ТФ, что и df
    try:
        import pandas_ta as ta

        atr_series = ta.atr(
            high=df["high"], low=df["low"], close=df["close"], length=config.ATR_PERIOD
        )
        if atr_series is not None and not atr_series.dropna().empty:
            current_atr = atr_series.dropna().iloc[-1]
            pct = (atr_series.dropna() < current_atr).mean()
            atr_percentile = round(float(pct), 2)
            if pct > 0.75:
                volatility_state = "high"
            elif pct < 0.25:
                volatility_state = "low"
            else:
                volatility_state = "normal"
    except Exception:
        pass

    # Уровень
    level_price = level.price if level else None
    level_type = level.type if level else None
    level_strength = level.strength_score if level else None
    level_tags = list(level.tags) if level else []
    distance_to_level_atr = None
    if level is not None and result.atr > 0:
        distance_to_level_atr = round(abs(price - level.price) / result.atr, 2)

    # Время
    now = datetime.now()
    hour_utc = now.utctimetuple().tm_hour
    # МСК = UTC+3
    hour_msk = (hour_utc + 3) % 24
    session = _compute_session(hour_msk)

    # История сигналов
    recent_dir = recent_signal["direction"] if recent_signal else None
    recent_age = recent_signal["age_min"] if recent_signal else None

    return {
        "adx": round(ind.adx, 2) if ind.adx else None,
        "adx_state": ind.adx_state,
        "rsi": round(ind.rsi, 2) if ind.rsi else None,
        "rsi_state": ind.rsi_state,
        "trend": ind.trend,
        "ema_alignment": ema_alignment,
        "price_vs_ema_fast": price_vs_fast,
        "price_vs_ema_slow": price_vs_slow,
        "atr": round(result.atr, 5),
        "atr_percentile": atr_percentile,
        "volatility_state": volatility_state,
        "level_price": round(level_price, 5) if level_price else None,
        "level_type": level_type,
        "level_strength_score": level_strength,
        "level_tags": level_tags,
        "distance_to_level_atr": distance_to_level_atr,
        "recent_signal_direction": recent_dir,
        "recent_signal_age_min": recent_age,
        "session": session,
        "hour_utc": hour_utc,
    }


def _build_warnings(
    direction: str,
    result: AnalysisResult,
    level: Level | None,
    recent_signal: dict | None,
) -> list[str]:
    """
    Предупреждения о рисках. НЕ меняют score.
    Шаг 1: только информационные пометки.
    """
    warnings = []
    ind = result.indicators

    # ADX флэт
    if ind.adx is not None and ind.adx < config.ADX_THRESHOLD:
        warnings.append(f"ADX {ind.adx:.1f} flat — нет тренда")

    # Против тренда
    if ind.trend != "none":
        if direction == "long" and ind.trend == "down":
            warnings.append(f"LONG против тренда {ind.trend.upper()}")
        elif direction == "short" and ind.trend == "up":
            warnings.append(f"SHORT против тренда {ind.trend.upper()}")

    # RSI риск
    if ind.rsi is not None:
        if direction == "short":
            if ind.rsi < config.RSI_OVERSOLD:
                warnings.append(f"RSI {ind.rsi:.1f} перепродан — риск отскока")
            elif ind.rsi < config.RSI_NEAR_OVERSOLD:
                warnings.append(f"RSI {ind.rsi:.1f} near_oversold — риск отскока")
        else:  # long
            if ind.rsi > config.RSI_OVERBOUGHT:
                warnings.append(f"RSI {ind.rsi:.1f} перекуплен — риск коррекции")
            elif ind.rsi > config.RSI_NEAR_OVERBOUGHT:
                warnings.append(f"RSI {ind.rsi:.1f} near_overbought — риск коррекции")

    # Уровень
    if level is not None:
        if level.strength_score and level.strength_score > 40:
            warnings.append(f"Уровень сильный (score {level.strength_score:.0f})")

        if level.tags:
            warnings.append(f"Совпадение референсов: {', '.join(level.tags)}")

        # Цена прямо на уровне
        if level.distance_atr is not None and level.distance_atr < 0.1:
            warnings.append("Цена прямо на уровне — высокий риск ложного пробоя")

    # Cooldown: противоположный сигнал недавно
    if recent_signal is not None:
        recent_dir = recent_signal.get("direction")
        age = recent_signal.get("age_min")
        if recent_dir and recent_dir != direction and age is not None and age < 120:
            warnings.append(f"{age} мин назад был {recent_dir.upper()} — риск пилы")

    # Время суток
    now = datetime.now()
    hour_msk = (now.utctimetuple().tm_hour + 3) % 24
    if hour_msk >= 18 or hour_msk < 9:
        warnings.append("Низкая ликвидность (вне основных часов)")

    return warnings


def _commission_in_price(symbol: str) -> float:
    """Комиссия за круг в единицах цены (для net_rr)."""
    inst = get_instrument(symbol)
    if inst.step_cost == 0:
        return 0.0
    # commission_round в рублях, делим на step_cost → получаем пункты,
    # умножаем на price_step → получаем в цене
    commission_points = inst.commission_round / inst.step_cost
    return commission_points * inst.price_step


def _finalize_signal(
    signal: Signal,
    result: AnalysisResult,
    df: pd.DataFrame,
    level: Level | None,
    recent_signal: dict | None,
    symbol: str,
) -> Signal:
    """Заполняет context, warnings, R:R."""
    signal.context = _build_context(result, df, level, recent_signal)
    signal.warnings = _build_warnings(signal.direction, result, level, recent_signal)
    signal.compute_rr(commission_round=_commission_in_price(symbol))
    return signal


# ============================================================
# Детектор: Bounce
# ============================================================


def detect_bounce(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    signals = []
    price = result.current_price
    atr = result.atr
    tol = config.BOUNCE_TOLERANCE_ATR * atr

    for lv in result.levels:
        dist = abs(lv.price - price)
        if dist > tol:
            continue
        direction = "long" if lv.price <= price else "short"

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

        entry = price
        if direction == "long":
            stop = entry - config.STOP_POINTS * config.PRICE_STEP
            take = entry + config.TAKE_POINTS * config.PRICE_STEP
        else:
            stop = entry + config.STOP_POINTS * config.PRICE_STEP
            take = entry - config.TAKE_POINTS * config.PRICE_STEP

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
        signals.append(signal)

    return signals


# ============================================================
# Детектор: Breakout
# ============================================================


def detect_breakout(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    if len(df) < 2:
        return []

    signals = []
    price = result.current_price
    atr = result.atr
    buffer = config.BREAKOUT_BUFFER_ATR * atr
    last = df.iloc[-1]
    prev = df.iloc[-2]

    for lv in result.levels:
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

        matched = ["A1"]
        reasons = [f"свежий пробой уровня {lv.price:.3f}"]

        adx = result.indicators.adx
        if adx is not None and adx > config.ADX_BREAKOUT_THRESHOLD:
            matched.append("B2")
            reasons.append(f"ADX {adx:.1f} > {config.ADX_BREAKOUT_THRESHOLD}")

        if _has_volume_confirmation(df):
            matched.append("D3")
            reasons.append("объём выше среднего")

        score, strength = _compute_strength(matched)
        if strength == "none":
            continue

        entry = price
        if direction == "long":
            stop = entry - config.STOP_POINTS * config.PRICE_STEP
            take = entry + config.TAKE_POINTS * config.PRICE_STEP
        else:
            stop = entry + config.STOP_POINTS * config.PRICE_STEP
            take = entry - config.TAKE_POINTS * config.PRICE_STEP

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
        signals.append(signal)

    return signals


# ============================================================
# Детектор: Trend + Level
# ============================================================


def detect_trend_level(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    signals = []
    price = result.current_price
    atr = result.atr
    tol = config.TREND_LEVEL_TOLERANCE_ATR * atr
    trend = result.indicators.trend

    if trend == "none":
        return []

    direction = "long" if trend == "up" else "short"

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
            f"тренд {trend.upper()} по EMA",
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
        if direction == "long":
            stop = entry - config.STOP_POINTS * config.PRICE_STEP
            take = entry + config.TAKE_POINTS * config.PRICE_STEP
        else:
            stop = entry + config.STOP_POINTS * config.PRICE_STEP
            take = entry - config.TAKE_POINTS * config.PRICE_STEP

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
        signals.append(signal)

    return signals


# ============================================================
# Подсчёт силы (без изменений)
# ============================================================


def _compute_strength(matched: list[str]) -> tuple[float, str]:
    groups = {"A": [], "B": [], "C": [], "D": [], "E": []}
    for c in matched:
        g = c[0]
        if g in groups:
            groups[g].append(c)

    effective = []
    for g, items in groups.items():
        limit = 3 if g == "A" else 2
        effective.extend(items[:limit])

    has_a = len(groups["A"]) > 0
    has_c_or_d = len(groups["C"]) > 0 or len(groups["D"]) > 0
    score = float(len(effective))

    if not has_a or score < 1:
        return 0.0, "none"
    elif score == 1:
        return score, "weak"
    elif score == 2:
        return score, "medium"
    elif score >= 3 and has_c_or_d:
        return score, "strong"
    else:
        return score, "medium"


# ============================================================
# Агрегатор
# ============================================================


def detect_signals(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    """
    Запускает детекторы, обогащает сигналы context/warnings/R:R,
    дедуплицирует, сортирует.
    """
    from strategy.signal_history import get_recent_signal

    all_signals = []
    all_signals.extend(detect_bounce(result, df))
    all_signals.extend(detect_breakout(result, df))
    all_signals.extend(detect_trend_level(result, df))

    # Получаем последний сигнал из истории (для cooldown)
    recent = get_recent_signal(result.symbol, lookback_minutes=120)

    # Обогащаем
    for s in all_signals:
        # Найти уровень по level_price
        level = None
        if s.level_price is not None:
            for lv in result.levels:
                if abs(lv.price - s.level_price) < 0.0001:
                    level = lv
                    break
        _finalize_signal(s, result, df, level, recent, result.symbol)

    # Дедупликация
    best = {}
    for s in all_signals:
        key = (s.direction, round(s.level_price or 0, 3))
        if key not in best or s.strength_score > best[key].strength_score:
            best[key] = s

    deduped = sorted(best.values(), key=lambda s: s.strength_score, reverse=True)
    log.info("Сигналов: %d (после дедупликации из %d)", len(deduped), len(all_signals))
    return deduped
