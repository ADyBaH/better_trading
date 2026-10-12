import config
from core.logger import setup_logging, get_logger
from data.api_facade import get_candles_tf
from indicators.calc import add_indicators, interpret_indicators
from strategy.levels import find_fractals


def main() -> None:
    setup_logging()
    log = get_logger(__name__)
    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)

    tf = config.DEFAULT_TIMEFRAME
    print("\n" + "=" * 70)
    print(f"Таймфрейм: {tf}")
    print("=" * 70)

    df = get_candles_tf(tf, count=300)
    if df.empty:
        print("Нет данных.")
        return

    df = add_indicators(df)

    # --- Индикаторы ---
    print("\nПоследние 3 свечи с индикаторами:")
    cols = ["begin", "close", "ema_fast", "ema_slow", "rsi", "adx"]
    print(df[cols].tail(3).to_string(index=False))
    print()
    print(interpret_indicators(df, timeframe=tf))

    # --- Фракталы ---
    print("\n" + "-" * 70)
    print("Фракталы (последние 15):")
    print("-" * 70)
    fractals = find_fractals(df)
    if not fractals:
        print("Фракталов не найдено.")
    else:
        for f in fractals[-15:]:
            marker = "▲" if f["type"] == "up" else "▼"
            print(f"  {marker} {f['type']:>4} | {f['begin']} | {f['price']:.3f}")
        print(f"\nВсего фракталов: {len(fractals)}")
        up = sum(1 for f in fractals if f["type"] == "up")
        down = sum(1 for f in fractals if f["type"] == "down")
        print(f"  вверх: {up}, вниз: {down}")


if __name__ == "__main__":
    main()
