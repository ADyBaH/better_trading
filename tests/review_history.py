"""
Проверка новой логики тренда + сигналов + виртуальный PnL на истории 13-15.10.

Для каждой контрольной точки:
  1. Загружает M15 из БД.
  2. Обрезает до момента.
  3. Считает индикаторы, тренд-контекст.
  4. Показывает old trend vs new trend.
  5. Показывает warnings.
  6. Считает виртуальный PnL для сигналов (если есть).
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

import config
from core.models import AnalysisResult, Level
from data.api_facade import get_candles_tf
from indicators.calc import (
    add_indicators,
    get_atr,
    get_trend_context,
    get_main_trend,
)
from strategy.levels import build_levels
from strategy.signals import detect_signals, _build_warnings
from strategy.references import build_references

# ============================================================
# Контрольные точки
# ============================================================

CHECKPOINTS = [
    # 13.10 — медвежий день
    ("2026-10-13 09:10", "SHORT bounce/trend_level (сработал частично)"),
    ("2026-10-13 09:18", "LONG breakout (ложный)"),
    ("2026-10-13 10:56", "SHORT trend_level strong (score 4)"),
    # 14.10 — боковик
    ("2026-10-14 09:19", "Нет сигналов — боковик"),
    ("2026-10-14 11:26", "Нет сигналов"),
    # 15.10 — бычий день
    ("2026-10-15 08:07", "SHORT trend_level (ложный)"),
    ("2026-10-15 09:23", "LONG breakout (отработал)"),
    ("2026-10-15 10:23", "LONG breakout (отработал)"),
    ("2026-10-15 13:04", "LONG breakout (отработал)"),
    ("2026-10-15 14:19", "LONG breakout (проверка)"),
]


# ============================================================
# Вспомогательные
# ============================================================


def old_trend_by_ema(df_slice) -> str:
    """Старая логика: тренд по EMA."""
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
    max_bars: int = 20,
) -> dict:
    """
    Считает виртуальный PnL: что было бы, если войти по entry.
    Смотрим следующие max_bars свечей.
    """
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
        else:  # short
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
            # Таймаут — по последней цене
            last_close = row.close
            if direction == "long":
                pnl = (last_close - entry) / config.PRICE_STEP
            else:
                pnl = (entry - last_close) / config.PRICE_STEP
            return {"result": "timeout", "pnl_points": round(pnl, 1), "bars": i}

    return {"result": "no_data", "pnl_points": 0.0, "bars": 0}


# ============================================================
# Анализ в точке
# ============================================================


def analyze_at(df_m15: pd.DataFrame, df_h1: pd.DataFrame, ts: pd.Timestamp) -> dict:
    """Прогоняет новую логику на срезе до ts."""
    df_slice = df_m15[df_m15["begin"] <= ts].copy()
    if df_slice.empty:
        return {}

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

    trend_context = get_trend_context(
        df=df_slice,
        current_price=current_price,
        ema_fast=float(last["ema_fast"]) if pd.notna(last["ema_fast"]) else None,
        ema_slow=float(last["ema_slow"]) if pd.notna(last["ema_slow"]) else None,
        atr=atr,
    )
    main_trend_info = get_main_trend(trend_context)

    # --- Уровни и сигналы ---
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

    from core.models import IndicatorSnapshot

    indicators = IndicatorSnapshot(
        ema_fast=float(last["ema_fast"]) if pd.notna(last["ema_fast"]) else None,
        ema_slow=float(last["ema_slow"]) if pd.notna(last["ema_slow"]) else None,
        rsi=float(last["rsi"]) if pd.notna(last.get("rsi")) else None,
        adx=float(last["adx"]) if pd.notna(last.get("adx")) else None,
        trend=main_trend_info["trend"],
        adx_state=(
            "strong"
            if (last.get("adx") and last["adx"] > config.ADX_STRONG)
            else (
                "trend"
                if (last.get("adx") and last["adx"] > config.ADX_THRESHOLD)
                else "flat"
            )
        ),
        rsi_state="neutral",
        day_trend=trend_context["day_trend"],
        day_change_atr=trend_context["day_change_atr"],
        structure=trend_context["structure"],
        price_direction=trend_context["price_direction"],
        vote_sum=main_trend_info["vote_sum"],
        vote_breakdown=main_trend_info["vote_breakdown"],
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

    signals = detect_signals(result, df_slice)

    # --- Виртуальный PnL для каждого сигнала ---
    df_future = df_m15[df_m15["begin"] > ts].head(20)
    for s in signals:
        pnl = virtual_pnl(
            df_future, s.direction, s.entry_price, s.stop_price, s.take_price
        )
        s._virtual_pnl = pnl  # временно прикрепляем

    return {
        "current_price": current_price,
        "atr": atr,
        "old_trend": old_trend,
        "new_trend": main_trend_info["trend"],
        "vote_sum": main_trend_info["vote_sum"],
        "vote_breakdown": main_trend_info["vote_breakdown"],
        "context": trend_context,
        "signals": signals,
    }


# ============================================================
# main
# ============================================================


def main():
    print("=" * 80)
    print("Проверка новой логики тренда + сигналов + PnL на истории 13-15.10")
    print("=" * 80)

    df_m15 = get_candles_tf("M15", count=2000)
    df_h1 = get_candles_tf("H1", count=300)

    if df_m15.empty or df_h1.empty:
        print("Нет данных в БД.")
        return

    print(f"Данные: {df_m15['begin'].min()} → {df_m15['begin'].max()}")
    print(f"Свечей: {len(df_m15)}")

    total_win = 0
    total_loss = 0
    total_timeout = 0
    total_pnl = 0.0
    total_signals = 0

    for ts_str, comment in CHECKPOINTS:
        ts = pd.Timestamp(ts_str)
        result = analyze_at(df_m15, df_h1, ts)

        print(f"\n{'═' * 80}")
        print(f"  {ts_str}  |  {comment}")
        print(f"{'═' * 80}")

        if not result:
            print("  Нет данных.")
            continue

        ctx = result["context"]
        match = "✓" if result["old_trend"] == result["new_trend"] else "⚠ РАЗЛИЧАЕТСЯ"

        print(f"  Цена:     {result['current_price']:.3f}  |  ATR: {result['atr']:.5f}")
        print(
            f"  Old (EMA): {result['old_trend']:>10}  |  New: {result['new_trend']:>12}  ({match})"
        )
        print(f"  Голоса:   {result['vote_breakdown']} = {result['vote_sum']:+d}")
        print(
            f"  Контекст: day={ctx['day_trend']} ({ctx['day_change_atr']:+.2f} ATR) | "
            f"structure={ctx['structure']} | price={ctx['price_direction']}"
        )

        signals = result["signals"]
        if not signals:
            print("  Сигналов нет.")
            continue

        print(f"\n  Сигналы ({len(signals)}):")
        for i, s in enumerate(signals, 1):
            pnl = getattr(s, "_virtual_pnl", None)
            pnl_str = ""
            if pnl:
                pnl_str = f" → {pnl['result']} ({pnl['pnl_points']:+.1f} pts за {pnl['bars']} свечей)"
                total_signals += 1
                total_pnl += pnl["pnl_points"]
                if pnl["result"] == "win":
                    total_win += 1
                elif pnl["result"] == "loss":
                    total_loss += 1
                else:
                    total_timeout += 1

            print(
                f"    [{i}] {s.direction.upper()} {s.kind} ({s.strength}, score={s.strength_score:.1f}){pnl_str}"
            )
            for w in s.warnings:
                print(f"        ⚠ {w}")

    # --- Итоговая статистика ---
    print(f"\n{'═' * 80}")
    print("ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'═' * 80}")
    print(f"  Сигналов: {total_signals}")
    print(f"  Win:      {total_win}")
    print(f"  Loss:     {total_loss}")
    print(f"  Timeout:  {total_timeout}")
    if total_signals > 0:
        winrate = round(100 * total_win / total_signals, 1)
        print(f"  Winrate:  {winrate}%")
        print(f"  Total PnL: {total_pnl:+.1f} pts")


if __name__ == "__main__":
    main()
