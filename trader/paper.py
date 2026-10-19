"""Paper-tracking сигналов. Виртуальные сделки в storage/journal.db."""

import hashlib
import sqlite3
import json
from datetime import datetime, time
from typing import Optional
from core.logger import get_logger

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


# ============================================================
# Схема
# ============================================================

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE,
    source_analysis_path TEXT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    kind TEXT NOT NULL,
    strength TEXT,
    strength_score REAL,
    entry_price REAL NOT NULL,
    stop_price REAL NOT NULL,
    take_price REAL NOT NULL,
    level_price REAL,
    risk_reward REAL,
    net_rr REAL,
    trend_at_open TEXT,
    adx_at_open REAL,
    day_trend_at_open TEXT,
    structure_at_open TEXT,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    exit_price REAL,
    result TEXT DEFAULT 'open',
    result_points REAL,
    result_rub REAL,
    bars_to_close INTEGER,
    resolution_confidence TEXT,
    warnings TEXT,
    context TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_trades(result);
CREATE INDEX IF NOT EXISTS idx_paper_created ON paper_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_paper_symbol ON paper_trades(symbol);
"""


def init_paper_table(conn: sqlite3.Connection) -> None:
    """Идемпотентно создаёт таблицу paper_trades."""
    conn.executescript(CREATE_TABLE_SQL)
    conn.commit()


# ============================================================
# Утилиты
# ============================================================


def _signal_id(signal, symbol: str, created_at: datetime) -> str:
    """sha1 от (symbol, direction, kind, entry, created_at), первые 16 hex."""
    raw = (
        f"{symbol}|{signal.direction}|{signal.kind}|"
        f"{round(signal.entry_price, 5)}|{created_at.isoformat()}"
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


# ============================================================
# Резолв PnL
# ============================================================


def virtual_pnl(
    df_future,
    direction: str,
    entry: float,
    stop: float,
    take: float,
    max_bars: int = None,
) -> dict:
    """
    Считает виртуальный PnL по свечам вперёд.

    Логика:
    - идём по свечам df_future по порядку;
    - long: high >= take → win, low <= stop → loss;
    - short: low <= take → win, high >= stop → loss;
    - если обе задеты в одной свече — консервативно loss (ambiguous=True);
    - если max_bars пройден без касания — timeout по close последней свечи.

    Возвращает:
        {
            "result": "win" / "loss" / "timeout" / "no_data",
            "exit_price": float | None,
            "bars": int,
            "ambiguous": bool,
        }
    """
    import pandas as pd

    if max_bars is None:
        max_bars = config.PAPER_TIMEOUT_BARS

    if df_future is None or len(df_future) == 0:
        return {"result": "no_data", "exit_price": None, "bars": 0, "ambiguous": False}

    for i, row in enumerate(df_future.itertuples(), 1):
        high = row.high
        low = row.low

        if direction == "long":
            hit_take = high >= take
            hit_stop = low <= stop
        else:  # short
            hit_take = low <= take
            hit_stop = high >= stop

        # Оба касания в одной свече — консервативно loss
        if hit_take and hit_stop:
            return {
                "result": "loss",
                "exit_price": stop,
                "bars": i,
                "ambiguous": True,
            }

        if hit_take:
            return {
                "result": "win",
                "exit_price": take,
                "bars": i,
                "ambiguous": False,
            }

        if hit_stop:
            return {
                "result": "loss",
                "exit_price": stop,
                "bars": i,
                "ambiguous": False,
            }

        if i >= max_bars:
            return {
                "result": "timeout",
                "exit_price": float(row.close),
                "bars": i,
                "ambiguous": False,
            }

    # Свечей меньше, чем max_bars, и ни stop, ни take не задеты.
    # Это нормальная ситуация, когда сделка ещё открыта:
    # в реальном времени мы не должны её закрывать по таймауту раньше времени.
    # Вызывающий код (resolve_open_trades) сам решит: обновить partial-состояние
    # или оставить open.
    return {
        "result": "open",
        "exit_price": None,
        "bars": len(df_future),
        "ambiguous": False,
    }


# ============================================================
# Дедупликация
# ============================================================


def _is_duplicate(
    conn: sqlite3.Connection,
    signal,
    symbol: str,
    atr: float,
    now: datetime,
) -> bool:
    """
    Проверяет, есть ли уже открытая paper-сделка, которая делает новый сигнал дублем.

    Дубль, если ВСЕ условия:
    - status = 'open';
    - symbol совпадает;
    - direction совпадает;
    - kind совпадает;
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
          AND kind = ?
        """,
        (symbol, signal.direction, signal.kind),
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


# ============================================================
# Создание paper-сделки
# ============================================================


def save_signal_as_paper(
    conn: sqlite3.Connection,
    signals: list,
    result,
    source_analysis_path: str | None = None,
) -> int:
    """
    Создаёт paper-сделки из сигналов.

    Правила:
    - если не в PAPER_TRADING_HOURS — пропускаем (сделки не создаются);
    - если дубль по _is_duplicate — пропускаем;
    - INSERT OR IGNORE по signal_id (UNIQUE) — страховка от гонок.

    Возвращает количество созданных записей.
    """
    if not config.PAPER_ENABLED:
        return 0

    if not _is_in_paper_hours(result.timestamp):
        log.debug(
            "paper: %s вне PAPER_TRADING_HOURS — пропуск",
            result.timestamp.strftime("%H:%M"),
        )
        return 0

    created = 0

    for sig in signals:
        if _is_duplicate(conn, sig, result.symbol, result.atr, result.timestamp):
            log.debug(
                "paper: дубль %s %s @ %.5f — пропуск",
                sig.direction,
                sig.kind,
                sig.entry_price,
            )
            continue

        sid = _signal_id(sig, result.symbol, result.timestamp)

        ind = result.indicators
        adx_val = round(ind.adx, 2) if ind.adx is not None else None

        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO paper_trades (
                    signal_id, source_analysis_path, symbol, direction, kind,
                    strength, strength_score, entry_price, stop_price, take_price,
                    level_price, risk_reward, net_rr,
                    trend_at_open, adx_at_open, day_trend_at_open, structure_at_open,
                    created_at, result, warnings, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    source_analysis_path,
                    result.symbol,
                    sig.direction,
                    sig.kind,
                    sig.strength,
                    sig.strength_score,
                    sig.entry_price,
                    sig.stop_price,
                    sig.take_price,
                    sig.level_price,
                    sig.risk_reward,
                    sig.net_rr,
                    ind.trend,
                    adx_val,
                    ind.day_trend,
                    ind.structure,
                    result.timestamp.isoformat(),
                    "open",
                    (
                        json.dumps(sig.warnings, ensure_ascii=False)
                        if sig.warnings
                        else None
                    ),
                    (
                        json.dumps(sig.context, ensure_ascii=False, default=str)
                        if sig.context
                        else None
                    ),
                ),
            )
            if conn.total_changes > 0:  # INSERT прошёл
                created += 1
        except sqlite3.IntegrityError:
            # signal_id уже есть — пропускаем
            log.debug("paper: signal_id=%s уже существует", sid)
            continue

    conn.commit()
    if created:
        log.info("paper: создано %d сделок", created)
    return created


# ============================================================
# Резолв открытых сделок
# ============================================================


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

    rows = conn.execute(
        "SELECT * FROM paper_trades WHERE symbol = ? AND result = 'open'",
        (symbol,),
    ).fetchall()

    if not rows:
        return 0

    # Свечи тянем один раз на все сделки
    if df_m15 is None:
        count = config.PAPER_TIMEOUT_BARS + 30
        df_m15 = get_candles_tf("M15", count=count)

    if df_m15 is None or len(df_m15) == 0:
        log.warning("paper: нет M15 свечей для резолва (%s)", symbol)
        return 0

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

        confidence = "auto_ambiguous" if pnl.get("ambiguous") else "auto"

        conn.execute(
            """
            UPDATE paper_trades
            SET closed_at = ?,
                exit_price = ?,
                result = ?,
                result_points = ?,
                result_rub = ?,
                bars_to_close = ?,
                resolution_confidence = ?
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


