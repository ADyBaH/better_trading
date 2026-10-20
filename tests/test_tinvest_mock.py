"""Проверка мок-режима T-Invest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.api_tinvest import _mock_candles


def main():
    df = _mock_candles("M15", count=10)
    assert len(df) == 10
    assert list(df.columns) == ["begin", "open", "high", "low", "close", "volume"]
    assert str(df["begin"].dtype) in ("datetime64[ns]", "datetime64[us]")
    assert df["close"].between(12.4, 12.6).all()
    print("✅ Мок T-Invest работает")


if __name__ == "__main__":
    main()
