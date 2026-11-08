"""
Подбор STOP_ATR_MULT / TAKE_ATR_MULT на исторических paper-сделках.

Берёт закрытые и открытые сделки из paper_trades, восстанавливает ATR(H1)
на момент входа из take_price (take = entry ± TAKE_ATR_MULT × atr),
переигрывает каждую сделку с новыми множителями по реальным M15-свечам
и агрегирует winrate / PF / expectancy / total PnL.

Запуск:
    python scripts/backtest_stops.py
    python scripts/backtest_stops.py --db=storage/journal.db --since=2026-10-17
    python scripts/backtest_stops.py --grid=0.5,1.0 0.7,1.4 1.0,2.0

НЕ меняет БД. Только читает и печатает.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Позволяем запускать из корня репо
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.api_facade import get_candles_tf
from trader.paper import virtual_pnl
import config

# ============================================================
# Загрузка сделок
# ============================================================


def load_trades(db_path: str, since: str | None, symbol: str) -> list[dict]:
    """Читает paper_trades (все, кроме 'open' без created_at)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    where = ["symbol = ?"]
    params: list = [symbol]
    if since:
        where.append("created_at >= ?")
        params.append(since)

    rows = conn.execute(
        f"""
        SELECT id, symbol, direction, kind, entry_price, stop_price,
               take_price, created_at, result, result_points, result_rub
        FROM paper_trades
        WHERE {' AND '.join(where)}
        ORDER BY created_at
        """,
        params,
    ).fetchall()
    conn.close()

    return [dict(r) for r in rows]


# ============================================================
# Восстановление ATR из take_price
# ============================================================


def restore_atr(trade: dict, base_take_mult: float) -> float | None:
    """
    take = entry ± base_take_mult × atr  ⇒  atr = |take - entry| / base_take_mult

    base_take_mult — TAKE_ATR_MULT, с которым сделка была создана
    (по умолчанию 2.0 — так было во всех ветках).
    """
    entry = trade["entry_price"]
    take = trade["take_price"]
    if entry is None or take is None:
        return None
    dist = abs(take - entry)
    if dist <= 0 or base_take_mult <= 0:
        return None
    return dist / base_take_mult


# ============================================================
# Переигровка одной сделки
# ============================================================


def replay_trade(
    trade: dict,
    atr: float,
    stop_mult: float,
    take_mult: float,
    df_m15: pd.DataFrame,
    timeout_bars: int,
) -> dict | None:
    """
    Считает stop/take от entry с новыми множителями и прогоняет virtual_pnl
    по свечам после created_at.

    Возвращает dict с result / points / bars / exit_price или None, если
    нет данных для переигровки.
    """
    entry = trade["entry_price"]
    direction = trade["direction"]
    created_at = datetime.fromisoformat(trade["created_at"])

    if direction == "long":
        new_stop = entry - stop_mult * atr
        new_take = entry + take_mult * atr
    else:
        new_stop = entry + stop_mult * atr
        new_take = entry - take_mult * atr

    df_future = df_m15[df_m15["begin"] > created_at].copy()
    if len(df_future) == 0:
        return None

    pnl = virtual_pnl(
        df_future,
        direction,
        entry,
        new_stop,
        new_take,
        max_bars=timeout_bars,
    )

    # Конвертация в пункты (как в compute_trade_result: points = (exit-entry)/step)
    exit_price = pnl["exit_price"]
    if exit_price is None:
        return None  # open — не учитываем в агрегатах

    # points в «шагах цены» — как в paper_trades.result_points.
    # compute_trade_result использует (exit-entry)/price_step для long,
    # (entry-exit)/price_step для short — но там price_step из инструмента.
    # Здесь проще: pts = (exit - entry) / price_step для long,
    # (entry - exit) / price_step для short.
    inst_price_step = config.PRICE_STEP  # 0.001 для CNYRUBF
    if direction == "long":
        pts = (exit_price - entry) / inst_price_step
    else:
        pts = (entry - exit_price) / inst_price_step

    return {
        "result": pnl["result"],
        "exit_price": exit_price,
        "points": round(pts, 1),
        "bars": pnl["bars"],
        "stop": new_stop,
        "take": new_take,
    }


# ============================================================
# Агрегация
# ============================================================


