"""
Ядро анализа. Собирает AnalysisResult из модулей данных, индикаторов и уровней.
Никакого вывода — только модель данных.
"""

from datetime import datetime

from core.logger import get_logger
from core.models import AnalysisResult, IndicatorSnapshot, Level
from data.api_facade import get_candles_tf
from indicators.calc import add_indicators, get_atr
from strategy.levels import build_levels, find_fractals
from strategy.references import build_references

import config

log = get_logger(__name__)


def _build_indicator_snapshot(df) -> IndicatorSnapshot:
    """Собирает IndicatorSnapshot из последней строки DataFrame."""
    import pandas as pd

    last = df.iloc[-1]

    ema_fast = last.get("ema_fast")
    ema_slow = last.get("ema_slow")
    rsi = last.get("rsi")
    adx = last.get("adx")

    # Тренд
    if pd.isna(ema_fast) or pd.isna(ema_slow):
        trend = "none"
    elif ema_fast > ema_slow:
        trend = "up"
    else:
        trend = "down"

    # ADX
    if pd.isna(adx):
        adx_state = "none"
    elif adx > config.ADX_STRONG:
        adx_state = "strong"
    elif adx > config.ADX_THRESHOLD:
        adx_state = "trend"
    else:
        adx_state = "flat"

    # RSI
    if pd.isna(rsi):
        rsi_state = "none"
    elif rsi > config.RSI_OVERBOUGHT:
        rsi_state = "overbought"
    elif rsi < config.RSI_OVERSOLD:
        rsi_state = "oversold"
    elif rsi > config.RSI_NEAR_OVERBOUGHT:
        rsi_state = "near_overbought"
    elif rsi < config.RSI_NEAR_OVERSOLD:
        rsi_state = "near_oversold"
    else:
        rsi_state = "neutral"

    return IndicatorSnapshot(
        ema_fast=float(ema_fast) if not pd.isna(ema_fast) else None,
        ema_slow=float(ema_slow) if not pd.isna(ema_slow) else None,
        rsi=float(rsi) if not pd.isna(rsi) else None,
        adx=float(adx) if not pd.isna(adx) else None,
        trend=trend,
        adx_state=adx_state,
        rsi_state=rsi_state,
    )


def _dict_to_level(d: dict, source: str = "structural") -> Level:
    """Преобразует dict из build_levels/build_references в Level."""
    if source == "structural":
        return Level(
            price=float(d["price"]),
            type=str(d["type"]),
            weight=int(d["weight"]),
            tf_source=set(d.get("tf_source", set())),
            confirmed=bool(d.get("confirmed", False)),
            first_seen=d.get("first_seen"),
            last_seen=d.get("last_seen"),
        )
    else:  # references
        return Level(
            price=float(d["price"]),
            type=str(d["type"]),
            weight=int(d["weight"]),
            label=str(d.get("label", "")),
        )


def _attach_tags(
    structural: list[Level], references: list[Level], tolerance: float
) -> None:
    """
    Помечает структурные уровни тегами, если рядом есть референсный уровень.
    Пишет в Level.tags, мутирует список.
    """
    for lv in structural:
        for ref in references:
            if abs(lv.price - ref.price) <= tolerance:
                tag = f"+ {ref.label or ref.type}"
                if tag not in lv.tags:
                    lv.tags.append(tag)


def analyze(symbol: str = None, timeframe: str = None) -> AnalysisResult | None:
    """
    Главная функция. Возвращает AnalysisResult или None, если данных нет.
    """
    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.DEFAULT_TIMEFRAME

    # 1. Данные M5 + индикаторы
    df = get_candles_tf(timeframe, count=300)
    if df.empty:
        log.error("Нет данных для %s %s", symbol, timeframe)
        return None

    df = add_indicators(df)
    current_price = float(df["close"].iloc[-1])

    # 2. ATR(H1)
    df_atr = get_candles_tf(config.ATR_TF, count=50)
    atr = get_atr(df_atr, period=config.ATR_PERIOD)
    if atr is None:
        log.error("ATR не рассчитан")
        return None

    tolerance = config.LEVEL_TOLERANCE_ATR * atr

    # 3. Структурные уровни
    raw_levels = build_levels(
        symbol=symbol,
        tolerance=tolerance,
        current_price=current_price,
        atr=atr,
    )
    structural = [_dict_to_level(lv, "structural") for lv in raw_levels]

    # 4. Референсные уровни
    df_h1 = get_candles_tf("H1", count=200)
    raw_refs = build_references(
        current_price=current_price,
        atr=atr,
        df_intraday=df,
        df_h1=df_h1,
    )
    references = [_dict_to_level(r, "reference") for r in raw_refs]

    # 5. Пересечения слоёв — пишем в tags
    _attach_tags(structural, references, tolerance)

    # 6. Снимок индикаторов
    indicators = _build_indicator_snapshot(df)

    return AnalysisResult(
        symbol=symbol,
        timestamp=datetime.now(),
        current_price=current_price,
        atr=atr,
        timeframe=timeframe,
        indicators=indicators,
        levels=structural,
        references=references,
    )
