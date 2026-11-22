"""Аналитика по paper_trades: paper_stats."""

import sqlite3

import config
import trader.paper_db as db
from core.instruments import get_instrument
from trader.analytics.group import (
    _score_bucket,
    _rsi_bucket,
    _atr_pct_bucket,
    _adx_bucket,
    _pressure_bucket,
    _bars_bucket,
    _volume_bucket,
    _partial_day_bucket,
    _mae_ratio_bucket,
    _mfe_ratio_bucket,
    _session_bucket,
    _hour_bucket,
    _weekday_bucket,
    _group_with_ci,
)


def paper_stats(
    conn: sqlite3.Connection,
    since: str | None = None,
    until: str | None = None,
    symbol: str | None = None,
    known_only: bool = False,
    min_n: int = 0,
) -> dict:
    """
    Агрегаты по paper_trades. T-04: + bootstrap CI для PF/exp/winrate.
    T-13: + CI в by_score. Рефакторинг: все by_* через _group_with_ci.
    """
    filters = {
        "since": since,
        "until": until,
        "symbol": symbol,
        "known_only": known_only,
    }
    rows = db.get_stats_raw(conn, filters)

    total = len(rows)
    open_count = sum(1 for r in rows if r["result"] == "open")
    win = sum(1 for r in rows if r["result"] == "win")
    loss = sum(1 for r in rows if r["result"] == "loss")
    timeout = sum(1 for r in rows if r["result"] == "timeout")

    closed = win + loss + timeout
    closed_wl = win + loss
    winrate = round(100 * win / closed_wl, 1) if closed_wl > 0 else None

    total_points = round(sum(r["result_points"] or 0 for r in rows), 1)
    total_rub = round(sum(r["result_rub"] or 0 for r in rows), 2)

    win_points = [
        r["result_points"]
        for r in rows
        if r["result"] == "win" and r["result_points"] is not None
    ]
    loss_points = [
        r["result_points"]
        for r in rows
        if r["result"] == "loss" and r["result_points"] is not None
    ]
    avg_win = round(sum(win_points) / len(win_points), 1) if win_points else None
    avg_loss = round(sum(loss_points) / len(loss_points), 1) if loss_points else None

    # --- PF и expectancy ---
    win_rub = sum(r["result_rub"] or 0 for r in rows if r["result"] == "win")
    loss_rub = abs(sum(r["result_rub"] or 0 for r in rows if r["result"] == "loss"))
    profit_factor = round(win_rub / loss_rub, 2) if loss_rub > 0 else None
    expectancy = None
    if winrate is not None and avg_win is not None and avg_loss is not None:
        p = winrate / 100
        expectancy = round(p * avg_win + (1 - p) * avg_loss, 1)

    # --- T-04: Bootstrap CI для total ---
    from trader.bootstrap import (
        _bootstrap_ci,
        _pf_from_points,
        _exp_from_points,
        _winrate_from_points,
    )

    wl_points = [
        r["result_points"]
        for r in rows
        if r["result"] in ("win", "loss") and r["result_points"] is not None
    ]
    if len(wl_points) >= 5:
        pf_ci = _bootstrap_ci(wl_points, _pf_from_points)
        exp_ci = _bootstrap_ci(wl_points, _exp_from_points)
        winrate_ci = _bootstrap_ci(wl_points, _winrate_from_points)
    else:
        pf_ci = exp_ci = winrate_ci = None

    # --- Все разрезы через _group_with_ci (T-13 + рефакторинг) ---
    by_kind = _group_with_ci(rows, lambda r: r["kind"] or "unknown")
    by_trend = _group_with_ci(rows, lambda r: r["trend_at_open"] or "unknown")
    by_day_trend = _group_with_ci(rows, lambda r: r["day_trend_at_open"] or "unknown")
    by_week_trend = _group_with_ci(rows, lambda r: r["week_trend_at_open"] or "unknown")
    by_week_trend_direction = _group_with_ci(
        rows,
        lambda r: f"{r['week_trend_at_open'] or 'unknown'} / {r['direction'] or 'unknown'}",
    )
    by_market_state = _group_with_ci(
        rows, lambda r: r["market_state_at_open"] or "unknown"
    )
    by_rsi = _group_with_ci(rows, lambda r: _rsi_bucket(r["rsi_at_open"]))
    by_atr_percentile = _group_with_ci(
        rows, lambda r: _atr_pct_bucket(r["atr_percentile_at_open"])
    )
    by_score = _group_with_ci(rows, lambda r: _score_bucket(r["strength_score"]))
    by_adx = _group_with_ci(rows, lambda r: _adx_bucket(r["adx_at_open"]))
    by_pressure = _group_with_ci(
        rows, lambda r: _pressure_bucket(r["bid_vol"], r["ask_vol"])
    )
    by_bars = _group_with_ci(rows, lambda r: _bars_bucket(r["bars_to_close"]))
    by_session = _group_with_ci(rows, lambda r: _session_bucket(r["created_at"]))
    by_hour = _group_with_ci(rows, lambda r: _hour_bucket(r["created_at"]))
    by_weekday = _group_with_ci(rows, lambda r: _weekday_bucket(r["created_at"]))
    by_partial_day = _group_with_ci(
        rows, lambda r: _partial_day_bucket(r["partial_day_at_open"])
    )
    by_volume_ratio = _group_with_ci(
        rows, lambda r: _volume_bucket(r["volume_ratio_at_open"])
    )
    by_take_source = _group_with_ci(rows, lambda r: r["take_source"] or "unknown")

    # by_mae_ratio / by_mfe_ratio — специальные (нужен inst)
    def _mae_ratio_key(r):
        mae = r["mae_points"]
        if mae is None:
            return "unknown"
        try:
            inst = get_instrument(r["symbol"])
            stop_dist = abs(r["entry_price"] - r["stop_price"]) / inst.price_step
        except Exception:
            return "unknown"
        if stop_dist <= 0:
            return "unknown"
        return _mae_ratio_bucket(mae / stop_dist)

    def _mfe_ratio_key(r):
        mfe = r["mfe_points"]
        if mfe is None:
            return "unknown"
        try:
            inst = get_instrument(r["symbol"])
            take_dist = abs(r["take_price"] - r["entry_price"]) / inst.price_step
        except Exception:
            return "unknown"
        if take_dist <= 0:
            return "unknown"
        return _mfe_ratio_bucket(mfe / take_dist)

    by_mae_ratio = _group_with_ci(rows, _mae_ratio_key)
    by_mfe_ratio = _group_with_ci(rows, _mfe_ratio_key)

    # --- Виртуальный депозит ---
    closed_rows = [r for r in rows if r["result"] in ("win", "loss")]
    balance_after = config.VIRTUAL_DEPOSIT
    max_balance = config.VIRTUAL_DEPOSIT
    max_drawdown = 0.0

    for r in closed_rows:
        if r["balance_after"] is not None:
            balance_after = r["balance_after"]
            max_balance = max(max_balance, balance_after)
            drawdown = (max_balance - balance_after) / max_balance * 100
            max_drawdown = max(max_drawdown, drawdown)

    final_pnl_pct = (
        (balance_after - config.VIRTUAL_DEPOSIT) / config.VIRTUAL_DEPOSIT * 100
    )

    # --- _enrich / _filter_min_n / _process ---
    def _enrich(bucket_dict: dict) -> dict:
        for v in bucket_dict.values():
            wins = v.get("win", 0)
            losses = v.get("loss", 0)
            total_wl = wins + losses
            v["expectancy"] = round(v["points"] / total_wl, 1) if total_wl > 0 else None
        return bucket_dict

    def _filter_min_n(bucket_dict: dict, min_n: int) -> dict:
        if min_n <= 0:
            return bucket_dict
        return {k: v for k, v in bucket_dict.items() if v.get("total", 0) >= min_n}

    def _process(bucket_dict: dict) -> dict:
        return _filter_min_n(_enrich(bucket_dict), min_n)

    return {
        "total": total,
        "open": open_count,
        "closed": closed,
        "win": win,
        "loss": loss,
        "timeout": timeout,
        "winrate": winrate,
        "total_points": total_points,
        "total_rub": total_rub,
        "avg_win_points": avg_win,
        "avg_loss_points": avg_loss,
        "by_kind": _process(by_kind),
        "by_trend": _process(by_trend),
        "by_day_trend": _process(by_day_trend),
        "by_week_trend": _process(by_week_trend),
        "by_week_trend_direction": _process(by_week_trend_direction),
        "by_market_state": _process(by_market_state),
        "by_rsi": _process(by_rsi),
        "by_atr_percentile": _process(by_atr_percentile),
        "by_score": _process(by_score),
        "by_adx": _process(by_adx),
        "by_pressure": _process(by_pressure),
        "by_bars": _process(by_bars),
        "by_session": _process(by_session),
        "by_hour": _process(by_hour),
        "by_weekday": _process(by_weekday),
        "by_partial_day": _process(by_partial_day),
        "by_volume_ratio": _process(by_volume_ratio),
        "by_mae_ratio": _process(by_mae_ratio),
        "by_mfe_ratio": _process(by_mfe_ratio),
        "by_take_source": _process(by_take_source),
        "virtual_deposit_start": config.VIRTUAL_DEPOSIT,
        "virtual_deposit_end": balance_after,
        "virtual_pnl_pct": round(final_pnl_pct, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "profit_factor_ci": pf_ci,
        "expectancy_ci": exp_ci,
        "winrate_ci": winrate_ci,
    }
