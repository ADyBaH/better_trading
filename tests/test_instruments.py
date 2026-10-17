"""Проверка core.instruments.compute_trade_result.

Запуск: python tests/test_instruments.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.instruments import get_instrument, compute_trade_result

PASSED = 0
FAILED = 0


def check(name: str, actual, expected):
    """Сравнивает actual с expected. Печатает ✅ / ❌."""
    global PASSED, FAILED
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}")
        print(f"     expected: {expected!r}")
        print(f"     actual:   {actual!r}")


def check_raises(name: str, fn, exc_type):
    """Проверяет, что fn() бросает exc_type."""
    global PASSED, FAILED
    try:
        fn()
    except exc_type:
        PASSED += 1
        print(f"  ✅ {name} (бросил {exc_type.__name__})")
    except Exception as e:
        FAILED += 1
        print(f"  ❌ {name}: бросил {type(e).__name__}, ожидался {exc_type.__name__}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: не бросил {exc_type.__name__}")


def main():
    print("=" * 60)
    print("Проверка compute_trade_result (CNYRUBF)")
    print("=" * 60)

    inst = get_instrument("CNYRUBF")
    print(f"Инструмент: {inst.symbol}")
    print(f"  price_step:        {inst.price_step}")
    print(f"  step_cost:         {inst.step_cost}")
    print(f"  commission_round:  {inst.commission_round}")
    print()

    # --- Long win: 12.500 → 12.530 = +30 пунктов ---
    print("Long win (12.500 → 12.530):")
    points, rub = compute_trade_result(inst, "long", 12.500, 12.530)
    check("points = +30", points, 30.0)
    check("rub = 27.94 (30 − 2.06)", rub, 27.94)
    print()

    # --- Long loss: 12.500 → 12.470 = −30 пунктов ---
    print("Long loss (12.500 → 12.470):")
    points, rub = compute_trade_result(inst, "long", 12.500, 12.470)
    check("points = −30", points, -30.0)
    check("rub = −32.06 (−30 − 2.06)", rub, -32.06)
    print()

    # --- Short win: 12.530 → 12.500 ---
    print("Short win (12.530 → 12.500):")
    points, rub = compute_trade_result(inst, "short", 12.530, 12.500)
    check("points = +30", points, 30.0)
    check("rub = 27.94", rub, 27.94)
    print()

    # --- Short loss: 12.500 → 12.530 ---
    print("Short loss (12.500 → 12.530):")
    points, rub = compute_trade_result(inst, "short", 12.500, 12.530)
    check("points = −30", points, -30.0)
    check("rub = −32.06", rub, -32.06)
    print()

    # --- Size = 2: points те же, rub × 2, комиссия × 2 ---
    print("Size = 2 (long win 12.500 → 12.530):")
    points, rub = compute_trade_result(inst, "long", 12.500, 12.530, size=2)
    check("points = +30 (не зависит от size)", points, 30.0)
    check("rub = 55.88 (60 − 4.12)", rub, 55.88)
    print()

    # --- Override комиссии: 1.5₽ вместо 2.06₽ ---
    print("Override commission_round = 1.5:")
    points, rub = compute_trade_result(
        inst, "long", 12.500, 12.530, commission_round=1.5
    )
    check("rub = 28.5 (30 − 1.5)", rub, 28.5)
    print()

    # --- Невалидное направление ---
    print("Невалидное направление 'sideways':")
    check_raises(
        "ValueError на direction='sideways'",
        lambda: compute_trade_result(inst, "sideways", 12.500, 12.530),
        ValueError,
    )
    print()

    # --- Сводка ---
    print("=" * 60)
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