def aggregate(replayed: list[dict]) -> dict:
    """winrate, PF, expectancy, total_points по списку переигранных сделок."""
    wins = [r for r in replayed if r["result"] == "win"]
    losses = [r for r in replayed if r["result"] == "loss"]
    timeouts = [r for r in replayed if r["result"] == "timeout"]

    win_pts = sum(r["points"] for r in wins)
    loss_pts = sum(r["points"] for r in losses)
    total_pts = sum(r["points"] for r in replayed)
    total_rub = sum(r["points"] * config.STEP_COST for r in replayed)

    closed_wl = len(wins) + len(losses)
    winrate = round(100 * len(wins) / closed_wl, 1) if closed_wl else None

    avg_win = round(win_pts / len(wins), 1) if wins else None
    avg_loss = round(loss_pts / len(losses), 1) if losses else None

    profit_factor = None
    if loss_pts != 0:
        profit_factor = round(win_pts / abs(loss_pts), 2)

    expectancy = None
    if winrate is not None and avg_win is not None and avg_loss is not None:
        p = winrate / 100
        expectancy = round(p * avg_win + (1 - p) * avg_loss, 1)

    return {
        "total": len(replayed),
        "win": len(wins),
        "loss": len(losses),
        "timeout": len(timeouts),
        "winrate": winrate,
        "total_points": round(total_pts, 1),
        "total_rub": round(total_rub, 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
    }


# ============================================================
# main
# ============================================================


def parse_grid(s: str) -> list[tuple[float, float]]:
    """'0.5,1.0 0.7,1.4' -> [(0.5,1.0), (0.7,1.4)]"""
    result = []
    for pair in s.split():
        stop_s, take_s = pair.split(",")
        result.append((float(stop_s), float(take_s)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="storage/journal.db")
    parser.add_argument("--symbol", default="CNYRUBF")
    parser.add_argument("--since", default=None)
    parser.add_argument(
        "--base-take-mult",
        type=float,
        default=2.0,
        help="TAKE_ATR_MULT, с которым создавались сделки (для восстановления ATR)",
    )
    parser.add_argument(
        "--grid",
        default="1.0,2.0 0.7,1.4 0.5,1.0 0.3,0.6",
        help="пары 'stop_mult,take_mult' через пробел",
    )
    parser.add_argument(
        "--timeout-bars",
        type=int,
        default=config.PAPER_TIMEOUT_BARS,
        help="сколько M15-свечей ждать (по умолчанию из config)",
    )
    args = parser.parse_args()

    # --- 1. Сделки ---
    trades = load_trades(args.db, args.since, args.symbol)
    if not trades:
        print(f"❌ Нет сделок в {args.db} (symbol={args.symbol})")
        return 1

    print(f"Всего сделок: {len(trades)}")
    print(f"  закрытых: {sum(1 for t in trades if t['result'] in ('win', 'loss'))}")
    print(f"  timeout:  {sum(1 for t in trades if t['result'] == 'timeout')}")
    print(f"  open:     {sum(1 for t in trades if t['result'] == 'open')}")
    print()

    # --- 2. Свечи ---
    # Хватит на весь период, если сделки за месяц: ~30 дней × 96 M15 ≈ 3000.
    # Берём с запасом, но не больше, чем API готов отдать.
    print("Загружаю M15-свечи...")
    df_m15 = get_candles_tf("M15", count=5000)
    if df_m15 is None or len(df_m15) == 0:
        print("❌ Нет M15-свечей")
        return 1
    print(
        f"  свечей: {len(df_m15)}  [{df_m15['begin'].iloc[0]} .. {df_m15['begin'].iloc[-1]}]"
    )
    print()

    # --- 3. Восстановление ATR ---
    trades_with_atr = []
    skipped_no_atr = 0
    for t in trades:
        atr = restore_atr(t, args.base_take_mult)
        if atr is None:
            skipped_no_atr += 1
            continue
        t["_atr"] = atr
        trades_with_atr.append(t)

    if skipped_no_atr:
        print(f"⚠ Пропущено без ATR: {skipped_no_atr}")
    print(f"С восстановленным ATR: {len(trades_with_atr)}")
    print()

    # --- 4. Базовый прогон (текущие множители) ---
    print("=" * 70)
    print("БАЗОВЫЙ ПРОГОН (как было)")
    print("=" * 70)
    base_replayed = []
    for t in trades_with_atr:
        r = replay_trade(
            t,
            t["_atr"],
            args.base_take_mult / 2,
            args.base_take_mult,
            df_m15,
            args.timeout_bars,
        )
        if r:
            r["_id"] = t["id"]
            base_replayed.append(r)

    base = aggregate(base_replayed)
    print(
        f"  сделок: {base['total']}  "
        f"W/L/T: {base['win']}/{base['loss']}/{base['timeout']}"
    )
    print(
        f"  winrate: {base['winrate']}%  "
        f"PF: {base['profit_factor']}  "
        f"expectancy: {base['expectancy']} pts"
    )
    print(f"  total: {base['total_points']} pts / {base['total_rub']} ₽")
    print()

    # --- 5. Сетка ---
    grid = parse_grid(args.grid)
    print("=" * 70)
    print("ПОДБОР (stop_mult, take_mult)")
    print("=" * 70)
    print(f"  timeout_bars = {args.timeout_bars}")

    header = (
        f"{'stop':>6} {'take':>6} | "
        f"{'total':>5} {'W':>3} {'L':>3} {'T':>3} | "
        f"{'winrate':>8} {'PF':>5} {'exp':>7} | "
        f"{'pts':>8} {'rub':>9}"
    )
    print(header)
    print("-" * len(header))

    results = []
    for stop_mult, take_mult in grid:
        replayed = []
        for t in trades_with_atr:
            r = replay_trade(
                t,
                t["_atr"],
                stop_mult,
                take_mult,
                df_m15,
                args.timeout_bars,
            )
            if r:
                replayed.append(r)

        agg = aggregate(replayed)
        results.append((stop_mult, take_mult, agg))
        print(
            f"{stop_mult:>6.2f} {take_mult:>6.2f} | "
            f"{agg['total']:>5} {agg['win']:>3} {agg['loss']:>3} {agg['timeout']:>3} | "
            f"{str(agg['winrate']) + '%':>8} "
            f"{str(agg['profit_factor']):>5} "
            f"{str(agg['expectancy']):>7} | "
            f"{agg['total_points']:>+8.1f} {agg['total_rub']:>+9.2f}"
        )

    # --- 6. Лучший вариант ---
    valid = [
        r for r in results if r[2]["profit_factor"] is not None and r[2]["total"] >= 5
    ]
    if valid:
        best = max(valid, key=lambda r: r[2]["profit_factor"])
        print()
        print("=" * 70)
        print(f"ЛУЧШИЙ ПО PF: stop={best[0]} take={best[1]}")
        print(
            f"  PF={best[2]['profit_factor']}  "
            f"expectancy={best[2]['expectancy']}  "
            f"winrate={best[2]['winrate']}%  "
            f"total={best[2]['total_points']} pts"
        )
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
