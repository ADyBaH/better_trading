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
| `python journal_cli.py paper-export`                        | Экспорт paper_trades в CSV             |
| `python journal_cli.py paper-export --since=2026-10-27`     | CSV с даты                             |
| `python journal_cli.py paper-vs-real`                       | Лаг paper entry vs market (пункты)     |
| `python journal_cli.py paper-vs-real --since=2026-10-27`    | Лаг с даты                             |

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

### Бэктестер: `backtest.py`

Честный replay paper-логики на исторических свечах (`candles_*.json`), без look-ahead.

| Команда | Описание |
| --- | --- |
| `python scripts/backtest.py --since 2026-11-11 --until 2026-11-19` | Backtest с текущим конфигом |
| `... --compare` | Сравнить `current_config` vs `baseline` vs `skip_breakout` vs F1–F4 |
| `... --skip-breakout` | `PAPER_SKIP_BREAKOUT=True` |
| `... --breakout-filter F1` | Применить `BREAKOUT_FILTER="F1"` |

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

### Сохранение свечей в JSON

`runner.py` после каждого `save_analysis` дописывает снимок свечей в
`storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json` — рядом с `analysis_*.json`.

Управляется флагами в `config.py`:

| Флаг                         | Значение         | Что делает                                       |
| ---------------------------- | ---------------- | ------------------------------------------------ |
| `SAVE_CANDLES`               | `True` / `False` | Глобальный выключатель                           |
| `SAVE_CANDLES_ALWAYS`        | `True`           | **A**: писать каждый цикл                        |
|                              | `False`          | **B**: писать только когда есть сигналы          |
| `SAVE_CANDLES_MARK_SIGNALS`  | `True`           | Ставить `has_signals` / `signals_count` в снимке |
| `SAVE_CANDLES_TIMEFRAMES`    | `["M15"]`        | Какие ТФ сохранять (можно `["M15","H1","H4"]`)   |
| `SAVE_CANDLES_COUNT`         | `300`            | Сколько свечей в снимке                          |
| `SAVE_CANDLES_MAX_SNAPSHOTS` | `300`            | Защита от разрастания файла                      |

**Режимы:**

- **A** = `ALWAYS=True, MARK_SIGNALS=False` — все свечи, без маркера.
- **B** = `ALWAYS=False, MARK_SIGNALS=True` — только при сигналах, с маркером.
- **A+B** = `ALWAYS=True, MARK_SIGNALS=True` — все свечи + маркер, где были сигналы (текущий).

**Формат:**

````json
{
  "symbol": "CNYRUBF",
  "timeframe": "M15",
  "date": "2026-11-11",
  "count": 1,
  "last_updated": "2026-11-11T18:09:29",
  "snapshots": [
    {
      "saved_at": "2026-11-11T18:09:29",
      "has_signals": true,
      "signals_count": 1,
      "count": 300,
      "candles": [{"begin": "...", "open": 12.275, "high": 12.283, "low": 12.273, "close": 12.279, "volume": 21579}]
    }
  ]
}
````

## Ветки и их роли

### `main` (F)
- **Роль:** основная ветка (reference).
- **Настройки:** без фильтров, 120 сделок.
- **База:** `storage/journal.db`.
- **Цель:** сравнение с `experiment/aggressive-signals` и `feature/real-trading`.

### `experiment/aggressive-signals` (F)
- **Роль:** агрессивный полигон.
- **Настройки:** без фильтров, сниженные пороги (`BOUNCE_TOLERANCE_ATR = 0.4`, `TREND_LEVEL_TOLERANCE_ATR = 0.5`, `BREAKOUT_BUFFER_ATR = 0.1`, `ADX_BREAKOUT_THRESHOLD = 20`), расширенные часы (`PAPER_TRADING_HOURS` 09:00–20:00), `PAPER_DEDUP_MINUTES = 5`, `PAPER_MAX_OPEN = 0`.
- **База:** `storage/journal_aggressive.db`.
- **Цель:** накопить статистику быстрее (больше сигналов).

