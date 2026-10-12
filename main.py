import config
from core.logger import setup_logging, get_logger
from data.api_facade import get_candles_tf
from indicators.calc import add_indicators, interpret_indicators


def main() -> None:
    setup_logging()
    log = get_logger(__name__)
    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)

    for tf in config.TIMEFRAMES:
        print("\n" + "=" * 70)
        print(f"Таймфрейм: {tf}")
        print("=" * 70)

        df = get_candles_tf(tf, count=250)
        if df.empty:
            print("Нет данных.")
            continue

        df = add_indicators(df)

        cols = ["begin", "close", "ema_fast", "ema_slow", "rsi", "adx"]
        print(df[cols].tail(3).to_string(index=False))
        print()
        print(interpret_indicators(df, timeframe=tf))


if __name__ == "__main__":
    main()
