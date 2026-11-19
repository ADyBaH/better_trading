"""
Бэктестер paper-логики на исторических свечах.

Прогоняет detect_signals (с текущими фильтрами config.py) по барам M15
и считает PnL/PF/winrate/expectancy — как paper-stats.

Честный replay: на баре t подаётся df.iloc[:t+1] (без look-ahead).
Резолв — virtual_pnl по df.iloc[t+1:] (с комиссией).

Использование:
    python scripts/backtest.py --since 2026-11-01 --until 2026-11-19
    python scripts/backtest.py --since 2026-11-01 --until 2026-11-19 --compare
    python scripts/backtest.py --since 2026-11-13 --until 2026-11-13 --breakout-filter F1
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
from datetime import datetime, time, timedelta

import pandas as pd

import config
from core.analyzer import analyze_from_df
from core.instruments import get_instrument, compute_trade_result
from core.logger import setup_logging, get_logger
from trader.paper import virtual_pnl

log = get_logger(__name__)


# ============================================================
# Данные
# ============================================================


def _load_candles(since: str, until: str, tf: str = "M15") -> pd.DataFrame:
    """
    Читает свечи из candles_<tf>_<date>.json за [since, until].
    Склеивает все snapshots, дедуплицирует по begin.
    Fallback: get_candles_tf (последние N) — если файлов нет.
    """
    import json
    from pathlib import Path

    logs_dir = Path(config.LOG_PATH).parent
    since_dt = datetime.fromisoformat(since)
    until_dt = datetime.fromisoformat(until) + timedelta(days=1)

    frames = []
    cur = since_dt
    while cur < until_dt:
        date_str = cur.strftime("%Y-%m-%d")
        path = logs_dir / date_str / f"candles_{tf}_{date_str}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for snap in data.get("snapshots", []):
                    rows = snap.get("candles", [])
                    if rows:
                        frames.append(pd.DataFrame(rows))
            except Exception as e:
                log.warning("Не удалось прочитать %s: %s", path, e)
        cur += timedelta(days=1)

    if frames:
        df = pd.concat(frames, ignore_index=True)
        df["begin"] = pd.to_datetime(df["begin"])
        df = (
            df.drop_duplicates(subset=["begin"])
            .sort_values("begin")
            .reset_index(drop=True)
        )
        # Фильтр по [since, until]
        df = df[
            (df["begin"] >= pd.Timestamp(since))
            & (df["begin"] < pd.Timestamp(until_dt))
        ]
        log.info("%s: %d свечей из candles_*.json", tf, len(df))
        return df.reset_index(drop=True)

    # Fallback: get_candles_tf (последние N)
    log.warning("%s: candles_*.json нет — fallback на get_candles_tf", tf)
    from data.api_facade import get_candles_tf

    df = get_candles_tf(tf, count=3000)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["begin"] = pd.to_datetime(df["begin"])
    df = df.sort_values("begin").reset_index(drop=True)
    df = df[
        (df["begin"] >= pd.Timestamp(since)) & (df["begin"] < pd.Timestamp(until_dt))
    ]
    return df.reset_index(drop=True)


def _in_trading_hours(ts: datetime) -> bool:
    hours = config.PAPER_TRADING_HOURS
    start_h, start_m = map(int, hours["start"].split(":"))
    end_h, end_m = map(int, hours["end"].split(":"))
    t = ts.time()
    return time(start_h, start_m) <= t < time(end_h, end_m)


# ============================================================
# Резолв
# ============================================================


def _resolve(signal, df_future: pd.DataFrame, inst) -> dict:
    """Резолв сигнала по будущим свечам (с комиссией)."""
    if df_future is None or df_future.empty:
        return {"result": "open", "points": 0.0, "rub": 0.0, "bars": 0}

    pnl = virtual_pnl(
        df_future,
        signal.direction,
        signal.entry_price,
        signal.stop_price,
        signal.take_price,
        max_bars=config.PAPER_TIMEOUT_BARS,
        price_step=inst.price_step,
    )
    exit_price = pnl.get("exit_price")
    points = 0.0
    rub = 0.0
    if exit_price is not None:
        points, rub = compute_trade_result(
            inst, signal.direction, signal.entry_price, exit_price
        )
    return {
        "result": pnl.get("result", "unknown"),
        "points": points,
        "rub": rub,
        "bars": pnl.get("bars", 0),
    }


# ============================================================
# Backtest
# ============================================================


def run_backtest(
    df_m15: pd.DataFrame,
    df_h1: pd.DataFrame,
    df_h4: pd.DataFrame,
    symbol: str,
    filter_name: str | None = None,
    skip_breakout: bool = False,
    skip_filters: bool = False,
) -> dict:
    """
    Прогоняет detect_signals по барам последовательно (без look-ahead).
    Возвращает агрегаты: total, win, loss, timeout, points, rub, pf, exp.
    """
    inst = get_instrument(symbol)
    trades = []

    # --- Временно применяем фильтры ---
    saved = {}
    if skip_filters:
        # Отключаем все PAPER_SKIP_*, чтобы baseline/F1–F4 были изолированы
        for key in (
            "PAPER_SKIP_BULLISH_LONG",
            "PAPER_SKIP_NORMAL_BREAKOUT",
            "PAPER_SKIP_ADX_TREND",
            "PAPER_SKIP_BID_HEAVY",
            "PAPER_SKIP_PULLBACK_BOUNCE",
        ):
            saved.setdefault(key, getattr(config, key, None))
            setattr(config, key, False)

    for key in (
        "PAPER_SKIP_BREAKOUT",
        "BREAKOUT_FILTER",
        "PAPER_SKIP_BULLISH_LONG",
        "PAPER_SKIP_NORMAL_BREAKOUT",
        "PAPER_SKIP_ADX_TREND",
        "PAPER_SKIP_BID_HEAVY",
        "PAPER_SKIP_PULLBACK_BOUNCE",
    ):
        saved[key] = getattr(config, key, None)
    if skip_breakout:
        config.PAPER_SKIP_BREAKOUT = True
    if filter_name:
        config.BREAKOUT_FILTER = filter_name

    try:
        # Начинаем с n_impulse=12 + запас для индикаторов
        start_idx = max(250, 12 + 50)
        if len(df_m15) <= start_idx:
            log.warning("Мало свечей: %d (нужно > %d)", len(df_m15), start_idx)
            return _aggregate([])

        # Открытые сделки (резолв на каждом баре)
        open_trades = []

        for t in range(start_idx, len(df_m15)):
            bar_ts = df_m15["begin"].iloc[t]
            bar_dt = (
                bar_ts.to_pydatetime() if hasattr(bar_ts, "to_pydatetime") else bar_ts
            )

            # --- Резолв открытых сделок (по текущему бару) ---
            still_open = []
            for ot in open_trades:
                if t <= ot["entry_idx"]:
                    still_open.append(ot)
                    continue
                df_future = df_m15.iloc[ot["entry_idx"] + 1 : t + 1]
                res = _resolve(ot["signal"], df_future, inst)
                if res["result"] in ("open", "no_data"):
                    still_open.append(ot)
                else:
                    trades.append(res)
            open_trades = still_open

            # --- Новые сигналы (только в торговые часы) ---
            if not _in_trading_hours(bar_dt):
                continue

            # Честный replay: только прошлое
            df_past = df_m15.iloc[: t + 1]
            df_h1_past = df_h1[df_h1["begin"] <= bar_ts]
            df_h4_past = df_h4[df_h4["begin"] <= bar_ts]

            try:
                result = analyze_from_df(
                    df=df_past,
                    df_h1=df_h1_past if not df_h1_past.empty else None,
                    df_h4=df_h4_past if not df_h4_past.empty else None,
                    df_atr=df_h1_past if not df_h1_past.empty else None,
                    symbol=symbol,
                    timeframe="M15",
                    timestamp=bar_dt,
                    skip_age_check=True,
                    write_history=False,
                )
            except Exception as e:
                log.debug("[%s] analyze_from_df упал: %s", bar_ts, e)
                continue

            if result is None or not result.signals:
                continue

            for sig in result.signals:
                # Одна открытая сделка на направление
                if any(ot["signal"].direction == sig.direction for ot in open_trades):
                    continue
                open_trades.append({"signal": sig, "entry_idx": t})

        # --- Резолв оставшихся ---
        for ot in open_trades:
            df_future = df_m15.iloc[ot["entry_idx"] + 1 :]
            res = _resolve(ot["signal"], df_future, inst)
            if res["result"] not in ("open", "no_data"):
                trades.append(res)

    finally:
        for key, val in saved.items():
            if val is not None:
                setattr(config, key, val)

    return _aggregate(trades)


def _aggregate(trades: list[dict]) -> dict:
    w = sum(1 for t in trades if t["result"] == "win")
    l = sum(1 for t in trades if t["result"] == "loss")
    to = sum(1 for t in trades if t["result"] == "timeout")
    pts = sum(t["points"] for t in trades)
    rub = sum(t["rub"] for t in trades)

    win_rub = sum(t["rub"] for t in trades if t["result"] == "win")
    loss_rub = abs(sum(t["rub"] for t in trades if t["result"] == "loss"))
    pf = round(win_rub / loss_rub, 2) if loss_rub > 0 else None

    closed_wl = w + l
    exp = round(pts / closed_wl, 1) if closed_wl > 0 else None
    winrate = round(100 * w / closed_wl, 1) if closed_wl > 0 else None

    return {
        "total": len(trades),
        "win": w,
        "loss": l,
        "timeout": to,
        "winrate": winrate,
        "points": round(pts, 1),
        "rub": round(rub, 2),
        "pf": pf,
        "exp": exp,
    }


# ============================================================
# Main
# ============================================================


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Backtest paper-логики")
    parser.add_argument("--since", required=True, help="YYYY-MM-DD")
    parser.add_argument("--until", required=True, help="YYYY-MM-DD")
    parser.add_argument("--symbol", default=config.SYMBOL)
    parser.add_argument("--breakout-filter", default=None, help="none|F1|F2|F3|F4")
    parser.add_argument(
        "--skip-breakout", action="store_true", help="PAPER_SKIP_BREAKOUT=True"
    )
    parser.add_argument(
        "--compare", action="store_true", help="Сравнить baseline vs F1–F4"
    )
    args = parser.parse_args()

    print(f"\n=== Backtest {args.since} -> {args.until} ({args.symbol}) ===")

    df_m15 = _load_candles(args.since, args.until, "M15")
    if df_m15.empty:
        print("❌ Нет M15-свечей за период")
        return
    print(f"  M15: {len(df_m15)} свечей")

    df_h1 = _load_candles(args.since, args.until, "H1")
    df_h4 = _load_candles(args.since, args.until, "H4")
    print(f"  H1:  {len(df_h1)} свечей | H4: {len(df_h4)} свечей")

    if args.compare:
        variants = [
            # (name, filter_name, skip_breakout, skip_filters)
            ("current_config", None, False, False),  # как в Y (с PAPER_SKIP_*)
            ("baseline", None, False, True),  # чисто, без PAPER_SKIP_*
            ("skip_breakout", None, True, True),  # без breakout, чисто
            ("F1 ADX>=25", "F1", False, True),
            ("F2 ADX<20", "F2", False, True),
            ("F3 impulse", "F3", False, True),
            ("F4 week_trend", "F4", False, True),
        ]
        rows = []
        for name, flt, skip, skip_f in variants:
            res = run_backtest(
                df_m15, df_h1, df_h4, args.symbol,
                filter_name=flt, skip_breakout=skip, skip_filters=skip_f,
            )
            rows.append((name, res))

        print("\n-- Сравнение --")
        print(
            f"  {'variant':16} {'n':>4} {'W':>3} {'L':>3} {'T':>3} "
            f"{'pts':>8} {'rub':>9} {'PF':>5} {'exp':>7}"
        )
        for name, res in rows:
            print(
                f"  {name:16} {res['total']:>4} {res['win']:>3} "
                f"{res['loss']:>3} {res['timeout']:>3} "
                f"{res['points']:>+8.1f} {res['rub']:>+9.2f} "
                f"{str(res['pf']):>5} {str(res['exp']):>7}"
            )
        return

    res = run_backtest(
        df_m15,
        df_h1,
        df_h4,
        args.symbol,
        filter_name=args.breakout_filter,
        skip_breakout=args.skip_breakout,
    )
    print("\n-- Результат --")
    print(
        f"  n={res['total']} W={res['win']} L={res['loss']} T={res['timeout']} "
        f"winrate={res['winrate']}%"
    )
    print(
        f"  pts={res['points']:+.1f} rub={res['rub']:+.2f} "
        f"PF={res['pf']} exp={res['exp']}"
    )


if __name__ == "__main__":
    main()
