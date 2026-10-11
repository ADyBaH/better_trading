# core/logger.py
"""
Настройка логирования: файл + консоль.
Импортируй get_logger(__name__) в любом модуле.
"""

import logging
import sys
from pathlib import Path

import config

_configured = False


def _ensure_dirs() -> None:
    """Создаёт папки для логов, если их нет."""
    Path(config.LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(config.NOTIFY_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(config.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    """Инициализирует корневой логгер. Вызывается один раз из main.py."""
    global _configured
    if _configured:
        return

    _ensure_dirs()

    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)

    # Убираем возможные хендлеры (на случай повторного вызова)
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT)

    # --- Файл ---
    file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(config.LOG_LEVEL)
    root.addHandler(file_handler)

    # --- Консоль ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(config.LOG_LEVEL)
    root.addHandler(console_handler)

    _configured = True
    logging.getLogger(__name__).info(
        "Логирование инициализировано (version=%s, symbol=%s)",
        config.__version__,
        config.SYMBOL,
    )


def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с указанным именем."""
    return logging.getLogger(name)