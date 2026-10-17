# core/analyzer.py
"""
Ядро анализа. Собирает AnalysisResult из модулей данных, индикаторов и уровней.
Никакого вывода — только модель данных.
"""

from datetime import datetime

from core.logger import get_logger
from core.models import AnalysisResult, IndicatorSnapshot, Level, Signal
from data.api_facade import get_candles_tf
from indicators.calc import add_indicators, get_atr, get_trend_context, get_main_trend
from strategy.levels import build_levels, find_fractals
from strategy.references import build_references
from strategy.signals import detect_signals
import config

log = get_logger(__name__)


# ============================================================
# Индикаторы
# ============================================================


def _build_indicator_snapshot(
    df, current_price: float, atr: float
) -> IndicatorSnapshot:
    """
    Собирает IndicatorSnapshot из последней строки DataFrame
    + контекст тренда (day_trend, structure, price_direction).
    """
    import pandas as pd

    last = df.iloc[-1]

    ema_fast = last.get("ema_fast")
    ema_slow = last.get("ema_slow")
    rsi = last.get("rsi")
    adx = last.get("adx")

    # Приводим к float или None
    ema_fast_f = float(ema_fast) if not pd.isna(ema_fast) else None
    ema_slow_f = float(ema_slow) if not pd.isna(ema_slow) else None
    rsi_f = float(rsi) if not pd.isna(rsi) else None
    adx_f = float(adx) if not pd.isna(adx) else None

    # --- ADX state ---
    if adx_f is None:
        adx_state = "none"
    elif adx_f > config.ADX_STRONG:
        adx_state = "strong"
    elif adx_f > config.ADX_THRESHOLD:
        adx_state = "trend"
    else:
        adx_state = "flat"

    # --- RSI state ---
    if rsi_f is None:
        rsi_state = "none"
    elif rsi_f > config.RSI_OVERBOUGHT:
        rsi_state = "overbought"
    elif rsi_f < config.RSI_OVERSOLD:
        rsi_state = "oversold"
    elif rsi_f > config.RSI_NEAR_OVERBOUGHT:
        rsi_state = "near_overbought"
    elif rsi_f < config.RSI_NEAR_OVERSOLD:
        rsi_state = "near_oversold"
    else:
        rsi_state = "neutral"

    # --- Контекст тренда ---
    trend_context = get_trend_context(
        df=df,
        current_price=current_price,
        ema_fast=ema_fast_f,
        ema_slow=ema_slow_f,
        atr=atr,
    )

    main_trend_info = get_main_trend(trend_context)

    return IndicatorSnapshot(
        ema_fast=ema_fast_f,
        ema_slow=ema_slow_f,
        rsi=rsi_f,
        adx=adx_f,
        trend=main_trend_info["trend"],
        adx_state=adx_state,
        rsi_state=rsi_state,
        day_trend=trend_context["day_trend"],
        day_change_atr=trend_context["day_change_atr"],
        structure=trend_context["structure"],
        price_direction=trend_context["price_direction"],
        vote_sum=main_trend_info["vote_sum"],
        vote_breakdown=main_trend_info["vote_breakdown"],
    )


# ============================================================
# Конвертеры dict → Level
# ============================================================


def _dict_to_level(d: dict, source: str = "structural") -> Level:
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
    else:
        return Level(
            price=float(d["price"]),
            type=str(d["type"]),
            weight=int(d["weight"]),
            label=str(d.get("label", "")),
        )


# ============================================================
# Обогащение уровней: distance_atr, strength_score, age_days
# ============================================================


def _enrich_levels(levels: list[Level], current_price: float, atr: float) -> None:
    """
    Заполняет вычисляемые поля уровней:
        distance_atr   — |price - current| / atr
        age_days       — сколько дней с last_seen
        strength_score — weight × confirmed × tf_count × age_factor
    """
    now = datetime.now()

    for lv in levels:
        # distance_atr
        lv.distance_atr = (
            round(abs(lv.price - current_price) / atr, 2) if atr > 0 else None
        )

        # age_days
        if lv.last_seen is not None:
            delta = now - lv.last_seen
            lv.age_days = round(delta.total_seconds() / 86400, 1)
        else:
            lv.age_days = None

        # strength_score
        # Формула: weight × (1.3 если confirmed, иначе 1.0) × tf_count × age_factor
        tf_count = len(lv.tf_source) if lv.tf_source else 1
        confirmed_mult = 1.3 if lv.confirmed else 1.0

        # age_factor: 1.0 если свежий (<3д), 0.7 если <14д, 0.4 если старый
        if lv.age_days is None:
            age_factor = 1.0
        elif lv.age_days <= 3:
            age_factor = 1.0
        elif lv.age_days <= 14:
            age_factor = 0.7
        else:
            age_factor = 0.4

        lv.strength_score = round(lv.weight * confirmed_mult * tf_count * age_factor, 1)


def _attach_tags(
    structural: list[Level], references: list[Level], tolerance: float
) -> None:
    """Помечает структурные уровни тегами, если рядом есть референсный."""
    for lv in structural:
        for ref in references:
            if abs(lv.price - ref.price) <= tolerance:
                tag = f"+ {ref.label or ref.type}"
                if tag not in lv.tags:
                    lv.tags.append(tag)


# ============================================================
# Главная функция
# ============================================================


def analyze(symbol: str = None, timeframe: str = None) -> AnalysisResult | None:
    """Главная функция. Возвращает AnalysisResult или None, если данных нет."""
    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.DEFAULT_TIMEFRAME

    # 1. Данные M5 + индикаторы
    df = get_candles_tf(timeframe, count=300)
    if df.empty:
        log.error("Нет данных для %s %s", symbol, timeframe)
        return None

    df = add_indicators(df)
    current_price = float(df["close"].iloc[-1])

    # Логируем лаг данных (наблюдаемость, не влияет на сигналы)
    try:
        last_begin = df["begin"].iloc[-1]
        if hasattr(last_begin, "to_pydatetime"):
            last_begin = last_begin.to_pydatetime()
        data_age_min = int((datetime.now() - last_begin).total_seconds() / 60)
        log.info(
            "data_age=%d min (последняя свеча %s)",
            data_age_min,
            last_begin.strftime("%Y-%m-%d %H:%M"),
        )
    except Exception as e:
        log.debug("data_age не посчитан: %s", e)

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

    # 5. Пересечения слоёв
    _attach_tags(structural, references, tolerance)

    # 6. Обогащение уровней (distance_atr, strength_score, age_days)
    _enrich_levels(structural, current_price, atr)
    _enrich_levels(references, current_price, atr)

    # 7. Снимок индикаторов
    indicators = _build_indicator_snapshot(df, current_price, atr)

    # 8. Сигналы
    result = AnalysisResult(
        symbol=symbol,
        timestamp=datetime.now(),
        current_price=current_price,
        atr=atr,
        timeframe=timeframe,
        indicators=indicators,
        levels=structural,
        references=references,
        signals=[],  # пока пусто — заполним ниже
    )
    from strategy.signal_history import append_signals

    signals = detect_signals(result, df)
    result.signals = signals

    # Сохраняем в историю для будущего cooldown-анализа
    append_signals(signals, symbol)

    return result
