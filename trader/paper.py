"""Paper-tracking сигналов. Виртуальные сделки в storage/journal.db."""

import hashlib
import sqlite3
import json
from datetime import datetime, time
from typing import Optional
from core.logger import get_logger
from core.risk import calculate_position_size
from core.instruments import get_instrument
from typing import Optional, Dict, List
import trader.paper_db as db

import config
import os

# ANSI-цвета. Отключаются только если явно задан NO_COLOR
# (стандарт https://no-color.org/).
_USE_COLOR = not os.environ.get("NO_COLOR")

GREEN = "\033[92m" if _USE_COLOR else ""
RED = "\033[91m" if _USE_COLOR else ""
YELLOW = "\033[93m" if _USE_COLOR else ""
RESET = "\033[0m" if _USE_COLOR else ""

log = get_logger(__name__)


def init_paper_table(conn: sqlite3.Connection) -> None:
    db.init_db(conn)


def _signal_id(signal, symbol: str, created_at: datetime) -> str:
    """sha1 от (symbol, direction, kind, entry, created_at), первые 16 hex."""
    raw = (
        f"{symbol}|{signal.direction}|{signal.kind}|"
        f"{round(signal.entry_price, 5)}|{created_at.isoformat()}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _signal_id_from_dict(s: dict, symbol: str, created_at: datetime) -> str:
    """sha1 для skipped (dict, а не Signal)."""
    raw = (
        f"{symbol}|{s.get('direction')}|{s.get('kind')}|"
        f"{round(s.get('entry_price', 0.0), 5)}|{created_at.isoformat()}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _is_in_paper_hours(dt: datetime) -> bool:
    """
    Проверяет, попадает ли dt в PAPER_TRADING_HOURS.
    Время трактуется как МСК (naive datetime).
    """
    hours = config.PAPER_TRADING_HOURS
    start_h, start_m = map(int, hours["start"].split(":"))
    end_h, end_m = map(int, hours["end"].split(":"))

    t = dt.time()
    return time(start_h, start_m) <= t < time(end_h, end_m)


def virtual_pnl(
    df_future,
    direction: str,
    entry: float,
    stop: float,
    take: float,
    max_bars: int = None,
    price_step: float = 0.001,
) -> dict:
    """
    Считает виртуальный PnL по свечам вперёд + MFE/MAE.

    MFE (max favorable excursion) — максимум в пользу позиции (в пунктах).
    MAE (max adverse excursion) — максимум против позиции (в пунктах).

    Возвращает:
        {
            "result": "win" / "loss" / "timeout" / "open" / "no_data",
            "exit_price": float | None,
            "bars": int,
            "ambiguous": bool,
            "mfe_points": float,   # >= 0
            "mae_points": float,   # >= 0 (по модулю)
        }
    """
    import pandas as pd

    empty = {
        "result": "no_data",
        "exit_price": None,
        "bars": 0,
        "ambiguous": False,
        "mfe_points": 0.0,
        "mae_points": 0.0,
    }

    if max_bars is None:
        max_bars = config.PAPER_TIMEOUT_BARS

    if df_future is None or len(df_future) == 0:
        return empty

    mfe = 0.0  # max favorable (в пунктах, >= 0)
    mae = 0.0  # max adverse (в пунктах, >= 0)

    for i, row in enumerate(df_future.itertuples(), 1):
        high = row.high
        low = row.low

        # --- MFE/MAE по этой свече ---
        if direction == "long":
            fav = (high - entry) / price_step  # в пользу long
            adv = (entry - low) / price_step  # против long
        else:  # short
            fav = (entry - low) / price_step  # в пользу short
            adv = (high - entry) / price_step  # против short

        if fav > mfe:
            mfe = fav
        if adv > mae:
            mae = adv

        # --- Проверка take/stop ---
        if direction == "long":
            hit_take = high >= take
            hit_stop = low <= stop
        else:
            hit_take = low <= take
            hit_stop = high >= stop

        if hit_take and hit_stop:
            return {
                "result": "loss",
                "exit_price": stop,
                "bars": i,
                "ambiguous": True,
                "mfe_points": round(mfe, 1),
                "mae_points": round(mae, 1),
            }

        if hit_take:
            return {
                "result": "win",
                "exit_price": take,
                "bars": i,
                "ambiguous": False,
                "mfe_points": round(mfe, 1),
                "mae_points": round(mae, 1),
            }

        if hit_stop:
            return {
                "result": "loss",
                "exit_price": stop,
                "bars": i,
                "ambiguous": False,
                "mfe_points": round(mfe, 1),
                "mae_points": round(mae, 1),
            }

        if i >= max_bars:
            return {
                "result": "timeout",
                "exit_price": float(row.close),
                "bars": i,
                "ambiguous": False,
                "mfe_points": round(mfe, 1),
                "mae_points": round(mae, 1),
            }

    return {
        "result": "open",
        "exit_price": None,
        "bars": len(df_future),
        "ambiguous": False,
        "mfe_points": round(mfe, 1),
        "mae_points": round(mae, 1),
    }


def _is_duplicate(
    conn: sqlite3.Connection,
    signal,
    symbol: str,
    atr: float,
    now: datetime,
) -> bool:
    """
    Проверяет, есть ли уже открытая paper-сделка, которая делает новый сигнал дублем.

    ВАЖНО: kind НЕ учитывается — синхронизировано с дедупликацией в
    strategy/signals.py (bounce + trend_level на одном уровне = один сигнал).

    Дубль, если ВСЕ условия:
    - status = 'open';
    - symbol совпадает;
    - direction совпадает;
    - одно из:
        (a) abs(new.entry - old.entry) < PAPER_DEDUP_PRICE_TOL_ATR × ATR;
        (b) abs(now - old.created_at) < PAPER_DEDUP_MINUTES минут.
    """
    rows = conn.execute(
        """
        SELECT entry_price, created_at FROM paper_trades
        WHERE result = 'open'
          AND symbol = ?
          AND direction = ?
        """,
        (symbol, signal.direction),
    ).fetchall()

    if not rows:
        return False

    price_tol = config.PAPER_DEDUP_PRICE_TOL_ATR * atr
    now_ts = now.timestamp()

    for row in rows:
        old_entry = row["entry_price"]
        old_created_at = row["created_at"]

        # (a) близкая цена входа
        if abs(signal.entry_price - old_entry) < price_tol:
            return True

        # (b) жёсткое окно эха
        try:
            old_dt = datetime.fromisoformat(old_created_at)
            delta_min = abs(now_ts - old_dt.timestamp()) / 60
            if delta_min < config.PAPER_DEDUP_MINUTES:
                return True
        except Exception:
            # Если created_at битый — считаем дублем, чтобы не плодить мусор
            return True

    return False


def save_signal_as_paper(
    conn: sqlite3.Connection,
    signals: list,
    result,
    source_analysis_path: str | None = None,
    bid_vol: float | None = None,
    ask_vol: float | None = None,
    market_price_at_open: float | None = None,
) -> int:
    if not config.PAPER_ENABLED:
        return 0

    if not _is_in_paper_hours(result.timestamp):
        return 0

    # Проверка лимита открытых сделок через БД
    open_count = conn.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE result = 'open'"
    ).fetchone()[0]
    max_open = getattr(config, "PAPER_MAX_OPEN", 1)
    if max_open > 0 and open_count >= max_open:
        log.debug("paper: лимит %d достигнут", max_open)
        return 0

    created = 0
    inst = get_instrument(result.symbol)
    risk_rub = config.VIRTUAL_DEPOSIT * config.RISK_PER_TRADE_PCT

    for sig in signals:
        # Дедупликация через БД (T-05: единая функция)
        if _is_duplicate(conn, sig, result.symbol, result.atr, result.timestamp):
            continue

        sid = _signal_id(sig, result.symbol, result.timestamp)

        # Расчет размера позиции (Бизнес-логика)
        size = calculate_position_size(
            risk_rub=risk_rub,
            entry_price=sig.entry_price,
            stop_price=sig.stop_price,
            step_cost=inst.step_cost,
            price_step=inst.price_step,
        )

        if size <= 0:
            continue

        # Формируем плоский словарь данных
        data = {
            "signal_id": sid,
            "source_analysis_path": source_analysis_path,
            "symbol": result.symbol,
            "direction": sig.direction,
            "kind": sig.kind,
            "strength": sig.strength,
            "strength_score": sig.strength_score,
            "entry_price": sig.entry_price,
            "stop_price": sig.stop_price,
            "take_price": sig.take_price,
            "level_price": sig.level_price,
            "risk_reward": sig.risk_reward,
            "net_rr": sig.net_rr,
            "trend_at_open": result.indicators.trend,
            "adx_at_open": (
                round(result.indicators.adx, 2) if result.indicators.adx else None
            ),
            "day_trend_at_open": result.indicators.day_trend,
            "structure_at_open": result.indicators.structure,
            "partial_day_at_open": 1 if result.indicators.partial_day else 0,
            "week_trend_at_open": result.indicators.week_trend,
            "market_state_at_open": result.indicators.market_state,
            "rsi_at_open": result.indicators.rsi,
            "atr_percentile_at_open": sig.context.get("atr_percentile"),
            "created_at": result.timestamp.isoformat(),
            "result": "open",
            "warnings": (
                json.dumps(sig.warnings, ensure_ascii=False) if sig.warnings else None
            ),
            "context": (
                json.dumps(sig.context, ensure_ascii=False, default=str)
                if sig.context
                else None
            ),
            "bid_vol": bid_vol,
            "ask_vol": ask_vol,
            "market_price_at_open": market_price_at_open,
            "size": size,
            "balance_after": None,
            "mfe_source": "live",
            "mae_source": "live",
            "take_source": sig.take_source,
            "take_atr_value": sig.take_atr_value,
            "day_range_atr_at_open": result.indicators.day_range_atr_at_open,
        }

        if db.insert_trade(conn, data):
            created += 1

    conn.commit()
    return created


def save_skipped_signal(
    conn: sqlite3.Connection,
    result,
    source_analysis_path: str | None = None,
) -> int:
    """
    T-05: записывает заблокированные сигналы из result.skipped_signals в paper_skipped.
    Возвращает число записанных.
    """
    if not config.PAPER_ENABLED:
        return 0
    if not _is_in_paper_hours(result.timestamp):
        return 0

    skipped = getattr(result, "skipped_signals", [])
    if not skipped:
        return 0

    created = 0
    for s in skipped:
        sid = _signal_id_from_dict(s, result.symbol, result.timestamp)
        data = {
            "signal_id": sid,
            "symbol": result.symbol,
            "direction": s.get("direction", "any"),
            "kind": s.get("kind", "unknown"),
            "entry_price": s.get("entry_price", 0.0),
            "strength_score": s.get("strength_score"),
            "reason": s.get("reason", "unknown"),
            "context": None,
            "created_at": result.timestamp.isoformat(),
        }
        if db.insert_skipped(conn, data):
            created += 1

    conn.commit()
    return created


def _row_to_trade(row: sqlite3.Row) -> dict:
    """Преобразует строку paper_trades в dict для внутреннего использования."""
    return {
        "id": row["id"],
        "signal_id": row["signal_id"],
        "symbol": row["symbol"],
        "direction": row["direction"],
        "kind": row["kind"],
        "strength": row["strength"],
        "strength_score": row["strength_score"],
        "entry_price": row["entry_price"],
        "stop_price": row["stop_price"],
        "take_price": row["take_price"],
        "level_price": row["level_price"],
        "risk_reward": row["risk_reward"],
        "net_rr": row["net_rr"],
        "trend_at_open": row["trend_at_open"],
        "adx_at_open": row["adx_at_open"],
        "day_trend_at_open": row["day_trend_at_open"],
        "structure_at_open": row["structure_at_open"],
        "week_trend_at_open": row["week_trend_at_open"],
        "market_state_at_open": row["market_state_at_open"],
        "created_at": row["created_at"],
        "closed_at": row["closed_at"],
        "exit_price": row["exit_price"],
        "result": row["result"],
        "result_points": row["result_points"],
        "result_rub": row["result_rub"],
        "bars_to_close": row["bars_to_close"],
        "resolution_confidence": row["resolution_confidence"],
        "warnings": row["warnings"],
        "context": row["context"],
        "market_price_at_open": row["market_price_at_open"],
        "size": row["size"],
        "balance_after": row["balance_after"],
        "rsi_at_open": row["rsi_at_open"],
        "atr_percentile_at_open": row["atr_percentile_at_open"],
    }


def resolve_open_trades(
    conn: sqlite3.Connection,
    symbol: str,
    now: datetime,
    df_m15=None,
) -> int:
    """
    Резолвит открытые paper-сделки по symbol.

    Логика:
    - берём все сделки со status='open' по symbol;
    - если df_m15 не передан — тянем через get_candles_tf;
    - обрезаем свечи до created_at (только свечи ПОСЛЕ открытия);
    - зовём virtual_pnl;
    - если результат win/loss/timeout — обновляем запись:
        closed_at, exit_price, result, result_points, result_rub,
        bars_to_close, resolution_confidence;
    - если результат open/no_data — оставляем как есть.

    Возвращает количество закрытых сделок.
    """
    from data.api_facade import get_candles_tf

    rows = db.get_open_trades_by_symbol(conn, symbol)

    if not rows:
        return 0

    # Свечи тянем один раз на все сделки
    if df_m15 is None:
        count = config.PAPER_TIMEOUT_BARS + 30
        df_m15 = get_candles_tf("M15", count=count)

    if df_m15 is None or len(df_m15) == 0:
        log.warning("paper: нет M15 свечей для резолва (%s)", symbol)
        return 0

    # --- Наблюдаемость: насколько свежие данные для резолва ---
    data_age_min = None
    try:
        last_begin = df_m15["begin"].iloc[-1]
        if hasattr(last_begin, "to_pydatetime"):
            last_begin = last_begin.to_pydatetime()
        data_age_min = int((now - last_begin).total_seconds() / 60)
    except Exception:
        pass

    if data_age_min is not None:
        if data_age_min > config.DATA_MAX_AGE_BLOCK * 2:
            # Критический лаг: резолв по таким свечам исказит статистику.
            log.error(
                "paper: data_age=%d мин (> %d) — резолв пропущен, "
                "чтобы не портить exit_price",
                data_age_min,
                config.DATA_MAX_AGE_BLOCK * 2,
            )
            return 0
        elif data_age_min > config.DATA_MAX_AGE_BLOCK:
            log.warning(
                "paper: data_age=%d мин (> %d) — резолв по устаревшим свечам",
                data_age_min,
                config.DATA_MAX_AGE_BLOCK,
            )

    from core.instruments import get_instrument, compute_trade_result

    inst = get_instrument(symbol)
    closed = 0

    for row in rows:
        trade = _row_to_trade(row)

        try:
            created_at = datetime.fromisoformat(trade["created_at"])
        except Exception:
            log.warning("paper: битый created_at у id=%d, пропуск", trade["id"])
            continue

        # --- tz-совместимость: begin может быть tz-aware (ALOR — МСК),
        #     а created_at из isoformat — naive. Иначе сравнение всегда False,
        #     df_future пуст, и сделка «висит» вечно.
        begin_tz = getattr(df_m15["begin"].dt, "tz", None)
        if begin_tz is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=begin_tz)
        elif begin_tz is None and created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)

        # Только свечи строго после created_at
        # (свеча, в которой открыт сигнал, не участвует — это «нулевой» бар)
        df_future = df_m15[df_m15["begin"] > created_at].copy()

        pnl = virtual_pnl(
            df_future,
            trade["direction"],
            trade["entry_price"],
            trade["stop_price"],
            trade["take_price"],
            max_bars=config.PAPER_TIMEOUT_BARS,
            price_step=inst.price_step,
        )

        if pnl["result"] in ("open", "no_data"):
            continue

        # Закрываем
        exit_price = pnl["exit_price"]
        if exit_price is None:
            continue

        points, rub = compute_trade_result(
            inst,
            trade["direction"],
            trade["entry_price"],
            exit_price,
        )

        # Баланс после сделки
        prev_pnl = conn.execute(
            "SELECT COALESCE(SUM(result_rub), 0) FROM paper_trades "
            "WHERE symbol = ? AND result IN ('win', 'loss') AND id < ?",
            (trade["symbol"], trade["id"]),
        ).fetchone()[0]
        balance_after = round(config.VIRTUAL_DEPOSIT + prev_pnl + rub, 2)

        # auto_ambiguous — если stop и take задеты в одной свече (консервативно loss).
        # auto_stale — если на момент резолва данные были старше DATA_MAX_AGE_BLOCK.
        # auto — нормальный резолв.
        if pnl.get("ambiguous"):
            confidence = "auto_ambiguous"
        elif data_age_min is not None and data_age_min > config.DATA_MAX_AGE_BLOCK:
            confidence = "auto_stale"
        else:
            confidence = "auto"

        conn.execute(
            """
            UPDATE paper_trades
            SET closed_at = ?,
                exit_price = ?,
                result = ?,
                result_points = ?,
                result_rub = ?,
                bars_to_close = ?,
                resolution_confidence = ?,
                balance_after = ?,
                mfe_points = ?,
                mae_points = ?
            WHERE id = ?
            """,
            (
                now.isoformat(),
                exit_price,
                pnl["result"],
                points,
                rub,
                pnl["bars"],
                confidence,
                balance_after,
                pnl.get("mfe_points"),
                pnl.get("mae_points"),
                trade["id"],
            ),
        )
        closed += 1
        log.info(
            "paper: id=%d %s %s → %s (%+.1f pts / %+.2f₽, %d баров)",
            trade["id"],
            trade["direction"],
            trade["kind"],
            pnl["result"],
            points,
            rub,
            pnl["bars"],
        )

    conn.commit()
    if closed:
        log.info("paper: закрыто %d сделок по %s", closed, symbol)
    return closed


