"""Тесты на indicators/calc.py: add_indicators, get_atr, get_trend_context, get_main_trend."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from indicators.calc import (
    add_indicators,
    get_atr,
    get_trend_context,
    get_main_trend,
)

PASSED = 0
FAILED = 0


def check(name, actual, expected, tolerance=None):
    global PASSED, FAILED
    if tolerance is not None and isinstance(actual, (int, float)):
        ok = abs(actual - expected) <= tolerance
    else:
        if hasattr(actual, "item"):
            actual = actual.item()
        ok = actual == expected
    if ok:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: expected {expected!r}, got {actual!r}")


def make_candles(prices):
    """prices — список close. high/low — ±0.01."""
    base = datetime(2026, 10, 23, 10, 0)
    return pd.DataFrame(
        [
            {
                "begin": base + timedelta(minutes=15 * i),
                "open": p,
                "high": p + 0.01,
                "low": p - 0.01,
                "close": p,
                "volume": 100,
            }
            for i, p in enumerate(prices)
        ]
    )


def main():
    print("=" * 60)
    print("Тесты: indicators/calc.py")
    print("=" * 60)

    # --- add_indicators ---
    print("\nadd_indicators:")

    # Зигзаг с HH/HL для structure="bullish"
    prices_bull = []
    base = 12.5
    for i in range(50):
        for j in range(5):
            prices_bull.append(base + 0.001 * j)
        base += 0.005
        for j in range(3):
            prices_bull.append(base - 0.001 * j)
        base += 0.002
    while len(prices_bull) < 250:
        prices_bull.append(prices_bull[-1] + 0.0001)
    prices_bull = prices_bull[:250]

    df = make_candles(prices_bull)
    df = add_indicators(df)

    check("колонка ema_fast", "ema_fast" in df.columns, True)
    check("колонка ema_slow", "ema_slow" in df.columns, True)
    check("колонка rsi", "rsi" in df.columns, True)
    check("колонка adx", "adx" in df.columns, True)
    check("последний ema_fast не NaN", pd.notna(df["ema_fast"].iloc[-1]), True)
    check("последний ema_slow не NaN", pd.notna(df["ema_slow"].iloc[-1]), True)
    check("последний rsi не NaN", pd.notna(df["rsi"].iloc[-1]), True)
    check("последний adx не NaN", pd.notna(df["adx"].iloc[-1]), True)

    # На монотонном росте EMA_fast > EMA_slow
    check(
        "монотонный рост: ema_fast > ema_slow",
        df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1],
        True,
    )

    # --- get_atr ---
    print("\nget_atr:")

    # ATR на монотонном росте — примерно 0.02 (high-low = 0.02)
    atr = get_atr(df, period=14)
    check("ATR не None", atr is not None, True)
    if atr is not None:
        check("ATR ≈ 0.02", atr, 0.02, tolerance=0.005)

    # Мало свечей — None
    df_short = make_candles([12.5] * 5)
    atr_short = get_atr(df_short, period=14)
    check("мало свечей → None", atr_short, None)

    # --- get_trend_context ---
    print("\nget_trend_context:")

    # Монотонный рост → day_trend = bullish
    last = df.iloc[-1]
    ctx = get_trend_context(
        df=df,
        current_price=float(last["close"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"]),
        atr=atr,
    )
    check("day_change_atr > 0", ctx["day_change_atr"] > 0, True)
    check("price_direction up", ctx["price_direction"], "up")
    check(
        "structure — валидное значение",
        ctx["structure"] in ("bullish", "bearish", "mixed"),
        True,
    )

    # Монотонное падение → day_trend = bearish
    prices_down = [12.5 - 0.001 * i for i in range(250)]
    df_down = make_candles(prices_down)
    df_down = add_indicators(df_down)
    last_down = df_down.iloc[-1]
    atr_down = get_atr(df_down, period=14)
    ctx_down = get_trend_context(
        df=df_down,
        current_price=float(last_down["close"]),
        ema_fast=float(last_down["ema_fast"]),
        ema_slow=float(last_down["ema_slow"]),
        atr=atr_down,
    )
    check("day_change_atr < 0", ctx_down["day_change_atr"] < 0, True)
    check("price_direction down", ctx_down["price_direction"], "down")

    # --- get_main_trend ---
    print("\nget_main_trend:")

    # Рост → up или strong_up
    main = get_main_trend(ctx)
    check(
        "рост → up/strong_up",
        main["trend"] in ("up", "strong_up"),
        True,
    )
    check("vote_sum > 0", main["vote_sum"] > 0, True)
    check("vote_breakdown — dict", isinstance(main["vote_breakdown"], dict), True)

    # Падение → down или strong_down
    main_down = get_main_trend(ctx_down)
    check(
        "падение → down/strong_down",
        main_down["trend"] in ("down", "strong_down"),
        True,
    )
    check("vote_sum < 0", main_down["vote_sum"] < 0, True)

    # --- Сводка ---
    print("\n" + "=" * 60)
    total = PASSED + FAILED
    print(f"Прoйдено: {PASSED} / {total}")
    if FAILED:
        sys.exit(1)
    else:
        print("✅ Все проверки пройдены")
        sys.exit(0)


if __name__ == "__main__":
    main()
