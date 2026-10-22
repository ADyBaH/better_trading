# trade-assistant

Консольный аналитический помощник по фьючерсу **CNYRUBF** (MOEX).
Анализирует структуру рынка, находит уровни, детектирует сигналы,
ведёт журнал сделок с учётом комиссий и считает статистику.

**Не торгует автоматически.** Ручной вход, помощник для принятия решений.

## Что умеет

- **Тянет свечи** с MOEX ISS (минутные, агрегирует в M5 / M15 / H1).
- **Считает индикаторы**: EMA(50/200), RSI(14), ADX(14), ATR(14).
- **Строит карту уровней**:
  - Структурные (A+B): фракталы + кластеризация, мульти-ТФ (H1 + M15), веса.
  - Референсные (C): round numbers, PDH/PDL, PWH/PWL.
- **Детектирует сигналы**: bounce, breakout, trend_level с системой критериев (A/B/D).
- **Ведёт журнал сделок** с учётом комиссий биржи и брокера.
- **Мульти-инструмент**: спецификации инструментов в `core/instruments.py`.
- **Экспортирует** результат: консольный дашборд, JSON (flat / nested / full).
- **Раннер**: периодический анализ каждые 20 минут с сохранением по дням.
- **Paper-tracking**: автоматическая запись сигналов как виртуальных сделок
  в `paper_trades` (SQLite, `storage/journal.db`) с резолвом по stop/take/timeout.
- **Статистика paper-trades**: `journal_cli.py paper-stats`.
- **Тянет свечи** с MOEX ISS (с лагом) **или ALOR WebSocket (real-time, лаг 5 мин)**.

## Установка

```bash
git clone <repo>
cd better_trading
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## Быстрый старт

```bash
# 1. Посмотреть анализ рынка
python main.py

# 2. Записать сделку
python journal_cli.py add

# 3. Закрыть сделку
python journal_cli.py close <id> <price>

# 4. Посмотреть статистику
python journal_cli.py stats
```

## CLI Reference

### Анализ рынка: `main.py`

| Команда                           | Описание                                             |
| --------------------------------- | ---------------------------------------------------- |
| `python main.py`                  | Консольный дашборд (по умолчанию)                    |
| `python main.py --json`           | JSON, формат nested (по умолчанию)                   |
| `python main.py --json=flat`      | Плоский JSON — все уровни одним списком              |
| `python main.py --json=full`      | JSON с метаданными и конфигом                        |
| `python main.py --console --json` | Оба вывода сразу                                     |
| `python main.py --log`            | Технический лог в `storage/logs/run_<ts>.log`        |
| `python main.py --save`           | Сохранить вывод в `storage/logs/analysis_<ts>.<ext>` |
| `python main.py --log --save`     | Полный слепок запуска                                |
| `python main.py --symbol=<тикер>` | Другой инструмент (по умолчанию CNYRUBF)             |
| `python main.py --timeframe=M15`  | Другой таймфрейм (M5 / M15 / H1)                     |

### Журнал сделок: `journal_cli.py`

| Команда                                                     | Описание                               |
| ----------------------------------------------------------- | -------------------------------------- |
| `python journal_cli.py add`                                 | Добавить сделку (интерактивно)         |
| `python journal_cli.py list`                                | Последние 20 сделок                    |
| `python journal_cli.py list --open`                         | Только открытые                        |
| `python journal_cli.py add --closed`                        | Добавить закрытую сделку               |
| `python journal_cli.py list --wide`                         | Не обрезать комментарии                |
| `python journal_cli.py list --limit=N`                      | Показать N сделок                      |
| `python journal_cli.py close <id> <price>`                  | Закрыть сделку по цене                 |
| `python journal_cli.py close <id> --result=+25`             | Закрыть с override результата (пункты) |
| `python journal_cli.py close <id> <price> --commission=1.5` | Переопределить комиссию                |
| `python journal_cli.py delete <id>`                         | Удалить сделку                         |
| `python journal_cli.py stats`                               | Статистика по всем сделкам             |
| `python journal_cli.py paper-stats`                         | Статистика paper-сделок                |
| `python journal_cli.py paper-stats --since=2026-10-17`      | Paper с даты                           |
| `python journal_cli.py paper-stats --symbol=CNYRUBF`        | Paper по тикеру                        |
| `python journal_cli.py paper-trades`                        | Показать paper-сделки (таблица)        |
| `python journal_cli.py paper-trades --open`                 | Только открытые                        |
| `python journal_cli.py paper-trades --limit=10`             | Последние 10                           |
| `python journal_cli.py paper-trades --symbol=CNYRUBF`       | Фильтр по тикеру                       |

### Интерактивный ввод в `add`

- **Символ**: `CNYRUBF` (Enter — по умолчанию).
- **Направление**: `l` (long) или `s` (short). Также принимает `long` / `short`.
- **Цена входа**: с точкой — `12.513`.
- **Размер**: количество контрактов.
- **Стоп / Тейк**: цены или Enter (пропустить).
- **Комментарий**: свободный текст — что видел, почему вошёл.
- **Теги**: через запятую — `setup,from_signal`.
- **Тип сигнала**: `bounce` / `breakout` / `trend_level` или Enter (manual).
- **Сила сигнала**: `weak` / `medium` / `strong`.
- **Score сигнала**: число.
- **Комиссия**: Enter — из спецификации инструмента, или число для переопределения.

## Пример вывода

```
══════════════════════════════════════════════════════════════════════════════
  CNYRUBF | 2026-10-13 09:13 | Цена: 12.513