def format_paper_trade_short(row) -> str:
    """
    Короткая строка для консоли runner.py:
    '#5 short breakout score=3.0 entry=12.412 stop=12.438 take=12.360'
    """
    dir_color = RED if row["direction"] == "short" else GREEN
    dir_str = _colored(f"{row['direction']:5}", dir_color)
    return (
        f"#{row['id']} {dir_str} {row['kind']:12} "
        f"score={row['strength_score'] or 0:.1f} "
        f"entry={row['entry_price']:.3f} "
        f"stop={row['stop_price']:.3f} "
        f"take={row['take_price']:.3f}"
    )


def format_paper_trade_result(row) -> str:
    """
    Строка закрытой сделки:
    '#5 short breakout → win +33.6 pts / +31.54 ₽ (2 bars, auto)'
    """
    pts = row["result_points"] or 0
    rub = row["result_rub"] or 0
    sign = "+" if pts >= 0 else ""
    bars = row["bars_to_close"] or "?"
    conf = row["resolution_confidence"] or "?"
    result = row["result"]

    # Цвет результата
    if result == "win":
        result_str = _colored(f"{result:7}", GREEN)
        pts_str = _colored(f"{sign}{pts:.1f} pts", GREEN)
        rub_str = _colored(f"{sign}{rub:.2f} ₽", GREEN)
    elif result == "loss":
        result_str = _colored(f"{result:7}", RED)
        pts_str = _colored(f"{sign}{pts:.1f} pts", RED)
        rub_str = _colored(f"{sign}{rub:.2f} ₽", RED)
    else:  # open / timeout
        result_str = _colored(f"{result:7}", YELLOW)
        pts_str = f"{sign}{pts:.1f} pts"
        rub_str = f"{sign}{rub:.2f} ₽"

    dir_color = RED if row["direction"] == "short" else GREEN
    dir_str = _colored(f"{row['direction']:5}", dir_color)

    return (
        f"#{row['id']} {dir_str} {row['kind']:12} → "
        f"{result_str} {pts_str} / {rub_str} "
        f"({bars} bars, {conf})"
    )


def _colored(text: str, color: str) -> str:
    """Оборачивает текст в ANSI-цвет. Если цвета отключены — возвращает как есть."""
    if not _USE_COLOR or not color:
        return text
    return f"{color}{text}{RESET}"
