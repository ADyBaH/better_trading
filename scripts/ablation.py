"""
T-08: Ablation study фильтров на одном срезе.

Для каждого фильтра f:
  - прогон base с f.enabled=False (OFF) vs f.enabled=True (ON),
    все остальные фильтры зафиксированы.
  - ΔPF, Δexp, Δn, CI95% Δ (paired bootstrap разности).

Использование:
    python scripts/ablation.py --since 2026-11-11 --until 2026-11-19
    python scripts/ablation.py --since 2026-11-11 --until 2026-11-19 --only bullish_long
    python scripts/ablation.py --since 2026-11-11 --until 2026-11-19 --json
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import random
from typing import Callable

import pandas as pd

import config
from core.logger import setup_logging, get_logger

log = get_logger(__name__)


# ============================================================
# Список фильтров для ablation
# ============================================================


def _get_ablation_filters() -> list[tuple[str, str]]:
    """
    Возвращает список (name, config_attr) для ablation.

    Особые случаи:
    - breakout_filter → BREAKOUT_FILTER (enum F1-F4, не PAPER_SKIP_*)
    - breakout → PAPER_SKIP_BREAKOUT (kill-switch, bool)
    """
    from strategy.filters import get_filters

    result = []
    seen_attrs = set()
    seen_names = set()

    for f in get_filters():
        name = f.name
        if name in seen_names:
            continue

        # Особый случай: breakout_filter — это BREAKOUT_FILTER (enum)
        if name == "breakout_filter":
            if hasattr(config, "BREAKOUT_FILTER"):
                result.append(("breakout_filter", "BREAKOUT_FILTER"))
                seen_names.add(name)
            continue

        attr = f"PAPER_SKIP_{name.upper()}"
        if not hasattr(config, attr):
            log.warning("Фильтр %s: нет config.%s — пропуск", name, attr)
            continue
        if attr in seen_attrs:
            continue
        seen_attrs.add(attr)
        seen_names.add(name)
        result.append((name, attr))

    return result


# ============================================================
# Прогон
# ============================================================


def _run_variant(
    df_m15: pd.DataFrame,
    df_h1: pd.DataFrame,
    df_h4: pd.DataFrame,
    symbol: str,
    config_overrides: dict,
) -> dict:
    """Прогон backtest с временными config_overrides."""
    from scripts.backtest import run_backtest

    saved = {}
    for key, val in config_overrides.items():
        saved[key] = getattr(config, key, None)
        setattr(config, key, val)

    try:
        res = run_backtest(
            df_m15,
            df_h1,
            df_h4,
            symbol,
            filter_name=None,
            skip_breakout=False,
            skip_filters=False,
        )
    finally:
        for key, val in saved.items():
            if val is not None:
                setattr(config, key, val)

    return res


# ============================================================
# Paired bootstrap для Δ
# ============================================================


def _bootstrap_delta(
    trades_on: list[dict],
    trades_off: list[dict],
    n_iter: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Unpaired bootstrap для ΔPF / Δexp (ablation фильтров).

    Сравнивает две независимые выборки (on vs off).
    """
    if not trades_on or not trades_off:
        return {
            "delta_pf": None,
            "delta_exp": None,
            "delta_pf_ci": None,
            "delta_exp_ci": None,
            "n_on": len(trades_on),
            "n_off": len(trades_off),
        }

    def _pf(points_list):
        wins = sum(p for p in points_list if p > 0)
        losses = abs(sum(p for p in points_list if p < 0))
        return wins / losses if losses > 0 else None

    def _exp(points_list):
        if not points_list:
            return None
        return sum(points_list) / len(points_list)

    on_pts = [t["points"] for t in trades_on]
    off_pts = [t["points"] for t in trades_off]
    on_pf = _pf(on_pts)
    off_pf = _pf(off_pts)
    on_exp = _exp(on_pts)
    off_exp = _exp(off_pts)

    delta_pf = (on_pf - off_pf) if (on_pf is not None and off_pf is not None) else None
    delta_exp = (
        (on_exp - off_exp) if (on_exp is not None and off_exp is not None) else None
    )

    rng = random.Random(seed)
    pf_deltas = []
    exp_deltas = []

    for _ in range(n_iter):
        # Независимые выборки: on (n_on), off (n_off)
        on_sample = [rng.choice(on_pts) for _ in range(len(on_pts))]
        off_sample = [rng.choice(off_pts) for _ in range(len(off_pts))]
        pf_on_s = _pf(on_sample)
        pf_off_s = _pf(off_sample)
        exp_on_s = _exp(on_sample)
        exp_off_s = _exp(off_sample)
        if pf_on_s is not None and pf_off_s is not None:
            pf_deltas.append(pf_on_s - pf_off_s)
        if exp_on_s is not None and exp_off_s is not None:
            exp_deltas.append(exp_on_s - exp_off_s)

    def _ci(values):
        if not values:
            return None
        values.sort()
        lo = values[int(len(values) * (alpha / 2))]
        hi = values[int(len(values) * (1 - alpha / 2))]
        return (round(lo, 2), round(hi, 2))

    return {
        "delta_pf": round(delta_pf, 2) if delta_pf is not None else None,
        "delta_exp": round(delta_exp, 1) if delta_exp is not None else None,
        "delta_pf_ci": _ci(pf_deltas),
        "delta_exp_ci": _ci(exp_deltas),
        "n_on": len(on_pts),
        "n_off": len(off_pts),
    }


