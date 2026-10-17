"""Проверка trader.paper — базовая инфраструктура.

Запуск: python tests/test_paper.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from trader.paper import (
    init_paper_table,
    _signal_id,
    _is_in_paper_hours,
)
from core.models import Signal

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


def make_signal(direction="long", kind="bounce", entry=12.500):
    return Signal(
        direction=direction,
        kind=kind,
        strength="medium",
        strength_score=2.0,
        entry_price=entry,
        stop_price=entry - 0.03 if direction == "long" else entry + 0.03,
        take_price=entry + 0.06 if direction == "long" else entry - 0.06,
        matched_criteria=["A1", "A2"],
        reasons=[],
        level_price=entry - 0.001 if direction == "long" else entry + 0.001,
    )


def main():
    print("=" * 60)
    print("Проверка trader.paper (инфраструктура)")
    print("=" * 60)

    # --- init_paper_table ---
    print("\ninit_paper_table (in-memory):")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)
    tables = [
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]
    check("таблица paper_trades создана", "paper_trades" in tables, True)

    # Колонки
    cols = {
        r["name"] for r in conn.execute("PRAGMA table_info(paper_trades)").fetchall()
    }
    required = {
        "id",
        "signal_id",
        "source_analysis_path",
        "symbol",
        "direction",
        "kind",
        "strength",
        "strength_score",
        "entry_price",
        "stop_price",
        "take_price",
        "level_price",
        "risk_reward",
        "net_rr",
        "trend_at_open",
        "adx_at_open",
        "day_trend_at_open",
        "structure_at_open",
        "created_at",
        "closed_at",
        "exit_price",
        "result",
        "result_points",
        "result_rub",
        "bars_to_close",
        "resolution_confidence",
        "warnings",
        "context",
    }
    check("все обязательные колонки есть", required.issubset(cols), True)

    # Идемпотентность
    init_paper_table(conn)
    check("повторный вызов не падает", True, True)
    conn.close()

    # --- _signal_id ---
    print("\n_signal_id:")
    sig = make_signal(entry=12.500)
    ts = datetime(2026, 10, 17, 10, 0, 0)
    sid = _signal_id(sig, "CNYRUBF", ts)
    check("длина = 16", len(sid), 16)
    check("только hex", all(c in "0123456789abcdef" for c in sid), True)

    # Детерминизм
    sid2 = _signal_id(sig, "CNYRUBF", ts)
    check("детерминирован", sid == sid2, True)

    # Разные entry → разные id
    sig_b = make_signal(entry=12.510)
    sid_b = _signal_id(sig_b, "CNYRUBF", ts)
    check("разный entry → разный id", sid != sid_b, True)

    # Разное время → разные id
    ts_b = datetime(2026, 10, 17, 10, 15, 0)
    sid_t = _signal_id(sig, "CNYRUBF", ts_b)
    check("разное время → разный id", sid != sid_t, True)

    # --- _is_in_paper_hours ---
    print("\n_is_in_paper_hours:")
    check("10:00 — в часах", _is_in_paper_hours(datetime(2026, 10, 17, 10, 0)), True)
    check(
        "08:59 — не в часах", _is_in_paper_hours(datetime(2026, 10, 17, 8, 59)), False
    )
    check("09:00 — в часах", _is_in_paper_hours(datetime(2026, 10, 17, 9, 0)), True)
    check("17:59 — в часах", _is_in_paper_hours(datetime(2026, 10, 17, 17, 59)), True)
    check(
        "18:00 — не в часах", _is_in_paper_hours(datetime(2026, 10, 17, 18, 0)), False
    )
    check("03:00 — не в часах", _is_in_paper_hours(datetime(2026, 10, 17, 3, 0)), False)

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
