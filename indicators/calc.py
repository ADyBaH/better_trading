"""
Расчёт технических индикаторов через pandas_ta.
+ контекст тренда: day_trend, structure, price_direction.
"""

import pandas as pd
import pandas_ta as ta

import config
from core.logger import get_logger
from indicators.vote import vote, vote_raw

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


def _detect_structure(df: pd.DataFrame, period: int = 2) -> str:
    """
    Определяет структуру рынка по фракталам: HH/LL.

    Возвращает:
        "bullish" — higher highs и higher lows.
        "bearish" — lower highs и lower lows.
        "mixed"   — иначе.
    """
    from strategy.levels import find_fractals

    fractals = find_fractals(df, period=period)
    if not fractals:
        return "mixed"

    ups = [f for f in fractals if f["type"] == "up"]
    downs = [f for f in fractals if f["type"] == "down"]

    if len(ups) < 2 or len(downs) < 2:
        return "mixed"

    # Берём последние 2 фрактала каждого типа
    last_up, prev_up = ups[-1]["price"], ups[-2]["price"]
    last_down, prev_down = downs[-1]["price"], downs[-2]["price"]

    higher_highs = last_up > prev_up
    higher_lows = last_down > prev_down
    lower_highs = last_up < prev_up
    lower_lows = last_down < prev_down

    if higher_highs and higher_lows:
        return "bullish"
    elif lower_highs and lower_lows:
        return "bearish"
    return "mixed"


def get_trend_context(
    df: pd.DataFrame,
    current_price: float,
    ema_fast: float,
    ema_slow: float,
    atr: float,
) -> dict:
    """
    Собирает контекст тренда из нескольких источников.

    Возвращает dict с полями:
        ema_trend:       "up" / "down"
        day_trend:       "bullish" / "bearish" / "neutral" / "unknown"
        day_change_atr:  изменение дня в ATR
        day_open:        open первого бара дня (для прозрачности)
        day_atr_base:    ATR, использованный для day_change_atr
        partial_day:     True, если день не завершён (сейчас < 18:00 МСК)
        structure:       "bullish" / "bearish" / "mixed"
        price_direction: "up" / "down" / "unknown"
    """
    # --- 1. EMA-тренд ---
    if ema_fast is not None and ema_slow is not None:
        ema_trend = "up" if ema_fast > ema_slow else "down"
    else:
        ema_trend = "unknown"

    # --- 2. Дневной тренд ---
    day_trend = "unknown"
    day_change_atr = 0.0
    day_open = None
    day_atr_base = None
    partial_day = False

    if not df.empty and atr > 0:
        try:
            today = df["begin"].iloc[-1].date()
            day_df = df[df["begin"].dt.date == today]
            if not day_df.empty:
                day_open = float(day_df["open"].iloc[0])
                day_change = current_price - day_open
                day_change_atr = day_change / atr
                day_atr_base = atr

                # partial_day: сейчас < 18:00 МСК (день не завершён)
                from datetime import datetime, timedelta, timezone

                now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                    hours=3
                )
                hour_msk = now.hour
                partial_day = hour_msk < 18
        except Exception as e:
            log.debug("Не удалось посчитать day_change: %s", e)

    # --- 3. Структура ---
    structure = _detect_structure(df)

    # --- 4. day_trend: change + structure ---
    if day_change_atr > 0.7 and structure == "bullish":
        day_trend = "bullish"
    elif day_change_atr < -0.7 and structure == "bearish":
        day_trend = "bearish"
    elif day_change_atr > 0.7 or day_change_atr < -0.7:
        day_trend = "neutral"  # движение есть, но структура не подтверждает
    else:
        day_trend = "neutral"

    # --- 5. Направление цены за 20 свечей ---
    if len(df) >= 20:
        price_20_ago = float(df["close"].iloc[-20])
        price_direction = "up" if current_price > price_20_ago else "down"
    else:
        price_direction = "unknown"
    day_range_atr = 0.0
    if not df.empty and atr > 0:
        try:
            today = df["begin"].iloc[-1].date()
            day_df = df[df["begin"].dt.date == today]
            if not day_df.empty:
                day_high = float(day_df["high"].max())
                day_low = float(day_df["low"].min())
                day_range_atr = round((day_high - day_low) / atr, 2)
        except Exception:
            pass

    return {
        "ema_trend": ema_trend,
        "day_trend": day_trend,
        "day_change_atr": round(day_change_atr, 2),
        "day_open": day_open,
        "day_atr_base": round(day_atr_base, 5) if day_atr_base else None,
        "partial_day": partial_day,
        "structure": structure,
        "price_direction": price_direction,
        "day_range_atr": day_range_atr,
    }


def _tri(up: str, down: str, value: str) -> bool | None:
    """True → up, False → down, None → неизвестно (воздержался)."""
    if value == up:
        return True
    if value == down:
        return False
    return None


def get_main_trend(trend_context: dict) -> dict:
    """
    Голосование 4 источников → главный тренд.

    Возвращает:
        trend:         "up" / "down" / "strong_up" / "strong_down" / "transition"
        vote_sum:      сумма голосов
        vote_breakdown: dict {источник: голос}
    """
    ema = trend_context.get("ema_trend")
    day = trend_context.get("day_trend")
    structure = trend_context.get("structure")
    price_dir = trend_context.get("price_direction")

    result = vote(
        conditions=[
            ("ema", _tri("up", "down", ema)),
            ("day", _tri("bullish", "bearish", day)),
            ("structure", _tri("bullish", "bearish", structure)),
            ("price_direction", _tri("up", "down", price_dir)),
        ],
        thresholds=[
            (">=", 3, "strong_up"),
            (">=", 2, "up"),
            ("<=", -3, "strong_down"),
            ("<=", -2, "down"),
        ],
        default="transition",
    )

    return {
        "trend": result.label,
        "vote_sum": int(result.total),
        "vote_breakdown": {k: int(v) for k, v in result.breakdown.items()},
    }


def get_week_trend(df_h4) -> dict:
    """
    Недельный тренд по H4.
    Голоса:
        - EMA50 vs EMA200 на H4 (±1)
        - close vs close 5 дней назад (±1)
        - close vs open 5 дней назад (±1)
    Нейтральная зона: |week_change_atr| < 0.5 → neutral.
    """
    import pandas as pd
    import pandas_ta as ta

    empty = {"week_trend": "unknown", "week_change_atr": 0.0}
    if df_h4 is None or len(df_h4) < 200:
        return empty

    df = df_h4.copy().reset_index(drop=True)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    last = df.iloc[-1]
    if pd.isna(last["ema50"]) or pd.isna(last["ema200"]) or pd.isna(last["atr"]):
        return empty

    week_close_5d = df["close"].iloc[-30]
    week_open_5d = df["open"].iloc[-30]

    result = vote_raw(
        conditions=[
            ("ema50_200", last["ema50"] > last["ema200"]),
            ("close_5d", last["close"] > week_close_5d),
            ("open_5d", last["close"] > week_open_5d),
        ],
    )
    votes = int(result.total)

    week_change_atr = 0.0
    if last["atr"] > 0:
        week_change_atr = (last["close"] - week_open_5d) / last["atr"]

    if abs(week_change_atr) < 0.5:
        week_trend = "neutral"
    elif votes >= 1:
        week_trend = "bullish"
    elif votes <= -1:
        week_trend = "bearish"
    else:
        week_trend = "neutral"

    return {
        "week_trend": week_trend,
        "week_change_atr": round(float(week_change_atr), 2),
    }
