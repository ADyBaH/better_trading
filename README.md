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
- **Сохраняет свечи в JSON** рядом с анализом: `storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json`
  (массив `snapshots`, режимы A / B / A+B, маркер `has_signals`).
- **Статистика paper-trades**: `journal_cli.py paper-stats` (с разбивками по kind/trend/score/ADX/сессии).
- **Детальная таблица сделок**: `journal_cli.py paper-trades --wide` (ADX, Bid/Ask, R:R).
- **Тянет свечи** с MOEX ISS (с лагом) **или ALOR WebSocket (real-time, лаг 5 мин)**.
- **Экспорт paper-trades в CSV**: `journal_cli.py paper-export` → `storage/exports/paper_trades.csv`.
- **Недельный тренд** (`week_trend`): bullish / bearish / neutral по H4 (EMA50/200, close vs close-5d, close vs open-5d). Пишется в `paper_trades.week_trend_at_open`.
- **Разрезы `paper-stats`**: `by_week_trend`, `by_week_trend_direction` (week × long/short), `by_pressure` (bid/ask), `by_bars` (скорость закрытия).
- **Дедупликация без kind**: `bounce` + `trend_level` на одном уровне (direction + level_price) — это один сигнал (с большим score).
- **PF и expectancy**: `paper_stats` — profit_factor и expectancy.
- **Фильтры**: `bullish / long` и `normal + breakout/trend_level` (в Y включены, в F — нет).
- **`market_state`**: impulse / pullback / normal (по `impulse_atr`).
- **`by_rsi`** и **`by_atr_percentile`**: разрезы по RSI на входе и волатильности.
- **MFE/MAE** (max favorable/adverse excursion) — для тюнинга стопов/тейков.
- **`by_mfe_ratio`** — разрез по MFE/take (<0.3, 0.3-0.7, >0.7).
- **`--known-only`** + **`--min-n`** в `paper-stats` — чистые разрезы (без `unknown`).
- **`expectancy`** в каждом бакете `paper-stats`.
- **`partial_day`** — день не завершён (до 18:00), `day_open`/`day_atr_base`/`day_range_atr`.
- **Replay** (`analyze_from_df` + `verify_candles.py`) — прогон истории из `candles_*.json`.
- **`verify_filters.py`** — эффект фильтров Y на истории (win/loss/timeout).
- **Filter Registry** (`strategy/filters/`) — все фильтры в одном месте, `apply_filters` в `detect_signals`.

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

## Конфигурация

Все параметры (`config.py`), флаги фильтров, режимы paper/real, сохранение свечей —
в `CONFIG.md`. Обоснование фильтров — в `EXPERIMENTS.md`.

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
| `python journal_cli.py paper-stats --by-adx`                | Разбивка по ADX                        |
| `python journal_cli.py paper-stats --by-session`            | Разбивка по сессии                     |
| `python journal_cli.py paper-trades`                        | Показать paper-сделки (таблица)        |
| `python journal_cli.py paper-trades --open`                 | Только открытые                        |
| `python journal_cli.py paper-trades --limit=10`             | Последние 10                           |
| `python journal_cli.py paper-trades --symbol=CNYRUBF`       | Фильтр по тикеру                       |
| `python journal_cli.py paper-trades --wide`                 | ADX, Bid/Ask, R:R                      |
| `python journal_cli.py paper-trades --open --wide`          | Только открытые + расширенные поля     |
| `python journal_cli.py paper-export`                        | Экспорт paper_trades в CSV             |
| `python journal_cli.py paper-export --since=2026-10-20`     | CSV с даты                             |
| `python journal_cli.py paper-export --symbol=CNYRUBF`       | CSV по тикеру                          |
| `python journal_cli.py paper-vs-real`                       | Лаг paper entry vs market (пункты)     |
| `python journal_cli.py paper-vs-real --since=2026-10-27`    | Лаг с даты                             |

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

### Бэктестер: `backtest.py`

Честный replay paper-логики на исторических свечах (`candles_*.json`), без look-ahead.

| Команда                                                            | Описание                                                            |
| ------------------------------------------------------------------ | ------------------------------------------------------------------- |
| `python scripts/backtest.py --since 2026-11-11 --until 2026-11-19` | Backtest с текущим конфигом                                         |
| `... --compare`                                                    | Сравнить `current_config` vs `baseline` vs `skip_breakout` vs F1–F4 |
| `... --skip-breakout`                                              | `PAPER_SKIP_BREAKOUT=True`                                          |
| `... --breakout-filter F1`                                         | Применить `BREAKOUT_FILTER="F1"`                                    |

**Как работает:**

- читает `candles_M15_*.json` за период (склейка snapshots, дедуп по `begin`);
- идёт по барам **последовательно** (`df.iloc[:t+1]`, без look-ahead);
- резолвит через `virtual_pnl` + `compute_trade_result` (с комиссией);
- `--compare` — `run_backtest(skip_filters=True)` для изолированных вариантов.