# ============================================================
# Ablation
# ============================================================


def run_ablation(
    since: str,
    until: str,
    symbol: str,
    only: str | None = None,
) -> dict:
    """Запускает ablation для всех фильтров."""
    from scripts.backtest import _load_candles

    log.info("Загрузка свечей %s – %s", since, until)
    df_m15 = _load_candles(since, until, "M15")
    df_h1 = _load_candles(since, until, "H1")
    df_h4 = _load_candles(since, until, "H4")
    log.info("M15: %d, H1: %d, H4: %d", len(df_m15), len(df_h1), len(df_h4))

    if df_m15.empty:
        return {"error": "Нет M15-свечей"}

    filters = _get_ablation_filters()

    # --- Baseline: все фильтры OFF ---
    log.info("Baseline: все фильтры OFF")
    all_off = {}
    for name, attr in filters:
        all_off[attr] = "none" if attr == "BREAKOUT_FILTER" else False

    baseline = _run_variant(df_m15, df_h1, df_h4, symbol, all_off)
    log.info(
        "Baseline: n=%d, PF=%s, exp=%s",
        baseline["total"],
        baseline["pf"],
        baseline["exp"],
    )

    results = {
        "since": since,
        "until": until,
        "symbol": symbol,
        "baseline": baseline,
        "filters": {},
    }

    # --- Каждый фильтр: ON vs OFF (все остальные OFF) ---
    for name, attr in filters:
        if only and name != only:
            continue

        log.info("Ablation: %s (ON vs OFF)", name)
        on_overrides = dict(all_off)
        on_overrides[attr] = "F4" if attr == "BREAKOUT_FILTER" else True

        res_on = _run_variant(df_m15, df_h1, df_h4, symbol, on_overrides)
        res_off = baseline

        # Paired bootstrap
        delta = _bootstrap_delta(
            res_on.get("_trades", []),
            res_off.get("_trades", []),
        )

        results["filters"][name] = {
            "n_on": res_on["total"],
            "n_off": res_off["total"],
            "delta_n": res_on["total"] - res_off["total"],
            "pf_on": res_on["pf"],
            "pf_off": res_off["pf"],
            "delta_pf": (
                round((res_on["pf"] or 0) - (res_off["pf"] or 0), 2)
                if (res_on["pf"] is not None and res_off["pf"] is not None)
                else None
            ),
            "exp_on": res_on["exp"],
            "exp_off": res_off["exp"],
            "delta_exp": (
                round((res_on["exp"] or 0) - (res_off["exp"] or 0), 1)
                if (res_on["exp"] is not None and res_off["exp"] is not None)
                else None
            ),
            **delta,
        }

    # --- Пересечение: breakout × normal_breakout ---
    if (
        (not only)
        and any(n == "normal_breakout" for n, _ in filters)
        and any(n == "skip_breakout" for n, _ in filters)
    ):
        log.info("Ablation: пересечение breakout × normal_breakout")
        # Все OFF, кроме normal_breakout + skip_breakout
        combo = dict(all_off)
        combo["PAPER_SKIP_NORMAL_BREAKOUT"] = True
        combo["PAPER_SKIP_BREAKOUT"] = True
        res_combo = _run_variant(df_m15, df_h1, df_h4, symbol, combo)
        results["intersection_breakout_normal"] = {
            "n": res_combo["total"],
            "pf": res_combo["pf"],
            "exp": res_combo["exp"],
            "note": "PAPER_SKIP_BREAKOUT=True + PAPER_SKIP_NORMAL_BREAKOUT=True",
        }

    return results


