"""Тесты на backfill MFE/MAE и optimize_stops."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime, timedelta

import config
from scripts.optimize_stops import run_grid, _calc_pf_exp

PASSED = 0
FAILED = 0


def check(name, actual, expected):
    global PASSED, FAILED
    if hasattr(actual, "item"):
        actual = actual.item()
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: expected {expected!r}, got {actual!r}")


def _make_rows(
    n=5, mfe=100, mae=10, direction="long", entry=12.5, stop=12.4, take=12.7
):
    """Создаёт n сделок с заданными MFE/MAE."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": i + 1,
                "direction": direction,
                "entry_price": entry,
                "stop_price": stop,
                "take_price": take,
                "exit_price": entry,
                "mfe_points": mfe,
                "mae_points": mae,
                "result": "win",
                "created_at": f"2026-11-{10+i:02d}T12:00:00",
            }
        )
    return rows


class _FakeInst:
    price_step = 0.001
    step_cost = 1.0
    commission_round = 2.06
    commission_exchange = 0.58
    commission_broker = 0.45


def main():
    print("=" * 60)
    print("Тесты: MFE backfill + optimize_stops")
    print("=" * 60)

    # --- _calc_pf_exp ---
    print("\n_calc_pf_exp:")
    trades = [
        {"result": "win", "rub": 100, "points": 50},
        {"result": "loss", "rub": -50, "points": -25},
        {"result": "timeout", "rub": -10, "points": -5},
    ]
    pf, exp = _calc_pf_exp(trades)
    check("PF = 100 / 60", pf, 1.67)
    check("exp = (50-25-5)/3", exp, 6.7)

    # --- run_grid: базовый ---
    print("\nrun_grid:")
    rows = _make_rows(5, mfe=150, mae=10)  # MFE>take, MAE<stop
    inst = _FakeInst()
    # ATR в пунктах: (entry - stop) / price_step / STOP_ATR_MULT = 0.1/0.001/1.0 = 100
    res = run_grid(rows, inst, stop_mult=1.0, take_mult=1.0)
    check("5 win", res["w"], 5)
    check("0 loss", res["l"], 0)
    check("PF is None (нет loss)", res["pf"], None)

    # --- run_grid: стоп пробит ---
    rows = _make_rows(5, mfe=10, mae=200)  # MAE > stop, MFE < take
    res = run_grid(rows, inst, stop_mult=1.0, take_mult=1.0)
    check("0 win", res["w"], 0)
    check("5 loss", res["l"], 5)

    # --- run_grid: широкий стоп — меньше loss ---
    rows = _make_rows(5, mfe=10, mae=150)
    res_narrow = run_grid(rows, inst, stop_mult=1.0, take_mult=1.0)  # stop=100
    res_wide = run_grid(rows, inst, stop_mult=2.0, take_mult=1.0)  # stop=200
    check("узкий: loss=5", res_narrow["l"], 5)
    check("широкий: loss=0 (MAE<200)", res_wide["l"], 0)

    # --- run_grid: timeout ---
    rows = _make_rows(3, mfe=10, mae=10)  # ни стоп, ни тейк
    res = run_grid(rows, inst, stop_mult=1.0, take_mult=1.0)
    check("3 timeout", res["t"], 3)

    # --- run_grid: ambiguous -> loss ---
    rows = _make_rows(1, mfe=300, mae=300)  # и тейк, и стоп
    res = run_grid(rows, inst, stop_mult=1.0, take_mult=1.0)
    check("ambiguous -> loss", res["l"], 1)

    # --- run_grid: пустые mfe/mae пропускаются ---
    rows = _make_rows(3, mfe=100, mae=10)
    rows[0]["mfe_points"] = None
    res = run_grid(rows, inst, stop_mult=1.0, take_mult=1.0)
    check("None пропущен", res["n"], 2)

    print("\n" + "=" * 60)
    total = PASSED + FAILED
    print(f"Прoйдено: {PASSED} / {total}")
    if FAILED:
        sys.exit(1)
    else:
        print("✅ Все проверки пройдены")
        sys.exit(0)


if __name__ == "__main__":
    main()
