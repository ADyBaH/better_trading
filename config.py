# config.py

__version__ = "0.1.0"

# === ИНСТРУМЕНТ ===
SYMBOL = "CNYRUBF"          # фьючерс на юань к рублю
SYMBOL_NAME = "CNYRUBF"     # отображаемое имя
TIMEFRAMES = ["M5", "M15"]  # рабочие таймфреймы

# === ПАРАМЕТРЫ КОНТРАКТА ===
PRICE_STEP = 0.001          # шаг цены (1 пункт)
STEP_COST = 0.001           # стоимость 1 пункта в рублях
# Пример: 12.600 → 12.601 = 1 пункт = 0.001 рубля

# === ТОРГОВЫЕ ЧАСЫ ===
TRADING_HOURS = {
    "start": "09:00",
    "end": "20:00",
    "timezone": "Europe/Moscow",
}
TRADING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# === ПРАВИЛА ВХОДА ===
STOP_POINTS = 30            # стоп в пунктах
TAKE_POINTS = 60            # тейк в пунктах
MAX_TRADES_PER_DAY = 3      # лимит сделок
PAUSE_AFTER_LOSS_MIN = 10   # пауза после убытка

# === ИНДИКАТОРЫ ===
EMA_FAST = 50
EMA_SLOW = 200
RSI_PERIOD = 14
ADX_PERIOD = 14
ADX_THRESHOLD = 20
FRACTAL_PERIOD = 100        # сколько свечей смотреть для уровней
LEVEL_TOLERANCE = 10        # допуск для кластеризации уровней

# === ДАННЫЕ ===
DB_PATH = "data/market.db"
LOG_PATH = "logs/bot.log"
BACKUP_DIR = "backups"
NOTIFY_FILE = "logs/notifications.txt"

# === РАСПИСАНИЕ ===
CHECK_INTERVAL_MIN = 5      # проверка каждые 5 минут (закрытие M5)

# === ЛОГИРОВАНИЕ ===
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"