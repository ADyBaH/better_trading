# data/api_moex.py
"""
Обёртка над MOEX ISS для получения свечей по фьючерсам.
Возвращает pandas.DataFrame с колонками:
    begin, open, high, low, close, volume
"""

import requests
import pandas as pd
from datetime import datetime, timedelta

from core.logger import get_logger
import config

log = get_logger(__name__)

ISS_BASE_URL = "https://iss.moex.com/iss"
ISS_MAX_CANDLES_PER_REQUEST = 500  # лимит ISS на один запрос


def _fetch_one_day(symbol: str, interval: int, day: str) -> pd.DataFrame:
    """Тянет свечи за один день (внутренняя функция)."""
    url = (
        f"{ISS_BASE_URL}/engines/{config.ENGINE}/markets/{config.MARKET}"
        f"/securities/{symbol}/candles.json"
    )
    params = {
        "from": day,
        "till": day,
        "interval": interval,
        "iss.meta": "off",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    candles = data.get("candles", {})
    columns = candles.get("columns", [])
    rows = candles.get("data", [])

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=columns)
    return df


def get_candles_range(
    symbol: str,
    interval: int,
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    Тянет свечи за диапазон дат, разбивая на дни (из-за лимита ISS в 500 свечей).

    start, end: 'YYYY-MM-DD'
    """
    if interval not in (1, 10, 60, 24):
        raise ValueError(f"Недопустимый интервал: {interval}. Разрешено: 1, 10, 60, 24")

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    log.info("Запрос свечей: %s interval=%s %s → %s", symbol, interval, start, end)

    frames = []
    current = start_dt
    while current <= end_dt:
        day = current.strftime("%Y-%m-%d")
        df_day = _fetch_one_day(symbol, interval, day)
        if not df_day.empty:
            frames.append(df_day)
        current += timedelta(days=1)

    if not frames:
        log.warning("Свечей не получено: %s interval=%s %s→%s", symbol, interval, start, end)
        return pd.DataFrame(columns=["begin", "open", "high", "low", "close", "volume"])

    df = pd.concat(frames, ignore_index=True)

    # Оставляем только нужные колонки
    wanted = ["begin", "open", "high", "low", "close", "volume"]
    for col in wanted:
        if col not in df.columns:
            df[col] = None
    df = df[wanted]

    # Типы
    df["begin"] = pd.to_datetime(df["begin"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("begin").drop_duplicates("begin").reset_index(drop=True)
    log.info("Получено свечей: %d (период %s → %s)", len(df), df["begin"].min(), df["begin"].max())
    return df


def get_candles(
    symbol: str,
    interval: int,
    count: int = 500,
    tail: bool = True,   # <-- новый параметр
) -> pd.DataFrame:
    days_back = max(3, (count // 400) + 5)
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    df = get_candles_range(symbol, interval, start, end)
    if tail:
        return df.tail(count).reset_index(drop=True)
    return df
