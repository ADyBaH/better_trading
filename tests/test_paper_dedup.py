"""Проверка _is_duplicate и save_signal_as_paper.

Запуск: python tests/test_paper_dedup.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from trader.paper import (
    init_paper_table,
    _is_duplicate,
    save_signal_as_paper,
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
        warnings=["тестовое предупреждение"],
        context={"test": True},
    )


def make_result(signals, timestamp, symbol="CNYRUBF", atr=0.025):
    """Простой мок AnalysisResult — только нужные поля."""

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


def main():
    print("=" * 60)
    print("Проверка дедупликации и save_signal_as_paper")
    print("=" * 60)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_paper_table(conn)

    # --- 1. Первый сигнал создаётся ---
    print("\nПервый сигнал (10:00, long bounce @ 12.500):")
    ts1 = datetime(2026, 10, 17, 10, 0)
    sig1 = make_signal("long", "bounce", 12.500)
    r1 = make_result([sig1], ts1)
    created = save_signal_as_paper(conn, [sig1], r1, source_analysis_path="test1.json")
    check("создано 1", created, 1)
    count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    check("в БД 1 запись", count, 1)

    # --- 2. Тот же сигнал через 5 минут (эхо) — дубль ---
    print("\nТот же сигнал через 5 мин (10:05):")
    ts2 = datetime(2026, 10, 17, 10, 5)
    sig2 = make_signal("long", "bounce", 12.500)
    r2 = make_result([sig2], ts2)
    created = save_signal_as_paper(conn, [sig2], r2, source_analysis_path="test2.json")
    check("создано 0 (дубль по времени)", created, 0)
    count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    check("в БД всё ещё 1", count, 1)

    # --- 3. Тот же сигнал через 20 минут, цена та же — дубль по цене ---
    print("\nТот же сигнал через 20 мин (10:20):")
    ts3 = datetime(2026, 10, 17, 10, 20)
    sig3 = make_signal("long", "bounce", 12.500)
    r3 = make_result([sig3], ts3)
    created = save_signal_as_paper(conn, [sig3], r3, source_analysis_path="test3.json")
    check("создано 0 (дубль по цене)", created, 0)

    # --- 4. Через 20 минут, цена далеко (+0.05) — новый сигнал ---
    print("\nЧерез 20 мин, цена 12.550 (+0.05):")
    ts4 = datetime(2026, 10, 17, 10, 25)
    sig4 = make_signal("long", "bounce", 12.550)
    r4 = make_result([sig4], ts4)
    created = save_signal_as_paper(conn, [sig4], r4, source_analysis_path="test4.json")
    check("создано 1 (цена далеко)", created, 1)
    count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    check("в БД 2 записи", count, 2)

    # --- 5. Вне PAPER_TRADING_HOURS (03:00) — не создаётся ---
    print("\nВне PAPER_TRADING_HOURS (03:00):")
    ts5 = datetime(2026, 10, 17, 3, 0)
    sig5 = make_signal("long", "bounce", 12.600)
    r5 = make_result([sig5], ts5)
    created = save_signal_as_paper(conn, [sig5], r5, source_analysis_path="test5.json")
    check("создано 0 (вне часов)", created, 0)
    count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    check("в БД всё ещё 2", count, 2)

    # --- 6. Другое направление — не дубль ---
    print("\nShort bounce @ 12.500 (другое направление):")
    ts6 = datetime(2026, 10, 17, 10, 30)
    sig6 = make_signal("short", "bounce", 12.500)
    r6 = make_result([sig6], ts6)
    created = save_signal_as_paper(conn, [sig6], r6, source_analysis_path="test6.json")
    check("создано 1 (другое направление)", created, 1)
    count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    check("в БД 3 записи", count, 3)

    # --- 7. Другой kind — не дубль ---
    print("\nLong breakout @ 12.500 (другой kind):")
    ts7 = datetime(2026, 10, 17, 10, 35)
    sig7 = make_signal("long", "breakout", 12.500)
    r7 = make_result([sig7], ts7)
    created = save_signal_as_paper(conn, [sig7], r7, source_analysis_path="test7.json")
    check("создано 1 (другой kind)", created, 1)
    count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    check("в БД 4 записи", count, 4)

    # --- 8. После закрытия дубль разрешён ---
    print("\nПосле закрытия старой сделки — новая создаётся:")
    conn.execute("UPDATE paper_trades SET result = 'win' WHERE id = 1")
    conn.commit()
    ts8 = datetime(2026, 10, 17, 10, 40)
    sig8 = make_signal("long", "bounce", 12.500)
    r8 = make_result([sig8], ts8)
    created = save_signal_as_paper(conn, [sig8], r8, source_analysis_path="test8.json")
    check("создано 1 (старая закрыта)", created, 1)

    # --- 9. _is_duplicate напрямую ---
    print("\n_is_duplicate напрямую:")
    dup = _is_duplicate(conn, sig8, "CNYRUBF", atr=0.025, now=ts8)
    check("только что созданный — дубль", dup, True)

    # --- 10. context и warnings сохраняются как JSON ---
    print("\nСохранение context/warnings как JSON:")
    row = conn.execute(
        "SELECT warnings, context FROM paper_trades WHERE id = 2"
    ).fetchone()
    import json

    w = json.loads(row["warnings"])
    c = json.loads(row["context"])
    check("warnings — список", isinstance(w, list), True)
    check("warnings содержит строку", w[0], "тестовое предупреждение")
    check("context — dict", isinstance(c, dict), True)
    check("context['test'] = True", c["test"], True)

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