### `feature/real-trading` (Y)
- **Роль:** актуальная ветка (торгуем по ней).
- **Настройки:** с фильтрами (`PAPER_SKIP_BULLISH_LONG = True`, `PAPER_SKIP_NORMAL_BREAKOUT = True`), лимит 1, `PAPER_TRADING_HOURS` 09:00–18:00.
- **База:** `storage/journal.db` (в Y).
- **Цель:** торговля (PF 1.46, expectancy +9.9).

### Сравнение (17.11)

| Ветка | Сделок | Winrate | PnL | PF | Expectancy | Депозит |
|---|---|---|---|---|---|---|
| **Y (real-trading)** | 69 | 41.4% | +300.58 ₽ | **1.25** | **+6.2 pts** | +7.99% |
| **F (main)** | 84 | 30.0% | −273.04 ₽ | **0.63** | **−3.1 pts** | — |

**Y лучше F** по PF/expectancy — фильтры `bullish/long` и `normal+breakout` работают.

### Сравнение (11.11)

| Ветка | Сделок | Winrate | PnL | PF | Expectancy | Депозит |
|---|---|---|---|---|---|---|
| **Y (real-trading)** | 62 | 43.1% | +357.36 ₽ | **1.35** | **+7.8 pts** | +9.75% |
| **F (main)** | 56 | 29.5% | −172.48 ₽ | **0.61** | **−3.9 pts** | — |

**Y лучше F** по всем метрикам — фильтры `bullish/long` и `normal+breakout` работают.

**Просмотр:**

```bash
python journal_cli.py paper-stats
```

## Breakout: статус (Задача 3, 2026-11-19)

Baseline по `paper-stats`: 37 сделок, 10W/23L/1T, −71.54 ₽, exp −0.0.
Breakout — самый частый (47%) и убыточный; не работает ни в одном разрезе.

**Backtest на 11–19.11** (`scripts/backtest.py --compare`, 7 дней, M15):

| Вариант | n | W | L | T | Rub | PF | Exp | Решение |
|---|---|---|---|---|---|---|---|---|
| baseline (без `PAPER_SKIP_*`) | 23 | 5 | 14 | 4 | −201.88 | 0.44 | −8.1 | — |
| **skip breakout** (`PAPER_SKIP_BREAKOUT=True`) | 17 | 5 | 10 | 2 | **−84.02** | **0.73** | **−3.3** | **лучший (7 дней)** |
| F1 ADX≥25 | 21 | 5 | 12 | 4 | −161.16 | 0.51 | −6.9 | не работает |
| F2 ADX<20 | 18 | 5 | 11 | 2 | −103.68 | 0.67 | −4.2 | слабее skip |
| F3 impulse | 18 | 5 | 10 | 3 | −87.08 | 0.73 | −3.3 | = skip (нет impulse) |
| F4 week_trend | 23 | 5 | 14 | 4 | −201.88 | 0.44 | −8.1 | = baseline (бесполезен) |
| current_config (как в Y) | 15 | 4 | 10 | 1 | −89.70 | 0.62 | −4.2 | база Y |

**Выводы:**
- `PAPER_SKIP_BREAKOUT=True` — **лучший** результат (PF 0.73). Breakout — главный источник убытка.
- F1–F4 **не доказаны**: F4 = baseline (бесполезен), F3 = skip (нет impulse), F1 хуже базы, F2 слабее skip.
- `PAPER_SKIP_*` **работают**: current_config (0.62) > baseline (0.44).

**Оговорка:** n=15–23, 7 дней — **мало для статистики**. Нужно 30+ сделок и replay-гейт (match rate ≥ 70%).

**Флаги:** `PAPER_SKIP_BREAKOUT` (kill-switch), `BREAKOUT_FILTER` (`"none" | "F1" | "F2" | "F3" | "F4"`).

