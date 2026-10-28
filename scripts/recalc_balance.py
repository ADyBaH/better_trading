"""Пересчитывает balance_after для всех закрытых win/loss по порядку id."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import config

conn = sqlite3.connect("storage/journal.db")
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, result, result_rub FROM paper_trades "
    "WHERE result IN ('win', 'loss') ORDER BY id"
).fetchall()

balance = config.VIRTUAL_DEPOSIT
print(f"Старт: {balance:.2f} ₽\n")
for r in rows:
    rub = r["result_rub"] or 0
    balance = round(balance + rub, 2)
    conn.execute(
        "UPDATE paper_trades SET balance_after = ? WHERE id = ?",
        (balance, r["id"]),
    )
    print(f"  id={r['id']:3} {r['result']:4} rub={rub:+7.2f} → balance={balance:8.2f}")

conn.commit()
print(f"\nИтог: {balance:.2f} ₽ (PnL: {balance - config.VIRTUAL_DEPOSIT:+.2f} ₽)")
