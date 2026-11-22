"""Bucket-функции и группировка с bootstrap CI для аналитики."""

from core.instruments import get_instrument


def _score_bucket(score):
    if score is None:
        return "unknown"
    if score >= 3.0:
        return "3.0+"
    if score >= 2.5:
        return "2.5"
    if score >= 2.0:
        return "2.0"
    if score >= 1.5:
        return "1.5"
    return "1.0"


def _rsi_bucket(rsi):
    if rsi is None:
        return "unknown"
    if rsi < 30:
        return "<30 (oversold)"
    if rsi < 50:
        return "30-50"
    if rsi < 70:
        return "50-70"
    return ">70 (overbought)"


def _atr_pct_bucket(pct):
    if pct is None:
        return "unknown"
    if pct < 0.25:
        return "<0.25 (low)"
    if pct > 0.75:
        return ">0.75 (high)"
    return "0.25-0.75"


def _adx_bucket(adx):
    if adx is None:
        return "unknown"
    if adx < 20:
        return "flat (<20)"
    if adx < 25:
        return "trend (20-25)"
    return "strong (>25)"


def _pressure_bucket(bid, ask):
    if bid is None or ask is None:
        return "unknown"
    total = bid + ask
    if total <= 0:
        return "unknown"
    pct = bid / total * 100
    if pct < 40:
        return "ask-heavy (<40)"
    if pct > 60:
        return "bid-heavy (>60)"
    return "balanced (40-60)"


def _bars_bucket(bars):
    if bars is None:
        return "unknown"
    if bars <= 3:
        return "1-3"
    if bars <= 10:
        return "4-10"
    if bars <= 30:
        return "11-30"
    return "30+"


def _volume_bucket(vr):
    if vr is None:
        return "unknown"
    if vr < 0.8:
        return "<0.8 (низкий)"
    if vr <= 1.2:
        return "0.8-1.2 (средний)"
    if vr <= 2.0:
        return "1.2-2.0 (высокий)"
    return ">2.0 (очень высокий)"


def _partial_day_bucket(val):
    if val is None:
        return "unknown"
    if val:
        return "partial (до 18:00)"
    return "full day"


def _mae_ratio_bucket(ratio):
    if ratio is None:
        return "unknown"
    if ratio < 0.3:
        return "<0.3 (стоп далеко)"
    if ratio <= 0.7:
        return "0.3-0.7 (норм)"
    if ratio < 1.0:
        return "0.7-1.0 (почти стоп)"
    return ">=1.0 (был бы пробит)"


def _mfe_ratio_bucket(ratio):
    if ratio is None:
        return "unknown"
    if ratio < 0.3:
        return "<0.3 (не дошла)"
    if ratio <= 0.7:
        return "0.3-0.7 (частично)"
    return ">0.7 (почти/дошла)"


def _session_bucket(created_at_str):
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(created_at_str)
    except Exception:
        return "unknown"
    h = dt.hour
    if 9 <= h < 12:
        return "morning (09-12)"
    if 12 <= h < 17:
        return "day (12-17)"
    if 17 <= h < 20:
        return "evening (17-20)"
    return "night (20-09)"


def _hour_bucket(created_at_str):
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(created_at_str)
        return f"{dt.hour:02d}:00"
    except Exception:
        return "unknown"


def _weekday_bucket(created_at_str):
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(created_at_str)
        return dt.strftime("%a")
    except Exception:
        return "unknown"


def _group_with_ci(rows, key_fn, *, min_n: int = 5):
    """
    Группировка с bootstrap CI для каждого бакета.
    Возвращает {bucket: {total, win, loss, timeout, points, rub,
                          pf_ci, exp_ci, winrate_ci}}.
    """
    from trader.bootstrap import (
        _bootstrap_ci,
        _pf_from_points,
        _exp_from_points,
        _winrate_from_points,
    )

    result = {}
    for r in rows:
        bucket = key_fn(r)
        if bucket not in result:
            result[bucket] = {
                "total": 0,
                "win": 0,
                "loss": 0,
                "timeout": 0,
                "points": 0.0,
                "rub": 0.0,
                "_wl_points": [],
            }
        b = result[bucket]
        b["total"] += 1
        if r["result"] in ("win", "loss", "timeout"):
            b[r["result"]] += 1
        b["points"] += r["result_points"] or 0
        b["rub"] += r["result_rub"] or 0
        if r["result"] in ("win", "loss") and r["result_points"] is not None:
            b["_wl_points"].append(r["result_points"])

    for b in result.values():
        b["points"] = round(b["points"], 1)
        b["rub"] = round(b["rub"], 2)
        wl = b.pop("_wl_points")
        if len(wl) >= min_n:
            b["pf_ci"] = _bootstrap_ci(wl, _pf_from_points)
            b["exp_ci"] = _bootstrap_ci(wl, _exp_from_points)
            b["winrate_ci"] = _bootstrap_ci(wl, _winrate_from_points)
        else:
            b["pf_ci"] = b["exp_ci"] = b["winrate_ci"] = None
    return result
