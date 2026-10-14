# tests/test_aiomoex_v2.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp
import aiomoex


async def try_market_candles():
    print("=== aiomoex v2: get_market_candles ===")
    async with aiohttp.ClientSession() as session:
        try:
            data = await aiomoex.get_market_candles(
                session=session,
                security="CNYRUBF",
                market="forts",
                engine="futures",
                interval=1,
                start="2026-10-14",
                end="2026-10-14",
            )
            print(f"✓ Свечей: {len(data)}")
            if data:
                print(f"  Первая: {data[0].get('begin')}")
                print(f"  Последняя: {data[-1].get('begin')}")
                print(f"  Последние 3:")
                for row in data[-3:]:
                    print(f"    {row}")
        except Exception as e:
            print(f"❌ Ошибка: {type(e).__name__}: {e}")


async def try_raw_client():
    print("\n=== aiomoex v2: ISSClient (произвольный запрос) ===")
    url = (
        "https://iss.moex.com/iss/engines/futures/markets/forts"
        "/securities/CNYRUBF/candles.json"
    )
    arguments = {
        "from": "2026-10-14",
        "till": "2026-10-14",
        "interval": 1,
        "iss.meta": "off",
    }
    async with aiohttp.ClientSession() as session:
        try:
            client = aiomoex.ISSClient(session, url, arguments)
            data = await client.get()
            print(f"✓ Блоков в ответе: {len(data)}")
            if data:
                candles = data.get("candles", {})
                rows = candles.get("data", [])
                print(f"  Свечей: {len(rows)}")
                if rows:
                    print(f"  Первая: {rows[0][0]}")
                    print(f"  Последняя: {rows[-1][0]}")
        except Exception as e:
            print(f"❌ Ошибка: {type(e).__name__}: {e}")


def main():
    print("=" * 60)
    print("Эксперимент: aiomoex v2.x")
    print("=" * 60)
    asyncio.run(try_market_candles())
    asyncio.run(try_raw_client())
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
