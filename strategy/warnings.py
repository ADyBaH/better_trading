"""
Предупреждения о рисках (не меняют score).

Вынесено из strategy/signals.py (шаг 4 рефакторинга).
"""

from datetime import datetime

import pandas as pd

import config
from core.logger import get_logger
from core.models import AnalysisResult, Level

log = get_logger(__name__)


def _build_warnings(
    direction: str,
    result: AnalysisResult,
    level: Level | None,
    recent_signal: dict | None,
    df: pd.DataFrame,
) -> list[str]:
    """
    Предупреждения о рисках. НЕ меняют score.
    """
    warnings = []
    ind = result.indicators

    # ADX флэт
    if ind.adx is not None and ind.adx < config.ADX_THRESHOLD:
        warnings.append(f"ADX {ind.adx:.1f} flat — нет тренда")

    # --- Состояние рынка ---
    if ind.market_state == "pullback":
        warnings.append(
            f"🔄 Откат после импульса ({ind.impulse_atr:.1f} ATR) — вход против отката"
        )
    elif ind.market_state == "impulse":
        warnings.append(f"🚀 Импульс {ind.impulse_atr:.1f} ATR — риск входа на пике")

    # --- Недельный тренд ---
    if ind.week_trend == "neutral" and direction == "long":
        warnings.append("✅ neutral week + long — хороший контекст")

    # --- Стакан против входа ---
    ob = getattr(result, "order_book", None) or {}
    pressure = ob.get("pressure_pct")
    if pressure is not None:
        if direction == "short" and pressure > 60:
            warnings.append(f"⚠ bid-heavy ({pressure:.0f}%) — шорт против покупателей")
        elif direction == "long" and pressure < 40:
            warnings.append(f"⚠ ask-heavy ({pressure:.0f}%) — лонг против продавцов")

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

    # Свежесть данных
    if len(df) > 0:
        try:
            last = df["begin"].iloc[-1]
            if hasattr(last, "to_pydatetime"):
                last = last.to_pydatetime()
            age_min = int((datetime.now() - last).total_seconds() / 60)
            if age_min > config.DATA_MAX_AGE_BLOCK:
                warnings.append(f"Данные устарели на {age_min} мин — блокировка")
            elif age_min > config.DATA_MAX_AGE_MIN:
                warnings.append(f"Данные устарели на {age_min} мин (лаг биржи)")
        except Exception:
            pass

    # --- Конфликты тренда ---
    ind = result.indicators

    if ind.day_trend == "bullish" and direction == "short":
        warnings.append(f"⚠ День бычий ({ind.day_change_atr:+.1f} ATR) — не шорти")
    elif ind.day_trend == "bearish" and direction == "long":
        warnings.append(f"⚠ День медвежий ({ind.day_change_atr:+.1f} ATR) — не лонгуй")

    if ind.structure == "bullish" and direction == "short":
        warnings.append("⚠ Структура бычья (HH/HL) — не шорти")
    elif ind.structure == "bearish" and direction == "long":
        warnings.append("⚠ Структура медвежья (LH/LL) — не лонгуй")

    ema_trend = (
        "up"
        if ind.ema_fast and ind.ema_slow and ind.ema_fast > ind.ema_slow
        else "down"
    )
    if ema_trend == "down" and ind.day_trend == "bullish":
        warnings.append(
            f"⚠ Конфликт: EMA вниз, но день бычий ({ind.day_change_atr:+.1f} ATR)"
        )
    elif ema_trend == "up" and ind.day_trend == "bearish":
        warnings.append(
            f"⚠ Конфликт: EMA вверх, но день медвежий ({ind.day_change_atr:+.1f} ATR)"
        )

    if ind.trend == "transition":
        warnings.append(
            f"⚠ Тренд transition (голосов {ind.vote_sum:+d}) — сигнал ненадёжный"
        )

    # Время суток
    now = datetime.now()
    hour_msk = (now.utctimetuple().tm_hour + 3) % 24
    if hour_msk >= 18 or hour_msk < 9:
        warnings.append("Низкая ликвидность (вне основных часов)")

    # --- Late/chase: цена уже прошла > 1 ATR от уровня ---
    if level is not None and level.distance_atr is not None:
        if level.distance_atr > 1.0:
            warnings.append(
                f"⚠ late/chase: цена прошла {level.distance_atr:.1f} ATR от уровня"
            )

    return warnings
