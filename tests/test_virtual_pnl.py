"""Проверка trader.paper.virtual_pnl.

Запуск: python tests/test_virtual_pnl.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from trader.paper import virtual_pnl

PASSED = 0
FAILED = 0


def check(name: str, actual, expected):
    global PASSED, FAILED
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}")
        print(f"     expected: {expected!r}")
        print(f"     actual:   {actual!r}")


def make_candles(rows):
    """
    rows — список (high, low, close). open/begin/volume не важны для virtual_pnl.
    """
    return pd.DataFrame(
        [
            {"open": (h + l) / 2, "high": h, "low": l, "close": c, "volume": 100}
            for h, l, c in rows
        ]
    )


def main():
    print("=" * 60)
    print("Проверка virtual_pnl")
    print("=" * 60)

    # --- Long win ---
    print("\nLong win (entry=12.500, stop=12.470, take=12.530):")
    df = make_candles(
        [
            (12.510, 12.500, 12.505),
            (12.535, 12.510, 12.530),  # high >= take → win
        ]
    )
    r = virtual_pnl(df, "long", 12.500, 12.470, 12.530)
    check("result = win", r["result"], "win")
    check("exit_price = take", r["exit_price"], 12.530)
    check("bars = 2", r["bars"], 2)
    check("ambiguous = False", r["ambiguous"], False)

    # --- Long loss ---
    print("\nLong loss:")
    df = make_candles(
        [
            (12.510, 12.500, 12.505),
            (12.510, 12.465, 12.470),  # low <= stop → loss
        ]
    )
    r = virtual_pnl(df, "long", 12.500, 12.470, 12.530)
    check("result = loss", r["result"], "loss")
    check("exit_price = stop", r["exit_price"], 12.470)
    check("bars = 2", r["bars"], 2)

    # --- Short win ---
    print("\nShort win (entry=12.530, stop=12.560, take=12.500):")
    df = make_candles(
        [
            (12.535, 12.525, 12.530),
            (12.530, 12.495, 12.500),  # low <= take → win
        ]
    )
    r = virtual_pnl(df, "short", 12.530, 12.560, 12.500)
    check("result = win", r["result"], "win")
    check("exit_price = take", r["exit_price"], 12.500)

    # --- Short loss ---
    print("\nShort loss:")
    df = make_candles(
        [
            (12.535, 12.525, 12.530),
            (12.565, 12.530, 12.560),  # high >= stop → loss
        ]
    )
    r = virtual_pnl(df, "short", 12.530, 12.560, 12.500)
    check("result = loss", r["result"], "loss")
    check("exit_price = stop", r["exit_price"], 12.560)

    # --- Ambiguous (оба в одной свече) ---
    print("\nAmbiguous (одна свеча: и high >= take, и low <= stop):")
    df = make_candles(
        [
            (12.540, 12.460, 12.500),  # и take (12.530), и stop (12.470) задеты
        ]
    )
    r = virtual_pnl(df, "long", 12.500, 12.470, 12.530)
    check("result = loss (консервативно)", r["result"], "loss")
    check("ambiguous = True", r["ambiguous"], True)

    # --- Timeout ---
    print("\nTimeout (max_bars=3, ни stop, ни take):")
    df = make_candles(
        [
            (12.510, 12.490, 12.500),
            (12.515, 12.495, 12.505),
            (12.520, 12.500, 12.510),
        ]
    )
    r = virtual_pnl(df, "long", 12.500, 12.470, 12.530, max_bars=3)
    check("result = timeout", r["result"], "timeout")
    check("exit_price = close последней", r["exit_price"], 12.510)
    check("bars = 3", r["bars"], 3)

    # --- Open (свечей меньше max_bars, ничего не задето) ---
    print("\nOpen (2 свечи, max_bars=10, ничего не задето):")
    df = make_candles(
        [
            (12.510, 12.490, 12.500),
            (12.515, 12.495, 12.505),
        ]
    )
    r = virtual_pnl(df, "long", 12.500, 12.470, 12.530, max_bars=10)
    check("result = open", r["result"], "open")
    check("exit_price = None", r["exit_price"], None)
    check("bars = 2 (сколько было)", r["bars"], 2)

    # --- No data ---
    print("\nNo data (пустой DataFrame):")
    r = virtual_pnl(pd.DataFrame(), "long", 12.500, 12.470, 12.530)
    check("result = no_data", r["result"], "no_data")

    # --- Сводка ---
    print("\n" + "=" * 60)
    total = PASSED + FAILED
    print(f"Прoйдено: {PASSED} / {total}")
    if FAILED:
        print(f"❌ Провалено: {FAILED}")
        sys.exit(1)
    else:
        print("✅ Все проверки пройдены")
        sys.exit(0)


if __name__ == "__main__":
    main()
