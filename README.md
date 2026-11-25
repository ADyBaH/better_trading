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
- **Раннер**: периодический анализ каждые **5 минут** с сохранением по дням.
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
- **Bootstrap CI** (T-04): `paper_stats` — `pf_ci`, `exp_ci`, `winrate_ci`. `paper-stats` выводит `[lo, hi]`.
- **`paper_skipped`** (T-05): заблокированные сигналы (reason: filter, penalty, data_age). `journal_cli.py paper-skipped`.
- **`schema_versions`** (T-06): единый `trader/db.py`, миграции для 4 таблиц (`paper_trades`, `paper_skipped`, `trades`, `candles`).
- **Pre-registration** (T-07): `EXPERIMENT_ID` (env), `--experiment` в `paper-stats`, шаблон в `EXPERIMENTS.md`.
- **Ablation** (T-08): `scripts/ablation.py` (unpaired bootstrap, CI, пересечения).

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
| `python journal_cli.py paper-stats --experiment=EXP-...`    | T-07: фильтр по эксперименту           |
| `python journal_cli.py paper-skipped`                       | T-05: заблокированные сигналы (reason) |
| `python journal_cli.py paper-skipped --since=2026-11-22`    | T-05: с даты                           |
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

Автоматический запуск анализа каждые **5 минут** (`INTERVAL_MIN = 5`). Результаты сохраняются в `storage/logs/YYYY-MM-DD/`.

| Команда            | Описание                                |
| ------------------ | --------------------------------------- |
| `python runner.py` | Запустить раннер (цикл, каждые 5 минут) |
| `Ctrl+C`           | Остановить раннер                       |

**Что делает:**

- Каждые 5 минут запускает `analyze()`.
- Сохраняет результат в `storage/logs/YYYY-MM-DD/analysis_YYYY-MM-DD.json` и `.txt`.
- Логи сортируются по дням — старые не засоряются.
- Работает как фоновый процесс — остановка `Ctrl+C`.

**Пример вывода:**

```text
[цикл #1] 20:59:08
══════════════════════════════════════════════════════════════════
2026-10-15 20:59:11 | CNYRUBF | Цена: 12.519
Тренд: strong_down (голосов -3) | День: neutral | Структура: bearish
Сигналов: 0
Сохранено: analysis_2026-10-15.json, analysis_2026-10-15.txt
══════════════════════════════════════════════════════════════════
Следующий запуск ~21:04:11
```

### Бэктестер: `scripts/backtest.py`

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

### Ablation: `scripts/ablation.py` (T-08)

Ablation study фильтров (unpaired bootstrap, CI).

| Команда                                                            | Описание               |
| ------------------------------------------------------------------ | ---------------------- |
| `python scripts/ablation.py --since 2026-11-11 --until 2026-11-19` | Ablation всех фильтров |
| `... --only bullish_long`                                          | Только один фильтр     |
| `... --json`                                                       | Вывод в JSON           |

### `paper-stats` (с депозитом)

```text
Всего: 82 (закрытых 74, открытых 1)
Win: 26
Loss: 42
Timeout: 6
Winrate: 38.2% (без timeout) [26.5%, 50.0%]
Total PnL: +302.3 pts / +149.86 ₽
Депозит: 3000 ₽ → 3099.22 ₽ (+3.31%)
Max drawdown: 8.12%
Avg win: +51.7 pts
Avg loss: -26.3 pts
Profit factor: 1.08 [0.68, 1.99]
Expectancy: +3.5 pts [-6.1, +13.2]
```

**⚠️ CI включает breakeven** (PF [0.68, 1.99], Exp [-6.1, +13.2]) → **стратегия статистически не доказана**. См. `EXPERIMENTS.md` EXP-20261122-01.

Каждый цикл раннера:

1. Новые сигналы записываются в `paper_trades` (только в 09:00–18:00 МСК).
2. Открытые paper-сделки резолвятся по stop/take/timeout (20 M15-свечей, `PAPER_TIMEOUT_BARS`).
3. Результат считается с комиссией (`compute_trade_result`).

**Что НЕ делает:** не торгует, не отправляет ордера, не трогает `journal.db/trades`.

## Структура проекта

- `trader/` — журнал, paper-tracking, real (мок), экспорт CSV, **analytics/** (paper_stats, compute_stats, group).
- `data/` — MOEX ISS, ALOR WebSocket, SQLite, ресемплинг, candles_export.
- `core/` — analyzer, instruments, models, risk, logger, real_mode, db.
- `ui/` — console, json, notify.
- `strategy/` — signals, levels, references, filters/, signal_history.
- `indicators/` — calc (EMA, RSI, ADX, ATR).
- `scripts/` — backtest, ablation, verify*, optimize*, backfill_mfe_mae.
- `tests/` — pytest (юнит + интеграционные).

## 📊 Data Management

Приложение использует **SQLite** для хранения всех типов данных. Структура хранения оптимизирована для разделения потоков данных:

- `storage/market.db`: Хранит сырые рыночные данные (свечи, стакан).
- `storage/journal.db`: Хранит историю торговых сделок и результаты виртуального трейдинга.

### Paper-Tracking Infrastructure

Для системы виртуального трейдинга реализована продвинутая архитектура управления данными:

- **Layered Architecture**: Логика расчетов (PnL, статистика) полностью отделена от механизма доступа к данным (DAO pattern).
- **Schema Versions (T-06)**: Единый `trader/db.py` + `schema_versions` (версия на каждую таблицу, не общий `PRAGMA user_version`). Миграции для `paper_trades` (29), `paper_skipped` (1), `trades` (1), `candles` (1). Новые колонки добавляются автоматически.
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

1. **Данные**: свечи тянутся с MOEX ISS или ALOR WebSocket, кэшируются в `storage/market.db`. Если последняя свеча старше `CACHE_TTL_MINUTES` — докачка новых.
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

- **Юнит-тесты** (без сети): `test_instruments`, `test_levels`, `test_indicators`, `test_current_price` (мок), `test_notify`, `test_virtual_pnl`, `test_paper*`, `test_mfe_mae`, `test_real_trading` (мок), `test_alor_trade` (мок), `test_bootstrap`, `test_paper_skipped`, `test_real_mode`, `test_no_lookahead`.
- **Интеграционные** (сеть): `test_alor_integration`, `test_alor_orderbook`, `test_iss_lag`, `test_pagination` — помечены `@pytest.mark.integration`.
- **`test_journal_integrity`** — проверка **реальной** `journal.db` (skip, если нет файла).

**Покрытие** (на 2026-11-22): **305+ passed** (+ T-04/T-05/T-06/T-07/T-12/T-13).

## Ссылки

- `EXPERIMENTS.md` — журнал экспериментов (breakout, MFE/MAE, adaptive take, ablation, pre-registration).
- `BRANCHES.md` — ветки F/Y/aggressive, режимы, сравнения.
- `ROADMAP.md` — этапы развития.
- `CHANGELOG.md` — история версий.
- `NOTES.md` — ежедневные наблюдения.
- `CONFIG.md` — параметры `config.py`, флаги, фильтры, режимы.

## Дисклеймер

Это **инструмент для анализа**, не торговая система. Сигналы — не рекомендации.
Все решения принимает пользователь. Автор не несёт ответственности за торговые результаты.

## Лицензия

См. `LICENSE`.
