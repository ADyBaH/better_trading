"""
Точка входа. Прогоняет полный анализ по одному инструменту:
- индикаторы (EMA, RSI, ADX),
- фракталы на M5,
- ATR(H1) для нормализации,
- мульти-ТФ карта уровней (H1 + M15).
"""

import config
from core.logger import setup_logging, get_logger
from data.api_facade import get_candles_tf
from indicators.calc import add_indicators, interpret_indicators, get_atr
from strategy.levels import find_fractals, build_levels


def print_header(text: str, width: int = 70) -> None:
    print("\n" + "=" * width)
    print(text)
    print("=" * width)


def print_section(text: str, width: int = 70) -> None:
    print("\n" + "-" * width)
    print(text)
    print("-" * width)


def main() -> None:
    setup_logging()
    log = get_logger(__name__)
    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)

    # ============================================================
    # 1. Данные M5 + индикаторы
    # ============================================================
    tf = config.DEFAULT_TIMEFRAME
    print_header(f"Таймфрейм: {tf}")

    df = get_candles_tf(tf, count=300)
    if df.empty:
        print("Нет данных.")
        return

    df = add_indicators(df)
    current_price = df["close"].iloc[-1]

    print_section("Последние 3 свечи с индикаторами")
    cols = ["begin", "close", "ema_fast", "ema_slow", "rsi", "adx"]
    print(df[cols].tail(3).to_string(index=False))

    print()
    print(interpret_indicators(df, timeframe=tf))

    # ============================================================
    # 2. Фракталы на M5 (для контроля)
    # ============================================================
    print_section("Фракталы M5 (последние 15)")
    fractals_m5 = find_fractals(df)
    for f in fractals_m5[-15:]:
        marker = "▲" if f["type"] == "up" else "▼"
        print(f"  {marker} {f['type']:>4} | {f['begin']} | {f['price']:.3f}")

    up = sum(1 for f in fractals_m5 if f["type"] == "up")
    down = sum(1 for f in fractals_m5 if f["type"] == "down")
    print(f"\nВсего фракталов M5: {len(fractals_m5)} (вверх: {up}, вниз: {down})")

    # ============================================================
    # 3. ATR(H1)
    # ============================================================
    print_section(f"ATR({config.ATR_PERIOD}, {config.ATR_TF})")
    df_atr = get_candles_tf(config.ATR_TF, count=50)
    atr = get_atr(df_atr, period=config.ATR_PERIOD)
    if atr is None:
        print("ATR не рассчитан.")
        return

    tolerance = config.LEVEL_TOLERANCE_ATR * atr
    print(f"ATR = {atr:.5f}")
    print(f"Tolerance = {config.LEVEL_TOLERANCE_ATR} × ATR = {tolerance:.5f}")

    # ============================================================
    # 4. Мульти-ТФ карта уровней
    # ============================================================
    print_section("Уровни: мульти-ТФ карта")

    levels = build_levels(
        symbol=config.SYMBOL,
        tolerance=tolerance,
        current_price=current_price,
        atr=atr,
    )

    print(f"Текущая цена: {current_price:.3f}\n")
    print(
        f"{'Цена':>8} | {'Тип':>6} | {'Вес':>4} | "
        f"{'ТФ':>10} | {'Подтв':>5} | {'Последнее':>16} |"
    )
    print("-" * 78)

    for lv in levels:
        tfs = ",".join(sorted(lv["tf_source"]))
        confirmed = "✓" if lv["confirmed"] else ""
        marker = "↑" if lv["price"] > current_price else "↓"
        print(
            f"{lv['price']:>8.3f} | {lv['type']:>6} | {lv['weight']:>4} | "
            f"{tfs:>10} | {confirmed:>5} | "
            f"{lv['last_seen'].strftime('%Y-%m-%d %H:%M'):>16} | {marker}"
        )

    print(f"\nВсего уровней: {len(levels)}")

    if levels:
        weights = [lv["weight"] for lv in levels]
        print(
            f"Вес: min={min(weights)}, max={max(weights)}, "
            f"средний={sum(weights)/len(weights):.1f}"
        )
        confirmed_count = sum(1 for lv in levels if lv["confirmed"])
        print(f"Подтверждённых (на 2+ ТФ): {confirmed_count}")


if __name__ == "__main__":
    main()
