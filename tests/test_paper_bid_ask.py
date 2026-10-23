"""Тест: проверка записи bid_vol/ask_vol в paper_trades."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from datetime import datetime
from core.models import Signal
from trader.paper import init_paper_table, save_signal_as_paper

# Мок-сигнал
sig = Signal(
    direction="short",
    kind="bounce",
    strength="medium",
    strength_score=2.0,
    entry_price=12.150,
    stop_price=12.180,
    take_price=12.120,
    matched_criteria=["A1"],
    reasons=[],
    level_price=12.140,
    warnings=[],
    context={},
)


# Мок-результат
class MockInd:
    trend = "down"
    adx = 35.0
    day_trend = "bearish"
    structure = "bearish"


class MockResult:
    pass


r = MockResult()
r.symbol = "CNYRUBF"
r.atr = 0.025
r.timestamp = datetime.now()
r.indicators = MockInd()
r.signals = [sig]

conn = sqlite3.connect("storage/journal.db")
conn.row_factory = sqlite3.Row
init_paper_table(conn)

created = save_signal_as_paper(conn, [sig], r, bid_vol=33992, ask_vol=33399)
print(f"Создано: {created}")

row = conn.execute(
    "SELECT id, bid_vol, ask_vol FROM paper_trades ORDER BY id DESC LIMIT 1"
).fetchone()
if row:
    print(
        f"Последняя сделка: id={row['id']}, bid_vol={row['bid_vol']}, ask_vol={row['ask_vol']}"
    )
else:
    print("❌ Сделок нет")
conn.close()
