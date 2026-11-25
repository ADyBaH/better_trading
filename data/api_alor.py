"""ALOR WebSocket — получение свечей в реальном времени."""

import json
import time
import asyncio
import logging
import requests
import websockets
import pandas as pd
from datetime import datetime, timezone, timedelta
from core.logger import get_logger
from local_config import ALOR_TOKEN

WS_URL = "wss://api.alor.ru/ws"
OAUTH_URL = "https://oauth.alor.ru"

MSK = timezone(timedelta(hours=3))

_access_token = None
_token_expires_at = 0

log = logging.getLogger(__name__)

# BUG-12: retry с backoff для WS handshake
_WS_RETRY_ATTEMPTS = 3
_WS_RETRY_BACKOFF = (1, 2, 4)  # сек между попытками


async def _connect_ws_with_retry(ws_url: str, open_timeout: int = 10):
    """
    BUG-12: подключение к ALOR WS с retry и backoff.
    При таймауте handshake — повтор через 1, 2, 4 сек.
    После 3 неудач — пробрасывает исключение.
    """
    last_exc = None
    for attempt in range(_WS_RETRY_ATTEMPTS):
        try:
            ws = await websockets.connect(ws_url, open_timeout=open_timeout)
            if attempt > 0:
                log.warning("ALOR WS: подключение успешно с попытки %d", attempt + 1)
            return ws
        except (
            asyncio.TimeoutError,
            OSError,
            websockets.exceptions.WebSocketException,
        ) as e:
            last_exc = e
            if attempt < _WS_RETRY_ATTEMPTS - 1:
                delay = _WS_RETRY_BACKOFF[attempt]
                log.warning(
                    "ALOR WS: попытка %d/%d не удалась (%s), повтор через %d сек",
                    attempt + 1,
                    _WS_RETRY_ATTEMPTS,
                    type(e).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                log.error(
                    "ALOR WS: все %d попыток не удались (%s)",
                    _WS_RETRY_ATTEMPTS,
                    type(e).__name__,
                )
    raise last_exc


def _get_access_token() -> str:
    global _access_token, _token_expires_at
    if _access_token and time.time() < _token_expires_at:
        return _access_token
    resp = requests.post(f"{OAUTH_URL}/refresh?token={ALOR_TOKEN}", timeout=10)
    resp.raise_for_status()
    _access_token = resp.json()["AccessToken"]
    _token_expires_at = time.time() + 1500
    return _access_token


async def _fetch_candles_ws(
    symbol: str, interval: str, count: int = 50
) -> pd.DataFrame:
    import websockets

    tf_map = {"M1": "60", "M5": "300", "M15": "900", "H1": "3600", "H4": "14400"}
    tf = tf_map.get(interval)
    if not tf:
        raise ValueError(f"Неизвестный таймфрейм: {interval}")

    access = _get_access_token()

    # from = count свечей назад
    tf_minutes = int(tf) // 60
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(minutes=tf_minutes * count * 2)
    from_ts = int(from_dt.timestamp())

    rows = []

    try:
        async with await _connect_ws_with_retry(WS_URL, open_timeout=10) as ws:
            sub_msg = {
                "opcode": "BarsGetAndSubscribe",
                "guid": "sub-1",
                "exchange": "MOEX",
                "code": symbol,
                "instrumentGroup": "RFUD",
                "tf": tf,
                "format": "Simple",
                "token": access,
                "skipHistory": False,  # <-- ключ
                "from": from_ts,  # <-- ключ
            }
            await ws.send(json.dumps(sub_msg))
            log.info("ALOR WS: подписка на %s %s", symbol, interval)

            # Ждём 3 секунды, собираем всё
            deadline = time.time() + 7.0
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                except asyncio.TimeoutError:
                    break
                data = json.loads(msg)
                if "data" not in data:
                    continue
                bar = data["data"]
                t = bar.get("time")
                if isinstance(t, (int, float)):
                    begin = datetime.fromtimestamp(t, tz=MSK).replace(tzinfo=None)
                else:
                    begin = pd.to_datetime(t)
                rows.append(
                    {
                        "begin": begin,
                        "open": float(bar.get("open", 0)),
                        "high": float(bar.get("high", 0)),
                        "low": float(bar.get("low", 0)),
                        "close": float(bar.get("close", 0)),
                        "volume": int(bar.get("volume", 0)),
                    }
                )
    except Exception as e:
        log.error("ALOR WS ошибка: %s", e)
        if not rows:
            return pd.DataFrame(
                columns=["begin", "open", "high", "low", "close", "volume"]
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("begin").drop_duplicates("begin").reset_index(drop=True)
    log.info(
        "ALOR WS: получено %d свечей %s (%s), последняя: %s",
        len(df),
        symbol,
        interval,
        df["begin"].iloc[-1],
    )
    return df


def get_candles_range(
    symbol: str, interval: str, start: datetime, end: datetime
) -> pd.DataFrame:
    count = 300  # достаточно для анализа
    try:
        return asyncio.run(_fetch_candles_ws(symbol, interval, count))
    except Exception as e:
        log.error("ALOR: критическая ошибка: %s", e)
        return pd.DataFrame(columns=["begin", "open", "high", "low", "close", "volume"])


def get_order_book_pressure_sync(symbol: str) -> dict:
    """Синхронная обёртка: получает стакан и считает перевес."""
    import asyncio

    return asyncio.run(_get_order_book_pressure(symbol))


async def _get_order_book_pressure(symbol: str) -> dict:
    """Подключается к WS, получает стакан, считает перевес bid/ask."""

    access = _get_access_token()
    sub_msg = {
        "opcode": "OrderBookGetAndSubscribe",
        "guid": "ob-1",
        "exchange": "MOEX",
        "code": symbol,
        "instrumentGroup": "RFUD",
        "depth": 10,
        "format": "Simple",
        "token": access,
    }

    last_ob = None
    async with await _connect_ws_with_retry(WS_URL, open_timeout=10) as ws:
        await ws.send(json.dumps(sub_msg))
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3)
            data = json.loads(msg)
            if "data" in data:
                last_ob = data["data"]
        except asyncio.TimeoutError:
            pass

    if not last_ob:
        return {"bid_vol": 0, "ask_vol": 0, "pressure_pct": 50.0}

    bids = last_ob.get("bids", [])
    asks = last_ob.get("asks", [])
    bid_vol = sum(float(b.get("volume", 0)) for b in bids)
    ask_vol = sum(float(a.get("volume", 0)) for a in asks)
    total = bid_vol + ask_vol
    pressure = (bid_vol / total * 100) if total > 0 else 50.0

    return {"bid_vol": bid_vol, "ask_vol": ask_vol, "pressure_pct": pressure}


def get_current_price_sync(symbol: str) -> dict:
    """
    Возвращает текущую цену из стакана:
    bid, ask, last (если есть), mid (середина).
    В мок-режиме — заглушка.
    """
    import asyncio

    return asyncio.run(_get_current_price(symbol))


async def _get_current_price(symbol: str) -> dict:
    """Подключается к WS, берёт стакан, возвращает bid/ask/mid."""
    import websockets

    access = _get_access_token()
    sub_msg = {
        "opcode": "OrderBookGetAndSubscribe",
        "guid": "ob-price",
        "exchange": "MOEX",
        "code": symbol,
        "instrumentGroup": "RFUD",
        "depth": 1,
        "format": "Simple",
        "token": access,
    }

    last_ob = None
    try:
        async with await _connect_ws_with_retry(WS_URL, open_timeout=10) as ws:
            await ws.send(json.dumps(sub_msg))
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                data = json.loads(msg)
                if "data" in data:
                    last_ob = data["data"]
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        log.error("get_current_price: %s", e)
        return {"bid": None, "ask": None, "mid": None}

    if not last_ob:
        return {"bid": None, "ask": None, "mid": None}

    bids = last_ob.get("bids", [])
    asks = last_ob.get("asks", [])

    bid = float(bids[0]["price"]) if bids else None
    ask = float(asks[0]["price"]) if asks else None

    mid = None
    if bid is not None and ask is not None:
        mid = round((bid + ask) / 2, 5)

    return {"bid": bid, "ask": ask, "mid": mid}
