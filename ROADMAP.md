# ROADMAP — trade-assistant

Консольный аналитический помощник по фьючерсу **CNYRUBF** (MOEX).
Не торгует сам. Показывает уровни, индикаторы, сигналы.
Ведёт журнал сделок с учётом комиссий.

---

## Общая логика

**Что НЕ делаем сейчас:**

- Автоторговля (проект — только сигнальщик).
- Scheduler, VPS.
- Telegram (заблокирован).
- Реальное исполнение ордеров.

---

## Этап 1. Данные с MOEX ✅

- [x] ISS: методы, тикеры фьючерсов, лимиты.
- [x] `data/api_moex.py` — обёртка: `get_candles(...) -> DataFrame`.
- [x] `data/storage_sqlite.py` — сохранение свечей в `storage/market.db`.
- [x] `data/api_facade.py` — фасад: «дай N свечей, если нет — скачай».
- [x] Пагинация ISS: лимит 500 свечей обойдён через `start`.
- [x] Проверено: за 14.10 — **999 свечей** (07:00–23:49) вместо 500.

## Этап 2. Индикаторы ✅

- [x] `indicators/calc.py`: EMA(50/200), RSI(14), ADX(14), ATR(14).
- [x] `add_indicators(df) -> df`.
- [x] `get_atr(df, period)` — последнее значение ATR.
- [x] `data/resample.py` — M1 → M5 / M15 / H1 / H4.

## Этап 3. Уровни ✅

### 3.1. Базовые фракталы

- [x] `strategy/levels.py`: `find_fractals(df, period=2)`.

### 3.2. ATR + кластеризация

- [x] `cluster_levels` + `_merge_nearby_clusters`.
- [x] `LEVELS_MIN_WEIGHT = 2`.

### 3.3. Мульти-ТФ + веса

- [x] `build_levels()` — карта по `LEVEL_TIMEFRAMES`.
- [x] Веса ТФ, бонус 30% за подтверждение.
- [x] Фильтр `±LEVELS_RANGE_ATR × ATR`, кап `LEVELS_MAX_SHOW=7`.

### 3.4. Референсные уровни (слой C)

- [x] `strategy/references.py`: round numbers, PDH/PDL, PWH/PWL.
- [x] Отдельный список, не смешивается со структурными.

### 3.5. Модель + рендереры + CLI

- [x] `core/models.py`, `core/analyzer.py`.
- [x] `ui/render_console.py`, `ui/render_json.py`.
- [x] `main.py` — argparse + `--console` / `--json` / `--log` / `--save`.

## Этап 4. Логика сигналов (MVP-1) ✅

- [x] `core/models.py`: `Signal`.
- [x] `detect_bounce`, `detect_breakout`, `detect_trend_level`.
- [x] Система критериев A, B, D.
- [x] `_compute_strength` — score + strength.
- [x] Дедупликация по `(direction, level_price)`.
- [x] Обогащение уровней: `distance_atr`, `strength_score`, `age_days`.
- [x] Табличный рендер.

## Этап 5. Журнал сделок ✅

- [x] `trader/journal.py`, SQLite `storage/journal.db`.
- [x] CRUD, `compute_result()` через `Instrument`.
- [x] `trader/stats.py`: winrate, PnL, avg win/loss, разбивки.
- [x] `journal_cli.py`: `add`, `list`, `close`, `delete`, `stats`.
- [x] Мульти-инструмент: `core/instruments.py`.
- [x] Учёт комиссий (MOEX 0.58 ₽ + Финам 0.45 ₽ = 2.06 ₽/круг).
- [x] Проверено: `+40 pts / +37.94 ₽` (40 ₽ gross − 2.06 ₽ комиссия).

## Этап 6. Обогащение сигналов ✅

### 6.1. Шаг 1 — контекст, warnings, R:R

- [x] `Signal`: `context`, `warnings`, `risk_reward`, `net_rr`.
- [x] `strategy/signal_history.py` — история в `storage/logs/signals_history.json`.
- [x] `_build_context()` (20 полей), `_build_warnings()`, `_compute_session()`.
- [x] `ui/render_console.py`: колонки `R:R`, `Net`, `⚠`.
- [x] `tests/test_signals_enrichment.py`: 6 мок-тестов.

### 6.2. Адаптация к задержке ISS

- [x] `DEFAULT_TIMEFRAME = "M15"`.
- [x] `LEVEL_TIMEFRAMES = ["H4", "H1", "M15"]`.
- [x] `USE_ATR_STOPS = True`: стоп = 1.0 × ATR(H1), тейк = 2.0 × ATR(H1).
- [x] `DATA_MAX_AGE_MIN`, `CACHE_TTL_MINUTES = 15`.

