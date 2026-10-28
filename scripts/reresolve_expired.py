"""Возвращает expired-сделки в open для повторного резолва."""

import sqlite3
from datetime import datetime

conn = sqlite3.connect("storage/journal.db")
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, symbol, created_at FROM paper_trades WHERE result = 'expired'"
).fetchall()

print(f"Найдено expired: {len(rows)}")
for r in rows:
    print(f"  id={r['id']} created={r['created_at']}")

confirm = input("Вернуть в open? [y/N]: ")
if confirm.lower() != "y":
    print("Отменено.")
    raise SystemExit(0)

for r in rows:
    conn.execute(
        "UPDATE paper_trades SET result='open', closed_at=NULL, exit_price=NULL, "
        "result_points=NULL, result_rub=NULL, bars_to_close=NULL, "
        "resolution_confidence=NULL, balance_after=NULL WHERE id=?",
        (r["id"],),
    )
conn.commit()
print(f"Возвращено в open: {len(rows)}")
print("Теперь запусти runner.py — resolve_open_trades закроет их по stop/take/timeout.")
