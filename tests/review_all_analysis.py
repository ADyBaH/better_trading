"""
Полный прогон всех сохранённых analysis_*.json за 13-15.10
на новой логике тренда с виртуальным PnL.

Для каждого снимка:
    1. Извлекает timestamp из имени файла.
    2. Обрезает свечи из БД до этого времени.
    3. Считает: old_trend, new_trend, vote_sum, context.
    4. Строит уровни и сигналы по новой логике.
    5. Считает виртуальный PnL (50 M15 вперёд).
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

import config
from core.models import AnalysisResult, Level, IndicatorSnapshot
from data.api_facade import get_candles_tf
from indicators.calc import (
    add_indicators,
    get_atr,
    get_trend_context,
    get_main_trend,
)
from strategy.levels import build_levels
from strategy.references import build_references
from strategy.signals import detect_signals

# ============================================================
# Конфиг
# ============================================================

LOGS_DIR = Path(config.LOG_PATH).parent
START_DATE = pd.Timestamp("2026-10-13 00:00:00")
PNL_FORWARD_BARS = 50  # M15 свечей вперёд для PnL
MIN_BARS_FOR_EMA = 250  # минимум свечей, чтобы EMA200 посчиталась


# ============================================================
# Поиск файлов и извлечение timestamp
# ============================================================


def find_analysis_files():
    """
    Ищет все analysis_*.json в logs/.
    Поддерживает 2 формата:
        1. Старый: logs/analysis_2026-10-13_09-10-15.json
        2. Новый:  logs/2026-10-13/analysis_09-10-15.json
    Возвращает [(path, timestamp), ...], отфильтрованные и отсортированные.
    """
    # Паттерн для старого формата (дата в имени)
    pattern_old = re.compile(
        r"analysis_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})\.(json|txt)$"
    )
    # Паттерн для нового формата (дата в папке)
    pattern_new = re.compile(r"analysis_(\d{2})-(\d{2})-(\d{2})\.(json|txt)$")

    results = []

    # Старый формат: файлы в корне logs/
    for p in LOGS_DIR.glob("analysis_*.json"):
        m = pattern_old.match(p.name)
        if not m:
            continue
        try:
            ts = pd.Timestamp(
                f"{m.group(1)}-{m.group(2)}-{m.group(3)} "
                f"{m.group(4)}:{m.group(5)}:{m.group(6)}"
            )
        except Exception:
            continue
        if ts < START_DATE:
            continue
        results.append((p, ts))

    # Новый формат: файлы в logs/YYYY-MM-DD/
    for date_dir in LOGS_DIR.glob("????-??-??"):
        if not date_dir.is_dir():
            continue
        date_str = date_dir.name  # "2026-10-15"
        for p in date_dir.glob("analysis_*.json"):
            m = pattern_new.match(p.name)
            if not m:
                continue
            try:
                ts = pd.Timestamp(
                    f"{date_str} " f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
                )
            except Exception:
                continue
            if ts < START_DATE:
                continue
            results.append((p, ts))

    results.sort(key=lambda x: x[1])
    return results


# ============================================================
# Вспомогательные
# ============================================================


def old_trend_by_ema(df_slice) -> str:
    last = df_slice.iloc[-1]
    ema_fast = last.get("ema_fast")
    ema_slow = last.get("ema_slow")
    if pd.isna(ema_fast) or pd.isna(ema_slow):
        return "none"
    return "up" if ema_fast > ema_slow else "down"


def virtual_pnl(
    df_future: pd.DataFrame,
    direction: str,
    entry: float,
    stop: float,
    take: float,
    max_bars: int = PNL_FORWARD_BARS,
) -> dict:
    """Считает виртуальный PnL."""
    if df_future.empty:
        return {"result": "no_data", "pnl_points": 0.0, "bars": 0}

    for i, row in enumerate(df_future.itertuples(), 1):
        high = row.high
        low = row.low

        if direction == "long":
            if high >= take:
                return {
                    "result": "win",
                    "pnl_points": round((take - entry) / config.PRICE_STEP, 1),
                    "bars": i,
                }
            if low <= stop:
                return {
                    "result": "loss",
                    "pnl_points": round((stop - entry) / config.PRICE_STEP, 1),
                    "bars": i,
                }
        else:
            if low <= take:
                return {
                    "result": "win",
                    "pnl_points": round((entry - take) / config.PRICE_STEP, 1),
                    "bars": i,
                }
            if high >= stop:
                return {
                    "result": "loss",
                    "pnl_points": round((entry - stop) / config.PRICE_STEP, 1),
                    "bars": i,
                }

        if i >= max_bars:
            last_close = row.close
            if direction == "long":
                pnl = (last_close - entry) / config.PRICE_STEP
            else:
                pnl = (entry - last_close) / config.PRICE_STEP
            return {"result": "timeout", "pnl_points": round(pnl, 1), "bars": i}

    return {"result": "no_data", "pnl_points": 0.0, "bars": 0}


# ============================================================
# Анализ в одной точке
# ============================================================


def analyze_at(df_m15: pd.DataFrame, df_h1: pd.DataFrame, ts: pd.Timestamp) -> dict:
    df_slice = df_m15[df_m15["begin"] <= ts].copy()
    if len(df_slice) < MIN_BARS_FOR_EMA:
        return {"error": f"мало свечей ({len(df_slice)} < {MIN_BARS_FOR_EMA})"}

    df_slice = add_indicators(df_slice)
    current_price = float(df_slice["close"].iloc[-1])

    df_h1_slice = df_h1[df_h1["begin"] <= ts].copy()
    atr = (
        get_atr(df_h1_slice, period=config.ATR_PERIOD)
        if not df_h1_slice.empty
        else None
    )
    if atr is None:
        atr = get_atr(df_slice, period=config.ATR_PERIOD)
    if atr is None:
        atr = 0.025

    last = df_slice.iloc[-1]
    old_trend = old_trend_by_ema(df_slice)

    ctx = get_trend_context(
        df=df_slice,
        current_price=current_price,
        ema_fast=float(last["ema_fast"]) if pd.notna(last["ema_fast"]) else None,
        ema_slow=float(last["ema_slow"]) if pd.notna(last["ema_slow"]) else None,
        atr=atr,
    )
    main_info = get_main_trend(ctx)

    # Уровни
    tolerance = config.LEVEL_TOLERANCE_ATR * atr
    raw_levels = build_levels(
        symbol=config.SYMBOL,
        tolerance=tolerance,
        current_price=current_price,
        atr=atr,
    )
    structural = [
        Level(
            price=float(d["price"]),
            type=str(d["type"]),
            weight=int(d["weight"]),
            tf_source=set(d.get("tf_source", set())),
            confirmed=bool(d.get("confirmed", False)),
            first_seen=d.get("first_seen"),
            last_seen=d.get("last_seen"),
        )
        for d in raw_levels
    ]

    df_h1_full = get_candles_tf("H1", count=200)
    raw_refs = build_references(
        current_price=current_price,
        atr=atr,
        df_intraday=df_slice,
        df_h1=df_h1_full,
    )
    references = [
        Level(
            price=float(r["price"]),
            type=str(r["type"]),
            weight=int(r["weight"]),
            label=str(r.get("label", "")),
        )
        for r in raw_refs
    ]

    # Индикаторы
    rsi_state = "neutral"
    if last.get("rsi") is not None and not pd.isna(last["rsi"]):
        r = float(last["rsi"])
        if r > config.RSI_OVERBOUGHT:
            rsi_state = "overbought"
        elif r < config.RSI_OVERSOLD:
            rsi_state = "oversold"
        elif r > config.RSI_NEAR_OVERBOUGHT:
            rsi_state = "near_overbought"
        elif r < config.RSI_NEAR_OVERSOLD:
            rsi_state = "near_oversold"

    adx_state = "flat"
    if last.get("adx") is not None and not pd.isna(last["adx"]):
        a = float(last["adx"])
        if a > config.ADX_STRONG:
            adx_state = "strong"
        elif a > config.ADX_THRESHOLD:
            adx_state = "trend"

    indicators = IndicatorSnapshot(
        ema_fast=float(last["ema_fast"]) if pd.notna(last["ema_fast"]) else None,
        ema_slow=float(last["ema_slow"]) if pd.notna(last["ema_slow"]) else None,
        rsi=float(last["rsi"]) if pd.notna(last.get("rsi")) else None,
        adx=float(last["adx"]) if pd.notna(last.get("adx")) else None,
        trend=main_info["trend"],
        adx_state=adx_state,
        rsi_state=rsi_state,
        day_trend=ctx["day_trend"],
        day_change_atr=ctx["day_change_atr"],
        structure=ctx["structure"],
        price_direction=ctx["price_direction"],
        vote_sum=main_info["vote_sum"],
        vote_breakdown=main_info["vote_breakdown"],
    )

    result = AnalysisResult(
        symbol=config.SYMBOL,
        timestamp=datetime.now(),
        current_price=current_price,
        atr=atr,
        timeframe="M15",
        indicators=indicators,
        levels=structural,
        references=references,
    )

    original_block = config.DATA_MAX_AGE_BLOCK
    config.DATA_MAX_AGE_BLOCK = 999999
    try:
        signals = detect_signals(result, df_slice)
    finally:
        config.DATA_MAX_AGE_BLOCK = original_block

    # PnL для каждого сигнала
    df_future = df_m15[df_m15["begin"] > ts].head(PNL_FORWARD_BARS)
    signals_with_pnl = []
    for s in signals:
        pnl = virtual_pnl(
            df_future, s.direction, s.entry_price, s.stop_price, s.take_price
        )
        signals_with_pnl.append((s, pnl))

    return {
        "current_price": current_price,
        "atr": atr,
        "old_trend": old_trend,
        "new_trend": main_info["trend"],
        "vote_sum": main_info["vote_sum"],
        "vote_breakdown": main_info["vote_breakdown"],
        "context": ctx,
        "signals": signals_with_pnl,
    }


# ============================================================
# main
# ============================================================


def main():
    print("=" * 80)
    print("Полный прогон всех analysis_*.json за 13-15.10")
    print("=" * 80)

    files = find_analysis_files()
    print(f"Найдено файлов: {len(files)}")

    if not files:
        print("Нет файлов для анализа.")
        return

    # Загружаем свечи
    print("Загружаю M15 и H1 из БД...")
    df_m15 = get_candles_tf("M15", count=3000)
    df_h1 = get_candles_tf("H1", count=500)

    if df_m15.empty or df_h1.empty:
        print("Нет свечей в БД.")
        return

    print(f"Диапазон M15: {df_m15['begin'].min()} → {df_m15['begin'].max()}")
    print(f"Свечей M15: {len(df_m15)}\n")

    # Статистика
    total_points = 0
    points_with_signals = 0
    old_new_diff = 0
    total_signals = 0
    win_count = 0
    loss_count = 0
    timeout_count = 0
    total_pnl = 0.0

    # Дедупликация
    seen_timestamps = set()  # по секунде: "2026-10-13 09:10:15"
    seen_signals = set()  # по сигналу: (минута, direction, kind, level)

    # Ошибки
    errors = []

    for path, ts in files:
        # --- Дедупликация точек по секунде ---
        ts_key = ts.strftime("%Y-%m-%d %H:%M:%S")
        if ts_key in seen_timestamps:
            continue
        seen_timestamps.add(ts_key)

        r = analyze_at(df_m15, df_h1, ts)
        total_points += 1

        if "error" in r:
            errors.append((path.name, r["error"]))
            continue

        old = r["old_trend"]
        new = r["new_trend"]
        if old != new:
            old_new_diff += 1

        signals = r["signals"]
        if signals:
            points_with_signals += 1

        # --- Дедупликация сигналов ---
        # Ключ: (минута, direction, kind, level_price)
        # Так один и тот же сигнал, сработавший на 3 соседних свечах,
        # считается ОДИН раз
        unique_signals = []
        for s, pnl in signals:
            sig_key = (
                ts.strftime("%Y-%m-%d %H:%M"),  # минута
                s.direction,
                s.kind,
                round(s.level_price or 0, 5),
            )
            if sig_key in seen_signals:
                continue
            seen_signals.add(sig_key)
            unique_signals.append((s, pnl))

        # Краткий вывод по точке
        match = "⚠" if old != new else " "
        print(
            f"{ts.strftime('%m-%d %H:%M')} | {r['current_price']:.3f} | "
            f"old={old:>10} new={new:>12} {match} | "
            f"votes={r['vote_sum']:+d} | signals={len(unique_signals)}"
        )

        for s, pnl in unique_signals:
            total_signals += 1
            total_pnl += pnl["pnl_points"]
            if pnl["result"] == "win":
                win_count += 1
            elif pnl["result"] == "loss":
                loss_count += 1
            elif pnl["result"] == "timeout":
                timeout_count += 1

            print(
                f"     → {s.direction.upper()} {s.kind} ({s.strength}, score={s.strength_score:.1f}) | "
                f"{pnl['result']} {pnl['pnl_points']:+.1f} pts / {pnl['bars']} bars"
            )

    # Итог
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"  Всего точек:               {total_points}")
    print(
        f"  Старых != новых трендов:   {old_new_diff} ({100*old_new_diff//max(total_points,1)}%)"
    )
    print(f"  Точек с сигналами:         {points_with_signals}")
    print(f"  Всего сигналов:            {total_signals}")
    print(f"  Win:                       {win_count}")
    print(f"  Loss:                      {loss_count}")
    print(f"  Timeout:                   {timeout_count}")
    if total_signals > 0:
        print(f"  Winrate:                   {100*win_count/total_signals:.1f}%")
        print(f"  Total PnL (виртуальный):   {total_pnl:+.1f} pts")
    if errors:
        print(f"\n  Ошибок: {len(errors)}")
        for name, err in errors[:5]:
            print(f"    {name}: {err}")


if __name__ == "__main__":
    main()
