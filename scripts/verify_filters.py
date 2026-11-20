"""
Проверяет эффект фильтров Y на истории (13.11+):
- сколько сигналов отсекает каждый фильтр,
- из отсечённых — win/loss/timeout,
- из прошедших — win/loss/timeout.

Использование:
    python scripts/verify_filters.py --date 2026-11-13
"""

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
from datetime import datetime

import pandas as pd

import config
from core.logger import setup_logging, get_logger
from trader.paper import virtual_pnl
from strategy.filters import get_filters
from core.models import Signal

log = get_logger(__name__)

LOGS_DIR = Path(config.LOG_PATH).parent


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Не удалось прочитать %s: %s", path, e)
        return None


def _df_from_snapshot(snapshot: dict) -> pd.DataFrame:
    rows = snapshot.get("candles", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["begin"] = pd.to_datetime(df["begin"])
    return df.sort_values("begin").reset_index(drop=True)


def _resolve_signal(sig: dict, df_m15: pd.DataFrame) -> dict:
    """Резолв сигнала по M15-свечам ПОСЛЕ его timestamp."""
    from core.instruments import get_instrument, compute_trade_result

    ts_str = sig.get("_timestamp") or sig.get("timestamp") or sig.get("saved_at")
    if not ts_str:
        return {"result": "unknown", "points": 0, "rub": 0, "bars": 0}

    try:
        ts = datetime.fromisoformat(ts_str)
    except Exception:
        return {"result": "unknown", "points": 0, "rub": 0, "bars": 0}

    direction = sig.get("direction")
    entry = sig.get("entry_price")
    stop = sig.get("stop_price")
    take = sig.get("take_price")
    if not all([direction, entry, stop, take]):
        return {"result": "unknown", "points": 0, "rub": 0, "bars": 0}

    inst = get_instrument(sig.get("symbol") or "CNYRUBF")
    price_step = inst.price_step

    df_future = df_m15[df_m15["begin"] > ts].copy()
    if df_future.empty:
        return {"result": "open", "points": 0, "rub": 0, "bars": 0}

    pnl = virtual_pnl(
        df_future,
        direction,
        entry,
        stop,
        take,
        max_bars=config.PAPER_TIMEOUT_BARS,
        price_step=price_step,
    )

    exit_price = pnl.get("exit_price")
    points = 0.0
    rub = 0.0
    if exit_price is not None:
        points, rub = compute_trade_result(inst, direction, entry, exit_price)

    return {
        "result": pnl.get("result", "unknown"),
        "exit_price": exit_price,
        "bars": pnl.get("bars", 0),
        "points": points,
        "rub": rub,
        "ambiguous": pnl.get("ambiguous", False),
    }


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Эффект фильтров Y на истории")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    date_dir = LOGS_DIR / args.date
    if not date_dir.exists():
        log.error("Папка не найдена: %s", date_dir)
        return

    analysis = _load_json(date_dir / f"analysis_{args.date}.json")
    if not analysis or not analysis.get("snapshots"):
        log.error("Нет analysis для %s", args.date)
        return

    # Свечи M15
    candles_data = _load_json(date_dir / f"candles_M15_{args.date}.json")
    if not candles_data or not candles_data.get("snapshots"):
        log.error("Нет candles_M15 для %s", args.date)
        return
    df_m15 = _df_from_snapshot(candles_data["snapshots"][-1])

    # Собираем все сигналы из analysis
    all_signals = []
    for snap in analysis["snapshots"]:
        ind = snap.get("indicators") or {}
        for sig in snap.get("signals") or []:
            sig["_indicators"] = ind
            sig["_timestamp"] = snap.get("timestamp")
            all_signals.append(sig)

    if not all_signals:
        print(f"\nНет сигналов в analysis за {args.date}")
        return

    # Резолв каждого
    print(f"\n═══ Фильтры {args.date} ═══")
    print(f"  Всего сигналов: {len(all_signals)}\n")

    for sig in all_signals:
        pnl = _resolve_signal(sig, df_m15)
        sig["_result"] = pnl.get("result", "unknown")
        sig["_points"] = pnl.get("points", 0)
        sig["_rub"] = pnl.get("rub", 0)

    def _fake_result_from_dict(ind: dict, sig: dict):
        """Собирает минимальный AnalysisResult из dict-индикаторов."""

        class _Ind:
            pass

        class _Res:
            pass

        r = _Res()
        r.indicators = _Ind()
        r.indicators.week_trend = ind.get("week_trend", "unknown")
        r.indicators.market_state = ind.get("market_state", "normal")
        r.indicators.adx = ind.get("adx")
        r.indicators.trend = ind.get("trend", "none")
        r.indicators.day_trend = ind.get("day_trend", "neutral")
        r.indicators.structure = ind.get("structure", "mixed")
        r.indicators.vote_sum = ind.get("vote_sum", 0)
        r.indicators.rsi = ind.get("rsi")
        r.order_book = {}
        return r

    def _signal_from_dict(sig: dict) -> Signal:
        """Конвертирует dict (из analysis) → Signal (для реестра)."""
        return Signal(
            direction=sig.get("direction", ""),
            kind=sig.get("kind", ""),
            strength=sig.get("strength", "medium"),
            strength_score=sig.get("strength_score", 0.0),
            entry_price=sig.get("entry_price", 0.0),
            stop_price=sig.get("stop_price", 0.0),
            take_price=sig.get("take_price", 0.0),
            level_price=sig.get("level_price"),
        )

    def _filter_blocks(f, sig: dict) -> bool:
        """Применяет фильтр к dict-сигналу. Возвращает True, если блокирует."""
        ind_dict = sig.get("_indicators") or {}
        result = _fake_result_from_dict(ind_dict, sig)
        signal = _signal_from_dict(sig)
        return f.fn(signal, result).blocked

    def _stats(signals):
        w = sum(1 for s in signals if s.get("_result") == "win")
        l = sum(1 for s in signals if s.get("_result") == "loss")
        t = sum(1 for s in signals if s.get("_result") == "timeout")
        o = sum(1 for s in signals if s.get("_result") == "open")
        pts = sum(s.get("_points") or 0 for s in signals)
        rub = sum(s.get("_rub") or 0 for s in signals)

        win_rub = sum(s.get("_rub") or 0 for s in signals if s.get("_result") == "win")
        loss_rub = abs(
            sum(s.get("_rub") or 0 for s in signals if s.get("_result") == "loss")
        )
        pf = round(win_rub / loss_rub, 2) if loss_rub > 0 else None

        closed_wl = w + l
        exp = round(pts / closed_wl, 1) if closed_wl > 0 else None

        return {
            "total": len(signals),
            "win": w,
            "loss": l,
            "timeout": t,
            "open": o,
            "points": round(pts, 1),
            "rub": round(rub, 2),
            "pf": pf,
            "exp": exp,
        }

    print("── Все сигналы (без фильтров) ──")
    all_stats = _stats(all_signals)
    print(
        f"  total={all_stats['total']} W={all_stats['win']} L={all_stats['loss']} "
        f"T={all_stats['timeout']} O={all_stats['open']} | "
        f"pts={all_stats['points']:+.1f} rub={all_stats['rub']:+.2f} "
        f"PF={all_stats['pf']} exp={all_stats['exp']}"
    )
    print()

    for f in get_filters():
        blocked, passed = [], []
        for s in all_signals:
            if _filter_blocks(f, s):
                blocked.append(s)
            else:
                passed.append(s)

        enabled_str = "ON" if f.enabled else "OFF"
        print(f"── Фильтр: {f.name} ({enabled_str}) ──")
        if not blocked:
            print(f"  отсекает 0 сигналов")
            print()
            continue

        b_stats = _stats(blocked)
        p_stats = _stats(passed)
        print(
            f"  отсекает {b_stats['total']}: W={b_stats['win']} L={b_stats['loss']} "
            f"T={b_stats['timeout']} O={b_stats['open']} | "
            f"pts={b_stats['points']:+.1f} rub={b_stats['rub']:+.2f} "
            f"PF={b_stats['pf']} exp={b_stats['exp']}"
        )
        print(
            f"  проходит {p_stats['total']}: W={p_stats['win']} L={p_stats['loss']} "
            f"T={p_stats['timeout']} O={p_stats['open']} | "
            f"pts={p_stats['points']:+.1f} rub={p_stats['rub']:+.2f} "
            f"PF={p_stats['pf']} exp={p_stats['exp']}"
        )
        print()

        # --- Все фильтры Y вместе ---
    print("── Все фильтры Y вместе ──")
    blocked_all, passed_all = [], []
    for s in all_signals:
        if any(_filter_blocks(f, s) for f in get_filters()):
            blocked_all.append(s)
        else:
            passed_all.append(s)

    b_stats_all = _stats(blocked_all)
    p_stats_all = _stats(passed_all)
    print(
        f"  отсечено {b_stats_all['total']}: W={b_stats_all['win']} L={b_stats_all['loss']} "
        f"T={b_stats_all['timeout']} O={b_stats_all['open']} | "
        f"pts={b_stats_all['points']:+.1f} rub={b_stats_all['rub']:+.2f}"
    )
    print(
        f"  прошло   {p_stats_all['total']}: W={p_stats_all['win']} L={p_stats_all['loss']} "
        f"T={p_stats_all['timeout']} O={p_stats_all['open']} | "
        f"pts={p_stats_all['points']:+.1f} rub={p_stats_all['rub']:+.2f}"
    )
    print()

    # Вывод: полезны ли фильтры?
    print("── Вывод ──")
    if b_stats_all["total"] > 0:
        b_winrate = round(
            100 * b_stats_all["win"] / max(b_stats_all["win"] + b_stats_all["loss"], 1),
            1,
        )
        p_winrate = (
            round(
                100
                * p_stats_all["win"]
                / max(p_stats_all["win"] + p_stats_all["loss"], 1),
                1,
            )
            if p_stats_all["total"] > 0
            else 0
        )
        print(f"  Отсечённые: winrate={b_winrate}% rub={b_stats_all['rub']:+.2f}")
        print(f"  Прошедшие:  winrate={p_winrate}% rub={p_stats_all['rub']:+.2f}")
        if b_stats_all["rub"] < 0:
            print(
                f"  ✅ Фильтры режут УБЫТОЧНЫЕ (отсечено {b_stats_all['rub']:+.2f} ₽)"
            )
        else:
            print(
                f"  ⚠️ Фильтры режут ПРИБЫЛЬНЫЕ (отсечено {b_stats_all['rub']:+.2f} ₽) — пересмотреть"
            )


if __name__ == "__main__":
    main()
