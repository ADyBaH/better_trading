"""
Фасад над источниками данных.
Логика:
  1. Если БД свежая (последняя свеча < CACHE_TTL_MINUTES назад) — берём из БД.
  2. Иначе — докачиваем только новые свечи с биржи, дописываем в БД, берём из БД.
"""

from datetime import datetime, timedelta

import pandas as pd

from core.logger import get_logger
from data import api_moex, storage_sqlite
from data.resample import resample

import config

log = get_logger(__name__)


def _is_cache_fresh(symbol: str, interval: int) -> bool:
    """Проверяет, свежая ли БД: последняя свеча не старше CACHE_TTL_MINUTES."""
    last_begin_str = storage_sqlite.get_last_begin(symbol, interval)
    if last_begin_str is None:
        return False

    try:
        last_begin = pd.Timestamp(last_begin_str)
    except Exception:
        return False

    age_minutes = (datetime.now() - last_begin).total_seconds() / 60
    return age_minutes < config.CACHE_TTL_MINUTES


def _fetch_incremental(symbol: str, interval: int, count: int) -> pd.DataFrame:
    """
    Докачивает только свечи новее, чем последняя в БД.
    Если БД пуста — тянет count свечей.
    """
    last_begin_str = storage_sqlite.get_last_begin(symbol, interval)

    if last_begin_str is None:
        # БД пуста — тянем обычным способом
        log.info("БД пуста, тянем %d свечей с биржи", count)
        return api_moex.get_candles(symbol, interval, count, tail=False)

    # Есть последняя свеча — тянем свечи после неё
    last_begin = pd.Timestamp(last_begin_str)
    # Отступаем на одну минуту назад, чтобы не пропустить пограничную свечу
    start = (last_begin + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    end = datetime.now().strftime("%Y-%m-%d")

    log.info("Докачка с %s → %s", start, end)

    # get_candles_range принимает только даты, но с 2026-10-13 у нас start уже дата
    # Проще: тянем по датам, потом фильтруем по времени
    start_date = last_begin.strftime("%Y-%m-%d")
    df = api_moex.get_candles_range(symbol, interval, start_date, end)

    if df.empty:
        return df

    # Фильтруем только свечи новее last_begin
    df = df[df["begin"] > last_begin].reset_index(drop=True)
    return df


def get_candles(
    symbol: str = None,
    interval: int = None,
    count: int = 500,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Возвращает последние `count` минутных свечей.
    - Если БД свежая — из БД.
    - Иначе — докачиваем новые свечи с биржи.
    - force_refresh=True — игнорируем свежесть, докачиваем всегда.
    """
    symbol = symbol or config.SYMBOL
    interval = interval or config.BASE_INTERVAL

    storage_sqlite.init_db()

    # --- Проверка свежести ---
    if not force_refresh and _is_cache_fresh(symbol, interval):
        df = storage_sqlite.load_candles(symbol, interval, count)
        log.debug("БД свежая, взято %d свечей", len(df))
        return df.tail(count).reset_index(drop=True)

    # --- Докачка ---
    df_new = _fetch_incremental(symbol, interval, count)
    if not df_new.empty:
        storage_sqlite.save_candles(symbol, interval, df_new)

    # --- Возврат из БД (там теперь актуально) ---
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
    """
    symbol = symbol or config.SYMBOL

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

    need_m1 = (count + config.EMA_SLOW) * tf_minutes
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
