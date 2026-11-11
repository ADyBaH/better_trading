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

## [0.11.0] — 2026-11-11

### Добавлено

- **Сохранение свечей в JSON** рядом с анализом: `data/candles_export.py`,
  `storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json`.
- **Флаги** в `config.py`: `SAVE_CANDLES`, `SAVE_CANDLES_ALWAYS`,
  `SAVE_CANDLES_MARK_SIGNALS`, `SAVE_CANDLES_TIMEFRAMES`,
  `SAVE_CANDLES_COUNT`, `SAVE_CANDLES_MAX_SNAPSHOTS`.
- **Режимы** A (все свечи) / B (только при сигналах) / A+B (все + маркер).
- `runner.py`: вызов `save_candles_snapshots` после `save_analysis`.

### Статистика (11.11)

- **Y (62 сделки):** winrate **43.1%**, PnL **+357.36 ₽**, PF **1.35**, expectancy **+7.8 pts**, депозит **+9.75%**.
- **F (56 сделок):** winrate **29.5%**, PnL **−172.48 ₽**, PF **0.61**, expectancy **−3.9 pts**.
- **Y лучше F** по всем метрикам — фильтры работают.
- **Кандидаты на фильтры** (после 20+): `bullish / short`, `bid-heavy (>60)`, `ADX trend (20-25)`.

### Известные ограничения

- Файл свечей растёт ~4–6 МБ/день на M15 (144 снимка × 300 свечей).
- Выходные свечи (`volume < 100`) попадают в снимок — фильтровать при анализе.
- **`unknown` в разрезах — шум** (старые сделки до миграций): 25 `week_trend`, 39 `market_state`, 47 `RSI`, 59 `ATR pct` в Y. Разрезы на 20+ «известных» — после миграции.
