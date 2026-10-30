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
