"""
Replay свечей из candles_*.json через analyze_from_df.
Сравнивает с analysis_*.json (сигналы).

Использование:
    python scripts/verify_candles.py --date 2026-11-13
"""

import sys
from pathlib import Path

# --- Добавляем корень проекта в sys.path ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
from datetime import datetime

import pandas as pd

import config
from core.analyzer import analyze_from_df
from core.logger import setup_logging, get_logger

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
    """candles из snapshot → DataFrame."""
    rows = snapshot.get("candles", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["begin"] = pd.to_datetime(df["begin"])
    return df.sort_values("begin").reset_index(drop=True)


def _df_before(df, ts, count=None, exclude_current=True):
    if df is None or df.empty or "begin" not in df.columns:
        return pd.DataFrame()
    df = df[df["begin"] < ts]
    if exclude_current and len(df) > 0:
        # исключаем свечу, которая соответствует ts (незакрытая в live)
        last_begin = df["begin"].iloc[-1]
        if last_begin >= ts - pd.Timedelta(minutes=15):
            df = df.iloc[:-1]
    if count is not None:
        df = df.tail(count)
    return df.reset_index(drop=True)


def replay_date(date_str: str) -> dict:
    date_dir = LOGS_DIR / date_str
    if not date_dir.exists():
        log.error("Папка не найдена: %s", date_dir)
        return {}

    analysis = _load_json(date_dir / f"analysis_{date_str}.json")
    if not analysis or not analysis.get("snapshots"):
        log.error("Нет analysis snapshots для %s", date_str)
        return {}

    # Свечи по ТФ: берём последний snapshot каждого
    candles_by_tf = {}
    for tf in ("M15", "H1", "H4"):
        path = date_dir / f"candles_{tf}_{date_str}.json"
        data = _load_json(path)
        if data and data.get("snapshots"):
            last = data["snapshots"][-1]
            candles_by_tf[tf] = _df_from_snapshot(last)

    # --- Fallback: если H1/H4 нет в candles_*.json — тянем из market.db ---
    from data.api_facade import get_candles_tf

    h1_df = candles_by_tf.get("H1")
    if h1_df is None or h1_df.empty:
        log.info("H1 нет в candles_*.json — тянем из market.db")
        try:
            candles_by_tf["H1"] = get_candles_tf("H1", count=300)
        except Exception as e:
            log.warning("Не удалось получить H1: %s", e)

    h4_df = candles_by_tf.get("H4")
    if h4_df is None or h4_df.empty:
        log.info("H4 нет в candles_*.json — тянем из market.db")
        try:
            candles_by_tf["H4"] = get_candles_tf("H4", count=300)
        except Exception as e:
            log.warning("Не удалось получить H4: %s", e)

    m15_df = candles_by_tf.get("M15")
    if m15_df is None or m15_df.empty:
        log.error("Нет M15 свечей для %s", date_str)
        return {}

    results = {"date": date_str, "snapshots": [], "summary": {}}
    mismatches = 0
    total_signals_analysis = 0
    total_signals_replay = 0
    matched = 0

    for snap in analysis["snapshots"]:
        sigs_analysis = snap.get("signals") or []
        if not sigs_analysis:
            continue

        ts_str = snap.get("timestamp")
        if not ts_str:
            continue
        ts = datetime.fromisoformat(ts_str)

        df_m15 = _df_before(candles_by_tf["M15"], ts, count=300, exclude_current=False)
        df_h1 = _df_before(
            candles_by_tf["H1"], ts, count=None, exclude_current=False
        )  # H1 — не критично
        df_h4 = _df_before(candles_by_tf["H4"], ts, count=None, exclude_current=False)

        if df_m15.empty:
            continue

        # --- DEBUG ---
        print(
            f"[{ts_str}] M15={len(df_m15)} H1={len(df_h1)} H4={len(df_h4)} | "
            f"m15_last={df_m15['begin'].iloc[-1] if not df_m15.empty else '—'} | "
            f"h1_last={df_h1['begin'].iloc[-1] if not df_h1.empty else '—'}"
        )

        result = analyze_from_df(
            df=df_m15,
            df_h1=df_h1 if not df_h1.empty else None,
            df_h4=df_h4 if not df_h4.empty else None,
            df_atr=df_h1 if not df_h1.empty else None,
            symbol=analysis.get("symbol"),
            timeframe=analysis.get("timeframe"),
            timestamp=ts,
            skip_age_check=True,
            skip_filters=True,
            write_history=False,
        )

        sigs_replay = result.signals if result else []

        # Сравнение с допуском по entry (0.5 ATR)
        atr = result.atr if result else 0.0
        tol = 0.5 * atr

        # Сравниваем только direction + entry (kind — look-ahead M15)
        a_set = {(s["direction"], s["entry_price"]) for s in sigs_analysis}
        r_set = {(s.direction, s.entry_price) for s in sigs_replay}

        def _match_sets(a_set, r_set, tol):
            matched_set = set()
            only_a = set()
            for a in a_set:
                found = False
                for r in r_set:
                    if a[0] == r[0] and abs(a[1] - r[1]) <= tol:
                        matched_set.add(a)
                        found = True
                        break
                if not found:
                    only_a.add(a)
            only_r = set()
            for r in r_set:
                found = False
                for a in a_set:
                    if a[0] == r[0] and abs(a[1] - r[1]) <= tol:
                        found = True
                        break
                if not found:
                    only_r.add(r)
            return matched_set, only_a, only_r

        match, only_a, only_r = _match_sets(a_set, r_set, tol)
        match_out = [(x[0], round(x[1], 3)) for x in match]
        only_a_out = [(x[0], round(x[1], 3)) for x in only_a]
        only_r_out = [(x[0], round(x[1], 3)) for x in only_r]

        total_signals_analysis += len(a_set)
        total_signals_replay += len(r_set)
        matched += len(match)
        if only_a or only_r:
            mismatches += 1

        results["snapshots"].append(
            {
                "timestamp": ts_str,
                "analysis": [(x[0], round(x[1], 3)) for x in a_set],
                "replay": [(x[0], round(x[1], 3)) for x in r_set],
                "match": match_out,
                "only_analysis": only_a_out,
                "only_replay": only_r_out,
            }
        )

    results["summary"] = {
        "snapshots_with_signals": len(results["snapshots"]),
        "mismatches": mismatches,
        "signals_analysis": total_signals_analysis,
        "signals_replay": total_signals_replay,
        "matched": matched,
        "match_rate_pct": round(100 * matched / max(total_signals_analysis, 1), 1),
    }

    return results


def main():
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Replay candles и сравнение с analysis"
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    res = replay_date(args.date)

    print()
    print(f"═══ Replay {args.date} ═══")
    s = res.get("summary", {})
    print(f"  Snapshots with signals: {s.get('snapshots_with_signals', 0)}")
    print(f"  Mismatches:             {s.get('mismatches', 0)}")
    print(f"  Signals analysis:       {s.get('signals_analysis', 0)}")
    print(f"  Signals replay:         {s.get('signals_replay', 0)}")
    print(f"  Matched:                {s.get('matched', 0)}")
    print(f"  Match rate:             {s.get('match_rate_pct', 0)}%")
    print()

    for snap in res.get("snapshots", []):
        if snap["only_analysis"] or snap["only_replay"]:
            print(f"  [{snap['timestamp']}]")
            if snap["only_analysis"]:
                print(f"    only analysis: {snap['only_analysis']}")
            if snap["only_replay"]:
                print(f"    only replay:   {snap['only_replay']}")


if __name__ == "__main__":
    main()