**Replay-гейт:** `scripts/verify_filters.py --date YYYY-MM-DD` (F1–F4, с комиссией).
**Backtest:** `scripts/backtest.py --since YYYY-MM-DD --until YYYY-MM-DD --compare` (честный replay, без look-ahead).
**Match rate:** `scripts/verify_candles.py --date YYYY-MM-DD` — сейчас 0% (replay применяет фильтры Y к историческим сигналам); replay-гейт заблокирован до фикса.

## MFE/MAE + stop/take (Задачи 4–5, 2026-11-20)

**Что сделано:**
- `volume_ratio_at_open`, `mfe_source`, `mae_source` в `paper_trades` (миграция).
- `by_volume_ratio`, `by_mae_ratio` в `paper_stats`.
- Backfill MFE/MAE по `candles_*.json`: **14 обновлено, 50 unavailable** (файлы с 11.11).
- `scripts/optimize_stops.py`: сетка 5×6 (stop × take), train/test, PF/exp.
- `paper-stats` — блок «Рекомендация stop/take» (read-only, `Confidence: low` при n<30).

**Результаты (backfill, n=14):**

| MFE ratio | n | W | L | T | Rub | Exp |
|---|---|---|---|---|---|---|
| <0.3 (не дошла) | 11 | 0 | 11 | 0 | −298.06 | −25.0 |
| 0.3–0.7 | 4 | 0 | 2 | 2 | −38.94 | −15.3 |
| >0.7 (почти/дошла) | 7 | 5 | 2 | 0 | +156.18 | +24.4 |

| MAE ratio | n | W | L | T | Rub | Exp |
|---|---|---|---|---|---|---|
| <0.3 (стоп далеко) | 6 | 4 | 0 | 2 | +180.84 | +48.3 |
| 0.3–0.7 | 1 | 0 | 1 | 0 | −26.26 | −24.2 |
| 0.7–1.0 (почти стоп) | 6 | 1 | 5 | 0 | −89.26 | −12.8 |
| ≥1.0 (был бы пробит) | 9 | 0 | 9 | 0 | −246.14 | −25.3 |

**Вывод:** тейк 2.0 ATR **слишком далёк** (11 сделок MFE < 0.3 — все loss), стоп 1.0 ATR **узок** (9 сделок MAE ≥ 1.0 — все loss). **Но** `optimize_stops.py` на n=14: **все** комбинации PF < 1, train/test **нестабильны** (0.6/2.0: train PF 0.4, test 2.03).

**Решение:** `STOP_ATR_MULT=1.0`, `TAKE_ATR_MULT=2.0` — **НЕ менять** до **n ≥ 30** (оверфит на 14 сделках). Пересмотреть через 2 недели.

**CLI:**
```bash
python scripts/backfill_mfe_mae.py --dry-run   # проверка
python scripts/backfill_mfe_mae.py             # заполнить MFE/MAE
python scripts/optimize_stops.py               # сетка stop × take
python journal_cli.py paper-stats              # блок «Рекомендация stop/take»
```
## Адаптивный take (Задача 1, 2026-11-20)

**Формула:** `take = min(2.0×ATR, 0.6×day_range_atr×ATR)`, но не меньше `0.8×ATR`.
**Fallback:** если `day_range_atr < 0.5` (partial_day) — `take = 2.0×ATR` (baseline).

**Флаги:**
- `ADAPTIVE_TAKE_ENABLED = True` (в config.py);
- `TAKE_DAY_RANGE_FRAC = 0.6`;
- `MIN_TAKE_ATR = 0.8`.

**Миграция `paper_trades`:**
- `take_source` (`atr` / `day_range`);
- `take_atr_value` (2.0×ATR в пунктах);
- `day_range_atr_at_open`.

**`paper-stats`:** разрез `by_take_source`.

**A/B на backtest 11–19.11:**

