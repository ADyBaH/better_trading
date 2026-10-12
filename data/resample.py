"""
Ресемплинг минутных свечей в M5 / M15 / M60.
MOEX ISS отдаёт только интервалы 1, 10, 60, 24 минут.
Всё остальное строим сами из минутных.
"""

import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)

# Соответствие наших имён таймфреймов и правил pandas
TIMEFRAME_RULES = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "M60": "60min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Преобразует минутные свечи в свечи нужного таймфрейма.

    df — DataFrame с колонками: begin, open, high, low, close, volume.
    timeframe — 'M5', 'M15', 'M60' и т.д. (см. TIMEFRAME_RULES).

    Возвращает DataFrame с теми же колонками.
    """
    if df.empty:
        return df

    if timeframe not in TIMEFRAME_RULES:
        raise ValueError(
            f"Неизвестный таймфрейм: {timeframe}. "
            f"Доступные: {list(TIMEFRAME_RULES.keys())}"
        )

    rule = TIMEFRAME_RULES[timeframe]

    df = df.copy()
    df = df.set_index("begin")

    # Правила агрегации:
    #   open   — первое значение в окне
    #   high   — максимум
    #   low    — минимум
    #   close  — последнее значение
    #   volume — сумма
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    # label="left" + closed="left" — свеча помечается временем начала,
    #   это привычнее для трейдинга (свеча 10:00 = интервал 10:00–10:05).
    # dropna() — убираем окна, в которых не было данных (ночь, выходные).
    resampled = (
        df.resample(rule, label="left", closed="left")
        .agg(agg)
        .dropna(subset=["open", "close"])
        .reset_index()
    )

    log.debug("Ресемплинг %s: %d → %d свечей", timeframe, len(df), len(resampled))
    return resampled
