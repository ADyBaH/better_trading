"""Проверка целостности журнала: size, commission, result_rub.

Запуск: python tests/test_journal_integrity.py
"""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

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


def main():
    print("=" * 60)
    print("Проверка целостности journal.db")
    print("=" * 60)

    db_path = Path(config.DB_PATH).parent / "journal.db"
    print(f"БД: {db_path}")
    if not db_path.exists():
        print("❌ journal.db не найден")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # --- 1. Все закрытые сделки ---
    rows = conn.execute(
        "SELECT id, symbol, size, commission_rub, result_points, result_rub "
        "FROM trades WHERE exit_price IS NOT NULL ORDER BY id"
    ).fetchall()

    print(f"\nЗакрытых сделок: {len(rows)}")
    print(f"{'id':>3} {'size':>4} {'comm':>8} {'pts':>7} {'rub':>8}")
    for r in rows:
        print(
            f"{r['id']:>3} {r['size']:>4} {str(r['commission_rub']):>8} "
            f"{r['result_points']:>7} {r['result_rub']:>8}"
        )

    # --- 2. Сделки с size > 1 (потенциально затронуты правкой) ---
    print("\nСделки с size > 1:")
    size_gt_1 = [r for r in rows if r["size"] > 1]
    if not size_gt_1:
        check("нет сделок с size > 1", True, True)
    else:
        for r in size_gt_1:
            print(
                f"  id={r['id']} size={r['size']} "
                f"comm={r['commission_rub']} pts={r['result_points']} rub={r['result_rub']}"
            )
        # Проверим формулу: rub ≈ pts × step_cost × size − comm × size
        from core.instruments import get_instrument

        for r in size_gt_1:
            inst = get_instrument(r["symbol"])
            comm = (
                r["commission_rub"]
                if r["commission_rub"] is not None
                else inst.commission_round
            )
            expected_rub = round(
                r["result_points"] * inst.step_cost * r["size"] - comm * r["size"], 2
            )
            check(
                f"id={r['id']}: rub по новой формуле",
                r["result_rub"],
                expected_rub,
            )

    # --- 3. Сделки с commission_rub (потенциально затронуты) ---
    print("\nСделки с явным commission_rub:")
    with_comm = [r for r in rows if r["commission_rub"] is not None]
    if not with_comm:
        check("нет сделок с явным commission_rub", True, True)
    else:
        for r in with_comm:
            print(
                f"  id={r['id']} size={r['size']} comm={r['commission_rub']} rub={r['result_rub']}"
            )

    # --- 4. Сводные цифры (должны совпасть с journal_cli.py stats) ---
    print("\nСводные цифры:")
    total_pts = sum(r["result_points"] or 0 for r in rows)
    total_rub = sum(r["result_rub"] or 0 for r in rows)
    wins = sum(1 for r in rows if (r["result_points"] or 0) > 0)
    losses = sum(1 for r in rows if (r["result_points"] or 0) < 0)
    be = sum(1 for r in rows if (r["result_points"] or 0) == 0)

    print(f"  Total PnL: {total_pts:+.1f} pts / {total_rub:+.2f} ₽")
    print(f"  W/L/BE: {wins}/{losses}/{be}")

    check("Total PnL (pts) совпадает с ожиданием", round(total_pts, 1), 16.0)
    check("Total PnL (rub) совпадает с ожиданием", round(total_rub, 2), -4.60)
    check("Winrate = 50%", (wins, losses), (5, 5))

    conn.close()

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
