# CONFIG — параметры и настройки trade-assistant

Справочник по `config.py`: флаги, параметры, режимы, фильтры.
Историю экспериментов и обоснования — см. `EXPERIMENTS.md`.
Ветки и режимы — см. `BRANCHES.md`.

---

## Инструмент и таймфреймы

| Параметр             | Значение              | Описание                                                     |
| -------------------- | --------------------- | ------------------------------------------------------------ |
| `DEFAULT_INSTRUMENT` | `"CNYRUBF"`           | Инструмент по умолчанию (ссылается на `core/instruments.py`) |
| `TIMEFRAMES`         | `["M5", "M15", "H1"]` | Доступные таймфреймы                                         |
| `DEFAULT_TIMEFRAME`  | `"M15"`               | Таймфрейм по умолчанию                                       |
| `LEVEL_TIMEFRAMES`   | `["H4", "H1", "M15"]` | ТФ для построения уровней                                    |

---

## Индикаторы

| Параметр     | Значение | Описание                 |
| ------------ | -------- | ------------------------ |
| `EMA_FAST`   | `50`     | Быстрая EMA              |
| `EMA_SLOW`   | `200`    | Медленная EMA            |
| `RSI_PERIOD` | `14`     | Период RSI               |
| `ADX_PERIOD` | `14`     | Период ADX               |
| `ATR_PERIOD` | `14`     | Период ATR               |
| `ATR_TF`     | `"H1"`   | ТФ для ATR (стопы/тейки) |

---

## Уровни

| Параметр              | Значение | Описание                           |
| --------------------- | -------- | ---------------------------------- |
| `FRACTAL_PERIOD`      | `2`      | Период фрактала                    |
| `LEVEL_TOLERANCE_ATR` | `0.25`   | Допуск кластеризации (× ATR)       |
| `LEVELS_RANGE_ATR`    | `2.5`    | Фильтр уровней вокруг цены (× ATR) |
| `LEVELS_MIN_WEIGHT`   | `2`      | Минимальный вес кластера           |
| `LEVELS_MAX_SHOW`     | `7`      | Максимум уровней в выводе          |

---

## Сигналы

| Параметр                    | Значение | Описание                   |
| --------------------------- | -------- | -------------------------- |
| `BOUNCE_TOLERANCE_ATR`      | `0.5`    | Допуск bounce (× ATR)      |
| `TREND_LEVEL_TOLERANCE_ATR` | `0.5`    | Допуск trend_level (× ATR) |
| `BREAKOUT_BUFFER_ATR`       | `0.1`    | Буфер пробоя (× ATR)       |
| `RSI_BOUNCE_LONG`           | `35`     | RSI для long-bounce        |
| `RSI_BOUNCE_SHORT`          | `65`     | RSI для short-bounce       |
| `ADX_BREAKOUT_THRESHOLD`    | `25`     | ADX для breakout           |
| `VOLUME_MULTIPLIER`         | `1.2`    | Множитель объёма           |
| `VOLUME_RATIO_CAP`          | `5.0`    | Клип volume_ratio          |

---

## Стопы и тейки

| Параметр                | Значение | Описание                                               |
| ----------------------- | -------- | ------------------------------------------------------ |
| `USE_ATR_STOPS`         | `True`   | Стопы от ATR (а не фикс. пункты)                       |
| `STOP_ATR_MULT`         | `1.0`    | Стоп = 1.0 × ATR(H1)                                   |
| `TAKE_ATR_MULT`         | `2.0`    | Тейк = 2.0 × ATR(H1)                                   |
| `ADAPTIVE_TAKE_ENABLED` | `True`   | Адаптивный take (см. `EXPERIMENTS.md` EXP-20261120-02) |
| `TAKE_DAY_RANGE_FRAC`   | `0.6`    | `take = min(2.0×ATR, 0.6×day_range_atr×ATR)`           |
| `MIN_TAKE_ATR`          | `0.8`    | Минимальный take (× ATR)                               |

---

## Данные и кэш

| Параметр             | Значение | Описание                                |
| -------------------- | -------- | --------------------------------------- |
| `DATA_PROVIDER`      | `"alor"` | `"alor"` (real-time) или `"moex"` (ISS) |
| `CACHE_TTL_MINUTES`  | `4`      | TTL кэша (для ALOR)                     |
| `DATA_MAX_AGE_MIN`   | `5`      | Макс. возраст данных (мин)              |
| `DATA_MAX_AGE_BLOCK` | `15`     | Блокировка анализа при большем лаге     |

