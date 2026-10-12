"""
Поиск уровней на свечах.

Начинаем с простого: фракталы (Bill Williams).
Фрактал вверх — свеча, у которой high выше, чем у N свечей слева и справа.
Фрактал вниз  — свеча, у которой low ниже, чем у N свечей слева и справа.

Позже добавим:
- кластеризацию близких фракталов в уровни,
- ATR-нормализацию,
- мульти-ТФ и веса,
- референсные уровни (round numbers, PDH/PDL).
"""

import pandas as pd

from core.logger import get_logger
import config

log = get_logger(__name__)


def find_fractals(df: pd.DataFrame, period: int = None) -> list[dict]:
    """
    Находит фракталы в DataFrame со свечами.

    df — DataFrame с колонками: begin, open, high, low, close, volume.
    period — сколько свечей слева и справа проверять (по умолчанию из config).

    Возвращает список словарей:
        {
            "begin":  Timestamp,
            "price":  float,
            "type":   "up" | "down",
            "index":  int,       # индекс свечи в исходном df
        }
    """
    period = period or config.FRACTAL_PERIOD

    if len(df) < 2 * period + 1:
        log.warning(
            "Слишком мало свечей для фракталов: %d (нужно ≥%d)",
            len(df),
            2 * period + 1,
        )
        return []

    fractals = []
    highs = df["high"].values
    lows = df["low"].values

    # Начинаем с period и заканчиваем на len(df) - period - 1,
    # потому что для фрактала нужны соседи слева и справа.
    for i in range(period, len(df) - period):
        # --- Фрактал вверх ---
        window_high = highs[i - period : i + period + 1]
        if highs[i] == window_high.max() and (window_high == highs[i]).sum() == 1:
            fractals.append(
                {
                    "begin": df["begin"].iloc[i],
                    "price": float(highs[i]),
                    "type": "up",
                    "index": i,
                }
            )

        # --- Фрактал вниз ---
        window_low = lows[i - period : i + period + 1]
        if lows[i] == window_low.min() and (window_low == lows[i]).sum() == 1:
            fractals.append(
                {
                    "begin": df["begin"].iloc[i],
                    "price": float(lows[i]),
                    "type": "down",
                    "index": i,
                }
            )

    # Сортируем по времени
    fractals.sort(key=lambda f: f["begin"])
    log.info("Найдено фракталов: %d (period=%d)", len(fractals), period)
    return fractals
