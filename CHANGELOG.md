# CHANGELOG

## [0.16.0] — 2026-11-20

### Добавлено

- **Filter Registry** (`strategy/filters/`) — все фильтры в одном месте.
  - `base.py`: `Filter`, `FilterResult`, `register_filter`, `apply_filters`, `get_filters`.
  - `trend.py`: `bullish_long`, `normal_breakout`, `bullish_short`.
  - `adx.py`: `adx_trend`, `adx_flat_breakout`.
  - `orderbook.py`: `bid_heavy`.
  - `bounce.py`: `pullback_bounce`.
  - `breakout.py`: kill-switch (`PAPER_SKIP_BREAKOUT`) + F1–F4 (`BREAKOUT_FILTER`) через `enabled_fn`.
- **`strategy/signals.py`**: 7+ `if getattr(config, ...): continue` → `apply_filters(s, result)`.
- **`scripts/verify_filters.py`**: `get_filters()` + PF/exp (больше не дублирует логику).
- **`tests/test_signals.py`**: 12 кейсов F1–F4 + kill-switch (pytest).

### Исправлено

- `detect_signals` — **только** `apply_filters` (фильтры), штрафы EMA/пила/late-chase — **отдельно** (это не фильтры).
- `get_recent_signal(..., now=None)` — `cutoff` и `age_min` от `now` (было `datetime.now()`).

### Известные ограничения

- `test_filters.py` — **TODO** (по одному тесту на фильтр).
- `verify_filters.py` — `_filter_blocks` применяет **все** фильтры (включая `enabled=False`); `enabled_str` — только для вывода. **Не баг** (для анализа эффекта), но **надо** документировать.

## [0.15.0] — 2026-11-20

### Тесты

- **Все** `check()`-**тесты** **переписаны** **на** **pytest** (15 **файлов**): `test_instruments` (17), `test_levels` (7), `test_indicators` (22), `test_current_price` (4), `test_notify` (5), `test_virtual_pnl` (8), `test_paper` (14), `test_paper_dedup` (9), `test_paper_resolve` (7), `test_paper_stats` (7), `test_paper_stats_extra` (4), `test_paper_export` (3), `test_real_trading` (5), `test_alor_trade` (4), `test_journal_integrity` (4, интеграционный).
- **Интеграционные** **помечены** `@pytest.mark.integration`.
- **`pyproject.toml`** — `[tool.pytest.ini_options]`.
- **`README.md`** — раздел «Тесты».

### Исправлено

- `_compute_stops` **возвращает** 3 **значения** (stop, take, meta) — **тесты** **обновлены**.
- `trader/paper.py` — `_columns`/`_placeholders` **согласованы** (SQL syntax).

### Известные ограничения

- `test_signals.py` — **не** **переписан** **на** **pytest** (**после** **рефактора** `signals.py`).
- `test_mfe_backfill.py` — **не** **переписан**.

## [0.14.0] — 2026-11-20

### Добавлено

- **Адаптивный take** (Задача 1): `take = min(2.0×ATR, 0.6×day_range_atr×ATR)`, не меньше `0.8×ATR`.
- **`ADAPTIVE_TAKE_ENABLED`**, **`TAKE_DAY_RANGE_FRAC=0.6`**, **`MIN_TAKE_ATR=0.8`** в `config.py`.
- **`_compute_stops`** → 3 значения (stop, take, meta).
- **`Signal.take_source`**, **`take_atr_value`**, **`day_range_atr_at_open`**.
- **Миграция `paper_trades`**: `take_source`, `take_atr_value`, `day_range_atr_at_open`.
- **`paper_stats`**: `by_take_source`.
- **`scripts/backtest.py`**: `adaptive_take` (A/B: baseline vs adaptive).

### Результат (11–19.11, n=23)

- **baseline (take=2.0):** PF=0.44, exp=−8.1.
- **adaptive take:** PF=0.44, exp=−8.1 — **идентично**.
- **Причина:** `day_range_atr ~3.5` → `0.6 × 3.5 = 2.1 > 2.0` → адаптивный **не сработал**.

### Решение

- `ADAPTIVE_TAKE_ENABLED=True` — **оставить** (для низкой волатильности).
- Гипотеза **не проверена** на высокой волатильности.

### Известные ограничения

- `by_take_source`: `unknown` у старых (80), новые — заполняются.
- Адаптивный take **не срабатывает** при `day_range_atr > 3.33`.

## [0.13.0] — 2026-11-20

### Добавлено

