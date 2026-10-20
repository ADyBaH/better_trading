"""T-Invest API — обёртка. Пока без токена — мок-режим."""

import pandas as pd
from datetime import datetime, timedelta
from core.logger import get_logger
import config

log = get_logger(__name__)

# Пока токена нет — используем мок
_MOCK_MODE = True


def get_candles_range(symbol, interval, start, end):
    """
    Возвращает DataFrame с колонками begin, open, high, low, close, volume.
    В мок-режиме — синтетические данные (синусоида), чтобы тесты работали.
    """
    if _MOCK_MODE:
        return _mock_candles(interval, count=50)

    # --- Реальный вызов (когда будет токен) ---
    # from brokerbridge import BrokerBridgeClient, BrokerStrategy, CandleResolution
    # async with BrokerBridgeClient(broker=BrokerStrategy.TINVEST) as client:
    #     df = await client.get_candles(
    #         figi="...",  # нужно будет найти FIGI для CNYRUBF
    #         from_time=start,
    #         to_time=end,
    #         resolution=...,
    #     )
    # return _normalize(df)
    raise NotImplementedError("Реальный T-Invest пока не подключён (нужен токен)")


def _mock_candles(interval: str, count: int = 50) -> pd.DataFrame:
    """Синтетические свечи для тестов. Цена вокруг 12.5, синусоида."""
    import math

    base_price = 12.5
    rows = []
    now = datetime.now().replace(second=0, microsecond=0)

    for i in range(count):
        # Синусоида для предсказуемых тестов
        offset = math.sin(i / 5) * 0.05
        close = round(base_price + offset, 3)
        high = round(close + 0.01, 3)
        low = round(close - 0.01, 3)
        open_ = round(close - offset * 0.1, 3)  # грубо
        begin = now - timedelta(minutes=15 * (count - i))
        rows.append(
            {
                "begin": begin,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + i * 10,
            }
        )

    return pd.DataFrame(rows)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит ответ brokerbridge к формату MOEX ISS."""
    # brokerbridge отдаёт индекс Unix-секунды, колонки OHLCV
    df = df.reset_index()
    df = df.rename(columns={"index": "begin"})
    df["begin"] = pd.to_datetime(df["begin"], unit="s")
    # Убедимся, что колонки в нужном порядке
    return df[["begin", "open", "high", "low", "close", "volume"]]
