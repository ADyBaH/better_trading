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
    """
    Тянет свечи за один день с пагинацией.

    ISS отдаёт максимум 500 свечей за запрос. Если нужно больше —
    используем параметр `start` и идём по страницам, пока не закончатся.
    """
    url = (
        f"{ISS_BASE_URL}/engines/{config.ENGINE}/markets/{config.MARKET}"
        f"/securities/{symbol}/candles.json"
    )

    all_rows = []
    columns = None
    start = 0
    page_size = 500
    page_num = 0

    while True:
        params = {
            "from": day,
            "till": day,
            "interval": interval,
            "start": start,
            "iss.meta": "off",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
        except Exception as e:
            log.warning("Ошибка запроса ISS (страница %d): %s", page_num, e)
            break

        data = response.json()
        candles = data.get("candles", {})
        rows = candles.get("data", [])
        if columns is None:
            columns = candles.get("columns", [])

        if not rows:
            break

        all_rows.extend(rows)
        page_num += 1

        # Если получили меньше, чем размер страницы — это последняя
        if len(rows) < page_size:
            break

        start += page_size

        # Защита от бесконечного цикла
        if page_num > 20:
            log.warning("Пагинация превысила 20 страниц, прерываем")
            break

    if not all_rows:
        return pd.DataFrame()

    if columns is None:
        columns = []

    log.debug("Свечей за %s: %d (страниц: %d)", day, len(all_rows), page_num + 1)
    return pd.DataFrame(all_rows, columns=columns)


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
        log.warning(
            "Свечей не получено: %s interval=%s %s→%s", symbol, interval, start, end
        )
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
    log.info(
        "Получено свечей: %d (период %s → %s)",
        len(df),
        df["begin"].min(),
        df["begin"].max(),
    )
    return df


def get_candles(
    symbol: str,
    interval: int,
    count: int = 500,
    tail: bool = True,  # <-- новый параметр
) -> pd.DataFrame:
    days_back = max(3, (count // 400) + 5)
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    df = get_candles_range(symbol, interval, start, end)
    if tail:
        return df.tail(count).reset_index(drop=True)
    return df