- **MFE/MAE + volume_ratio** (Задача 4): `volume_ratio_at_open`, `mfe_source`, `mae_source` в `paper_trades`.
- **`by_volume_ratio`**, **`by_mae_ratio`** в `paper_stats`.
- **`scripts/backfill_mfe_mae.py`**: backfill по `candles_*.json` (14 обновлено, 50 unavailable).
- **`scripts/optimize_stops.py`** (Задача 5): сетка stop × take, train/test, PF/exp.
- **`paper-stats`** — блок «Рекомендация stop/take» (read-only, `Confidence: low` при n<30).
- **`tests/test_mfe_backfill.py`**: 12 проверок (PF/exp, grid, ambiguous).

### Исправлено

- `journal_cli.py`: `Vol` после `Size` в `paper-trades --wide` (было сдвиг).
- `_calc_pf_exp`: timeout = loss (PF и exp согласованы).

### Результаты (n=14, 11–19.11)

- **MFE < 0.3**: 11L (все loss, −298 ₽) — тейк 2.0 ATR далёк.
- **MAE ≥ 1.0**: 9L (все loss, −246 ₽) — стоп 1.0 ATR узок.
- **`optimize_stops.py`**: все комбинации PF < 1, train/test нестабильны.

### Решение

- `STOP_ATR_MULT=1.0`, `TAKE_ATR_MULT=2.0` — **НЕ менять** до n ≥ 30 (оверфит).

### Известные ограничения

- `n=14` — мало (нужно 30+).
- `mfe_source=unavailable` у 50 (до 11.11, нет `candles_*.json`).
- `volume_ratio_at_open` — `unknown` у старых, новые — заполняются.

## [0.12.0] — 2026-11-19

### Добавлено

- **`PAPER_SKIP_BREAKOUT`** (kill-switch): `True` — `breakout` не создаётся вообще.
- **`BREAKOUT_FILTER`** (enum): `"none" | "F1" | "F2" | "F3" | "F4"` — условные фильтры для breakout.
  - F1: ADX ≥ 25 (strong) только.
  - F2: ADX < 20 (flat) только.
  - F3: `market_state == "impulse"` только.
  - F4: `week_trend` не противоречит `direction` (neutral пропускаем).
- **`strategy/signals.py`**: `_breakout_passes_filter()` + блоки в `detect_signals`.
- **`core/analyzer.py`**: `market_state = "impulse"` (impulse_atr > 2.0, retrace < 0.2 × impulse).
- **`core/analyzer.py`**: `analyze_from_df(write_history=True)` — `False` для backtest/replay.
- **`scripts/backtest.py`**: честный replay paper-логики (без look-ahead, `df.iloc[:t+1]`).
  - `_load_candles`: из `candles_*.json` (склейка snapshots, дедуп), fallback `get_candles_tf`.
  - `--compare`: `current_config` vs `baseline` vs `skip_breakout` vs F1–F4.
  - `run_backtest(skip_filters=True)` — изолированные варианты.
- **`scripts/verify_filters.py`**: F1–F4 безусловно, `compute_trade_result` (с комиссией), PF/exp.
- **`tests/test_signals.py`**: 12 кейсов на F1–F4 + kill-switch.

### Исправлено

- **`get_recent_signal(..., now=None)`**: `cutoff` и `age_min` от `now` (было `datetime.now()`).
  Чинит: match rate 0% в `verify_candles.py` (пила на реальной истории), ложный штраф «пила» в тестах.
- **`detect_signals`**: передаёт `now=result.timestamp` в `get_recent_signal`.

### Статистика (backtest 11–19.11, 7 дней)

| Вариант           | n   | W   | L   | T   | Rub        | PF       | Exp      |
| ----------------- | --- | --- | --- | --- | ---------- | -------- | -------- |
| baseline          | 23  | 5   | 14  | 4   | −201.88    | 0.44     | −8.1     |
| **skip_breakout** | 17  | 5   | 10  | 2   | **−84.02** | **0.73** | **−3.3** |
| F1 ADX≥25         | 21  | 5   | 12  | 4   | −161.16    | 0.51     | −6.9     |
| F2 ADX<20         | 18  | 5   | 11  | 2   | −103.68    | 0.67     | −4.2     |
| F3 impulse        | 18  | 5   | 10  | 3   | −87.08     | 0.73     | −3.3     |
| F4 week_trend     | 23  | 5   | 14  | 4   | −201.88    | 0.44     | −8.1     |
| current_config    | 15  | 4   | 10  | 1   | −89.70     | 0.62     | −4.2     |

**Вывод:** `skip_breakout` — лучший (PF 0.73). F1–F4 не доказаны (n=15–23, мало).

