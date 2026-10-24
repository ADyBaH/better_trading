"""Тесты на новые группировки paper_stats: by_adx, by_session, by_hour, by_weekday."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from datetime import datetime, timedelta
from trader.paper import init_paper_table, paper_stats

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


def insert_trade(
    conn, signal_id, result, created_at, adx_at_open=None, points=0.0, rub=0.0
):
    conn.execute(
        """
        INSERT INTO paper_trades (
            signal_id, symbol, direction, kind, strength, strength_score,
            entry_price, stop_price, take_price,
            trend_at_open, adx_at_open, day_trend_at_open, structure_at_open,
            created_at, result, result_points, result_rub
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            "CNYRUBF",
            "short",
            "breakout",
            "medium",
            2.0,
            12.500,
            12.470,
            12.560,
            "down",
            adx_at_open,
            "bearish",
            "bearish",
            created_at,
            result,
            points,
            rub,
        ),
    )


def main():
    print("=" * 60)
    print("Тесты: paper_stats — by_adx, by_session, by_hour, by_weekday")
    print("=" * 60)

    # --- 1. by_adx ---
    print("\nby_adx (3 бакета):")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)

    insert_trade(
        conn, "a1", "win", "2026-10-23T10:00:00", adx_at_open=15.0, points=10, rub=8
    )
    insert_trade(
        conn, "a2", "loss", "2026-10-23T11:00:00", adx_at_open=15.0, points=-5, rub=-7
    )
    insert_trade(
        conn, "a3", "win", "2026-10-23T12:00:00", adx_at_open=22.0, points=20, rub=18
    )
    insert_trade(
        conn, "a4", "win", "2026-10-23T13:00:00", adx_at_open=30.0, points=30, rub=28
    )
    insert_trade(
        conn, "a5", "loss", "2026-10-23T14:00:00", adx_at_open=35.0, points=-10, rub=-12
    )
    insert_trade(
        conn, "a6", "win", "2026-10-23T15:00:00", adx_at_open=None, points=5, rub=3
    )
    conn.commit()

    s = paper_stats(conn)
    check("flat (<20) total", s["by_adx"]["flat (<20)"]["total"], 2)
    check("flat (<20) win", s["by_adx"]["flat (<20)"]["win"], 1)
    check("flat (<20) loss", s["by_adx"]["flat (<20)"]["loss"], 1)
    check("trend (20-25) total", s["by_adx"]["trend (20-25)"]["total"], 1)
    check("strong (>25) total", s["by_adx"]["strong (>25)"]["total"], 2)
    check("strong (>25) win", s["by_adx"]["strong (>25)"]["win"], 1)
    check("strong (>25) loss", s["by_adx"]["strong (>25)"]["loss"], 1)
    check("unknown total", s["by_adx"]["unknown"]["total"], 1)

    # --- 2. by_session ---
    print("\nby_session (4 сессии):")
    conn2 = sqlite3.connect(":memory:")
    conn2.row_factory = sqlite3.Row
    init_paper_table(conn2)

    insert_trade(conn2, "s1", "win", "2026-10-23T10:00:00", points=10, rub=8)  # morning
    insert_trade(conn2, "s2", "win", "2026-10-23T14:00:00", points=20, rub=18)  # day
    insert_trade(
        conn2, "s3", "loss", "2026-10-23T18:00:00", points=-10, rub=-12
    )  # evening
    insert_trade(conn2, "s4", "win", "2026-10-23T21:00:00", points=5, rub=3)  # night
    conn2.commit()

    s2 = paper_stats(conn2)
    check("morning total", s2["by_session"]["morning (09-12)"]["total"], 1)
    check("day total", s2["by_session"]["day (12-17)"]["total"], 1)
    check("evening total", s2["by_session"]["evening (17-20)"]["total"], 1)
    check("night total", s2["by_session"]["night (20-09)"]["total"], 1)

    # --- 3. by_hour ---
    print("\nby_hour (по часам):")
    conn3 = sqlite3.connect(":memory:")
    conn3.row_factory = sqlite3.Row
    init_paper_table(conn3)

    insert_trade(conn3, "h1", "win", "2026-10-23T09:15:00", points=10, rub=8)
    insert_trade(conn3, "h2", "win", "2026-10-23T09:45:00", points=5, rub=3)
    insert_trade(conn3, "h3", "loss", "2026-10-23T17:30:00", points=-10, rub=-12)
    conn3.commit()

    s3 = paper_stats(conn3)
    check("09:00 total", s3["by_hour"]["09:00"]["total"], 2)
    check("09:00 win", s3["by_hour"]["09:00"]["win"], 2)
    check("17:00 total", s3["by_hour"]["17:00"]["total"], 1)
    check("17:00 loss", s3["by_hour"]["17:00"]["loss"], 1)

    # --- 4. by_weekday ---
    print("\nby_weekday (по дням):")
    conn4 = sqlite3.connect(":memory:")
    conn4.row_factory = sqlite3.Row
    init_paper_table(conn4)

    # 2026-10-19 — Monday, 2026-10-20 — Tuesday, 2026-10-21 — Wednesday
    insert_trade(conn4, "w1", "win", "2026-10-19T10:00:00", points=10, rub=8)  # Mon
    insert_trade(conn4, "w2", "win", "2026-10-20T10:00:00", points=20, rub=18)  # Tue
    insert_trade(conn4, "w3", "win", "2026-10-21T10:00:00", points=30, rub=28)  # Wed
    insert_trade(conn4, "w4", "loss", "2026-10-21T14:00:00", points=-10, rub=-12)  # Wed
    conn4.commit()

    s4 = paper_stats(conn4)
    check("Mon total", s4["by_weekday"]["Mon"]["total"], 1)
    check("Tue total", s4["by_weekday"]["Tue"]["total"], 1)
    check("Wed total", s4["by_weekday"]["Wed"]["total"], 2)
    check("Wed win", s4["by_weekday"]["Wed"]["win"], 1)
    check("Wed loss", s4["by_weekday"]["Wed"]["loss"], 1)

    conn.close()
    conn2.close()
    conn3.close()
    conn4.close()

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