## Этап 7. Структура файлов (рефакторинг) ✅

- [x] `data/` — только код. `storage/` — только данные + логи.
- [x] `market.db`, `journal.db`, `signals_history.json` в `storage/`.
- [x] `logs/` → `storage/logs/`.
- [x] `.gitignore` — только `storage/` + `*.db-journal`.
- [x] Проверено: `git ls-files data/` показывает все `.py`.

## Этап 8. Multi-source trend (голосование источников) ✅

### 8.1. Контекст тренда

- [x] `indicators/calc.py`: `_detect_structure`, `get_trend_context`, `get_main_trend`.
- [x] Пороги голосования: `+2/-2` = up/down, `+3/-3` = strong, `-1..+1` = transition.

### 8.2. Модель + analyzer

- [x] `IndicatorSnapshot`: `day_trend`, `day_change_atr`, `structure`,
      `price_direction`, `vote_sum`, `vote_breakdown`.
- [x] Проверено на 15.10: `trend: up` вместо ошибочного `down`.

### 8.3. Отображение в дашборде

- [x] `format_indicators`, `format_trend_context` в `models.py`.
- [x] Вывод: `Тренд ВВЕРХ (голосов +2) | ADX 41.6 | RSI 65.4` + строка контекста.
- [x] Убрана старая `interpret_indicators`.

### 8.4. Штрафы и блокировки

- [x] `PENALTY_TREND_TRANSITION = 1.5`, `PENALTY_BREAKOUT_TRANSITION = 1.0`.
- [x] `detect_trend_level` — блок при transition.
- [x] `detect_breakout` — штраф −1.0 при transition + блок двойного конфликта.
- [x] `_build_warnings` — 4 типа конфликтов.
- [x] `tests/test_trend_conflict.py`.

### 8.5. Фильтр против тренда + дедупликация

- [x] `_is_direction_allowed` — блок против тренда для bounce/breakout.
- [x] Штраф −0.5 за transition для bounce.
- [x] Двухуровневая дедупликация в `review_all_analysis`.
- [x] **Результат на 13–15.10:** 13 сигналов, winrate **53.8%**, PnL **+209.9**.

## Этап 9. Раннер + эксперименты ✅

### 9.1. Скрипт-раннер

- [x] `runner.py` — анализ каждые 20 минут.
- [x] Сохранение в `storage/logs/YYYY-MM-DD/analysis_HH-MM-SS.{json,txt}`.
- [x] Корректная остановка Ctrl+C.

### 9.2. Тюнинг transition (закрыт)

**Ветка:** `experiment/transition-tuning` (закрыта, не смержена)
| Вариант | Сигналов | Win | Loss | Winrate | PnL |
|---------|----------|-----|------|---------|-----|
| **Baseline** | 13 | 7 | 6 | **53.8%** | **+209.9** |
| A: блок против дня | 14 | 7 | 6 | 50.0% | +209.9 |
| B: блок всех transition | 9 | 5 | 4 | 55.6% | +167.5 |
**Решение:** оставляем baseline. B снижает PnL на 20% без существенного роста winrate.

---

## Этап 10. Paper-tracking ✅

### 10.1. Инфраструктура

- [x] `core/instruments.py`: `compute_trade_result()` — общая формула points/rub.
- [x] `trader/journal.py`: `connect_journal` (алиас), `Trade.compute_result()` на общей формуле.
- [x] `trader/paper.py`: схема `paper_trades` в `storage/journal.db`.
- [x] Поля: `signal_id`, `source_analysis_path`, `trend_at_open`, `adx_at_open`,
      `day_trend_at_open`, `structure_at_open`, `resolution_confidence`.
- [x] `init_paper_table()`, `_signal_id()`, `_is_in_paper_hours()`.

### 10.2. Логика

- [x] `virtual_pnl()` — win/loss/timeout/open, консервативный ambiguous.
- [x] `_is_duplicate()` — по ATR (0.25) + окно эха (15 мин).
- [x] `save_signal_as_paper()` — только в `PAPER_TRADING_HOURS` (09:00–18:00).
- [x] `resolve_open_trades()` — по 50 торговым M15-свечам, `>` (свеча открытия игнорируется).
- [x] `paper_stats()` — агрегаты, разбивки по kind/trend/day_trend/score.

### 10.3. Интеграция

- [x] `runner.py`: `save_signal_as_paper` + `resolve_open_trades` каждый цикл.
- [x] `analyzer.py`: `log.info("data_age=...")` — наблюдаемость лага.
- [x] `journal_cli.py`: команда `paper-stats` с `--since` / `--until` / `--symbol`.

### 10.4. Тесты