### Известные ограничения

- **n=15–23** — мало для статистики. Нужно 30+ сделок и replay-гейт (match rate ≥ 70%).
- **`verify_candles.py` match rate 0%** — replay применяет фильтры Y к историческим сигналам (фикс отдельно).
- **`candles_*.json` есть только с 11.11** — backtest возможен на 11–19.11.

## [0.9.0] — 2026-10-29

### Добавлено

- **week_trend** (недельный тренд): `get_week_trend`, `IndicatorSnapshot.week_trend`, `week_change_atr`.
- **paper_trades**: `week_trend_at_open` (миграция).
- **paper_stats**: `by_week_trend`, `by_week_trend_direction`.
- **journal_cli**: вывод `По недельному тренду`, `По недельному тренду × направление`.

### Исправлено

- `init_paper_table`: `row_factory = sqlite3.Row` (иначе `row["name"]` падал на голом `conn`).
- `save_signal_as_paper`: динамический `_columns` (защита от «N values for M columns»).
- `ui/render_console.py`: `★` → `*` (широкий Unicode ломал таблицу), `tablefmt="psql"`, авто-ширина.

### Известные ограничения

- `week_trend` в F: 72 сделки `unknown` (до миграции). Новые — `bearish` (рынок падает).
- `by_week_trend_direction` — ждёт 20–30 новых сделок.

### Исправлено

- `detect_signals`: дедупликация **не различает kind** — `bounce` + `trend_level` на одном уровне схлопываются в один сигнал (с большим score). Причина: #30/#31 в Y.
- `detect_signals`: дедупликация без `kind` (bounce + trend_level на одном уровне — один сигнал).

## [0.10.0] — 2026-11-05

### Добавлено

- **PF и expectancy**: `paper_stats` — `profit_factor`, `expectancy`.
- **`journal_cli.py`**: вывод `Profit factor` и `Expectancy`.
- **`bullish / long`** фильтр: `PAPER_SKIP_BULLISH_LONG = True` (в Y).
  Блокировка LONG при `week_trend == "bullish"`.
- **`normal + breakout`** фильтр: `PAPER_SKIP_NORMAL_BREAKOUT = True` (в Y).
  Блокировка `breakout` / `trend_level` при `market_state == "normal"`.
- **`market_state`**: `impulse_atr`, `impulse_dir`, `market_state` (normal / pullback / impulse).
- **`by_rsi`** и **`by_atr_percentile`**: разрезы по RSI на входе и волатильности.
- **`market_state_at_open`**, **`rsi_at_open`**, **`atr_percentile_at_open`** — миграция `paper_trades`.

### Исправлено

