"""
Детекторы сигналов.
MVP-1: bounce, breakout, trend_level.
Система критериев: A (структурные), B (индикаторные), D (контекст).
C и E — в следующих версиях.
"""

import pandas as pd

from core.logger import get_logger
from core.models import AnalysisResult, Level, Signal

import config

log = get_logger(__name__)


# ============================================================
# Вспомогательные: свечи-паттерны
# ============================================================


def _is_rejection_candle(row: pd.Series, direction: str) -> bool:
    """
    Свеча-разворот (пин-бар / rejection).
    direction='long' — ищем нижний хвост (бычий разворот).
    direction='short' — ищем верхний хвост (медвежий разворот).
    """
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    body = abs(c - o)
    total_range = h - l
    if total_range == 0:
        return False

    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    if direction == "long":
        # нижний хвост > 2×body, тело в верхней половине
        return lower_shadow > 2 * body and lower_shadow > total_range * 0.5
    else:
        return upper_shadow > 2 * body and upper_shadow > total_range * 0.5


def _is_engulfing(df: pd.DataFrame, direction: str) -> bool:
    """Engulfing на последней свече относительно предыдущей."""
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
    """D3: объём последней свечи выше среднего × множитель."""
    if len(df) < config.VOLUME_LOOKBACK + 1:
        return False
    avg_volume = df["volume"].iloc[-config.VOLUME_LOOKBACK - 1 : -1].mean()
    if avg_volume <= 0:
        return False
    return df["volume"].iloc[-1] > avg_volume * config.VOLUME_MULTIPLIER


# ============================================================
# Поиск ближайшего уровня
# ============================================================


def _nearest_level(
    levels: list[Level],
    price: float,
    direction: str = "any",
) -> Level | None:
    """
    Ближайший уровень относительно цены.
    direction='any' — любой; 'above' — только выше; 'below' — только ниже.
    """
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
# Детектор: Bounce
# ============================================================


def detect_bounce(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    """
    Отбой от уровня.
    A1: цена у уровня (в пределах BOUNCE_TOLERANCE_ATR × ATR).
    A2: свеча-разворот (пин-бар или engulfing).
    A3: направление согласуется с уровнем (от поддержки — лонг, от сопротивления — шорт).
    B1: RSI подтверждает.
    D3: объём выше среднего.
    """
    signals = []
    price = result.current_price
    atr = result.atr
    tol = config.BOUNCE_TOLERANCE_ATR * atr

    for lv in result.levels:
        dist = abs(lv.price - price)
        if dist > tol:
            continue

        # Определяем направление: если уровень ниже цены — отбой вверх (лонг),
        # если выше — вниз (шорт)
        direction = "long" if lv.price <= price else "short"

        # A2: свеча-подтверждение
        has_candle = _is_rejection_candle(df.iloc[-1], direction) or _is_engulfing(
            df, direction
        )
        if not has_candle:
            continue

        # Собираем критерии
        matched = ["A1", "A2"]
        reasons = [f"цена у уровня {lv.price:.3f} (d={dist/atr:.2f} ATR)"]
        reasons.append("свеча-разворот")

        # B1: RSI
        rsi = result.indicators.rsi
        if rsi is not None:
            if direction == "long" and rsi < config.RSI_BOUNCE_LONG:
                matched.append("B1")
                reasons.append(f"RSI {rsi:.1f} < {config.RSI_BOUNCE_LONG}")
            elif direction == "short" and rsi > config.RSI_BOUNCE_SHORT:
                matched.append("B1")
                reasons.append(f"RSI {rsi:.1f} > {config.RSI_BOUNCE_SHORT}")

        # D3: объём
        if _has_volume_confirmation(df):
            matched.append("D3")
            reasons.append("объём выше среднего")

        # Считаем score и strength
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

        signals.append(
            Signal(
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
        )

    return signals


# ============================================================
# Детектор: Breakout
# ============================================================


def detect_breakout(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    """
    Пробой уровня.
    A1: последняя свеча ЗАКРЫЛАСЬ за уровнем, а предыдущая — НЕТ.
        (свежий пробой, а не «давно ниже уровня»)
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

    for lv in result.levels:
        # Пробой вверх: prev.close <= lv.price, last.close > lv.price + buffer
        if (
            prev["close"] <= lv.price
            and last["close"] > lv.price + buffer
            and price > lv.price
        ):
            direction = "long"
        # Пробой вниз: prev.close >= lv.price, last.close < lv.price - buffer
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

        signals.append(
            Signal(
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
        )

    return signals


# ============================================================
# Детектор: Trend + Level
# ============================================================


def detect_trend_level(result: AnalysisResult, df: pd.DataFrame) -> list[Signal]:
    """
    Тренд + отбой от уровня по направлению тренда.
    A1: цена у уровня.
    A2: свеча-подтверждение.
    A3: тренд по EMA совпадает с направлением.
    """
    signals = []
    price = result.current_price
    atr = result.atr
    tol = config.TREND_LEVEL_TOLERANCE_ATR * atr
    trend = result.indicators.trend

    if trend == "none":
        return []

    # В тренде вверх ищем отбой от поддержки (лонг), вниз — от сопротивления (шорт)
    direction = "long" if trend == "up" else "short"

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

        signals.append(
            Signal(
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
        )

    return signals


# ============================================================
# Подсчёт силы
# ============================================================


def _compute_strength(matched: list[str]) -> tuple[float, str]:
    """
    Считает score и уровень силы по списку критериев.
    Правила MVP-1:
      - обязательный якорь: ≥1 из группы A
      - не более 2 из одной группы, кроме A (там 3 подкритерия)
      - weak:   score=1 + есть A
      - medium: score=2 + есть A
      - strong: score≥3 + есть A + есть из C или D
    """
    groups = {"A": [], "B": [], "C": [], "D": [], "E": []}
    for c in matched:
        g = c[0]
        if g in groups:
            groups[g].append(c)

    # Обрезаем: для A — до 3 (A1, A2, A3 — разные критерии),
    # для остальных — до 2 (защита от дублей)
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
    all_signals = []
    all_signals.extend(detect_bounce(result, df))
    all_signals.extend(detect_breakout(result, df))
    all_signals.extend(detect_trend_level(result, df))

    # --- Дедупликация ---
    # Ключ: (direction, level_price округлённый, на который указывает сигнал).
    # Оставляем сигнал с максимальным strength_score.
    best = {}
    for s in all_signals:
        key = (s.direction, round(s.level_price or 0, 3))
        if key not in best or s.strength_score > best[key].strength_score:
            best[key] = s

    deduped = sorted(best.values(), key=lambda s: s.strength_score, reverse=True)
    log.info("Сигналов: %d (после дедупликации из %d)", len(deduped), len(all_signals))
    return deduped
