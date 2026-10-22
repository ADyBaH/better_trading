"""ALOR WebSocket — получение свечей в реальном времени."""

import asyncio
import json
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from core.logger import get_logger
from local_config import ALOR_TOKEN

log = get_logger(__name__)

WS_URL = "wss://api.alor.ru/ws"
OAUTH_URL = "https://oauth.alor.ru"

MSK = timezone(timedelta(hours=3))

_access_token = None
_token_expires_at = 0


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
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
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