# ============================================================
# Вывод
# ============================================================


def print_results(results: dict) -> None:
    baseline = results["baseline"]
    print()
    print("═══ Baseline (все фильтры OFF) ═══")
    print(
        f"  n={baseline['total']}, PF={baseline['pf']}, exp={baseline['exp']}, "
        f"rub={baseline['rub']:+.2f}"
    )

    print()
    print("═══ Ablation ═══")
    print(
        f"  {'filter':22} {'n_on':>5} {'n_off':>6} {'Δn':>5} "
        f"{'PF_on':>6} {'PF_off':>7} {'ΔPF':>7} {'ΔPF_CI':>14} "
        f"{'Exp_on':>7} {'Exp_off':>8} {'ΔExp':>6} {'ΔExp_CI':>14}"
    )
    print(
        f"  {'-'*22} {'-'*5} {'-'*6} {'-'*5} {'-'*6} {'-'*7} {'-'*7} "
        f"{'-'*14} {'-'*7} {'-'*8} {'-'*6} {'-'*14}"
    )

    for name, d in results["filters"].items():

        def _fmt(v, fmt):
            return fmt.format(v) if v is not None else "—"

        def _fmt_ci(ci):
            if ci is None:
                return "—"
            return f"[{ci[0]:+.2f}, {ci[1]:+.2f}]"

        print(
            f"  {name:22} {d['n_on']:>5} {d['n_off']:>6} {d['delta_n']:>+5} "
            f"{_fmt(d['pf_on'], '{:.2f}'):>6} {_fmt(d['pf_off'], '{:.2f}'):>7} "
            f"{_fmt(d['delta_pf'], '{:+.2f}'):>7} {_fmt_ci(d.get('delta_pf_ci')):>14} "
            f"{_fmt(d['exp_on'], '{:+.1f}'):>7} {_fmt(d['exp_off'], '{:+.1f}'):>8} "
            f"{_fmt(d['delta_exp'], '{:+.1f}'):>6} {_fmt_ci(d.get('delta_exp_ci')):>14}"
        )

    # Пересечения
    if "intersection_breakout_normal" in results:
        inter = results["intersection_breakout_normal"]
        print()
        print("═══ Пересечения ═══")
        print(
            f"  {inter['note']}: n={inter['n']}, PF={inter['pf']}, exp={inter['exp']}"
        )


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="T-08: Ablation study фильтров")
    parser.add_argument("--since", required=True, help="YYYY-MM-DD")
    parser.add_argument("--until", required=True, help="YYYY-MM-DD")
    parser.add_argument("--symbol", default=config.SYMBOL)
    parser.add_argument("--only", default=None, help="Только один фильтр")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")
    args = parser.parse_args()

    results = run_ablation(args.since, args.until, args.symbol, only=args.only)

    if args.json:
        # Убрать _trades из JSON (большой)
        def _strip(obj):
            if isinstance(obj, dict):
                return {k: _strip(v) for k, v in obj.items() if k != "_trades"}
            if isinstance(obj, list):
                return [_strip(x) for x in obj]
            return obj

        print(json.dumps(_strip(results), indent=2, default=str))
    else:
        print_results(results)


if __name__ == "__main__":
    main()
