"""
Backfill MFE/MAE для старых paper_trades по candles_*.json.

Использование:
    python scripts/backfill_mfe_mae.py
    python scripts/backfill_mfe_mae.py --dry-run
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
from datetime import datetime

import pandas as pd

import config
from core.logger import setup_logging, get_logger
from trader.journal import connect_journal
from trader.paper import init_paper_table, virtual_pnl
from core.instruments import get_instrument, compute_trade_result

log = get_logger(__name__)

LOGS_DIR = Path(config.LOG_PATH).parent


def _load_candles_for_date(date_str: str, tf: str = "M15") -> pd.DataFrame:
    """Читает candles_<tf>_<date>.json, склеивает snapshots, дедуп по begin."""
    path = LOGS_DIR / date_str / f"candles_{tf}_{date_str}.json"
    if not path.exists():
        return pd.DataFrame()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.warning("Не удалось прочитать %s: %s", path, e)
        return pd.DataFrame()

    frames = []
    for snap in data.get("snapshots", []):
        rows = snap.get("candles", [])
        if rows:
            frames.append(pd.DataFrame(rows))

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["begin"] = pd.to_datetime(df["begin"])
    df = (
        df.drop_duplicates(subset=["begin"]).sort_values("begin").reset_index(drop=True)
    )
    return df


def _backfill_one(trade: dict, inst, use_market_price: bool = False) -> dict | None:
    """
    Возвращает dict с mfe_points/mae_points/mfe_source/mae_source или None.
    """
    created_at = datetime.fromisoformat(trade["created_at"])
    closed_at = None
    if trade["closed_at"]:
        try:
            closed_at = datetime.fromisoformat(trade["closed_at"])
        except Exception:
            pass

    # Определяем дату (сделка могла перейти через полночь)
    dates = {created_at.strftime("%Y-%m-%d")}
    if closed_at:
        dates.add(closed_at.strftime("%Y-%m-%d"))

    frames = []
    for d in dates:
        df = _load_candles_for_date(d)
        if not df.empty:
            frames.append(df)

    if not frames:
        return {"mfe_source": "unavailable", "mae_source": "unavailable"}

    df = pd.concat(frames, ignore_index=True)
    df = (
        df.drop_duplicates(subset=["begin"]).sort_values("begin").reset_index(drop=True)
    )

    # Свечи строго после created_at
    df_future = df[df["begin"] > created_at]
    if closed_at:
        df_future = df_future[df_future["begin"] <= closed_at]
    df_future = df_future.head(config.PAPER_TIMEOUT_BARS + 5)

    if df_future.empty:
        return {"mfe_source": "unavailable", "mae_source": "unavailable"}

    # T-24b: entry = market_price_at_open (фактическая цена), если флаг и есть
    entry = trade["entry_price"]
    if use_market_price and trade.get("market_price_at_open") is not None:
        entry = trade["market_price_at_open"]

    pnl = virtual_pnl(
        df_future,
        trade["direction"],
        entry,
        trade["stop_price"],
        trade["take_price"],
        max_bars=config.PAPER_TIMEOUT_BARS,
        price_step=inst.price_step,
    )

    # T-24b: маркер источника, чтобы paper-stats мог отличать
    src = "backfill"
    if use_market_price and trade.get("market_price_at_open") is not None:
        if abs(trade["market_price_at_open"] - trade["entry_price"]) > 0.0001:
            src = "backfill_market_price"
    return {
        "mfe_points": pnl["mfe_points"],
        "mae_points": pnl["mae_points"],
        "mfe_source": src,
        "mae_source": src,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill MFE/MAE")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD (включительно)")
    parser.add_argument("--until", default=None, help="YYYY-MM-DD (включительно)")
    parser.add_argument(
        "--use-market-price",
        action="store_true",
        help="T-24b: entry = market_price_at_open (не entry_price/close)",
    )
    args = parser.parse_args()
    setup_logging()

    with connect_journal() as conn:
        init_paper_table(conn)
        where = [
            "result IN ('win', 'loss', 'timeout')",
            "(mfe_source IS NULL OR mfe_source != 'live')",
        ]
        params = []

        if args.use_market_price:
            # T-24b: пересчитать ВСЕ с market_price != entry, не только no_mfe
            where.append("market_price_at_open IS NOT NULL")
            where.append("abs(market_price_at_open - entry_price) > 0.0001")
        else:
            # старое поведение: только сделки без MFE
            where.append("mfe_points IS NULL")

        if args.since:
            where.append("date(created_at) >= ?")
            params.append(args.since)
        if args.until:
            where.append("date(created_at) <= ?")
            params.append(args.until)

        sql = "SELECT * FROM paper_trades WHERE " + " AND ".join(where)
        rows = conn.execute(sql, params).fetchall()

        if not rows:
            print("Нет сделок для backfill.")
            return

        print(f"Сделок для backfill: {len(rows)}")
        inst = get_instrument(config.DEFAULT_INSTRUMENT)

        updated = 0
        unavailable = 0
        for row in rows:
            trade = dict(row)
            res = _backfill_one(trade, inst, use_market_price=args.use_market_price)
            if res is None:
                continue

            if res["mfe_source"] == "unavailable":
                unavailable += 1
                if args.dry_run:
                    print(f"  #{trade['id']} {trade['created_at'][:10]}: unavailable")
                else:
                    conn.execute(
                        "UPDATE paper_trades SET mfe_source='unavailable', mae_source='unavailable' WHERE id=?",
                        (trade["id"],),
                    )
            else:
                updated += 1
                if args.dry_run:
                    print(
                        f"  #{trade['id']} {trade['created_at'][:10]}: "
                        f"mfe {trade['mfe_points']}→{res['mfe_points']} "
                        f"mae {trade['mae_points']}→{res['mae_points']} "
                        f"src={res['mfe_source']}"
                    )
                else:
                    conn.execute(
                        """UPDATE paper_trades
                           SET mfe_points=?, mae_points=?, mfe_source=?, mae_source=?
                           WHERE id=?""",
                        (
                            res["mfe_points"],
                            res["mae_points"],
                            res["mfe_source"],
                            res["mae_source"],
                            trade["id"],
                        ),
                    )

        if not args.dry_run:
            conn.commit()

    print(f"Backfill: {updated} обновлено, {unavailable} unavailable")
    if args.dry_run:
        print("(dry-run, без записи в БД)")


if __name__ == "__main__":
    main()
