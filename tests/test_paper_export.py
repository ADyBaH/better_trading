"""Тест экспорта paper_trades в CSV."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import csv
from trader.paper import init_paper_table
from trader.paper_export import export_paper_trades

PASSED = 0
FAILED = 0


def check(name, actual, expected):
    global PASSED, FAILED
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: expected {expected!r}, got {actual!r}")


def main():
    print("=" * 60)
    print("Тест: paper_export")
    print("=" * 60)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)

    # Пустая БД — 0 записей
    print("\nПустая БД:")
    tmp = Path("storage/exports/_test_empty.csv")
    count = export_paper_trades(conn, str(tmp))
    check("0 записей", count, 0)

    # Добавляем 2 сделки
    print("\n2 сделки:")
    conn.execute(
        """INSERT INTO paper_trades (
            signal_id, symbol, direction, kind, strength, strength_score,
            entry_price, stop_price, take_price, created_at, result,
            result_points, result_rub, adx_at_open
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "e1",
            "CNYRUBF",
            "short",
            "breakout",
            "medium",
            2.0,
            12.500,
            12.470,
            12.560,
            "2026-10-23T10:00:00",
            "win",
            10.0,
            8.0,
            25.5,
        ),
    )
    conn.execute(
        """INSERT INTO paper_trades (
            signal_id, symbol, direction, kind, strength, strength_score,
            entry_price, stop_price, take_price, created_at, result,
            result_points, result_rub, adx_at_open
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "e2",
            "CNYRUBF",
            "short",
            "bounce",
            "weak",
            1.5,
            12.400,
            12.430,
            12.360,
            "2026-10-23T14:00:00",
            "loss",
            -5.0,
            -7.0,
            18.0,
        ),
    )
    conn.commit()

    tmp2 = Path("storage/exports/_test_2trades.csv")
    count = export_paper_trades(conn, str(tmp2))
    check("2 записи", count, 2)
    check("файл существует", tmp2.exists(), True)

    with open(tmp2, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    check("CSV: 2 строки", len(rows), 2)
    check("CSV: колонка symbol", rows[0]["symbol"], "CNYRUBF")
    check("CSV: колонка result", rows[0]["result"], "win")
    check("CSV: колонка adx_at_open", rows[0]["adx_at_open"], "25.5")
    check("CSV: колонка result_rub", rows[0]["result_rub"], "8.0")

    # Фильтр по symbol
    print("\nФильтр по symbol:")
    tmp3 = Path("storage/exports/_test_filtered.csv")
    count = export_paper_trades(conn, str(tmp3), symbol="SBER")
    check("0 записей (SBER нет)", count, 0)

    # Удаляем временные файлы
    for p in (tmp, tmp2, tmp3):
        if p.exists():
            p.unlink()

    conn.close()

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
