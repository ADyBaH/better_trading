"""Разведка Order Book ALOR: перевес bid/ask."""

import sys
import asyncio
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from local_config import ALOR_TOKEN

WS_URL = "wss://api.alor.ru/ws"
OAUTH_URL = "https://oauth.alor.ru"

MSK = timezone(timedelta(hours=3))


def get_access_token():
    resp = requests.post(f"{OAUTH_URL}/refresh?token={ALOR_TOKEN}", timeout=10)
    resp.raise_for_status()
    return resp.json()["AccessToken"]


async def main():
    access = get_access_token()
    print(f"✅ Access Token: {access[:30]}...")

    # Подписка на стакан (глубина 10)
    sub_msg = {
        "opcode": "OrderBookGetAndSubscribe",
        "guid": "ob-1",
        "exchange": "MOEX",
        "code": "CNYRUBF",
        "instrumentGroup": "RFUD",
        "depth": 10,
        "format": "Simple",
        "token": access,
    }

    async with websockets.connect(WS_URL, open_timeout=10) as ws:
        await ws.send(json.dumps(sub_msg))
        print("→ Подписка на стакан (глубина 10)")

        last_ob = None
        start = time.time()

        while time.time() - start < 5:  # слушаем 5 секунд
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                data = json.loads(msg)
                if "data" not in data:
                    continue
                ob = data["data"]
                last_ob = ob
            except asyncio.TimeoutError:
                break

    if not last_ob:
        print("❌ Стакан не получен")
        return

    # Считаем перевес
    bids = last_ob.get("bids", [])
    asks = last_ob.get("asks", [])
    bid_vol = sum(float(b.get("volume", 0)) for b in bids)
    ask_vol = sum(float(a.get("volume", 0)) for a in asks)

    print(f"\n✅ Стакан получен (глубина 10)")
    print(f"  Bid (покупка): {bid_vol:.0f}")
    print(f"  Ask (продажа): {ask_vol:.0f}")
    if bid_vol + ask_vol > 0:
        pressure = bid_vol / (bid_vol + ask_vol) * 100
        print(f"  Перевес покупателей: {pressure:.1f}%")
        if pressure > 60:
            print("  ✅ Перевес на покупку (бычий)")
        elif pressure < 40:
            print("  ✅ Перевес на продажу (медвежий)")
        else:
            print("  ⚖️ Баланс")
    else:
        print("  ⚠️ Нулевой объём в стакане")

    # Показываем 3 лучших bid/ask
    print("\n  Лучшие 3 bid:")
    for b in bids[:3]:
        print(f"    price={b.get('price')}, volume={b.get('volume')}")
    print("  Лучшие 3 ask:")
    for a in asks[:3]:
        print(f"    price={a.get('price')}, volume={a.get('volume')}")


if __name__ == "__main__":
    asyncio.run(main())
