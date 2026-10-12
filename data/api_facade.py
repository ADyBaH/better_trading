"""
Фасад над источниками данных.
Логика: сначала смотрим в БД, если там мало — докачиваем с биржи и сохраняем.
"""

import pandas as pd

from core.logger import get_logger
from data import api_moex, storage_sqlite
from data.resample import resample

import config

log = get_logger(__name__)


def get_candles(
    symbol: str = None,
    interval: int = None,
    count: int = 500,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Возвращает последние `count` минутных свечей.
    (Это базовая функция; для других ТФ используй get_candles_tf.)
    """
    symbol = symbol or config.SYMBOL
    interval = interval or config.BASE_INTERVAL

    storage_sqlite.init_db()

    if not force_refresh:
        df = storage_sqlite.load_candles(symbol, interval, count)
        if len(df) >= count:
            log.debug("Взято из БД: %d свечей", len(df))
            return df.tail(count).reset_index(drop=True)

    df_new = api_moex.get_candles(symbol, interval, count, tail=False)
    if not df_new.empty:
        storage_sqlite.save_candles(symbol, interval, df_new)

    df = storage_sqlite.load_candles(symbol, interval, count)
    return df.tail(count).reset_index(drop=True)


def get_candles_tf(
    timeframe: str,
    count: int = 500,
    symbol: str = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Возвращает последние `count` свечей указанного таймфрейма.
    Внутри тянет M1 и ресемплит.

    Важно: чтобы получить `count` свечей M5, нужно ~count * 5 минутных свечей,
    поэтому берём с запасом.
    """
    symbol = symbol or config.SYMBOL

    # Сколько минутных свечей нужно для `count` свечей данного ТФ + запас на прогрев EMA200
    tf_minutes = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "M60": 60,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
    }.get(timeframe)
    if tf_minutes is None:
        raise ValueError(f"Неизвестный таймфрейм: {timeframe}")

    # Нужно count свечей ТФ + EMA_SLOW свечей на прогрев, помноженные на минуты
    need_m1 = (count + config.EMA_SLOW) * tf_minutes
    # Плюс запас на выходные/ночь — берём с коэффициентом
    need_m1_with_reserve = int(need_m1 * 1.5)

    log.info(
        "Запрос %s: нужно ~%d минутных свечей для %d свечей %s",
        timeframe,
        need_m1_with_reserve,
        count,
        timeframe,
    )

    df_m1 = get_candles(
        symbol=symbol,
        interval=config.BASE_INTERVAL,
        count=need_m1_with_reserve,
        force_refresh=force_refresh,
    )

    if df_m1.empty:
        log.warning("Нет минутных данных для ресемплинга в %s", timeframe)
        return df_m1

    df_tf = resample(df_m1, timeframe)
    log.info("После ресемплинга %s: %d свечей", timeframe, len(df_tf))
    return df_tf.tail(count).reset_index(drop=True)
