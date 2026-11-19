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
    from core.instruments import get_instrument

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
        if direction == "long":
            points = round((exit_price - entry) / price_step, 1)
        else:
            points = round((entry - exit_price) / price_step, 1)
        rub = round(points * inst.step_cost, 2)

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

    # Применяем фильтры
    def _filtered_by(sig, filter_name):
        """Возвращает True, если сигнал отсекается фильтром."""
        ind = sig.get("_indicators") or {}
        direction = sig.get("direction")
        kind = sig.get("kind")

        if filter_name == "adx_trend":
            return (
                getattr(config, "PAPER_SKIP_ADX_TREND", False)
                and ind.get("adx") is not None
                and 20 <= ind.get("adx") < 25
            )
        if filter_name == "bullish_long":
            return (
                getattr(config, "PAPER_SKIP_BULLISH_LONG", False)
                and ind.get("week_trend") == "bullish"
                and direction == "long"
            )
        if filter_name == "normal_breakout":
            return (
                getattr(config, "PAPER_SKIP_NORMAL_BREAKOUT", False)
                and ind.get("market_state") == "normal"
                and kind in ("breakout", "trend_level")
            )
        if filter_name == "bullish_short":
            return (
                getattr(config, "PAPER_SKIP_BULLISH_SHORT", False)
                and ind.get("week_trend") == "bullish"
                and direction == "short"
            )
        if filter_name == "adx_flat_breakout":
            return (
                getattr(config, "PAPER_SKIP_ADX_FLAT_BREAKOUT", False)
                and kind == "breakout"
                and (ind.get("adx") or 0) < 20
            )
        return False

    filters = [
        "bullish_long",
        "normal_breakout",
        "bullish_short",
        "adx_flat_breakout",
        "adx_trend",
    ]

    def _stats(signals):
        w = sum(1 for s in signals if s.get("_result") == "win")
        l = sum(1 for s in signals if s.get("_result") == "loss")
        t = sum(1 for s in signals if s.get("_result") == "timeout")
        o = sum(1 for s in signals if s.get("_result") == "open")
        pts = sum(s.get("_points") or 0 for s in signals)
        rub = sum(s.get("_rub") or 0 for s in signals)
        return {
            "total": len(signals),
            "win": w,
            "loss": l,
            "timeout": t,
            "open": o,
            "points": round(pts, 1),
            "rub": round(rub, 2),
        }

    print("── Все сигналы (без фильтров) ──")
    all_stats = _stats(all_signals)
    print(
        f"  total={all_stats['total']} W={all_stats['win']} L={all_stats['loss']} T={all_stats['timeout']} O={all_stats['open']} | pts={all_stats['points']:+.1f} rub={all_stats['rub']:+.2f}"
    )
    print()

    for fname in filters:
        enabled = "ON" if any(_filtered_by(s, fname) for s in all_signals) else "OFF"
        blocked = [s for s in all_signals if _filtered_by(s, fname)]
        passed = [s for s in all_signals if not _filtered_by(s, fname)]

        print(f"── Фильтр: {fname} ({enabled}) ──")
        if not blocked:
            print(f"  отсекает 0 сигналов")
            print()
            continue

        b_stats = _stats(blocked)
        p_stats = _stats(passed)
        print(
            f"  отсекает {b_stats['total']}: W={b_stats['win']} L={b_stats['loss']} T={b_stats['timeout']} O={b_stats['open']} | pts={b_stats['points']:+.1f} rub={b_stats['rub']:+.2f}"
        )
        print(
            f"  проходит {p_stats['total']}: W={p_stats['win']} L={p_stats['loss']} T={p_stats['timeout']} O={p_stats['open']} | pts={p_stats['points']:+.1f} rub={p_stats['rub']:+.2f}"
        )
        print()

    # Итог: все фильтры вместе
    print("── Все фильтры Y вместе ──")
    blocked_all = [s for s in all_signals if any(_filtered_by(s, f) for f in filters)]
    passed_all = [
        s for s in all_signals if not any(_filtered_by(s, f) for f in filters)
    ]
    b_stats = _stats(blocked_all)
    p_stats = _stats(passed_all)
    print(
        f"  отсечено {b_stats['total']}: W={b_stats['win']} L={b_stats['loss']} T={b_stats['timeout']} O={b_stats['open']} | pts={b_stats['points']:+.1f} rub={b_stats['rub']:+.2f}"
    )
    print(
        f"  прошло   {p_stats['total']}: W={p_stats['win']} L={p_stats['loss']} T={p_stats['timeout']} O={p_stats['open']} | pts={p_stats['points']:+.1f} rub={p_stats['rub']:+.2f}"
    )
    print()

    # Вывод: полезны ли фильтры?
    print("── Вывод ──")
    if b_stats["total"] > 0:
        b_winrate = round(
            100 * b_stats["win"] / max(b_stats["win"] + b_stats["loss"], 1), 1
        )
        p_winrate = (
            round(100 * p_stats["win"] / max(p_stats["win"] + p_stats["loss"], 1), 1)
            if p_stats["total"] > 0
            else 0
        )
        print(f"  Отсечённые: winrate={b_winrate}% rub={b_stats['rub']:+.2f}")
        print(f"  Прошедшие:  winrate={p_winrate}% rub={p_stats['rub']:+.2f}")
        if b_stats["rub"] < 0:
            print(f"  ✅ Фильтры режут УБЫТОЧНЫЕ (отсечено {b_stats['rub']:+.2f} ₽)")
        else:
            print(
                f"  ⚠️ Фильтры режут ПРИБЫЛЬНЫЕ (отсечено {b_stats['rub']:+.2f} ₽) — пересмотреть"
            )


if __name__ == "__main__":
    main()
