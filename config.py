__version__ = "0.6.0"

# ============================================================
# ИНСТРУМЕНТ
# ============================================================
from core.instruments import get_instrument, list_instruments

DEFAULT_INSTRUMENT = "CNYRUBF"
_ACTIVE = get_instrument(DEFAULT_INSTRUMENT)

# Прокси-константы для обратной совместимости.
SYMBOL = _ACTIVE.symbol
SYMBOL_NAME = _ACTIVE.name
MARKET = _ACTIVE.market
ENGINE = _ACTIVE.engine
PRICE_STEP = _ACTIVE.price_step
STEP_COST = _ACTIVE.step_cost

# Таймфрейм для генерации сигналов (НЕ для ручного анализа).
# M15 — компромисс: задержка ISS ~15 мин = 1 свеча M15 назад.
DEFAULT_TIMEFRAME = "M15"

# Базовый интервал, который тянем с биржи (в минутах).
# MOEX ISS поддерживает: 1, 10, 60, 24.
BASE_INTERVAL = 1

# Таймфреймы для отображения в дашборде (не для сигналов).
TIMEFRAMES = ["M5", "M15", "H1"]

# ============================================================
# ТОРГОВЫЕ ЧАСЫ
# ============================================================
TRADING_HOURS = {
    "start": "08:00",
    "end": "20:00",
    "timezone": "Europe/Moscow",
}
TRADING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# ============================================================
# ПРАВИЛА ВХОДА
# ============================================================
STOP_POINTS = 30  # fallback, если USE_ATR_STOPS = False
TAKE_POINTS = 60  # fallback, если USE_ATR_STOPS = False
MAX_TRADES_PER_DAY = 3
PAUSE_AFTER_LOSS_MIN = 10

# ============================================================
# ИНДИКАТОРЫ
# ============================================================
EMA_FAST = 50
EMA_SLOW = 200

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
RSI_NEAR_OVERBOUGHT = 60
RSI_NEAR_OVERSOLD = 40

ADX_PERIOD = 14
ADX_THRESHOLD = 20
ADX_STRONG = 25

# ============================================================
# УРОВНИ
# ============================================================
FRACTAL_PERIOD = 2

ATR_PERIOD = 14
ATR_TF = "H1"
LEVEL_TOLERANCE_ATR = 0.25

LEVELS_RANGE_ATR = 2.5
LEVELS_MAX_SHOW = 7
LEVELS_MIN_WEIGHT = 2

# H4 — стабильность (weight 3), H1 — свежесть (2), M15 — уточнение (1).
LEVEL_TIMEFRAMES = ["H4", "H1", "M15"]
LEVEL_TF_WEIGHTS = {"H4": 3, "H1": 2, "M15": 1}

# Референсные уровни
ROUND_STEP = 0.05
SHOW_PDH_PDL = True
SHOW_PWH_PWL = True

# ============================================================
# СИГНАЛЫ
# ============================================================
# --- Bounce ---
BOUNCE_TOLERANCE_ATR = 0.3
RSI_BOUNCE_LONG = 35
RSI_BOUNCE_SHORT = 65

# --- Breakout ---
ADX_BREAKOUT_THRESHOLD = 25
BREAKOUT_BUFFER_ATR = 0.15

# --- Trend + Level ---
TREND_LEVEL_TOLERANCE_ATR = 0.4

# --- Объём ---
VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5

# --- Стопы / тейки ---
# От ATR(H1) — адаптируется к волатильности.
# Если USE_ATR_STOPS = False — берутся STOP_POINTS / TAKE_POINTS.
USE_ATR_STOPS = True
STOP_ATR_MULT = 1.0  # стоп = 1.0 × ATR(H1)
TAKE_ATR_MULT = 2.0  # тейк = 2.0 × ATR(H1)

# --- Свежесть данных ---
DATA_MAX_AGE_MIN = 15  # если последняя свеча старше — warning в сигнале
DATA_MAX_AGE_BLOCK = 30  # блокировка — не создавать сигнал

# ============================================================
# ДАННЫЕ
# ============================================================
DB_PATH = "storage/market.db"
LOG_PATH = "storage/logs/bot.log"
BACKUP_DIR = "storage/backups"
NOTIFY_FILE = "storage/logs/notifications.txt"

# Сколько минут считать кэш свежим.
# ISS обновляет данные с лагом ~15 мин — TTL 15 уменьшает «слепоту».
CACHE_TTL_MINUTES = 15

# ============================================================
# РАСПИСАНИЕ
# ============================================================
CHECK_INTERVAL_MIN = 5

# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# --- Штрафы за конфликты тренда ---
PENALTY_TREND_TRANSITION = 1.5  # для trend_level при transition
PENALTY_BREAKOUT_TRANSITION = 1.0  # для breakout при transition
PENALTY_BOUNCE_TRANSITION = 0.5