# ============================================================
# Статистика
# ============================================================


def paper_stats(
    conn: sqlite3.Connection,
    since: str | None = None,
    until: str | None = None,
    symbol: str | None = None,
) -> dict:
    """
    Агрегаты по paper_trades.

    since/until — ISO-строки (например, "2026-10-17" или "2026-10-17T09:00:00").
    symbol — фильтр по тикеру (None = все).

    Возвращает dict:
        total, open, win, loss, timeout,
        winrate (по закрытым win/(win+loss), timeout не считается),
        total_points, total_rub,
        avg_win_points, avg_loss_points,
        by_kind, by_trend, by_score, by_day_trend, by_session
    """
    where = []
    params = []

    if since:
        where.append("created_at >= ?")
        params.append(since)
    if until:
        where.append("created_at < ?")
        params.append(until)
    if symbol:
        where.append("symbol = ?")
        params.append(symbol)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"SELECT * FROM paper_trades {where_sql} ORDER BY created_at",
        params,
    ).fetchall()

    total = len(rows)
    open_count = sum(1 for r in rows if r["result"] == "open")
    win = sum(1 for r in rows if r["result"] == "win")
    loss = sum(1 for r in rows if r["result"] == "loss")
    timeout = sum(1 for r in rows if r["result"] == "timeout")

    closed = win + loss + timeout
    closed_wl = win + loss  # winrate без timeout
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

    # --- Разбивки ---
    def _group(key: str) -> dict:
        result = {}
        for r in rows:
            val = r[key]
            if val is None:
                val = "unknown"
            if val not in result:
                result[val] = {
                    "total": 0,
                    "win": 0,
                    "loss": 0,
                    "timeout": 0,
                    "points": 0.0,
                    "rub": 0.0,
                }
            result[val]["total"] += 1
            if r["result"] in ("win", "loss", "timeout"):
                result[val][r["result"]] += 1
            result[val]["points"] += r["result_points"] or 0
            result[val]["rub"] += r["result_rub"] or 0
        # Округляем
        for v in result.values():
            v["points"] = round(v["points"], 1)
            v["rub"] = round(v["rub"], 2)
        return result

    by_kind = _group("kind")
    by_trend = _group("trend_at_open")
    by_day_trend = _group("day_trend_at_open")

    # by_score — бакеты (1.0, 1.5, 2.0, 2.5, 3.0+)
    by_score = {}
    for r in rows:
        score = r["strength_score"]
        if score is None:
            bucket = "unknown"
        elif score >= 3.0:
            bucket = "3.0+"
        elif score >= 2.5:
            bucket = "2.5"
        elif score >= 2.0:
            bucket = "2.0"
        elif score >= 1.5:
            bucket = "1.5"
        else:
            bucket = "1.0"
        if bucket not in by_score:
            by_score[bucket] = {
                "total": 0,
                "win": 0,
                "loss": 0,
                "timeout": 0,
                "points": 0.0,
                "rub": 0.0,
            }
        by_score[bucket]["total"] += 1
        if r["result"] in ("win", "loss", "timeout"):
            by_score[bucket][r["result"]] += 1
        by_score[bucket]["points"] += r["result_points"] or 0
        by_score[bucket]["rub"] += r["result_rub"] or 0
    for v in by_score.values():
        v["points"] = round(v["points"], 1)
        v["rub"] = round(v["rub"], 2)

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
        "by_kind": by_kind,
        "by_trend": by_trend,
        "by_day_trend": by_day_trend,
        "by_score": by_score,
    }


# ============================================================
# Форматирование для вывода
# ============================================================


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
