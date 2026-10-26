"""Тест get_current_price_sync (мок-режим)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.api_alor import get_current_price_sync

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
    print("Тест: get_current_price_sync")
    print("=" * 60)

    result = get_current_price_sync("CNYRUBF")

    check("есть ключ bid", "bid" in result, True)
    check("есть ключ ask", "ask" in result, True)
    check("есть ключ mid", "mid" in result, True)

    if result["bid"] is not None and result["ask"] is not None:
        check("bid < ask", result["bid"] < result["ask"], True)
        check(
            "mid ≈ (bid+ask)/2",
            result["mid"],
            round((result["bid"] + result["ask"]) / 2, 5),
        )
        print(f"  bid={result['bid']}, ask={result['ask']}, mid={result['mid']}")
    else:
        print("  ⚠️ bid/ask = None (ALOR не отвечает?)")

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
