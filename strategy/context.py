"""
Сборка context сигнала (19 полей) + сессия.

Вынесено из strategy/signals.py (шаг 3 рефакторинга).
"""

import pandas as pd

import config
from core.logger import get_logger
from core.models import AnalysisResult, Level

log = get_logger(__name__)


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

    # Свежесть данных
    data_age_minutes = None
    last_candle_time = None
    if len(df) > 0:
        try:
            last_candle_time = df["begin"].iloc[-1]
            if hasattr(last_candle_time, "to_pydatetime"):
                last_candle_time = last_candle_time.to_pydatetime()
            data_age_minutes = int(
                (result.timestamp - last_candle_time).total_seconds() / 60
            )
        except Exception:
            pass

    # Время
    now = result.timestamp
    hour_utc = now.utctimetuple().tm_hour
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
        "data_age_minutes": data_age_minutes,
        "last_candle_time": last_candle_time.isoformat() if last_candle_time else None,
        "volume_ratio": ind.volume_ratio,
    }