- [x] `tests/test_paper.py` — 14 проверок (инфраструктура).
- [x] `tests/test_paper_dedup.py` — 19 проверок (дедуп, создание).
- [x] `tests/test_paper_resolve.py` — 25 проверок (резолв).
- [x] `tests/test_paper_stats.py` — 30 проверок (агрегаты).
- [x] `tests/test_instruments.py` — 12 проверок (compute_trade_result).
- [x] `tests/test_journal_integrity.py` — 5 проверок (журнал не сломан).

**Итого:** 105 проверок, все ✅.

---

### 10.5. Больше информации от paper-trades

- [x] `tests/show_paper_trades.py` — таблица всех paper-сделок с деталями
      (entry/stop/take/exit/result/pts/rub/bars/conf).
- [x] `journal_cli.py paper-trades` — то же через `tabulate`, с `--open` / `--limit` / `--symbol`.
- [x] `runner.py` — вывод новых (`+`) и закрытых (`✓`) сделок в консоль.
- [x] `trader/paper.py`: `format_paper_trade_short`, `format_paper_trade_result`.

---

## Этап 11. ALOR WebSocket (real-time данные) ✅

### 11.1. Подключение

- [x] Прямой JWT-флоу (Refresh → Access).
- [x] WebSocket `wss://api.alor.ru/ws`.
- [x] Подписка `BarsGetAndSubscribe` с `skipHistory=False` и `from`.
- [x] Время в МСК (UTC+3) для корректного `data_age`.

### 11.2. Интеграция

- [x] `api_facade.py`: ветка `DATA_PROVIDER='alor'` (без ресемплинга).
- [x] `runner.py`: интервал 5 минут.
- [x] `config.py`: `CACHE_TTL_MINUTES=4`.
- [x] `core/logger.py`: `RotatingFileHandler` (лог в один файл).
- [x] `runner.py`: `save_analysis` в один файл `analysis_YYYY-MM-DD.*`.

### 11.3. Order Book (для будущего анализа)

- [x] `api_alor.py`: `get_order_book_pressure_sync` (перевес bid/ask).
- [x] `paper_trades`: поля `bid_vol`, `ask_vol` на момент входа.

### 11.4. Результат

- **data_age:** 5–10 минут (вместо 20–30 у MOEX ISS).
- **Свечей:** M15 — 300+, H1 — 300+, H4 — 300+.
- **Уровни:** 59 после кластера (полноценный анализ).
- **Статистика 19–22.10:** 14 сделок, 12W/2L, winrate 85.7%, +464.1 pts / +435.26 ₽.

**Вывод:** real-time данные работают. Можно собирать статистику с задержкой 5 минут.

---

### 11.5. Наблюдаемость

- [x] `paper-trades --wide`: ADX, Bid, Ask, R:R.
- [x] `paper_stats`: `by_adx` (flat/trend/strong), `by_session` (morning/day/evening/night), `by_hour`, `by_weekday`.
- [x] `--by-adx`, `--by-session` флаги в `paper-stats`.

---

## Этап 12. Real-trading (мок-режим) ⏸

### 12.1. Инфраструктура

- [x] `data/api_alor_trade.py` — POST-ордера (place_order, cancel_order, get_orders).
- [x] `_MOCK_MODE = True` — реальные ордера НЕ ставятся.
- [x] `core/risk.py` — `calculate_position_size`.
- [x] `trader/real.py` — `open_real_trade`, `close_real_trade` (мок).
- [x] `ui/notify.py` — звук + `storage/logs/notifications.txt`.

### 12.2. Интеграция

- [x] `runner.py` — при сигнале: paper + notify + real (мок).

### 12.3. Тесты

- [x] `test_alor_trade.py` — 9 проверок.
- [x] `test_real_trading.py` — 9 проверок.
- [x] `test_notify.py` — 5 проверок.

**Итого: 23 проверки.**

### 12.4. Что НЕ делаем

- Реальные ордера (только мок).
- Авто-торговля (только ручное подтверждение).
- Риск > 1% депозита.

**Следующий шаг:** через 2 недели paper-tracking → если winrate 70%+ → тесты с реальными ордерами (на малом депозите).

## Этап 13. market_price_at_open (лаг paper vs real) ✅

### 13.1. Инфраструктура

- [x] `data/api_alor.py`: `get_current_price_sync` (bid/ask/mid из стакана).
- [x] `trader/paper.py`: миграция + `market_price_at_open` в `paper_trades`.
- [x] `runner.py`: `get_current_price_sync` → `market_price_at_open`.
- [x] `journal_cli.py`: `--wide` показывает `Mkt`.

### 13.2. Результат