---

## Виртуальный депозит и риск

| Параметр             | Значение | Описание                |
| -------------------- | -------- | ----------------------- |
| `VIRTUAL_DEPOSIT`    | `3000`   | Виртуальный депозит (₽) |
| `RISK_PER_TRADE_PCT` | `0.01`   | Риск на сделку (1%)     |

---

## Paper-tracking

| Параметр              | Значение             | Описание                        |
| --------------------- | -------------------- | ------------------------------- |
| `PAPER_ENABLED`       | `True`               | Включить paper-tracking         |
| `PAPER_TRADING_HOURS` | `("09:00", "18:00")` | Торговые часы (МСК)             |
| `PAPER_TIMEOUT_BARS`  | `60`                 | Таймаут резолва (M15-свечей)    |
| `PAPER_DEDUP_MINUTES` | `5`                  | Окно эха дедупликации           |
| `PAPER_MAX_OPEN`      | `1`                  | Лимит открытых (0 — без лимита) |

---

## Real-trading (мок)

| Параметр            | Значение | Описание                                   |
| ------------------- | -------- | ------------------------------------------ |
| `REAL_TRADING_MODE` | `"mock"` | `"mock"` (ордера не ставятся) или `"live"` |
| `_MOCK_MODE`        | `True`   | Внутренний флаг мок-режима                 |

**Включение реальных ордеров** — только после 2 недель paper с winrate 70%+, на малом депозите (1% риск), с ручным подтверждением. См. `BRANCHES.md` → «Режимы».

---

## Сохранение свечей в JSON

| Параметр                     | Значение  | Описание                                        |
| ---------------------------- | --------- | ----------------------------------------------- |
| `SAVE_CANDLES`               | `True`    | Глобальный выключатель                          |
| `SAVE_CANDLES_ALWAYS`        | `True`    | **A**: каждый цикл / **B**: только при сигналах |
| `SAVE_CANDLES_MARK_SIGNALS`  | `True`    | Ставить `has_signals` / `signals_count`         |
| `SAVE_CANDLES_TIMEFRAMES`    | `["M15"]` | Какие ТФ сохранять                              |
| `SAVE_CANDLES_COUNT`         | `300`     | Сколько свечей в снимке                         |
| `SAVE_CANDLES_MAX_SNAPSHOTS` | `300`     | Защита от разрастания файла                     |

**Режимы:**

- **A** = `ALWAYS=True, MARK_SIGNALS=False` — все свечи, без маркера.
- **B** = `ALWAYS=False, MARK_SIGNALS=True` — только при сигналах, с маркером.
- **A+B** = `ALWAYS=True, MARK_SIGNALS=True` — все свечи + маркер (текущий).

**Формат файла** (`storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json`):

```
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
      "candles": [
        {
          "begin": "...",
          "open": 12.275,
          "high": 12.283,
          "low": 12.273,
          "close": 12.279,
          "volume": 21579
        }
      ]
    }
  ]
}
```

---

## Фильтры сигналов

Применяются в `strategy/signals.py` → `detect_signals()` через `strategy/filters/` (Filter Registry).
Порядок: фильтры → `_finalize_signal` → штрафы EMA/пила/late-chase.

### Глобальные (все kind)

| Флаг                           | Значение в Y | Что блокирует                                             | Статистика                         |
| ------------------------------ | ------------ | --------------------------------------------------------- | ---------------------------------- |
| `PAPER_SKIP_BULLISH_LONG`      | `True`       | LONG при `week_trend == "bullish"`                        | −103 ₽ (replay 11/13.11) — полезен |
| `PAPER_SKIP_NORMAL_BREAKOUT`   | `True`       | `breakout` / `trend_level` при `market_state == "normal"` | −139.72 ₽ (n=17) — полезен         |
| `PAPER_SKIP_BULLISH_SHORT`     | `False`      | SHORT при `week_trend == "bullish"`                       | +21.72 ₽ (n=8) — **НЕ включать**   |
| `PAPER_SKIP_ADX_FLAT_BREAKOUT` | `False`      | `breakout` при ADX < 20                                   | +50.28 ₽ (n=7) — **НЕ включать**   |
| `PAPER_SKIP_PULLBACK_BOUNCE`   | `True`       | `bounce` при `market_state == "pullback"`                 | 10 сделок, 1W/7L, −81.94 ₽         |
| `PAPER_SKIP_ADX_TREND`         | `True`       | все kind при ADX 20–25                                    | 17 сделок, 1W/12L, −256.36 ₽       |
| `PAPER_SKIP_BID_HEAVY`         | `True`       | все kind при `pressure_pct > 60`                          | 6 сделок, 0W/5L, −150.30 ₽         |

