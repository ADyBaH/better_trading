# core/analyzer.py
"""
Ядро анализа. Собирает AnalysisResult из модулей данных, индикаторов и уровней.
Никакого вывода — только модель данных.
"""

from datetime import datetime

from core.logger import get_logger
from core.models import AnalysisResult, IndicatorSnapshot, Level, Signal
from data.api_facade import get_candles_tf
from indicators.calc import (
    add_indicators,
    get_atr,
    get_trend_context,
    get_main_trend,
    get_week_trend,
)
import pandas as pd
from strategy.levels import build_levels, find_fractals
from strategy.references import build_references
from strategy.signals import detect_signals
import config

log = get_logger(__name__)

# T-26: кэш свечей по ТФ (в памяти процесса)
_candles_cache: dict[str, "pd.DataFrame"] = {}
_last_fetch: dict[str, "datetime"] = {}


def _tf_due(tf: str, now: datetime) -> bool:
    """T-26: пора ли обновлять ТФ (закрылся ли бар + 5 сек)."""
    if not getattr(config, "TF_CACHE_ENABLED", True):
        return True
    interval = getattr(config, "TF_REFRESH_MINUTES", {}).get(tf)
    if not interval:
        return True  # ТФ не в списке — тянем всегда (безопасный fallback)
    last = _last_fetch.get(tf)
    if last is None:
        return True
    return (now - last).total_seconds() >= interval * 60 - 5


def _get_cached(tf: str, count: int, now: datetime) -> "pd.DataFrame":
    """T-26: тянем свечи только если ТФ закрылся, иначе — кэш."""
    if _tf_due(tf, now):
        df = get_candles_tf(tf, count=count)
        _candles_cache[tf] = df
        _last_fetch[tf] = now
        log.info("T-26: обновлён %s (count=%d)", tf, count)
    else:
        log.debug("T-26: %s из кэша (последнее обновление %s)", tf, _last_fetch[tf])
    return _candles_cache.get(tf)


# ============================================================
# Индикаторы
# ============================================================


