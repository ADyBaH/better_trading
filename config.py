from core.instruments import get_instrument
import os  # в начале файла, если нет

__version__ = "0.11.0"

# ============================================================
# ИНСТРУМЕНТ
# ============================================================

DATA_PROVIDER = "alor"  # "moex" | "alor" | "tinvest"
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
    "start": "09:00",
    "end": "19:00",
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
USE_ATR_STOPS = True
STOP_ATR_MULT = 1.0  # стоп = 1.0 × ATR(H1)
TAKE_ATR_MULT = 2.0  # тейк = 2.0 × ATR(H1)

# --- Штрафы за конфликты тренда ---
PENALTY_TREND_TRANSITION = 1.5  # для trend_level при transition
PENALTY_BREAKOUT_TRANSITION = 1.0  # для breakout при transition
PENALTY_BOUNCE_TRANSITION = 0.5

# --- Свежесть данных ---
DATA_MAX_AGE_MIN = 20  # если последняя свеча старше — warning в сигнале
DATA_MAX_AGE_BLOCK = 30  # T-01b: M15 закрытая всегда 15–30 мин + лаг ALOR

# ============================================================
# ДАННЫЕ
# ============================================================
DB_PATH = "storage/market.db"
LOG_PATH = "storage/logs/bot.log"
BACKUP_DIR = "storage/backups"
NOTIFY_FILE = "storage/logs/notifications.txt"

# Сколько минут считать кэш свежим.
# ISS обновляет данные с лагом ~15 мин — TTL 15 уменьшает «слепоту».
CACHE_TTL_MINUTES = 4

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

# ============================================================
# PAPER-TRACKING
# ============================================================
PAPER_ENABLED = True

# Лимит открытых paper-сделок: 0 — без лимита, 1 — не более одной.
PAPER_MAX_OPEN = 0

# Торговые часы для paper-tracking (отдельно от TRADING_HOURS).
# Новые paper-сделки создаются только в этом окне (МСК).
# Резолв открытых сделок работает всегда — иначе зависнут.
PAPER_TRADING_HOURS = {
    "start": os.environ.get("PAPER_START", "09:00"),
    "end": os.environ.get("PAPER_END", "18:00"),
    "timezone": "Europe/Moscow",
}

# Timeout: сколько торговых M15 свечей ждём stop/take,
# прежде чем закрыть по close. 50 × M15 = 12.5 часов торгового времени.
PAPER_TIMEOUT_BARS = 20

# Дедупликация: не создавать дубль, если есть открытая сделка того же
# направления и kind с entry в пределах PAPER_DEDUP_PRICE_TOL_ATR × ATR(H1)
PAPER_DEDUP_PRICE_TOL_ATR = 0.25
PAPER_DEDUP_MINUTES = 5  # жёсткое окно эха (не создавать дубль в пределах 15 мин)

# ============================================================
# ЭКСПЕРИМЕНТЫ (T-07: pre-registration)
# ============================================================
# ID текущего эксперимента (например, "EXP-20261122-01").
# None — вне эксперимента (baseline).
# Пишется в paper_trades.experiment_id и analysis_*.json.
# Без pre-registration в EXPERIMENTS.md эксперимент не считается.
EXPERIMENT_ID: str | None = os.environ.get("EXPERIMENT_ID")

# ============================================================
# ВИРТУАЛЬНЫЙ ДЕПОЗИТ (paper-tracking)
# ============================================================
VIRTUAL_DEPOSIT = 3000.0  # стартовый депозит, ₽
RISK_PER_TRADE_PCT = 0.01  # 1% риска на сделку

# --- Фильтры (по статистике) ---
# Y (feature/real-trading): bullish_long + normal_breakout — ON
# F (experiment/aggressive-signals): все OFF (полигон)
PAPER_SKIP_BULLISH_LONG = True  # −103 ₽ (replay 11/13.11) — полезен
PAPER_SKIP_NORMAL_BREAKOUT = True  # −139.72 ₽ (paper_trades, n=17) — полезен
PAPER_SKIP_BULLISH_SHORT = False  # +21.72 ₽ (paper_trades, n=8) — НЕ включать
PAPER_SKIP_ADX_FLAT_BREAKOUT = False  # +50.28 ₽ (paper_trades, n=7) — НЕ включать
PAPER_SKIP_PULLBACK_BOUNCE = True  # 10 сделок, 1W/7L, −81.94 ₽
PAPER_SKIP_ADX_TREND = True  # 17 сделок, 1W/12L, −256.36 ₽
PAPER_SKIP_BID_HEAVY = True  # 6 сделок, 0W/5L, −150.30 ₽

# --- Breakout: статус (Задача 3, paper-stats 2026-11-19, n=37) ---
# baseline: 10W/23L/1T, −71.54 ₽, exp −0.0 — не работает ни в одном разрезе.
# kill-switch: True — breakout не создаётся вообще (эксперимент Y на 2 недели).
PAPER_SKIP_BREAKOUT = False

# Условный фильтр для breakout (взаимоисключающие варианты):
#   "none" — без фильтра (как сейчас)
#   "F1"   — ADX >= 25 (strong) только
#   "F2"   — ADX < 20 (flat) только
#   "F3"   — market_state == impulse только
#   "F4"   — week_trend не противоречит direction (neutral пропускаем)
BREAKOUT_FILTER = "none"

# ============================================================
# СОХРАНЕНИЕ СВЕЧЕЙ В JSON
# ============================================================
SAVE_CANDLES = True  # глобальный выключатель (вкл/выкл фичу)
SAVE_CANDLES_ALWAYS = True  # ФЛАГ «ВСЕ СВЕЧИ»: True — писать каждый цикл (A)
#                    False — только при сигналах (B)
SAVE_CANDLES_MARK_SIGNALS = (
    True  # ставить has_signals/signals_count в снимке (B-маркер)
)
SAVE_CANDLES_TIMEFRAMES = ["M15", "H1", "H4"]  # какие ТФ сохранять
SAVE_CANDLES_COUNT = 300
# Разные count по ТФ (H4 нужно больше для EMA200: 200 + запас)
SAVE_CANDLES_COUNT_BY_TF = {
    "M15": 300,
    "H1": 300,
    "H4": 500,
}
SAVE_CANDLES_MAX_SNAPSHOTS = 300  # защита от разрастания
VOLUME_RATIO_CAP = 5.0  # глобальный cap, чтобы выбросы (17–20x) не завышали score

# --- Адаптивный take: take = min(2.0×ATR, 0.6×day_range×ATR) ---
ADAPTIVE_TAKE_ENABLED = True  # эксперимент; False = baseline (2.0×ATR)
TAKE_DAY_RANGE_FRAC = 0.6  # доля дневного диапазона
MIN_TAKE_ATR = 0.8  # защита от слишком близкого тейка (partial_day)


# ============================================================
# REAL-TRADING
# ============================================================
# Единственный источник истины для режима real-торговли.
#   "mock" — ордера НЕ ставятся (по умолчанию, безопасно)
#   "live" — реальные ордера (требует CONFIRM_LIVE=1 в env)
REAL_TRADING_MODE = "mock"

# Дополнительное подтверждение для live (защита от случайного переключения).
# Устанавливается ТОЛЬКО через env: export CONFIRM_LIVE=1
# В коде/config.py значение НЕ хардкодить.
CONFIRM_LIVE_ENV_VAR = "CONFIRM_LIVE"