- Сделка #7: `entry_price = 12.050` (close), `market_price_at_open = 12.073` (real).
- **Разница 23 пункта** — лаг paper vs real.

**Вывод:** лаг **существенен** (23 пункта). Через 2 недели — **сравнить** paper vs real.

## Идеи на будущее (после статистики)

- Штрафы к score: ADX > 30 / RSI экстремум (max, не сумма).
- Cooldown как блокировка (< 2 часов назад был противоположный).
- PDH/PDL и round в детекции сигналов (с пометкой `level_source`).
- Failed breakout, retest.
- MACD (критерий B3).
- C: мульти-ТФ подтверждение.
- E: тесты уровня.
- `atr_percentile` через справочник за 90 дней.

## Упаковка и удобство ⏸

- [ ] Тесты на `indicators/calc.py`, `strategy/levels.py`.
- [ ] `core/errors.py` — свои исключения.
- [ ] `ui/` — интерактивное меню в консоли.
- [ ] Экспорт журнала в CSV / Excel.

## Отложено (не сейчас)

- `core/scheduler.py`, `core/state.py`.
- Telegram-бот.
- VPS.
- Реальное исполнение сделок.

---

## Текущий статус

**Версия:** 0.8.0
**Готово:** этапы 1–11 (ALOR WebSocket, real-time), **наблюдаемость** (`--wide`, `by_adx`, `by_session`, `by_hour`, `by_weekday`).
**В работе:** сбор статистики (19 сделок, 70.6% winrate).
**Режим:** baseline. Фильтры НЕ внедряются до 40+ сигналов.
**Следующий шаг:** через 2 недели (≈05.11) — разбор `paper_stats` на 40+ сделках.

---

## Гипотезы после paper-tracking (проверить на 40+ сигналах)

Источник: 19–24.10 (19 сделок, winrate 70.6%, PnL +374.1 pts).

**Важно:** 19 сделок — ещё не статистика. Проверяем на 40+.

1. **breakout > trend_level > bounce** — breakout 75% (6/8), trend_level 62.5% (5/8), bounce 33% (1/3). **Подтверждается.**
2. **strong_down — лучший режим** — 100% winrate (5/5). **Подтверждается.**
3. **Вечер (17:00–20:00) — рискованное время** — 0/4 (0%), -62.4 pts. **Подтверждается.** Проверить на 10+ вечерних сделках.
4. **Утро (09:00–12:00) — рабочее** — 6/7 (86%), +212.2 pts. **Гипотеза «утро — рискованное» не подтверждается.**
5. **ADX flat (<20) — не блокировать** — 3/3 (100%), +133.1 pts. Но n=3 — шум. Проверить.
6. **Стакан против входа (bid > ask для short)** — loss #16, #17. n=2, мало. Проверить на 10+.
7. **Score не коррелирует с winrate** — score 1.0 — 100% (n=3), score 3.0+ — 60% (n=10). Проверить.
8. **Дедуп близких сигналов** — не проверялось.
9. **«Пила» (< 60 мин)** — не проверялось.
10. **RSI-экстремумы** — не проверялось.

**Решение по фильтрам:** НЕ внедряем до 40+ сигналов.
**Вечер:** если 10+ вечерних сделок подтвердят убыточность — рассмотреть отключение `PAPER_TRADING_HOURS` после 17:00.

### 19–24.10.2026 — статистика за 19 сделок

- **Сделок:** 19 (12W / 5L / 0T / 2 open), winrate 70.6%.
- **PnL:** +374.1 pts / +339.08 ₽.
- **По типам:**
  - breakout: 6/8 (75%), +217.3 pts.
  - trend_level: 5/8 (62.5%), +153.2 pts.
  - bounce: 1/3 (33%), +3.6 pts.
- **По тренду:**
  - strong_down: 5/5 (100%), +230.5 pts.
  - down: 6/12 (50%), +110 pts.
  - transition: 1/2 (50%), +33.6 pts.
- **Наблюдения:**
  - breakout > trend_level > bounce (подтверждает гипотезу).
  - strong_down — 100% winrate (n=5).
  - bounce — слабый (n=3).
  - score не коррелирует с winrate (n мал).
- **Вывод:** стратегия работает. Ждём 40+ сделок.

### 24.10.2026 — by_hour, by_weekday

- **По часу:** 09:00–10:00 — 5/5 (100%); 12:00–13:00 — 5/5 (100%); **17:00 — 0/2 (-62.4 pts)**.
- **По дню недели:** Wed — 6/6 (+280.3); Tue — 3/3 (+133.3); Thu — 0/2 (-57.6); Fri — 0/1 (-32.4).
- **Вывод:** 17:00 и четверг/пятница — убыточные (n мало).