def _build_indicator_snapshot(
    df,
    current_price: float,
    atr: float,
    df_h4=None,
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

    # --- Недельный тренд (H4) ---
    if df_h4 is None:
        # T-26: fallback через кэш (не тянем сеть, если df_h4 не передан)
        df_h4 = _get_cached("H4", 300, datetime.now())
    week_ctx = get_week_trend(df_h4)
    # from data.api_facade import get_candles_tf

    # df_h4 = get_candles_tf("H4", count=300)
    # week_ctx = get_week_trend(df_h4)

    # --- Импульс и состояние рынка (M15) ---
    n_impulse = 12  # 12 M15 = 3 часа
    n_pullback = 3  # 6 M15 = 1.5 часа

    impulse_atr = 0.0
    pullback_atr = 0.0
    impulse_dir = "none"
    market_state = "normal"

    if len(df) > n_impulse and atr > 0:
        price_n_ago = float(df["close"].iloc[-n_impulse])
        impulse_atr = abs(current_price - price_n_ago) / atr

        if impulse_atr > 1.5:
            if current_price > price_n_ago:
                impulse_dir = "up"
            else:
                impulse_dir = "down"

    if len(df) > n_pullback and atr > 0:
        price_n_ago_pb = float(df["close"].iloc[-n_pullback])
        pullback_atr = abs(current_price - price_n_ago_pb) / atr

    # --- Pullback: откат от экстремума импульса ---
    # ВАЖНО: всё внутри if len(df) > n_impulse and impulse_dir in ("up", "down"),
    # иначе window/retrace не определены (UnboundLocalError).
    if len(df) > n_impulse and atr > 0 and impulse_dir in ("up", "down"):
        window = df.iloc[-n_impulse:]

        if impulse_dir == "up":
            peak = window["high"].max()
            retrace = (peak - current_price) / atr
        else:
            trough = window["low"].min()
            retrace = (current_price - trough) / atr

        # pullback: откат 0.2..0.7 × impulse (как было)
        if impulse_atr > 1.2 and 0.2 < retrace < impulse_atr * 0.7:
            market_state = "pullback"
        # impulse: сильный импульс (>= 2.0 ATR) и почти нет отката (< 0.2)
        # пороги из ROADMAP п.18.1: impulse > 2.0, откат < 0.2 × impulse
        elif impulse_atr > 2.0 and retrace < 0.2 * impulse_atr:
            market_state = "impulse"

    # --- Volume ratio: последняя свеча / среднее за VOLUME_LOOKBACK ---
    volume_ratio = 1.0
    try:
        import config as _cfg

        if len(df) > _cfg.VOLUME_LOOKBACK and df["volume"].iloc[-1] > 0:
            avg_vol = df["volume"].iloc[-_cfg.VOLUME_LOOKBACK - 1 : -1].mean()
            if avg_vol > 0:
                volume_ratio = round(
                    min(float(df["volume"].iloc[-1] / avg_vol), 5.0), 2
                )
    except Exception:
        pass

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
        day_open=trend_context.get("day_open"),
        day_atr_base=trend_context.get("day_atr_base"),
        partial_day=trend_context.get("partial_day", False),
        structure=trend_context["structure"],
        price_direction=trend_context["price_direction"],
        vote_sum=main_trend_info["vote_sum"],
        vote_breakdown=main_trend_info["vote_breakdown"],
        week_trend=week_ctx["week_trend"],
        week_change_atr=week_ctx["week_change_atr"],
        impulse_atr=round(impulse_atr, 2),
        impulse_dir=impulse_dir,
        market_state=market_state,
        volume_ratio=volume_ratio,
        day_range_atr=trend_context.get("day_range_atr", 0.0),
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


def _enrich_levels(
    levels: list[Level], current_price: float, atr: float, now: datetime | None = None
) -> None:
    """
    Заполняет вычисляемые поля уровней:
        distance_atr   — |price - current| / atr
        age_days       — сколько дней с last_seen
        strength_score — weight × confirmed × tf_count × age_factor
    """
    now = now or datetime.now()

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


def analyze_from_df(
    df: "pd.DataFrame",
    df_h1: "pd.DataFrame | None" = None,
    df_h4: "pd.DataFrame | None" = None,
    df_atr: "pd.DataFrame | None" = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    order_book: dict | None = None,
    timestamp: datetime | None = None,
    skip_age_check: bool = False,
    skip_filters: bool = False,
    write_history: bool = True,
) -> AnalysisResult | None:
    """
    Собирает AnalysisResult из готовых DataFrame. Без сети.

    df       — M15 (или timeframe) — для индикаторов и сигналов.
    df_h1    — H1 — для references (PWH/PWL).
    df_h4    — H4 — для week_trend.
    df_atr   — H1 — для ATR. Если None, используется df_h1.

    Возвращает AnalysisResult или None, если данных нет.

    write_history — писать ли сигналы в signals_history.json.
        True (по умолчанию) — для live/runner (cooldown, «пила»).
        False — для backtest/replay: иначе исторические сигналы
        засоряют live-историю (пишутся с datetime.now(), а не
        с result.timestamp) и ломают cooldown в раннере.
    """
    import pandas as pd

    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.DEFAULT_TIMEFRAME

    if df is None or df.empty:
        log.error("analyze_from_df: пустой df для %s %s", symbol, timeframe)
        return None

    # 1. Индикаторы на M15
    df = add_indicators(df)
    current_price = float(df["close"].iloc[-1])

    # 2. ATR
    df_atr_use = df_atr if df_atr is not None else df_h1
    if df_atr_use is None or df_atr_use.empty:
        log.error("analyze_from_df: нет df_atr / df_h1 для ATR")
        return None
    atr = get_atr(df_atr_use, period=config.ATR_PERIOD)
    if atr is None:
        log.error("analyze_from_df: ATR не рассчитан")
        return None

    tolerance = config.LEVEL_TOLERANCE_ATR * atr

    # 3. Структурные уровни (нужны df_h1, df_h4 — или fallback на df)
    df_h1_use = df_h1 if df_h1 is not None else df
    df_h4_use = df_h4 if df_h4 is not None else df

    # build_levels тянет данные из api_facade — надо передать df-ы.
    # Пока — упрощённо: если df_h1/df_h4 None, build_levels сам тянет (сеть).
    # Для replay передавай df_h1/df_h4 явно.
    raw_levels = build_levels(
        symbol=symbol,
        tolerance=tolerance,
        current_price=current_price,
        atr=atr,
        df_intraday=df,
        df_h1=df_h1_use,
        df_h4=df_h4_use,
    )
    structural = [_dict_to_level(lv, "structural") for lv in raw_levels]

    # 4. Референсные уровни
    raw_refs = build_references(
        current_price=current_price,
        atr=atr,
        df_intraday=df,
        df_h1=df_h1_use,
    )
    references = [_dict_to_level(r, "reference") for r in raw_refs]

    # T-01b: ts нужен для _enrich_levels (age_days от ts, а не от now).
    ts = timestamp or datetime.now()

    # 5. Пересечения + обогащение
    _attach_tags(structural, references, tolerance)
    _enrich_levels(structural, current_price, atr, now=ts)
    _enrich_levels(references, current_price, atr, now=ts)

    # 6. Индикаторы
    indicators = _build_indicator_snapshot(df, current_price, atr, df_h4=df_h4_use)

    ts = timestamp or datetime.now()

    # 7. AnalysisResult
    result = AnalysisResult(
        symbol=symbol,
        timestamp=ts,
        current_price=current_price,
        atr=atr,
        timeframe=timeframe,
        indicators=indicators,
        levels=structural,
        references=references,
        signals=[],
        order_book=order_book or {},
    )

    # 8. Сигналы
    from strategy.signal_history import append_signals

    # --- skip_filters: временно отключаем фильтры (для replay) ---
    _saved_filters = {}
    if skip_filters:
        for k in (
            "PAPER_SKIP_BULLISH_LONG",
            "PAPER_SKIP_NORMAL_BREAKOUT",
            "PAPER_SKIP_BULLISH_SHORT",
            "PAPER_SKIP_ADX_FLAT_BREAKOUT",
            "PAPER_SKIP_ADX_TREND",
            "PAPER_SKIP_BID_HEAVY",
            "PAPER_SKIP_BREAKOUT",
        ):
            if hasattr(config, k):
                _saved_filters[k] = getattr(config, k)
                setattr(config, k, False)

    try:
        signals = detect_signals(
            result,
            df,
            now=ts,
            skip_age_check=skip_age_check,
            skip_filters=skip_filters,
        )
    finally:
        for k, v in _saved_filters.items():
            setattr(config, k, v)

    result.signals = signals
    if write_history:
        append_signals(signals, symbol)

    return result


def _drop_unclosed(
    df: pd.DataFrame | None, tf: str, now: datetime
) -> pd.DataFrame | None:
    """
    T-01b: оставить только ЗАКРЫТЫЕ свечи (begin + duration <= now).

    Live (ALOR) отдаёт текущую незакрытую свечу — это look-ahead.
    Для согласования с replay (verify_candles.py, backtest.py) отбрасываем её.
    """
    if df is None or df.empty:
        return df
    tf_min = {"M5": 5, "M15": 15, "H1": 60, "H4": 240}.get(tf, 60)
    delta = pd.Timedelta(minutes=tf_min)
    return df[df["begin"] + delta <= now].reset_index(drop=True)


def analyze(symbol: str = None, timeframe: str = None) -> AnalysisResult | None:
    """Обёртка: тянет данные из сети (api_facade) и вызывает analyze_from_df."""
    from core.time_utils import now_msk

    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.DEFAULT_TIMEFRAME

    _now = now_msk()

    # 1. M15 — только закрытые (T-01b)
    df = _drop_unclosed(_get_cached(timeframe, 300, _now), timeframe, _now)
    if df is None or df.empty:
        log.error("Нет данных для %s %s (или все свечи незакрыты)", symbol, timeframe)
        return None

    # Логируем лаг (наблюдаемость)
    try:
        last_begin = df["begin"].iloc[-1]
        if hasattr(last_begin, "to_pydatetime"):
            last_begin = last_begin.to_pydatetime()
        data_age_min = int((_now - last_begin).total_seconds() / 60)
        log.info(
            "data_age=%d min (последняя свеча %s)",
            data_age_min,
            last_begin.strftime("%Y-%m-%d %H:%M"),
        )
    except Exception as e:
        log.debug("data_age не посчитан: %s", e)

    # 2. H1, H4, ATR — тоже только закрытые (T-01b)
    df_h1 = _drop_unclosed(_get_cached("H1", 200, _now), "H1", _now)
    df_h4 = _drop_unclosed(_get_cached("H4", 300, _now), "H4", _now)
    df_atr = _drop_unclosed(_get_cached(config.ATR_TF, 200, _now), config.ATR_TF, _now)

    # 3. order_book (если ALOR)
    order_book = {}
    if config.DATA_PROVIDER == "alor":
        try:
            from data.api_alor import get_order_book_pressure_sync

            order_book = get_order_book_pressure_sync(symbol)
        except Exception as e:
            log.debug("order_book не получен: %s", e)

    return analyze_from_df(
        df=df,
        df_h1=df_h1,
        df_h4=df_h4,
        df_atr=df_atr,
        symbol=symbol,
        timeframe=timeframe,
        order_book=order_book,
    )