| Вариант | n | W | L | T | Rub | PF | Exp |
|---|---|---|---|---|---|---|---|
| baseline (take=2.0) | 23 | 5 | 14 | 4 | −201.88 | 0.44 | −8.1 |
| **adaptive take** | 23 | 5 | 14 | 4 | **−201.88** | **0.44** | **−8.1** |

**Вывод:** на 11–19.11 `day_range_atr ~3.5` (высокая волатильность) → `0.6 × 3.5 = 2.1 > 2.0` → `min` даёт `atr` → **адаптивный take = baseline** (не сработал).

**Решение:** `ADAPTIVE_TAKE_ENABLED=True` — **оставить** (для низкой волатильности `day_range_atr < 3.33`). Гипотеза **не проверена** на этих данных. Пересмотреть при накоплении волатильных дней или снизить `TAKE_DAY_RANGE_FRAC` до 0.5.

**CLI:**
```bash
python scripts/backtest.py --since 2026-11-11 --until 2026-11-19 --compare
python journal_cli.py paper-stats | grep -A 5 "take_source"
```

## Структура проекта

```
├── trader/
│   ├── journal.py              # журнал реальных сделок (SQLite, trades)
│   ├── paper.py                # paper-tracking (paper_trades)
│   ├── paper_export.py         # экспорт paper_trades в CSV
│   ├── paper_vs_real.py        # сравнение entry vs market (лаг)
│   ├── real.py                 # real-trading (мок-режим)
│   └── stats.py                # статистика журнала
│
├── data/
│   ├── api_moex.py             # запросы к MOEX ISS
│   ├── api_alor.py             # ALOR WebSocket (свечи, стакан, цена)
│   ├── api_alor_trade.py       # ALOR POST-ордера (мок-режим)
│   ├── api_facade.py           # кэш + докачка
│   ├── storage_sqlite.py       # хранение свечей
│   ├── candles_export.py       # сохранение свечей в JSON (рядом с analysis)
│   └── resample.py             # M1 → M5/M15/H1/H4
│
├── core/
│   ├── analyzer.py             # ядро анализа
│   ├── instruments.py          # спецификации + compute_trade_result
│   ├── models.py               # Level, Signal, AnalysisResult
│   ├── risk.py                 # calculate_position_size (риск → размер)
│   ├── logger.py               # логирование
│   ├── errors.py               # (отложено)
│   ├── scheduler.py            # (отложено)
│   └── state.py                # (отложено)
│
├── ui/
│   ├── render_console.py       # консольный дашборд
│   ├── render_json.py          # JSON-рендеры
│   └── notify.py               # звук + notifications.txt
│
├── scripts/
│   └── fix_open_trades.py      # закрыть open (expired)
│
├── tests/
│   ├── test_instruments.py     # compute_trade_result
│   ├── test_signals.py         # signals.py (23 проверки)
│   ├── test_levels.py          # levels.py (14 проверок)
│   ├── test_indicators.py      # calc.py (22 проверки)
│   ├── test_paper_stats_extra.py  # by_adx/by_session/by_hour/by_weekday (21)
│   ├── test_paper_export.py    # CSV-экспорт (9)
│   ├── test_alor_trade.py      # POST-ордера (мок) (9)
│   ├── test_real_trading.py    # risk + real (мок) (9)
│   ├── test_notify.py          # уведомления (5)
│   └── test_current_price.py   # get_current_price (5)
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
- **Виртуальный депозит**: `VIRTUAL_DEPOSIT = 3000` (₽), `RISK_PER_TRADE_PCT = 0.01` (1%).
- **Paper-tracking**: `PAPER_ENABLED`, `PAPER_TRADING_HOURS` (09:00–18:00),
  `PAPER_TIMEOUT_BARS = 60`, `PAPER_DEDUP_MINUTES = 5`.
- **Фильтры**: `PAPER_SKIP_BULLISH_LONG` (True в Y, False в F),
  `PAPER_SKIP_NORMAL_BREAKOUT` (True в Y, False в F).
- **`market_state`**: `impulse > 2.0`, `pullback > 1.2` и откат `< 0.7 × impulse`.
- **MFE/MAE**: `mfe_points`, `mae_points` в `paper_trades`.
- **Partial day**: `partial_day_at_open` в `paper_trades`, `by_partial_day` в `paper-stats`.
- **`DATA_MAX_AGE_MIN = 5`**, **`DATA_MAX_AGE_BLOCK = 15`** (ALOR лаг ~7 мин).
- **`VOLUME_RATIO_CAP = 5.0`** — клип volume_ratio.

## Фильтры сигналов (config.py)

Фильтры применяются в `strategy/signals.py` → `detect_signals()`. Порядок важен:
сигнал проходит фильтры **до** `_finalize_signal` (не тратим `compute_rr` на отсечённые)
и **до** штрафов EMA/пила/late-chase (фильтр работает на «сыром» сигнале).

### Глобальные (по статистике, все kind)

| Флаг | Значение в Y | Что блокирует | Статистика (обоснование) |
|---|---|---|---|
| `PAPER_SKIP_BULLISH_LONG` | `True` | LONG при `week_trend == "bullish"` | −103 ₽ (replay 11/13.11) — полезен |
| `PAPER_SKIP_NORMAL_BREAKOUT` | `True` | `breakout` / `trend_level` при `market_state == "normal"` | −139.72 ₽ (paper_trades, n=17) — полезен |
| `PAPER_SKIP_BULLISH_SHORT` | `False` | SHORT при `week_trend == "bullish"` | +21.72 ₽ (n=8) — **НЕ включать** |
| `PAPER_SKIP_ADX_FLAT_BREAKOUT` | `False` | `breakout` при ADX < 20 | +50.28 ₽ (n=7) — **НЕ включать** |
| `PAPER_SKIP_PULLBACK_BOUNCE` | `True` | `bounce` при `market_state == "pullback"` | 10 сделок, 1W/7L, −81.94 ₽ |
| `PAPER_SKIP_ADX_TREND` | `True` | все kind при ADX 20–25 | 17 сделок, 1W/12L, −256.36 ₽ |
| `PAPER_SKIP_BID_HEAVY` | `True` | все kind при `pressure_pct > 60` | 6 сделок, 0W/5L, −150.30 ₽ |

### Breakout: kill-switch и условные фильтры (Задача 3)

| Флаг | Значение | Что делает |
|---|---|---|
| `PAPER_SKIP_BREAKOUT` | `False` | `True` — `breakout` не создаётся вообще (kill-switch для эксперимента Y) |
| `BREAKOUT_FILTER` | `"none"` | Условный фильтр для `breakout`: `"none"` / `"F1"` / `"F2"` / `"F3"` / `"F4"` |

**Условные фильтры `BREAKOUT_FILTER`** (взаимоисключающие, применяются только к `kind == "breakout"`):

| Код | Условие прохождения | Гипотеза |
|---|---|---|
| `F1` | `ADX >= 25` (strong) | breakout в trend (20–25) — пила, в strong — импульс |
| `F2` | `ADX < 20` (flat) | flat — лучший ADX-бакет (+303.82 ₽ на 19 сделках) |
| `F3` | `market_state == "impulse"` | breakout в normal/pullback убыточен; impulse — не проверен (n=0) |
| `F4` | `week_trend` не противоречит `direction` (`neutral` пропускаем) | совпадение с недельным трендом |

**Композиция с `PAPER_SKIP_ADX_TREND`:** ADX 20–25 режется `PAPER_SKIP_ADX_TREND` **раньше**, чем доходит до F1/F2. F1 оставляет только ≥ 25, F2 — < 20. Пересечения нет.

**Композиция `PAPER_SKIP_BREAKOUT` и `BREAKOUT_FILTER`:** kill-switch проверяется **первым** (если `True` — breakout не создаётся, `BREAKOUT_FILTER` не имеет значения). Если `PAPER_SKIP_BREAKOUT=False` — работает `BREAKOUT_FILTER`.

### Как проверить эффект фильтров

```bash
# Replay-эффект F1–F4 на истории (с комиссией, PF/exp)
python scripts/verify_filters.py --date 2026-11-13

