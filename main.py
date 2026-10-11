# main.py
"""
Точка входа. Пока просто проверяем, что каркас работает.
"""

import config
from core.logger import setup_logging, get_logger


def main() -> None:
    setup_logging()
    log = get_logger(__name__)

    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)
    log.debug("DEBUG-сообщение (видно, если LOG_LEVEL=DEBUG)")
    log.warning("Это тестовое предупреждение")
    log.info("Каркас проекта работает. Папки созданы, лог пишется.")
    log.info("=== Готово ===")


if __name__ == "__main__":
    main()