"""
Точка входа. Прогоняет полный анализ по одному инструменту:
- индикаторы (EMA, RSI, ADX),
- фракталы,
- ATR(H1) для нормализации,
- кластеризация фракталов в уровни.
"""

import config
from core.logger import setup_logging, get_logger
from data.api_facade import get_candles_tf
from indicators.calc import add_indicators, interpret_indicators, get_atr
from strategy.levels import find_fractals, cluster_levels


def print_header(text: str, width: int = 70) -> None:
    """Печатает заголовок с рамкой."""
    print("\n" + "=" * width)
    print(text)
    print("=" * width)


def print_section(text: str, width: int = 70) -> None:
    """Печатает подзаголовок с разделителем."""
    print("\n" + "-" * width)
    print(text)
    print("-" * width)


def main() -> None:
    setup_logging()
    log = get_logger(__name__)
    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)

    tf = config.DEFAULT_TIMEFRAME
    print_header(f"Таймфрейм: {tf}")

    # ============================================================
    # 1. Данные
    # ============================================================
    df = get_candles_tf(tf, count=300)
    if df.empty:
        print("Нет данных.")
        return

    # ============================================================
    # 2. Индикаторы
    # ============================================================
    df = add_indicators(df)

    print_section("Последние 3 свечи с индикаторами")
    cols = ["begin", "close", "ema_fast", "ema_slow", "rsi", "adx"]
    print(df[cols].tail(3).to_string(index=False))

    print()
    print(interpret_indicators(df, timeframe=tf))

    # ============================================================
    # 3. Фракталы
    # ============================================================
    print_section("Фракталы (последние 15)")
    fractals = find_fractals(df)
    if not fractals:
        print("Фракталов не найдено.")
        return

    for f in fractals[-15:]:
        marker = "▲" if f["type"] == "up" else "▼"
        print(f"  {marker} {f['type']:>4} | {f['begin']} | {f['price']:.3f}")

    up = sum(1 for f in fractals if f["type"] == "up")
    down = sum(1 for f in fractals if f["type"] == "down")
    print(f"\nВсего фракталов: {len(fractals)} (вверх: {up}, вниз: {down})")

    # ============================================================
    # 4. ATR(H1) — нормализация допуска
    # ============================================================
    print_section(f"ATR({config.ATR_PERIOD}, {config.ATR_TF}) — нормализация допуска")

    df_atr = get_candles_tf(config.ATR_TF, count=50)
    atr = get_atr(df_atr, period=config.ATR_PERIOD)
    if atr is None:
        print("ATR не рассчитан.")
        return

    tolerance = config.LEVEL_TOLERANCE_ATR * atr
    print(f"ATR = {atr:.5f}")
    print(f"Tolerance = {config.LEVEL_TOLERANCE_ATR} × ATR = {tolerance:.5f}")

    # ============================================================
    # 5. Кластеризация фракталов
    # ============================================================
    print_section("Уровни после кластеризации")

    levels = cluster_levels(
        fractals,
        tolerance=tolerance,
        min_weight=config.LEVELS_MIN_WEIGHT,
    )

    if not levels:
        print("Уровней не найдено.")
        return

    # Сортируем по цене — сверху вниз
    levels.sort(key=lambda lv: lv["price"], reverse=True)

    # Текущая цена — для пометки уровней «выше / ниже рынка»
    current_price = df["close"].iloc[-1]

    print(f"Текущая цена: {current_price:.3f}\n")
    print(
        f"{'Цена':>8} | {'Тип':>6} | {'Вес':>4} | "
        f"{'Первое появление':>17} | {'Последнее':>17} |"
    )
    print("-" * 78)

    for lv in levels:
        marker = "↑" if lv["price"] > current_price else "↓"
        print(
            f"{lv['price']:>8.3f} | {lv['type']:>6} | {lv['weight']:>4} | "
            f"{lv['first_seen'].strftime('%Y-%m-%d %H:%M'):>17} | "
            f"{lv['last_seen'].strftime('%Y-%m-%d %H:%M'):>17} | {marker}"
        )

    print(f"\nВсего уровней: {len(levels)}")

    # Небольшая статистика по весам
    weights = [lv["weight"] for lv in levels]
    if weights:
        print(
            f"Вес: min={min(weights)}, max={max(weights)}, "
            f"средний={sum(weights)/len(weights):.1f}"
        )


if __name__ == "__main__":
    main()