Обоснование — в `EXPERIMENTS.md` (EXP-20261119-01) и `NOTES.md` (наблюдения 11.11/17.11).

### Breakout: kill-switch и условные фильтры

| Флаг                  | Значение | Что делает                                            |
| --------------------- | -------- | ----------------------------------------------------- |
| `PAPER_SKIP_BREAKOUT` | `False`  | `True` — `breakout` не создаётся вообще (kill-switch) |
| `BREAKOUT_FILTER`     | `"none"` | `"none"` / `"F1"` / `"F2"` / `"F3"` / `"F4"`          |

**Условные фильтры** (взаимоисключающие, только для `kind == "breakout"`):

| Код  | Условие прохождения                                             | Гипотеза                                                         |
| ---- | --------------------------------------------------------------- | ---------------------------------------------------------------- |
| `F1` | `ADX >= 25` (strong)                                            | breakout в trend (20–25) — пила, в strong — импульс              |
| `F2` | `ADX < 20` (flat)                                               | flat — лучший ADX-бакет (+303.82 ₽ на 19 сделках)                |
| `F3` | `market_state == "impulse"`                                     | breakout в normal/pullback убыточен; impulse — не проверен (n=0) |
| `F4` | `week_trend` не противоречит `direction` (`neutral` пропускаем) | совпадение с недельным трендом                                   |

**Композиция с `PAPER_SKIP_ADX_TREND`:** ADX 20–25 режется `PAPER_SKIP_ADX_TREND` **раньше**, чем доходит до F1/F2. F1 оставляет только ≥ 25, F2 — < 20. Пересечения нет.

**Композиция `PAPER_SKIP_BREAKOUT` и `BREAKOUT_FILTER`:** kill-switch проверяется **первым** (если `True` — breakout не создаётся, `BREAKOUT_FILTER` не имеет значения). Если `PAPER_SKIP_BREAKOUT=False` — работает `BREAKOUT_FILTER`.

---

## Рынок: market_state

| Параметр       | Значение                          | Описание               |
| -------------- | --------------------------------- | ---------------------- |
| `impulse_atr`  | `> 2.0`                           | Импульс (12 M15 / ATR) |
| `pullback_atr` | `> 1.2` и откат `< 0.7 × impulse` | Откат                  |
| `market_state` | `normal` / `pullback` / `impulse` | Состояние рынка        |

> ⚠️ **Известное ограничение:** `pullback` пока не создаёт сделки (окно 6 M15 слишком большое). Планируется снизить до 3 M15.

---

## Интерактивный ввод `journal_cli.py add`

| Поле         | Значение                                                 |
| ------------ | -------------------------------------------------------- |
| Символ       | `CNYRUBF` (Enter — по умолчанию)                         |
| Направление  | `l` / `s` (или `long` / `short`)                         |
| Цена входа   | с точкой — `12.513`                                      |
| Размер       | количество контрактов                                    |
| Стоп / Тейк  | цены или Enter (пропустить)                              |
| Комментарий  | свободный текст                                          |
| Теги         | через запятую — `setup,from_signal`                      |
| Тип сигнала  | `bounce` / `breakout` / `trend_level` или Enter (manual) |
| Сила сигнала | `weak` / `medium` / `strong`                             |
| Score        | число                                                    |
| Комиссия     | Enter — из спецификации, или число                       |

---

## Как проверить эффект фильтров

```
# Replay-эффект F1–F4 на истории (с комиссией, PF/exp)
python scripts/verify_filters.py --date 2026-11-13

# Сверка replay с живым paper (match rate)
python scripts/verify_candles.py --date 2026-11-13

# Живой paper (Y): до/после
python journal_cli.py paper-stats --until=2026-11-19
python journal_cli.py paper-stats --since=2026-11-19
```

---

## Ссылки

- `EXPERIMENTS.md` — журнал экспериментов (breakout, MFE/MAE, adaptive take).
- `BRANCHES.md` — ветки F/Y/aggressive, режимы, сравнения.
- `README.md` — установка, быстрый старт, CLI Reference.
- `ROADMAP.md` — этапы развития.
- `CHANGELOG.md` — история версий.
- `NOTES.md` — ежедневные наблюдения.
