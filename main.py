import config
from core.logger import setup_logging, get_logger
from data.api_facade import get_candles


def main() -> None:
    setup_logging()
    log = get_logger(__name__)
    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)

    # Первый запуск — тянет с биржи
    log.info("--- Первый вызов (с биржи) ---")
    df = get_candles(count=500)
    print(df.tail(5))
    print(f"Свечей: {len(df)}, период: {df['begin'].min()} → {df['begin'].max()}")

    # Второй запуск — должен взять из БД (в логах увидишь "Взято из БД")
    log.info("--- Второй вызов (из БД) ---")
    df2 = get_candles(count=500)
    print(f"Свечей: {len(df2)}, период: {df2['begin'].min()} → {df2['begin'].max()}")


if __name__ == "__main__":
    main()