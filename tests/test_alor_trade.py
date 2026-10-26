"""Тесты на data/api_alor_trade.py (мок-режим)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.api_alor_trade import place_order, cancel_order, get_orders

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


def main():
    print("=" * 60)
    print("Тест: ALOR Trade API (мок-режим)")
    print("=" * 60)

    # place_order
    print("\nplace_order:")
    result = place_order("CNYRUBF", "buy", 1)
    check("status = mock", result["status"], "mock")
    check("symbol = CNYRUBF", result["symbol"], "CNYRUBF")
    check("side = buy", result["side"], "buy")
    check("quantity = 1", result["quantity"], 1)
    check("order_id начинается с mock-", result["order_id"].startswith("mock-"), True)

    # place_order с limit
    print("\nplace_order (limit):")
    result = place_order("CNYRUBF", "sell", 1, order_type="limit", price=12.500)
    check("status = mock", result["status"], "mock")
    check("price = 12.500", result["price"], 12.500)

    # cancel_order
    print("\ncancel_order:")
    ok = cancel_order("mock-123")
    check("cancel = True", ok, True)

    # get_orders
    print("\nget_orders:")
    orders = get_orders()
    check("пустой список", orders, [])

    # Сводка
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
