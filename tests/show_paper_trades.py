"""Показать все paper-сделки.

Запуск: python tests/show_paper_trades.py
       python tests/show_paper_trades.py --open
       python tests/show_paper_trades.py --limit=10
"""

import sys
import argparse
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="Только открытые")
    parser.add_argument("--limit", type=int, default=100, help="Сколько показать")
    parser.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    args = parser.parse_args()

    db_path = Path(config.DB_PATH).parent / "journal.db"
    if not db_path.exists():
        print(f"❌ {db_path} не найден")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    from trader.paper import init_paper_table

    init_paper_table(conn)

    where = []
    params = []
    if args.open:
        where.append("result = 'open'")
    if args.symbol:
        where.append("symbol = ?")
        params.append(args.symbol)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM paper_trades {where_sql} ORDER BY id DESC LIMIT ?",
        (*params, args.limit),
    ).fetchall()
    rows = conn.execute(
        f"SELECT * FROM paper_trades {where_sql} ORDER BY id DESC LIMIT ?",
        (*params, args.limit),
    ).fetchall()

    if not rows:
        print("Paper-сделок нет.")
        return

    print(
        f"{'id':>3} {'dir':<6} {'kind':<12} {'score':>5} "
        f"{'entry':>8} {'stop':>8} {'take':>8} "
        f"{'exit':>8} {'result':<8} "
        f"{'pts':>7} {'rub':>9} {'bars':>5} {'conf':<13} "
        f"{'created_at':<19}"
    )
    print("-" * 150)

    from trader.paper import _colored, GREEN, RED, YELLOW

    for r in rows:
        exit_str = f"{r['exit_price']:>8.3f}" if r["exit_price"] else "       —"
        pts_str = (
            f"{r['result_points']:>+7.1f}"
            if r["result_points"] is not None
            else "      —"
        )
        rub_str = (
            f"{r['result_rub']:>+9.2f}" if r["result_rub"] is not None else "        —"
        )
        bars_str = f"{r['bars_to_close']:>5}" if r["bars_to_close"] else "    —"
        conf_str = r["resolution_confidence"] or "—"

        # Цвет результата
        result = r["result"]
        if result == "win":
            result_str = _colored(f"{result:<8}", GREEN)
            pts_str = _colored(pts_str, GREEN)
            rub_str = _colored(rub_str, GREEN)
        elif result == "loss":
            result_str = _colored(f"{result:<8}", RED)
            pts_str = _colored(pts_str, RED)
            rub_str = _colored(rub_str, RED)
        elif result == "open":
            result_str = _colored(f"{result:<8}", YELLOW)
        else:
            result_str = f"{result:<8}"

        # Цвет направления
        dir_color = RED if r["direction"] == "short" else GREEN
        dir_str = _colored(f"{r['direction']:<6}", dir_color)

        print(
            f"{r['id']:>3} {dir_str} {r['kind']:<12} "
            f"{r['strength_score'] or 0:>5.1f} "
            f"{r['entry_price']:>8.3f} {r['stop_price']:>8.3f} {r['take_price']:>8.3f} "
            f"{exit_str} {result_str} "
            f"{pts_str} {rub_str} {bars_str} {conf_str:<13} "
            f"{r['created_at'][:19]:<19}"
        )

    # Сводка
    print()
    by_result = {}
    for r in rows:
        by_result[r["result"]] = by_result.get(r["result"], 0) + 1
    print("По result:", by_result)

    conn.close()


if __name__ == "__main__":
    main()