# Сверка replay с живым paper (match rate)
python scripts/verify_candles.py --date 2026-11-13

# Живой paper (Y): до/после
python journal_cli.py paper-stats --until=2026-11-19
python journal_cli.py paper-stats --since=2026-11-19
```
---

## Real-trading (мок-режим)

**Важно:** реальные ордера **НЕ** ставятся (`_MOCK_MODE = True`).

### Что есть

- `data/api_alor_trade.py`: `place_order`, `cancel_order`, `get_orders` (мок).
- `trader/real.py`: `open_real_trade`, `close_real_trade` (мок).
- `core/risk.py`: `calculate_position_size` (риск → размер).
- `ui/notify.py`: звук + `storage/logs/notifications.txt`.

### Как включить реальные ордера

1. `data/api_alor_trade.py`: `_MOCK_MODE = False`.
2. `trader/real.py`: `_MOCK_MODE = False`.
3. **Только** после 2 недель paper-tracking с winrate 70%+.
4. **Только** на **малом** депозите (1% риск).

### Что **не** делаем

- Авто-торговля (только ручное подтверждение).
- Риск > 1% депозита.
- Реальные ордера без тестов.

## Что в планах

- [ ] Telegram-уведомления (когда/если заработает).
- [ ] Автозапись сигналов в журнал.
- [ ] Failed breakout, retest.
- [ ] MACD, мульти-ТФ подтверждение сигналов (C), тесты уровня (E).
- [ ] Scheduler + VPS для автономной работы.
- [ ] Экспорт журнала в CSV / Excel.
- [ ] Тесты на ключевые модули.
- [ ] **MFE/MAE** — max favorable/adverse excursion.
- [ ] **`volume_ratio`** — объём на входе / средний объём.
- [ ] **`stale`** — флаг устаревшего уровня (>10 дней).
- [ ] **`data_age`** — в meta JSON.

## Тесты

Все тесты — на **pytest**. **Конфиг** — в `pyproject.toml` (`[tool.pytest.ini_options]`).

**Команды:**

| Команда | Что делает |
|---|---|
| `pytest tests/ -v -m "not integration"` | **Все быстрые тесты** (без сети) — **основная** |
| `pytest tests/ -v -m integration` | Только интеграционные (ALOR / MOEX ISS, нужна сеть) |
| `pytest tests/ -v -m ""` | Все тесты (включая интеграционные) |
| `pytest tests/test_instruments.py -v` | Один файл |
| `pytest tests/test_instruments.py::TestComputeTradeResult::test_long_profit -v` | Один тест |

**Структура:**
- **Юнит-тесты** (без сети): `test_instruments`, `test_levels`, `test_indicators`, `test_current_price` (мок), `test_notify`, `test_virtual_pnl`, `test_paper*`, `test_mfe_mae`, `test_real_trading` (мок), `test_alor_trade` (мок).
- **Интеграционные** (сеть): `test_alor_integration`, `test_alor_orderbook`, `test_iss_lag`, `test_pagination` — помечены `@pytest.mark.integration`.
- **`test_journal_integrity`** — проверка **реальной** `journal.db` (skip, если нет файла).

**Покрытие** (на 2026-11-20): **162 passed**, **6 failed** (`test_paper_end_of_day` — требует `end_of_day`, **в** **работе**).

## Дисклеймер

Это **инструмент для анализа**, не торговая система. Сигналы — не рекомендации.
Все решения принимает пользователь. Автор не несёт ответственности за торговые результаты.

## Лицензия

См. `LICENSE`.