══════════════════════════════════════════════════════════════════════════════

Тренд ВНИЗ (EMA50<EMA200) | ADX 26.7 (сильный) | RSI 46.1 (нейтрально)
ATR(H1) = 0.02574

── СИГНАЛЫ ───────────────────────────────────────────────────────────────
╭────────┬─────────────┬────────┬───────┬────────┬────────┬────────┬──────────╮
│ Напр   │ Тип         │ Сила   │ Score │ Вход   │ Стоп   │ Тейк   │ Критерии │
├────────┼─────────────┼────────┼───────┼────────┼────────┼────────┼──────────┤
│ SHORT  │ trend_level │ medium │     3 │ 12.513 │ 12.543 │ 12.453 │ A1,A2,A3 │
╰────────┴─────────────┴────────┴───────┴────────┴────────┴────────┴──────────╯

── Структурные уровни ────────────────────────────────────────────────────
╭─────────┬───────┬───────┬────────┬─────────┬─────────┬─────┬────────────────┬───────╮
│    Цена │   Вес │ Тип   │ ТФ     │ Живёт   │   Score │ ★   │ Теги           │ Поз   │
├─────────┼───────┼───────┼────────┼─────────┼─────────┼─────┼────────────────┼───────┤
│ 12.5702 │    10 │ down  │ H1,M15 │ 1д      │    26   │ ★★  │                │ ↑     │
│ 12.5151 │    19 │ mixed │ H1,M15 │ 1ч      │    49.4 │ ★★★ │ + PWL          │ ↑     │
│ 12.4999 │    16 │ mixed │ H1,M15 │ 58м     │    41.6 │ ★★★ │ + PDL + 12.500 │ ↓     │
╰─────────┴───────┴───────┴────────┴─────────┴─────────┴─────┴────────────────┴───────╯
```

### Раннер: `runner.py`

Автоматический запуск анализа каждые 20 минут. Результаты сохраняются в `logs/YYYY-MM-DD/`.

| Команда            | Описание                                 |
| ------------------ | ---------------------------------------- |
| `python runner.py` | Запустить раннер (цикл, каждые 20 минут) |
| `Ctrl+C`           | Остановить раннер                        |

**Что делает:**

- Каждые 20 минут запускает `analyze()`.
- Сохраняет результат в `logs/YYYY-MM-DD/analysis_HH-MM-SS.json` и `.txt`.
- Логи сортируются по дням — старые не засоряются.
- Работает как фоновый процесс — остановка `Ctrl+C`.

**Пример вывода:**

```
[цикл #1] 20:59:08
══════════════════════════════════════════════════════════════════
  2026-10-15 20:59:11  |  CNYRUBF  |  Цена: 12.519
  Тренд: strong_down (голосов -3)  |  День: neutral  |  Структура: bearish
  Сигналов: 0
  Сохранено: analysis_20-59-11.json, analysis_20-59-11.txt
══════════════════════════════════════════════════════════════════
  Следующий запуск ~21:19:11
```

## Paper-tracking

Каждый цикл раннера:

1. Новые сигналы записываются в `paper_trades` (только в 09:00–18:00 МСК).
2. Открытые paper-сделки резолвятся по stop/take/timeout (50 M15-свечей).
3. Результат считается с комиссией (`compute_trade_result`).

**Что НЕ делает:** не торгует, не отправляет ордера, не трогает `journal.db/trades`.

**Просмотр:**

```bash
python journal_cli.py paper-stats
```

## Структура проекта

```
better_trading/
├── main.py                     # точка входа анализа
├── runner.py                   # периодический анализ (каждые 20 мин)
├── journal_cli.py              # CLI журнала + paper-stats
├── config.py                   # параметры приложения
├── pyproject.toml
├── requirements.txt
├── README.md
├── ROADMAP.md
├── LICENSE
│
├── core/
│   ├── analyzer.py             # ядро анализа
│   ├── instruments.py          # спецификации + compute_trade_result
│   ├── models.py               # Level, Signal, AnalysisResult
│   ├── logger.py               # логирование
│   ├── errors.py               # (отложено)
│   ├── scheduler.py            # (отложено)
│   └── state.py                # (отложено)
│
├── data/
│   ├── api_moex.py             # запросы к MOEX ISS
│   ├── api_facade.py           # кэш + докачка
│   ├── storage_sqlite.py       # хранение свечей
│   ├── storage.py              # (вспомогательное)
│   └── resample.py             # M1 → M5/M15/H1/H4
│
├── indicators/
│   └── calc.py                 # EMA, RSI, ADX, ATR
│
├── strategy/
│   ├── levels.py               # фракталы + кластеризация
│   ├── references.py           # round, PDH/PDL, PWH/PWL
│   ├── signals.py              # bounce, breakout, trend_level
│   ├── signal_history.py       # история сигналов
│   └── trend.py                # голосование тренда
│
├── trader/
│   ├── journal.py              # журнал реальных сделок (SQLite, trades)
│   ├── paper.py                # paper-tracking (SQLite, paper_trades)
│   └── stats.py                # статистика журнала
│
├── ui/
│   ├── render_console.py       # консольный дашборд
│   └── render_json.py          # JSON-рендеры
│
├── storage/                    # данные (в .gitignore)
│   ├── market.db               # свечи
│   ├── journal.db              # trades + paper_trades
│   └── logs/
│       ├── bot.log
│       ├── signals_history.json
│       └── YYYY-MM-DD/
│           ├── analysis_HH-MM-SS.json
│           └── analysis_HH-MM-SS.txt
│
└── tests/                      # скрипты-проверки
    ├── test_instruments.py
    ├── test_journal_integrity.py
    ├── test_paper.py
    ├── test_paper_dedup.py
    ├── test_paper_resolve.py
    ├── test_paper_stats.py
    ├── test_virtual_pnl.py
    ├── test_signals_enrichment.py
    ├── test_trend_conflict.py
    ├── test_iss_lag.py
    ├── test_pagination.py
    ├── review_all_analysis.py
    └── review_history.py
```

## Инструменты и комиссии

Спецификации инструментов — в `core/instruments.py`. Для каждого инструмента заданы:

- `price_step` — шаг цены.
- `step_cost` — стоимость шага в рублях.
- `lot_size` — размер контракта.
- `commission_exchange` — биржевой сбор.
- `commission_broker` — брокерская комиссия.

**Текущие инструменты:**

| Тикер   | Шаг цены | Стоимость шага | Лот  | Биржа  | Брокер | Круг   |
| ------- | -------- | -------------- | ---- | ------ | ------ | ------ |
| CNYRUBF | 0.001    | 1.0 ₽          | 1000 | 0.58 ₽ | 0.45 ₽ | 2.06 ₽ |

**Добавить новый инструмент:** дополнить словарь `INSTRUMENTS` в `core/instruments.py` и (опционально) поменять `DEFAULT_INSTRUMENT` в `config.py`.

## Стек

- Python 3.10+
- `pandas`, `pandas_ta` — данные и индикаторы
- `requests` — запросы к MOEX ISS
- `tabulate` — таблицы в консоли
- SQLite — хранение свечей и журнала
- `websockets` — WebSocket-клиент для ALOR (real-time данные)

## Как это работает

1. **Данные**: свечи тянутся с MOEX ISS, кэшируются в `data/market.db`. Если последняя свеча старше `CACHE_TTL_MINUTES` — докачка новых.
2. **Индикаторы**: EMA, RSI, ADX, ATR через `pandas_ta`.
3. **Уровни**:
   - Фракталы на M15 и H1 → кластеризация по `0.25 × ATR(H1)` → веса по ТФ.
   - Референсные (round, PDH/PDL, PWH/PWL) — отдельным слоем.
   - Фильтр по `±2.5 × ATR(H1)` вокруг цены.
4. **Сигналы**: bounce, breakout, trend_level. Каждый получает score (A/B/D) и уровень силы.
5. **Журнал**: SQLite-таблица `trades`. Учитывает `symbol`, комиссию из спецификации, override результата.

## Параметры (config.py)

- **Инструмент**: `DEFAULT_INSTRUMENT` (ссылается на `instruments.py`).
- **Таймфреймы**: `TIMEFRAMES`, `DEFAULT_TIMEFRAME`.
- **Индикаторы**: `EMA_FAST`, `EMA_SLOW`, `RSI_PERIOD`, `ADX_PERIOD`.
- **Уровни**: `FRACTAL_PERIOD`, `ATR_PERIOD`, `ATR_TF`, `LEVEL_TOLERANCE_ATR`, `LEVELS_RANGE_ATR`.
- **Сигналы**: `BOUNCE_TOLERANCE_ATR`, `RSI_BOUNCE_LONG`, `ADX_BREAKOUT_THRESHOLD`, `VOLUME_MULTIPLIER`.
- **Торговые правила**: `STOP_POINTS`, `TAKE_POINTS`.
- **Кэш**: `CACHE_TTL_MINUTES`.
- **Источник данных**: `DATA_PROVIDER = "alor"` (real-time) или `"moex"` (ISS).
- **Кэш**: `CACHE_TTL_MINUTES = 4` (для ALOR).

## Что в планах

- [ ] Telegram-уведомления (когда/если заработает).
- [ ] Автозапись сигналов в журнал.
- [ ] Failed breakout, retest.
- [ ] MACD, мульти-ТФ подтверждение сигналов (C), тесты уровня (E).
- [ ] Scheduler + VPS для автономной работы.
- [ ] Экспорт журнала в CSV / Excel.
- [ ] Тесты на ключевые модули.

## Дисклеймер

Это **инструмент для анализа**, не торговая система. Сигналы — не рекомендации.
Все решения принимает пользователь. Автор не несёт ответственности за торговые результаты.

## Лицензия

См. `LICENSE`.
