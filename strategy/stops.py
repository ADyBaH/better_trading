"""
Расчёт stop/take (ATR + адаптивный take).

Вынесено из strategy/signals.py (шаг 5 рефакторинга).

Возвращает (stop, take, meta):
    meta = {
        "take_source": "atr" | "day_range",
        "take_atr_value": float | None,
        "day_range_atr_at_open": float | None,
    }
"""

import config
from core.logger import get_logger

log = get_logger(__name__)


def _compute_stops(
    entry: float,
    direction: str,
    atr: float,
    day_range_atr: float | None = None,
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
            # --- Адаптивный take ---
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
