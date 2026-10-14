"""
Диагностика лага MOEX ISS.
Запускает 5 тестов и печатает результаты.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from data.api_moex import get_candles, get_candles_range
import config


def test_1_current():
    print("\n=== Тест 1: Что отдаёт ISS прямо сейчас ===")
    print(f"Локальное время: {datetime.now()}")
    df = get_candles(config.SYMBOL, config.BASE_INTERVAL, count=10, tail=True)
    if df.empty:
        print("  ❌ Нет данных")
        return
    print(f"  Последняя свеча: {df['begin'].iloc[-1]}")
    print(f"  Цена: {df['close'].iloc[-1]}")
    print()
    print(df[["begin", "close"]].tail(10).to_string(index=False))


def test_2_today_range():
    print("\n=== Тест 2: Сколько свечей ISS отдаёт за день ===")
    df = get_candles_range(
        config.SYMBOL, config.BASE_INTERVAL, "2026-10-14", "2026-10-14"
    )
    if df.empty:
        print("  ❌ Нет данных")
        return
    print(f"  Всего свечей: {len(df)}")
    print(f"  Первая: {df['begin'].iloc[0]}")
    print(f"  Последняя: {df['begin'].iloc[-1]}")
    print()
    print(df[["begin", "close"]].tail(15).to_string(index=False))


def test_3_direct_candles():
    print("\n=== Тест 3: Прямой ISS-запрос (candles.json) ===")
    url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities/CNYRUBF/candles.json"
    params = {
        "from": "2026-10-14",
        "till": "2026-10-14",
        "interval": 1,
        "iss.meta": "off",
    }
    r = requests.get(url, params=params, timeout=30)
    data = r.json()
    candles = data.get("candles", {})
    columns = candles.get("columns", [])
    rows = candles.get("data", [])
    print(f"  Колонки: {columns}")
    print(f"  Всего: {len(rows)}")
    if rows:
        print(f"  Первая: {rows[0][0]}")
        print(f"  Последняя: {rows[-1][0]}")
        print("  Последние 5:")
        for row in rows[-5:]:
            print(f"    {row[0]} | close={row[4]}")


def test_4_direct_trades():
    print("\n=== Тест 4: Прямой ISS-запрос (trades.json) ===")
    url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities/CNYRUBF/trades.json"
    params = {
        "from": "2026-10-14",
        "till": "2026-10-14",
        "iss.meta": "off",
    }
    r = requests.get(url, params=params, timeout=30)
    data = r.json()
    trades = data.get("trades", {})
    columns = trades.get("columns", [])
    rows = trades.get("data", [])
    print(f"  Колонки: {columns}")
    print(f"  Всего trades: {len(rows)}")
    if rows:
        print(f"  Первая: {rows[0][0] if len(rows[0]) > 0 else '?'}")
        print(f"  Последняя: {rows[-1][0] if len(rows[-1]) > 0 else '?'}")
        print("  Последние 5:")
        for row in rows[-5:]:
            print(f"    {row}")


def test_5_stability():
    print("\n=== Тест 5: Стабильность ISS (3 запроса) ===")
    url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities/CNYRUBF/candles.json"
    params = {
        "interval": 1,
        "from": "2026-10-14",
        "till": "2026-10-14",
        "iss.meta": "off",
    }
    for i in range(3):
        t0 = time.time()
        r = requests.get(url, params=params, timeout=30)
        elapsed = time.time() - t0
        data = r.json()
        rows = data.get("candles", {}).get("data", [])
        last = rows[-1][0] if rows else "нет данных"
        print(
            f"  Запрос {i+1}: {len(rows)} свечей, последняя {last}, за {elapsed:.2f} сек"
        )
        time.sleep(3)


def main():
    print("=" * 60)
    print("Диагностика лага MOEX ISS")
    print("=" * 60)

    test_1_current()
    test_2_today_range()
    test_3_direct_candles()
    test_4_direct_trades()
    test_5_stability()

    print("\n" + "=" * 60)
    print("Готово.")
    print("=" * 60)


if __name__ == "__main__":
    main()
