import sqlite3
from collections import defaultdict

conn = sqlite3.connect("storage/journal.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT kind, adx_at_open, result, result_points, result_rub "
    "FROM paper_trades WHERE result IN ('win','loss','timeout')"
).fetchall()


def adx_bucket(adx):
    if adx is None:
        return "unknown"
    if adx < 20:
        return "flat (<20)"
    if adx < 25:
        return "trend (20-25)"
    return "strong (>25)"


stats = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "t": 0, "pts": 0.0, "rub": 0.0})
for r in rows:
    key = (r["kind"], adx_bucket(r["adx_at_open"]))
    s = stats[key]
    s["n"] += 1
    if r["result"] == "win":
        s["w"] += 1
    elif r["result"] == "loss":
        s["l"] += 1
    elif r["result"] == "timeout":
        s["t"] += 1
    s["pts"] += r["result_points"] or 0
    s["rub"] += r["result_rub"] or 0

print(
    f"{'kind':12} {'ADX':14} {'n':>3} {'W':>3} {'L':>3} {'T':>3} {'pts':>8} {'rub':>9}"
)
print("-" * 62)
for (kind, bucket), s in sorted(stats.items()):
    print(
        f"{kind:12} {bucket:14} {s['n']:>3} {s['w']:>3} {s['l']:>3} {s['t']:>3} "
        f"{s['pts']:>+8.1f} {s['rub']:>+9.2f}"
    )
