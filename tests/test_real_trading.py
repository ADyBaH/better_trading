"""Тесты на trader/real.py + core/risk.py (мок-режим)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.risk import calculate_position_size
from trader.real import open_real_trade, close_real_trade
from core.models import Signal

PASSED = 0
FAILED = 0


def check(name, actual, expected):
    global PASSED, FAILED
    if hasattr(actual, "item"):
        actual = actual.item()
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: expected {expected!r}, got {actual!r}")


def make_signal(direction="short", entry=12.500, stop=12.530, take=12.440):
    return Signal(
        direction=direction,
        kind="breakout",
        strength="medium",
        strength_score=2.0,
        entry_price=entry,
        stop_price=stop,
        take_price=take,
        matched_criteria=["A1", "B2"],
        reasons=[],
        level_price=entry,
    )


def main():
    print("=" * 60)
    print("Тест: real trading (мок-режим)")
    print("=" * 60)

    # --- calculate_position_size ---
    print("\ncalculate_position_size:")

    # risk=100₽, entry=12.500, stop=12.530, step=0.001, cost=1.0
    # stop_distance = 0.030 → stop_points = 30
    # risk_per_contract = 30 * 1.0 = 30₽
    # size = 100 / 30 = 3
    size = calculate_position_size(
        risk_rub=100.0,
        entry_price=12.500,
        stop_price=12.530,
        step_cost=1.0,
        price_step=0.001,
    )
    check("size = 3 (100₽ / 30₽)", size, 3)

    # risk=100₽, stop=0.010 → 10 pts → 10₽/contract → size = 10
    size = calculate_position_size(
        risk_rub=100.0,
        entry_price=12.500,
        stop_price=12.510,
        step_cost=1.0,
        price_step=0.001,
    )
    check("size = 10 (100₽ / 10₽)", size, 10)

    # risk=5₽ → size = 0 (не хватает на 1 контракт)
    size = calculate_position_size(
        risk_rub=5.0,
        entry_price=12.500,
        stop_price=12.530,
        step_cost=1.0,
        price_step=0.001,
    )
    check("size = 1 (минимум, 5₽ < 30₽)", size, 1)

    # --- open_real_trade ---
    print("\nopen_real_trade:")

    sig = make_signal(direction="short", entry=12.500, stop=12.530, take=12.440)
    result = open_real_trade(sig)
    check("не None", result is not None, True)
    if result:
        check("status = mock", result["status"], "mock")
        check("direction = short", result["direction"], "short")
        check("size > 0", result["size"] > 0, True)
        check(
            "trade_id начинается с real-", result["trade_id"].startswith("real-"), True
        )

    # --- close_real_trade ---
    print("\nclose_real_trade:")
    ok = close_real_trade("real-123")
    check("close = True", ok, True)

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
