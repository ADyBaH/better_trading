"""Закрывает все open paper-трейды (expired)."""

import sqlite3
from datetime import datetime
from pathlib import Path

db_path = Path("storage/journal.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id FROM paper_trades WHERE result = 'open'").fetchall()
if not rows:
    print("Нет открытых сделок.")
    conn.close()
    raise SystemExit(0)

now = datetime.now().isoformat()
for r in rows:
    conn.execute(
        "UPDATE paper_trades SET result = 'expired', closed_at = ? WHERE id = ?",
        (now, r["id"]),
    )
conn.commit()
print(f"Закрыто (expired): {len(rows)}")
for r in rows:
    print(f"  id={r['id']}")
conn.close()
