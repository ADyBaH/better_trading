"""
Сеточный поиск оптимальных STOP/TAKE по историческим MFE/MAE.

Использование:
    python scripts/optimize_stops.py
    python scripts/optimize_stops.py --min-n 20
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
from datetime import datetime

import config
from core.logger import setup_logging, get_logger
from trader.journal import connect_journal
from trader.paper import init_paper_table

log = get_logger(__name__)

# Сетка (в ATR)
STOP_GRID = [0.6, 0.8, 1.0, 1.2, 1.5]
TAKE_GRID = [0.8, 1.0, 1.2, 1.5, 2.0, 2.5]


def _calc_pf_exp(trades: list[dict]) -> tuple[float | None, float | None]:
    win_rub = sum(t["rub"] for t in trades if t["result"] == "win")
    # timeout = loss (консервативно, как virtual_pnl ambiguous)
    loss_rub = abs(sum(t["rub"] for t in trades if t["result"] in ("loss", "timeout")))
    pf = round(win_rub / loss_rub, 2) if loss_rub > 0 else None

    total = len(trades)
    exp = round(sum(t["points"] for t in trades) / total, 1) if total > 0 else None
    return pf, exp


def run_grid(rows: list[dict], inst, stop_mult: float, take_mult: float) -> dict:
    """
    Пересчитывает исходы для заданных (stop, take).
    MAE/MFE в пунктах, stop_dist/take_dist — в пунктах.
    Консервативно: если и стоп, и тейк задеты — loss (как virtual_pnl ambiguous).
    """
    trades = []
    for r in rows:
        mfe = r["mfe_points"]
        mae = r["mae_points"]
        if mfe is None or mae is None:
            continue

        entry = r["entry_price"]
        # stop_dist/take_dist для этой сделки (в пунктах)
        # stop_dist_orig = abs(entry - stop) / price_step
        # Но мы пересчитываем от ATR: stop_dist_new = stop_mult * ATR
        # ATR в пунктах: восстанавливаем из оригинального stop (STOP_ATR_MULT=1.0)
        stop_orig = abs(entry - r["stop_price"]) / inst.price_step
        atr_points = stop_orig / config.STOP_ATR_MULT  # ATR в пунктах

        stop_dist = stop_mult * atr_points
        take_dist = take_mult * atr_points

        # Исход
        hit_take = mfe >= take_dist
        hit_stop = mae >= stop_dist

        if hit_take and hit_stop:
            result = "loss"  # ambiguous -> loss
            exit_price = None
        elif hit_take:
            result = "win"
            exit_price = (
                entry + take_dist * inst.price_step
                if r["direction"] == "long"
                else entry - take_dist * inst.price_step
            )
        elif hit_stop:
            result = "loss"
            exit_price = (
                entry - stop_dist * inst.price_step
                if r["direction"] == "long"
                else entry + stop_dist * inst.price_step
            )
        else:
            result = "timeout"
            exit_price = r["exit_price"] or entry  # fallback

        # PnL
        points = 0.0
        rub = 0.0
        if exit_price is not None:
            from core.instruments import compute_trade_result

            points, rub = compute_trade_result(inst, r["direction"], entry, exit_price)

        trades.append({"result": result, "points": points, "rub": rub})

    w = sum(1 for t in trades if t["result"] == "win")
    l = sum(1 for t in trades if t["result"] == "loss")
    to = sum(1 for t in trades if t["result"] == "timeout")
    rub = sum(t["rub"] for t in trades)
    pf, exp = _calc_pf_exp(trades)

    return {
        "stop": stop_mult,
        "take": take_mult,
        "n": len(trades),
        "w": w,
        "l": l,
        "t": to,
        "rub": round(rub, 2),
        "pf": pf,
        "exp": exp,
    }


def main():
    parser = argparse.ArgumentParser(description="Оптимизация STOP/TAKE по MFE/MAE")
    parser.add_argument(
        "--min-n", type=int, default=10, help="Минимум сделок для вывода"
    )
    args = parser.parse_args()
    setup_logging()

    with connect_journal() as conn:
        init_paper_table(conn)
        rows = conn.execute("""
            SELECT * FROM paper_trades
            WHERE mfe_points IS NOT NULL AND mae_points IS NOT NULL
              AND result IN ('win', 'loss', 'timeout')
              AND mfe_source IN ('live', 'backfill')
            ORDER BY created_at
            """).fetchall()

    if not rows:
        print("Нет сделок с MFE/MAE для оптимизации.")
        return

    rows = [dict(r) for r in rows]
    print(f"Сделок с MFE/MAE: {len(rows)}")

    # Train/test split (70/30 по времени)
    split_idx = int(len(rows) * 0.7)
    train = rows[:split_idx]
    test = rows[split_idx:]
    print(f"Train: {len(train)} | Test: {len(test)}")

    from core.instruments import get_instrument

    inst = get_instrument(config.DEFAULT_INSTRUMENT)

    # Сетка
    results = []
    for stop in STOP_GRID:
        for take in TAKE_GRID:
            res = run_grid(rows, inst, stop, take)
            if res["n"] >= args.min_n:
                results.append(res)

    if not results:
        print(f"Нет комбинаций с n >= {args.min_n}.")
        return

    # Сортировка по PF (потом exp)
    results.sort(key=lambda x: (x["pf"] or 0, x["exp"] or 0), reverse=True)

    print("\n=== Топ-10 комбинаций (по PF) ===")
    print(
        f"  {'stop':>5} {'take':>5} {'n':>3} {'W':>2} {'L':>2} {'T':>2} {'rub':>8} {'PF':>5} {'exp':>6}"
    )
    for r in results[:10]:
        print(
            f"  {r['stop']:>5.1f} {r['take']:>5.1f} {r['n']:>3} {r['w']:>2} {r['l']:>2} {r['t']:>2} {r['rub']:>+8.2f} {str(r['pf']):>5} {str(r['exp']):>6}"
        )

    # Текущий (1.0, 2.0)
    current = next((r for r in results if r["stop"] == 1.0 and r["take"] == 2.0), None)
    if current:
        print(
            f"\nТекущее (1.0, 2.0): n={current['n']} PF={current['pf']} exp={current['exp']} rub={current['rub']:+.2f}"
        )

    print("\n=== Train/Test (топ-3) ===")
    for r in results[:3]:
        train_res = run_grid(train, inst, r["stop"], r["take"])
        test_res = run_grid(test, inst, r["stop"], r["take"])
        print(f"  stop={r['stop']} take={r['take']}:")
        print(
            f"    train: n={train_res['n']} PF={train_res['pf']} exp={train_res['exp']}"
        )
        print(f"    test:  n={test_res['n']} PF={test_res['pf']} exp={test_res['exp']}")


if __name__ == "__main__":
    main()
