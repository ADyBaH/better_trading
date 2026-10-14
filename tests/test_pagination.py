"""Проверка пагинации: сколько свечей за день, где последняя."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.api_moex import get_candles_range
import config


def main():
    day = "2026-10-14"
    print("=" * 60)
    print(f"Проверка пагинации ISS за {day}")
    print("=" * 60)

    df = get_candles_range(config.SYMBOL, config.BASE_INTERVAL, day, day)

    if df.empty:
        print("❌ Нет данных")
        return

    print(f"Всего свечей: {len(df)}")
    print(f"Первая:  {df['begin'].iloc[0]}")
    print(f"Последняя: {df['begin'].iloc[-1]}")
    print()
    print("Последние 10 свечей:")
    print(df[["begin", "close"]].tail(10).to_string(index=False))


if __name__ == "__main__":
    main()