**Ограничение:** `candles_*.json` есть только с 11.11 — backtest возможен на 11–19.11.

### `paper-stats` (с депозитом)

```
Всего: 48 (закрытых 40, открытых 1)
Win: 18
Loss: 21
Timeout: 1
Winrate: 46.2% (без timeout)
Total PnL: +399.8 pts / +317.40 ₽
Депозит: 3000 ₽ → 3301.46 ₽ (+10.05%)
Max drawdown: 7.04%
Avg win: +54.9 pts
Avg loss: -28.8 pts
Profit factor: 1.46
Expectancy: +9.9 pts
```

Каждый цикл раннера:

1. Новые сигналы записываются в `paper_trades` (только в 09:00–18:00 МСК).
2. Открытые paper-сделки резолвятся по stop/take/timeout (50 M15-свечей).
3. Результат считается с комиссией (`compute_trade_result`).

**Что НЕ делает:** не торгует, не отправляет ордера, не трогает `journal.db/trades`.

## Структура проекта

- `trader/` — журнал, paper-tracking, real (мок), экспорт CSV.
- `data/` — MOEX ISS, ALOR WebSocket, SQLite, ресемплинг, candles_export.
- `core/` — analyzer, instruments, models, risk, logger.
- `ui/` — console, json, notify.
- `strategy/` — signals, levels, references, filters/, signal_history.
- `indicators/` — calc (EMA, RSI, ADX, ATR).
- `scripts/` — backtest, verify*\*, optimize*\*, backfill_mfe_mae.
- `tests/` — pytest (юнит + интеграционные).

## 📊 Data Management

Приложение использует **SQLite** для хранения всех типов данных. Структура хранения оптимизирована для разделения потоков данных:

- `storage/market.db`: Хранит сырые рыночные данные (свечи, стакан).
- `storage/journal.db`: Хранит историю торговых сделок и результаты виртуального трейдинга.

### Paper-Tracking Infrastructure
Для системы виртуального трейдинга реализована продвинутая архитектура управления данными:
- **Layered Architecture**: Логика расчетов (PnL, статистика) полностью отделена от механизма доступа к данным (DAO pattern).
- **Automatic Migrations**: Система использует `PRAGMA user_version` для управления версиями схемы базы данных. Новые колонки добавляются автоматически в процессе инициализации.
- **Dynamic Schema Mapping**: Метод записи сделок автоматически определяет список доступных колонок в БД, что исключает ошибки рассинхронизации кода и структуры таблицы.


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

---

### Что **не** делаем

- Авто-торговля (только ручное подтверждение).
- Риск > 1% депозита.
- Реальные ордера без тестов.

## Тесты

Все тесты — на **pytest**. **Конфиг** — в `pyproject.toml` (`[tool.pytest.ini_options]`).

**Команды:**

| Команда                                                                         | Что делает                                          |
| ------------------------------------------------------------------------------- | --------------------------------------------------- |
| `pytest tests/ -v -m "not integration"`                                         | **Все быстрые тесты** (без сети) — **основная**     |
| `pytest tests/ -v -m integration`                                               | Только интеграционные (ALOR / MOEX ISS, нужна сеть) |
| `pytest tests/ -v -m ""`                                                        | Все тесты (включая интеграционные)                  |
| `pytest tests/test_instruments.py -v`                                           | Один файл                                           |
| `pytest tests/test_instruments.py::TestComputeTradeResult::test_long_profit -v` | Один тест                                           |

**Структура:**

- **Юнит-тесты** (без сети): `test_instruments`, `test_levels`, `test_indicators`, `test_current_price` (мок), `test_notify`, `test_virtual_pnl`, `test_paper*`, `test_mfe_mae`, `test_real_trading` (мок), `test_alor_trade` (мок).
- **Интеграционные** (сеть): `test_alor_integration`, `test_alor_orderbook`, `test_iss_lag`, `test_pagination` — помечены `@pytest.mark.integration`.
- **`test_journal_integrity`** — проверка **реальной** `journal.db` (skip, если нет файла).

**Покрытие** (на 2026-11-20): **162 passed**.

## Ссылки

```
- `EXPERIMENTS.md` — журнал экспериментов (breakout, MFE/MAE, adaptive take).
- `BRANCHES.md` — ветки F/Y/aggressive, режимы, сравнения.
- `ROADMAP.md` — этапы развития.
- `CHANGELOG.md` — история версий.
- `NOTES.md` — ежедневные наблюдения.
- `CONFIG.md` — параметры `config.py`, флаги, фильтры, режимы.
```

## Дисклеймер

Это **инструмент для анализа**, не торговая система. Сигналы — не рекомендации.
Все решения принимает пользователь. Автор не несёт ответственности за торговые результаты.

## Лицензия

См. `LICENSE`.
