# CHANGELOG

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