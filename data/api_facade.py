"""
Фасад над источниками данных.
Логика: сначала смотрим в БД, если там мало — докачиваем с биржи и сохраняем.
"""

import pandas as pd

from core.logger import get_logger
from data import api_moex, storage_sqlite

import config

log = get_logger(__name__)


def get_candles(
    symbol: str = None,
    interval: int = None,
    count: int = 500,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Возвращает последние `count` свечей.

    force_refresh=True — игнорировать БД, тянуть заново с биржи.
    """
    symbol = symbol or config.SYMBOL
    interval = interval or config.BASE_INTERVAL

    storage_sqlite.init_db()

    if not force_refresh:
        df = storage_sqlite.load_candles(symbol, interval, count)
        if len(df) >= count:
            log.info("Взято из БД: %d свечей", len(df))
            return df.tail(count).reset_index(drop=True)

    # Мало данных — тянем с биржи
    df_new = api_moex.get_candles(symbol, interval, count, tail=False)
    if not df_new.empty:
        storage_sqlite.save_candles(symbol, interval, df_new)

    # Возвращаем из БД (там теперь точно актуально)
    df = storage_sqlite.load_candles(symbol, interval, count)
    return df.tail(count).reset_index(drop=True)
