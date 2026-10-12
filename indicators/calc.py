"""
Расчёт технических индикаторов через pandas_ta.

Функции:
    add_indicators(df)          — добавляет EMA, RSI, ADX, DMP, DMN
    interpret_indicators(df)    — человекочитаемая сводка
    get_atr(df, period)         — последнее значение ATR
"""

import pandas as pd
import pandas_ta as ta

import config
from core.logger import get_logger

log = get_logger(__name__)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет EMA, RSI, ADX к DataFrame со свечами."""
    if df.empty:
        log.warning("Пустой DataFrame, индикаторы не считаем")
        return df

    df = df.copy()

    df["ema_fast"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["ema_slow"] = ta.ema(df["close"], length=config.EMA_SLOW)
    df["rsi"] = ta.rsi(df["close"], length=config.RSI_PERIOD)

    adx_result = ta.adx(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=config.ADX_PERIOD,
    )
    if adx_result is not None:
        df["adx"] = adx_result[f"ADX_{config.ADX_PERIOD}"]
        df["dmp"] = adx_result[f"DMP_{config.ADX_PERIOD}"]
        df["dmn"] = adx_result[f"DMN_{config.ADX_PERIOD}"]
    else:
        log.warning("ADX не рассчитан (недостаточно данных)")
        df["adx"] = None
        df["dmp"] = None
        df["dmn"] = None

    log.debug(
        "Индикаторы добавлены: EMA(%d/%d), RSI(%d), ADX(%d)",
        config.EMA_FAST,
        config.EMA_SLOW,
        config.RSI_PERIOD,
        config.ADX_PERIOD,
    )
    return df


def interpret_indicators(df: pd.DataFrame, timeframe: str = "") -> str:
    """Человекочитаемая интерпретация последних значений индикаторов."""
    if df.empty:
        return "Нет данных для интерпретации."

    last = df.iloc[-1]
    tf_prefix = f"[{timeframe}] " if timeframe else ""

    # --- Тренд ---
    ema_fast = last.get("ema_fast")
    ema_slow = last.get("ema_slow")
    if pd.isna(ema_fast) or pd.isna(ema_slow):
        trend_text = f"Тренд: недостаточно данных (нужно ≥{config.EMA_SLOW} свечей)"
    elif ema_fast > ema_slow:
        trend_text = f"Тренд: ВВЕРХ (EMA{config.EMA_FAST} > EMA{config.EMA_SLOW})"
    else:
        trend_text = f"Тренд: ВНИЗ (EMA{config.EMA_FAST} < EMA{config.EMA_SLOW})"

    # --- ADX ---
    adx = last.get("adx")
    if pd.isna(adx):
        adx_text = "ADX: нет данных"
    elif adx > config.ADX_STRONG:
        adx_text = f"ADX = {adx:.1f} (сильный тренд)"
    elif adx > config.ADX_THRESHOLD:
        adx_text = f"ADX = {adx:.1f} (тренд есть)"
    else:
        adx_text = f"ADX = {adx:.1f} (боковик, тренда нет)"

    # --- RSI ---
    rsi = last.get("rsi")
    if pd.isna(rsi):
        rsi_text = "RSI: нет данных"
    elif rsi > config.RSI_OVERBOUGHT:
        rsi_text = f"RSI = {rsi:.1f} (перекупленность)"
    elif rsi < config.RSI_OVERSOLD:
        rsi_text = f"RSI = {rsi:.1f} (перепроданность)"
    elif rsi > config.RSI_NEAR_OVERBOUGHT:
        rsi_text = f"RSI = {rsi:.1f} (близко к перекупленности)"
    elif rsi < config.RSI_NEAR_OVERSOLD:
        rsi_text = f"RSI = {rsi:.1f} (близко к перепроданности)"
    else:
        rsi_text = f"RSI = {rsi:.1f} (нейтрально)"

    return f"{tf_prefix}{trend_text}. {adx_text}. {rsi_text}."


def get_atr(df: pd.DataFrame, period: int = None) -> float | None:
    """
    Возвращает последнее значение ATR для переданного DataFrame.
    Если данных мало или ATR не рассчитан — возвращает None.
    """
    period = period or config.ATR_PERIOD

    if df.empty or len(df) < period + 1:
        log.warning(
            "Мало данных для ATR: %d свечей, нужно ≥%d",
            len(df),
            period + 1,
        )
        return None

    atr_series = ta.atr(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=period,
    )
    if atr_series is None or atr_series.dropna().empty:
        log.warning("ATR не рассчитан (pandas_ta вернул None или всё NaN)")
        return None

    value = float(atr_series.dropna().iloc[-1])
    log.debug("ATR(%d) = %.5f", period, value)
    return value