- **`pullback`** — 0 сделок (окно 6 M15 слишком большое; надо 3 M15).
- **`net_rr = null`** — только у старых сделок (#7), новые — числа.
- **`context = {}`** — только у старых, новые — заполнены.

### Известные ограничения

- **`pullback`** — 0 сделок (окно 6 M15). **Снизить** до 3 M15.
- **`normal`** — 9 сделок, 2W/6L, −65.28 ₽. **Фильтр** работает (не растёт).
- **`bullish / long`** — 10 сделок, 4W/6L, +38.40 ₽. **Фильтр** работает.
- **`bid-heavy`** — 4 сделки, 0W/3L, −103.68 ₽. **Убыточен** (n=4, ждём 10+).
- **`ask-heavy`** — 1 сделка, 0W/1L, −30.86 ₽. **Убыточен** (n=1, шум).

### Результаты

- **Y (48 сделок)**: PF **1.46**, expectancy **+9.9 pts**, winrate **46.2%**, PnL **+317.40 ₽**.
- **F (120 сделок)**: PF **1.27**, expectancy **+6.9 pts**, winrate **43.4%**, PnL **+565.20 ₽**.
- **Y лучше F** по PF и expectancy — фильтры работают.

## [0.10.1] — 2026-11-11

### Добавлено

- **Сохранение свечей в JSON** рядом с анализом: `data/candles_export.py`,
  `storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json`.
- **Флаги** в `config.py`: `SAVE_CANDLES`, `SAVE_CANDLES_ALWAYS`,
  `SAVE_CANDLES_MARK_SIGNALS`, `SAVE_CANDLES_TIMEFRAMES`,
  `SAVE_CANDLES_COUNT`, `SAVE_CANDLES_MAX_SNAPSHOTS`.
- **Режимы** A (все свечи) / B (только при сигналах) / A+B (все + маркер).
- `runner.py`: вызов `save_candles_snapshots` после `save_analysis`.

### Известные ограничения

- Файл растёт ~4–6 МБ/день на M15 (144 снимка × 300 свечей).
- Выходные свечи (`volume < 100`) попадают в снимок — фильтровать при анализе.

## [0.11.0] — 2026-11-17

### Добавлено

- **MFE/MAE** в `virtual_pnl`: `mfe_points`, `mae_points` (max favorable/adverse excursion).
- **`by_mfe_ratio`** в `paper_stats` (<0.3, 0.3-0.7, >0.7) — разрез по MFE/take.
- **`--known-only`** + **`--min-n`** в `paper-stats` — чистые разрезы (без `unknown`, без n<5).
- **`expectancy`** в каждом бакете `paper-stats` (pts / (win+loss)).
- **`partial_day`** + **`day_open`** + **`day_atr_base`** + **`day_range_atr`** в `IndicatorSnapshot`.
- **`by_partial_day`** в `paper_stats` — разрез partial (до 18:00) / full day.
- **`analyze_from_df`** в `core/analyzer.py` — сборка `AnalysisResult` из готовых `df` (без сети).
- **`scripts/verify_candles.py`** — replay свечей из `candles_*.json` vs `analysis_*.json`.
- **`scripts/verify_filters.py`** — эффект фильтров Y на истории (win/loss/timeout).
- **`tests/test_partial_day.py`** — 2 теста (partial_day, day_range_atr).
- **`tests/test_mfe_mae.py`** — 4 теста (win long/short, loss, timeout).
- **`tests/test_filtered_signal.py`** — 2 теста (RR не None у result.signals).
- **`tests/test_rr_fallback.py`** — RR для всех kind×direction.
- **`tests/test_volume_clip.py`** — клип volume_ratio.

### Исправлено

- **`RR = null`**: фильтрованные сигналы больше не попадают в `result.signals` (`passed_signals`).
- **`_finalize_signal`**: fallback для RR (если `compute_rr` не дал — считаем вручную).
- **`detect_signals`**: убран дубль `for s in all_signals` (был N×N вызовов).
- **`_compute_stops`**: защита от `stop_dist = 0`.
- **`volume_ratio`**: клип 5.0 (выбросы 17–20x не завышают score).
- **Дедуп** по `entry_price` (0.5 ATR) — `12.424` и `12.416` с `entry=12.410` → один сигнал.
- **Штраф EMA-конфликт** (−1.0) — убирает `trend_level` при `ema_alignment` против direction.
- **Штраф пила** (−1.0) — убирает сигнал при противоположном < 30 мин.
- **Штраф late/chase** (−1.0) — цена прошла > 1 ATR от уровня.
- **`DATA_MAX_AGE_BLOCK`** 30 → 10 → **15** (ALOR лаг ~7 мин).

### Статистика (17.11)

- **Y (69 сделок)**: winrate **41.4%**, PnL **+300.58 ₽**, PF **1.25**, expectancy **+6.2 pts**, депозит **+7.99%**.
- **F (84 сделки)**: winrate **30.0%**, PnL **−273.04 ₽**, PF **0.63**, expectancy **−3.1 pts**.
- **Y лучше F** по PF/expectancy — фильтры работают.
- **Фильтры Y** (paper_trades, n=17): `bullish_long` **−103 ₽** (полезен), `normal_breakout` **−139.72 ₽** (полезен), `bullish_short` **+21.72 ₽** (не включать), `adx_flat_breakout` **+50.28 ₽** (не включать).

### Известные ограничения

- **Replay match rate 10%** — look-ahead M15 (закрытая свеча vs незакрытая в live). Точный replay невозможен без M1.
- **`partial_day_at_open`** — не проверен на новых сделках (runner блокировал по `data_age=14`).
- **`DATA_MAX_AGE_BLOCK = 15`** — ALOR иногда отдаёт 14 мин.

## [Unreleased]

### Исправлено

- **Replay look-ahead (T-01, частично)**:
  - `core/analyzer.py`: `result.timestamp = timestamp` (не `datetime.now()`).
  - `scripts/verify_candles.py`: `_df_before` — H1/H4 `begin + duration <= ts` (без look-ahead).
  - `scripts/backtest.py`: H1/H4 `begin + duration <= bar_ts`; M15 — `[:t+1]` (как live).
  - `tests/test_no_lookahead.py`: 2 теста.

### Известные ограничения

- **Match rate 0–20%** (live сам имеет look-ahead: ALOR отдаёт текущую M15).
  H1/H4 — без look-ahead (правильные уровни). M15 — как live.
  **T-01b** (live без look-ahead) — отдельная задача.
