# BRANCHES — ветки и режимы trade-assistant

Сравнение веток и режимов. История экспериментов — в `EXPERIMENTS.md`.

## Ветки

### `main` (F) — reference

- **Роль:** основная ветка, база сравнения.
- **Настройки:** без фильтров, 120 сделок.
- **База:** `storage/journal.db`.
- **Цель:** сравнение с `experiment/aggressive-signals` и `feature/real-trading`.

### `experiment/aggressive-signals` — полигон

- **Роль:** агрессивный полигон, быстрый набор статистики.
- **Настройки:** без фильтров, сниженные пороги:
  - `BOUNCE_TOLERANCE_ATR = 0.4`
  - `TREND_LEVEL_TOLERANCE_ATR = 0.5`
  - `BREAKOUT_BUFFER_ATR = 0.1`
  - `ADX_BREAKOUT_THRESHOLD = 20`
  - `PAPER_TRADING_HOURS` 09:00–20:00
  - `PAPER_DEDUP_MINUTES = 5`
  - `PAPER_MAX_OPEN = 0`
- **База:** `storage/journal_aggressive.db`.
- **Цель:** накопить статистику быстрее (больше сигналов).

### `feature/real-trading` (Y) — актуальная

- **Роль:** актуальная ветка (торгуем по ней).
- **Настройки:** с фильтрами:
  - `PAPER_SKIP_BULLISH_LONG = True`
  - `PAPER_SKIP_NORMAL_BREAKOUT = True`
  - `PAPER_SKIP_BULLISH_SHORT = False`
  - `PAPER_SKIP_ADX_FLAT_BREAKOUT = False`
  - лимит 1 (`PAPER_MAX_OPEN = 1`)
  - `PAPER_TRADING_HOURS` 09:00–18:00
- **База:** `storage/journal.db` (в Y).
- **Цель:** торговля (PF 1.25, expectancy +6.2 на 17.11).

## Сравнение (17.11.2026)

| Ветка                | Сделок | Winrate | PnL       | PF       | Expectancy   | Депозит |
| -------------------- | ------ | ------- | --------- | -------- | ------------ | ------- |
| **F (main)**         | 84     | 30.0%   | −273.04 ₽ | **0.63** | **−3.1 pts** | —       |
| **Y (real-trading)** | 69     | 41.4%   | +300.58 ₽ | **1.25** | **+6.2 pts** | +7.99%  |
| **F (aggressive)**   | 0      | —       | —         | —        | —            | —       |

**Y лучше F** по PF/expectancy — фильтры `bullish/long` и `normal+breakout` работают.
**F (aggressive)** — только начинает, статистики пока нет.

## Сравнение (11.11.2026)

| Ветка                | Сделок | Winrate | PnL       | PF       | Expectancy   | Депозит |
| -------------------- | ------ | ------- | --------- | -------- | ------------ | ------- |
| **Y (real-trading)** | 62     | 43.1%   | +357.36 ₽ | **1.35** | **+7.8 pts** | +9.75%  |
| **F (main)**         | 56     | 29.5%   | −172.48 ₽ | **0.61** | **−3.9 pts** | —       |

**Y лучше F** по всем метрикам — фильтры `bullish/long` и `normal+breakout` работают.

## Режимы

### Paper-tracking (основной)

- Виртуальные сделки в `paper_trades` (`storage/journal.db`).
- Резолв по stop/take/timeout (50 M15-свечей).
- Не трогает `journal.db/trades`.

### Real-trading (мок)

- **Важно:** реальные ордера **НЕ** ставятся (`REAL_TRADING_MODE = "mock"`).
- `data/api_alor_trade.py`: `place_order`, `cancel_order`, `get_orders` (мок).
- `trader/real.py`: `open_real_trade`, `close_real_trade` (мок).
- `core/risk.py`: `calculate_position_size` (риск → размер).
- `ui/notify.py`: звук + `storage/logs/notifications.txt`.

**Как включить реальные ордера (после 2 недель paper с winrate 70%+):**

1. `config.py`: `REAL_TRADING_MODE = "live"`.
2. Только на **малом** депозите (1% риск).
3. Только с ручным подтверждением (авто-торговли нет).

**Что не делаем:** авто-торговля, риск > 1%, реальные ордера без тестов.

**Просмотр:**

```bash
python journal_cli.py paper-stats
```
