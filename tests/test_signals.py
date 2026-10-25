"""Тесты на detect_bounce, detect_breakout, detect_trend_level."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime, timedelta
from core.models import AnalysisResult, IndicatorSnapshot, Level, Signal
from strategy.signals import (
    detect_bounce,
    detect_breakout,
    detect_trend_level,
    _is_rejection_candle,
    _is_engulfing,
    _has_volume_confirmation,
    _compute_strength,
)

PASSED = 0
FAILED = 0


def check(name, actual, expected):
    global PASSED, FAILED
    # Приводим numpy-типы к Python
    if hasattr(actual, "item"):
        actual = actual.item()
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: expected {expected!r}, got {actual!r}")


def make_candles(rows):
    """rows — список (open, high, low, close, volume)."""
    base = datetime(2026, 10, 23, 10, 0)
    return pd.DataFrame(
        [
            {
                "begin": base + timedelta(minutes=15 * i),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            }
            for i, (o, h, l, c, v) in enumerate(rows)
        ]
    )


def make_result(
    levels,
    trend="down",
    adx=30.0,
    rsi=50.0,
    day_trend="bearish",
    current_price=12.500,
):
    ind = IndicatorSnapshot(
        ema_fast=12.5,
        ema_slow=12.6,
        rsi=rsi,
        adx=adx,
        trend=trend,
        adx_state="strong",
        rsi_state="neutral",
        day_trend=day_trend,
        structure="bearish",
        price_direction="down",
        vote_sum=-3,
    )
    return AnalysisResult(
        symbol="CNYRUBF",
        timestamp=datetime(2026, 10, 23, 10, 0),
        current_price=current_price,
        atr=0.030,
        timeframe="M15",
        indicators=ind,
        levels=levels,
        references=[],
        signals=[],
    )


def main():
    print("=" * 60)
    print("Тесты: signals.py")
    print("=" * 60)

    # --- _is_rejection_candle ---
    print("\n_is_rejection_candle:")
    # lower_shadow = 0.05, body = 0.01, total_range = 0.08
    row_long = pd.Series({"open": 12.50, "high": 12.52, "low": 12.44, "close": 12.49})
    check("long rejection", _is_rejection_candle(row_long, "long"), True)
    check("long не rejection", _is_rejection_candle(row_long, "short"), False)

    # short rejection: upper_shadow большой
    row_short = pd.Series({"open": 12.49, "high": 12.58, "low": 12.48, "close": 12.50})
    check("short rejection", _is_rejection_candle(row_short, "short"), True)

    # --- _is_engulfing ---
    print("\n_is_engulfing:")
    df = make_candles(
        [
            (12.50, 12.51, 12.49, 12.49, 100),  # prev red
            (12.48, 12.53, 12.47, 12.52, 200),  # cur green, engulfs
        ]
    )
    check("long engulfing", _is_engulfing(df, "long"), True)

    df_short = make_candles(
        [
            (12.49, 12.52, 12.48, 12.52, 100),  # prev green
            (12.53, 12.55, 12.47, 12.47, 200),  # cur red, engulfs
        ]
    )
    check("short engulfing", _is_engulfing(df_short, "short"), True)

    # --- _has_volume_confirmation ---
    print("\n_has_volume_confirmation:")
    volumes = [100] * 20 + [200]  # последняя в 2 раза больше
    df_vol = make_candles([(12.5, 12.5, 12.5, 12.5, v) for v in volumes])
    check("объём выше", _has_volume_confirmation(df_vol), True)
    volumes_low = [100] * 21
    df_vol_low = make_candles([(12.5, 12.5, 12.5, 12.5, v) for v in volumes_low])
    check("объём не выше", _has_volume_confirmation(df_vol_low), False)

    # --- _compute_strength ---
    print("\n_compute_strength:")
    score, strength = _compute_strength(["A1"])
    check("A1 → score 1, weak", (score, strength), (1.0, "weak"))
    score, strength = _compute_strength(["A1", "A2"])
    check("A1,A2 → score 2, medium", (score, strength), (2.0, "medium"))
    score, strength = _compute_strength(["A1", "A2", "D3"])
    check("A1,A2,D3 → score 3, strong", (score, strength), (3.0, "strong"))
    score, strength = _compute_strength(["A1", "A2", "A3"])
    check("A1,A2,A3 без D → score 3, medium", (score, strength), (3.0, "medium"))
    score, strength = _compute_strength(["B2"])
    check("только B2 → score 0, none", (score, strength), (0.0, "none"))

    # --- detect_breakout ---
    print("\ndetect_breakout:")
    level = Level(price=12.500, type="down", weight=5)
    df_break = make_candles(
        [
            (12.52, 12.53, 12.51, 12.52, 100),
            (12.48, 12.52, 12.47, 12.48, 200),
        ]
    )
    result = make_result([level], trend="down", adx=30.0, current_price=12.480)
    signals = detect_breakout(result, df_break)
    check("breakout short найден", len(signals), 1)
    level = Level(price=12.500, type="down", weight=5)
    df_break = make_candles(
        [
            (12.52, 12.53, 12.51, 12.52, 100),  # prev close > level
            (12.48, 12.52, 12.47, 12.48, 200),  # cur close < level - buffer
        ]
    )
    # price=12.480 < level=12.500
    result = make_result([level], trend="down", adx=30.0, current_price=12.480)
    signals = detect_breakout(result, df_break)
    check("breakout short найден", len(signals), 1)

    if signals:
        check("direction short", signals[0].direction, "short")
        check("kind breakout", signals[0].kind, "breakout")
        check("criteria A1", "A1" in signals[0].matched_criteria, True)

    # --- detect_bounce ---
    print("\ndetect_bounce:")
    level = Level(price=12.515, type="down", weight=5)
    df_bounce = make_candles(
        [
            (12.52, 12.53, 12.51, 12.52, 100),
            (12.51, 12.54, 12.49, 12.51, 200),
        ]
    )
    # price=12.510 < level=12.515 → short
    result = make_result([level], trend="down", adx=30.0, current_price=12.510)
    signals = detect_bounce(result, df_bounce)
    check("bounce short найден", len(signals), 1)

    if signals:
        check("direction short", signals[0].direction, "short")

    # --- detect_trend_level ---
    print("\ndetect_trend_level:")
    level = Level(price=12.510, type="down", weight=5)
    df_tl = make_candles(
        [
            (12.51, 12.52, 12.49, 12.50, 100),
            (12.50, 12.54, 12.49, 12.50, 200),
        ]
    )
    # price=12.500 < level=12.510 → short
    result = make_result([level], trend="down", adx=30.0, current_price=12.500)
    signals = detect_trend_level(result, df_tl)
    check("trend_level short найден", len(signals), 1)

    if signals:
        check("direction short", signals[0].direction, "short")
        check("criteria A3", "A3" in signals[0].matched_criteria, True)

    # --- detect_trend_level при transition ---
    print("\ndetect_trend_level при transition:")
    result = make_result([level], trend="transition", adx=15.0)
    signals = detect_trend_level(result, df_tl)
    check("transition → 0 сигналов", len(signals), 0)

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
