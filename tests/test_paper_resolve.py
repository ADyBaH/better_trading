"""Проверка resolve_open_trades.

Запуск: python tests/test_paper_resolve.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from trader.paper import (
    init_paper_table,
    save_signal_as_paper,
    resolve_open_trades,
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
        matched_criteria=["A1"],
        reasons=[],
        level_price=None,
        warnings=[],
        context={},
    )


def make_result(signals, timestamp, symbol="CNYRUBF", atr=0.025):
    class MockIndicator:
        trend = "up"
        adx = 25.0
        day_trend = "bullish"
        structure = "bullish"

    class MockResult:
        pass

    r = MockResult()
    r.symbol = symbol
    r.atr = atr
    r.timestamp = timestamp
    r.indicators = MockIndicator()
    r.signals = signals
    return r


def make_candles(start_time, rows):
    """
    rows — список (high, low, close).
    begin — start_time + i*15 минут.
    """
    data = []
    for i, (h, l, c) in enumerate(rows):
        data.append(
            {
                "begin": start_time + timedelta(minutes=15 * i),
                "open": (h + l) / 2,
                "high": h,
                "low": l,
                "close": c,
                "volume": 100,
            }
        )
    return pd.DataFrame(data)


def main():
    print("=" * 60)
    print("Проверка resolve_open_trades")
    print("=" * 60)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)

    ts_open = datetime(2026, 10, 17, 10, 0)

    # --- 1. Long → take ---
    print("\n1. Long → take (entry=12.500, take=12.560):")
    sig = make_signal("long", "bounce", 12.500)
    r = make_result([sig], ts_open)
    save_signal_as_paper(conn, [sig], r, source_analysis_path="t1.json")

    df = make_candles(
        ts_open + timedelta(minutes=15),
        [
            (12.510, 12.500, 12.505),  # 10:15
            (12.570, 12.510, 12.560),  # 10:30 — take
        ],
    )
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 10, 35), df_m15=df
    )
    check("закрыто 1", closed, 1)
    row = conn.execute("SELECT * FROM paper_trades WHERE id = 1").fetchone()
    check("result = win", row["result"], "win")
    check("exit_price = take", row["exit_price"], 12.560)
    check("bars_to_close = 2", row["bars_to_close"], 2)
    check("resolution = auto", row["resolution_confidence"], "auto")
    check("result_points = +60", row["result_points"], 60.0)
    check("result_rub = +57.94", row["result_rub"], 57.94)

    # --- 2. Long → stop ---
    # ВАЖНО: entry = 12.510, значит stop = 12.480, take = 12.570.
    print("\n2. Long → stop (entry=12.510, stop=12.480):")
    sig2 = make_signal("long", "bounce", 12.510)
    r2 = make_result([sig2], ts_open + timedelta(minutes=1))
    save_signal_as_paper(conn, [sig2], r2, source_analysis_path="t2.json")

    df2 = make_candles(
        ts_open + timedelta(minutes=15),
        [
            (12.505, 12.460, 12.470),  # low 12.460 <= stop 12.480 → loss по stop 12.480
        ],
    )
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 10, 30), df_m15=df2
    )
    check("закрыто 1", closed, 1)
    row = conn.execute("SELECT * FROM paper_trades WHERE id = 2").fetchone()
    check("result = loss", row["result"], "loss")
    check("exit_price = stop", row["exit_price"], 12.480)
    check("bars_to_close = 1", row["bars_to_close"], 1)
    check("result_points = -30", row["result_points"], -30.0)

    # --- 3. Short → take ---
    print("\n3. Short → take (entry=12.560, take=12.500):")
    sig3 = make_signal("short", "bounce", 12.560)
    r3 = make_result([sig3], ts_open + timedelta(minutes=2))
    save_signal_as_paper(conn, [sig3], r3, source_analysis_path="t3.json")

    df3 = make_candles(
        ts_open + timedelta(minutes=15),
        [
            (12.570, 12.490, 12.500),  # 10:15 — take
        ],
    )
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 10, 30), df_m15=df3
    )
    check("закрыто 1", closed, 1)
    row = conn.execute("SELECT * FROM paper_trades WHERE id = 3").fetchone()
    check("result = win", row["result"], "win")
    check("result_points = +60", row["result_points"], 60.0)

    # --- 4. Timeout (50 баров, ничего не задето) ---
    print("\n4. Timeout (50 баров, ни stop, ни take):")
    sig4 = make_signal("long", "bounce", 12.600)
    r4 = make_result([sig4], ts_open + timedelta(minutes=3))
    save_signal_as_paper(conn, [sig4], r4, source_analysis_path="t4.json")

    timeout_candles = [(12.610, 12.595, 12.605) for _ in range(50)]
    df4 = make_candles(ts_open + timedelta(minutes=15), timeout_candles)
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 23, 0), df_m15=df4
    )
    check("закрыто 1", closed, 1)
    row = conn.execute("SELECT * FROM paper_trades WHERE id = 4").fetchone()
    check("result = timeout", row["result"], "timeout")
    check("bars_to_close = 50", row["bars_to_close"], 50)
    # close последней = 12.605, entry = 12.600, points = +5
    check("result_points = +5", row["result_points"], 5.0)

    # --- 5. Open (мало свечей, ничего не задето) ---
    print("\n5. Open (2 свечи, ничего не задето):")
    sig5 = make_signal("long", "bounce", 12.700)
    r5 = make_result([sig5], ts_open + timedelta(minutes=4))
    save_signal_as_paper(conn, [sig5], r5, source_analysis_path="t5.json")

    df5 = make_candles(
        ts_open + timedelta(minutes=15),
        [
            (12.710, 12.695, 12.705),
            (12.715, 12.700, 12.710),
        ],
    )
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 10, 45), df_m15=df5
    )
    check("закрыто 0 (сделка открыта)", closed, 0)
    row = conn.execute("SELECT * FROM paper_trades WHERE id = 5").fetchone()
    check("result всё ещё open", row["result"], "open")

    conn.execute("UPDATE paper_trades SET result = 'expired' WHERE id = 5")
    conn.commit()
    # --- 6. Свеча открытия игнорируется ---
    # Сделка открыта ровно в 12:00. Первая свеча — тоже 12:00 (не > created_at).
    # Она задевает take, но участвовать не должна.
    print("\n6. Свеча открытия игнорируется (take в ней не считается):")
    sig6 = make_signal("long", "bounce", 12.800)
    r6 = make_result([sig6], ts_open + timedelta(hours=2))  # ровно 12:00
    save_signal_as_paper(conn, [sig6], r6, source_analysis_path="t6.json")

    df6 = make_candles(
        ts_open + timedelta(hours=2),  # 12:00
        [
            (12.870, 12.790, 12.800),  # 12:00 — take, НО это свеча открытия
            (12.810, 12.795, 12.805),  # 12:15 — ничего
            (12.815, 12.795, 12.810),  # 12:30 — ничего
        ],
    )
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 12, 45), df_m15=df6
    )
    check("закрыто 0 (take в свече открытия игнорируется)", closed, 0)

    conn.execute("UPDATE paper_trades SET result = 'expired' WHERE id = 6")
    conn.commit()

    # --- 7. Ambiguous (одна свеча: и stop, и take) ---
    print("\n7. Ambiguous (одна свеча: и stop, и take):")
    sig7 = make_signal("long", "bounce", 12.900)
    r7 = make_result([sig7], ts_open + timedelta(hours=3))  # 13:00
    max_id_before = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM paper_trades"
    ).fetchone()[0]
    save_signal_as_paper(conn, [sig7], r7, source_analysis_path="t7.json")
    row_id = conn.execute(
        "SELECT id FROM paper_trades WHERE id > ? ORDER BY id LIMIT 1", (max_id_before,)
    ).fetchone()["id"]

    df7 = make_candles(
        ts_open + timedelta(hours=3, minutes=15),  # 13:15
        [
            (12.970, 12.870, 12.900),  # и take (12.960), и stop (12.870)
        ],
    )
    closed = resolve_open_trades(
        conn, "CNYRUBF", datetime(2026, 10, 17, 13, 30), df_m15=df7
    )
    check("закрыто 1", closed, 1)
    row = conn.execute("SELECT * FROM paper_trades WHERE id = ?", (row_id,)).fetchone()
    check("result = loss (консервативно)", row["result"], "loss")
    check("resolution = auto_ambiguous", row["resolution_confidence"], "auto_ambiguous")

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
