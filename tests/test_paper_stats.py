"""Проверка paper_stats.

Запуск: python tests/test_paper_stats.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from trader.paper import init_paper_table, paper_stats

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


def insert_trade(
    conn,
    signal_id,
    direction="long",
    kind="bounce",
    score=2.0,
    trend="up",
    day_trend="bullish",
    result="win",
    points=30.0,
    rub=27.94,
    created_at="2026-10-17T10:00:00",
):
    conn.execute(
        """
        INSERT INTO paper_trades (
            signal_id, symbol, direction, kind, strength, strength_score,
            entry_price, stop_price, take_price,
            trend_at_open, day_trend_at_open, structure_at_open,
            created_at, result, result_points, result_rub
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            "CNYRUBF",
            direction,
            kind,
            "medium",
            score,
            12.500,
            12.470,
            12.560,
            trend,
            day_trend,
            "bullish",
            created_at,
            result,
            points,
            rub,
        ),
    )


def main():
    print("=" * 60)
    print("Проверка paper_stats")
    print("=" * 60)

    # --- 1. Пустая БД ---
    print("\n1. Пустая БД:")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)
    s = paper_stats(conn)
    check("total = 0", s["total"], 0)
    check("winrate = None", s["winrate"], None)
    check("total_points = 0", s["total_points"], 0.0)

    # --- 2. Три сделки: win, loss, open ---
    print("\n2. win + loss + open:")
    insert_trade(conn, "s1", result="win", points=30.0, rub=27.94)
    insert_trade(conn, "s2", result="loss", points=-20.0, rub=-22.06)
    insert_trade(conn, "s3", result="open", points=None, rub=None)
    conn.commit()
    s = paper_stats(conn)
    check("total = 3", s["total"], 3)
    check("open = 1", s["open"], 1)
    check("win = 1", s["win"], 1)
    check("loss = 1", s["loss"], 1)
    check("winrate = 50.0", s["winrate"], 50.0)
    check("total_points = +10.0", s["total_points"], 10.0)
    check("total_rub = +5.88", s["total_rub"], 5.88)
    check("avg_win = 30.0", s["avg_win_points"], 30.0)
    check("avg_loss = -20.0", s["avg_loss_points"], -20.0)

    # --- 3. Winrate без timeout ---
    print("\n3. winrate не считает timeout:")
    conn2 = sqlite3.connect(":memory:")
    conn2.row_factory = sqlite3.Row
    init_paper_table(conn2)
    insert_trade(conn2, "t1", result="win", points=30.0, rub=27.94)
    insert_trade(conn2, "t2", result="loss", points=-20.0, rub=-22.06)
    insert_trade(conn2, "t3", result="timeout", points=5.0, rub=2.94)
    conn2.commit()
    s = paper_stats(conn2)
    check("total = 3", s["total"], 3)
    check("winrate = 50.0 (timeout не в счёт)", s["winrate"], 50.0)
    check("timeout = 1", s["timeout"], 1)
    check("total_points = +15.0", s["total_points"], 15.0)

    # --- 4. by_kind ---
    print("\n4. by_kind:")
    conn3 = sqlite3.connect(":memory:")
    conn3.row_factory = sqlite3.Row
    init_paper_table(conn3)
    insert_trade(conn3, "k1", kind="breakout", result="win", points=30.0, rub=27.94)
    insert_trade(conn3, "k2", kind="breakout", result="win", points=40.0, rub=37.94)
    insert_trade(conn3, "k3", kind="breakout", result="loss", points=-20.0, rub=-22.06)
    insert_trade(
        conn3, "k4", kind="trend_level", result="loss", points=-15.0, rub=-17.06
    )
    conn3.commit()
    s = paper_stats(conn3)
    check("by_kind['breakout'].total = 3", s["by_kind"]["breakout"]["total"], 3)
    check("by_kind['breakout'].win = 2", s["by_kind"]["breakout"]["win"], 2)
    check("by_kind['breakout'].loss = 1", s["by_kind"]["breakout"]["loss"], 1)
    check(
        "by_kind['breakout'].points = +50.0", s["by_kind"]["breakout"]["points"], 50.0
    )
    check("by_kind['trend_level'].total = 1", s["by_kind"]["trend_level"]["total"], 1)
    check("by_kind['trend_level'].loss = 1", s["by_kind"]["trend_level"]["loss"], 1)

    # --- 5. by_score ---
    print("\n5. by_score (бакеты):")
    conn4 = sqlite3.connect(":memory:")
    conn4.row_factory = sqlite3.Row
    init_paper_table(conn4)
    insert_trade(conn4, "sc1", score=1.0, result="win", points=10.0, rub=7.94)
    insert_trade(conn4, "sc2", score=1.5, result="loss", points=-10.0, rub=-12.06)
    insert_trade(conn4, "sc3", score=2.0, result="win", points=20.0, rub=17.94)
    insert_trade(conn4, "sc4", score=2.5, result="win", points=25.0, rub=22.94)
    insert_trade(conn4, "sc5", score=3.0, result="loss", points=-30.0, rub=-32.06)
    insert_trade(conn4, "sc6", score=3.5, result="win", points=35.0, rub=32.94)
    conn4.commit()
    s = paper_stats(conn4)
    check("by_score['1.0'].total = 1", s["by_score"]["1.0"]["total"], 1)
    check("by_score['1.5'].total = 1", s["by_score"]["1.5"]["total"], 1)
    check("by_score['2.0'].total = 1", s["by_score"]["2.0"]["total"], 1)
    check("by_score['2.5'].total = 1", s["by_score"]["2.5"]["total"], 1)
    check("by_score['3.0+'].total = 2", s["by_score"]["3.0+"]["total"], 2)

    # --- 6. Фильтр по symbol ---
    print("\n6. Фильтр по symbol:")
    conn5 = sqlite3.connect(":memory:")
    conn5.row_factory = sqlite3.Row
    init_paper_table(conn5)
    insert_trade(conn5, "sym1", result="win")
    conn5.execute(
        "INSERT INTO paper_trades (signal_id, symbol, direction, kind, entry_price, stop_price, take_price, created_at, result, result_points, result_rub) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sym2",
            "SBER",
            "long",
            "bounce",
            100.0,
            99.0,
            102.0,
            "2026-10-17T10:00:00",
            "win",
            20.0,
            18.0,
        ),
    )
    conn5.commit()
    s_all = paper_stats(conn5)
    s_cny = paper_stats(conn5, symbol="CNYRUBF")
    check("без фильтра total = 2", s_all["total"], 2)
    check("symbol=CNYRUBF total = 1", s_cny["total"], 1)

    # --- 7. Фильтр по since ---
    print("\n7. Фильтр по since:")
    conn6 = sqlite3.connect(":memory:")
    conn6.row_factory = sqlite3.Row
    init_paper_table(conn6)
    insert_trade(conn6, "d1", created_at="2026-10-16T10:00:00", result="win")
    insert_trade(conn6, "d2", created_at="2026-10-17T10:00:00", result="win")
    conn6.commit()
    s = paper_stats(conn6, since="2026-10-17")
    check("since=2026-10-17 total = 1", s["total"], 1)

    conn.close()
    conn2.close()
    conn3.close()
    conn4.close()
    conn5.close()
    conn6.close()

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
