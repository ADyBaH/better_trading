"""Проверка api_alor.get_candles_range (DataFrame)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from data.api_alor import get_candles_range


def main():
    print("=" * 60)
    print("Проверка api_alor.get_candles_range")
    print("=" * 60)

    end = datetime.now()
    start = end - timedelta(days=1)  # за вчера

    df = get_candles_range("CNYRUBF", "M15", start, end)

    if df.empty:
        print("❌ Пустой DataFrame")
        return

    print(f"✅ Получено {len(df)} свечей")
    print("Колонки:", list(df.columns))
    print("Тип begin:", df["begin"].dtype)
    print("\nПоследние 5 строк:")
    print(df.tail(5))

    # Проверки
    assert list(df.columns) == ["begin", "open", "high", "low", "close", "volume"]
    assert df["close"].iloc[-1] > 0
    print("\n✅ Все проверки пройдены")


if __name__ == "__main__":
    main()
