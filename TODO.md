# TODO — активные баги и задачи

Активные баги и задачи. История экспериментов — в `EXPERIMENTS.md`.
Архитектурные улучшения — T-01…T-23 (см. трекер). Закрытые — в `CHANGELOG.md`.

**Последнее обновление:** 2026-11-21
**Состояние:** `pytest` — 262+ passed, 9 deselected, 0 failed; `pytest -m integration` — 9 passed.
**⚠️ Важно:** статистика 17.11 (PF 1.25) — **до** фикса look-ahead H1/H4 (T-01).
**После** фикса — **другая** (PF 0.24–0.53, убыточно). **Не** использовать старые цифры.

---

## 🔴 P0 — блокеры (сделано)

✅ **T-02**, **T-03** (не актуально), **T-15**, **T-16**, **T-17**, **T-19**, **T-20**, **T-21**, **T-18**.

---

## 🟠 P1 — статистическая честность / стабильность

### T-04. Bootstrap CI для PF/exp/winrate в paper-stats

**Приоритет:** P1. **Оценка:** 1 д.
**Симптом:** решения по n=14–23, без CI. PF 0.73 при n=17 — ±0.4.
**Фикс:** `_bootstrap_ci(values, stat_fn, n_iter=1000, alpha=0.05)` в `trader/stats.py`; вывод в `paper-stats`.
**Приёмка:** `paper-stats` показывает `PF 1.46 [1.02, 1.91]`; тест на 1000 выборок — coverage ≈ 95%.

---

### T-05. `paper_skipped` с reason (ablation «в живую»)

**Приоритет:** P1. **Оценка:** 1.5 д. **Зависит:** T-01.
**Симптом:** «runner блокировал по data_age=14» — следа нет.
**Фикс:** миграция `paper_skipped(...)`; `journal_cli.py paper-skipped --by-reason`.
**Приёмка:** на 1 дне live — counts по фильтрам; `paper_trades` не изменилась.

---

### T-06. `schema_version` + миграции + **рефакторинг работы с БД**

**Приоритет:** P1. **Оценка:** **2 д** (было 1 д — расширено).
**Симптом:**

- Десяток ручных `ALTER TABLE`, был баг SQL syntax (0.15.0). `_columns/_placeholders` рассинхронизируются.
- `trader/paper.py` **раздут** (~700+ строк): схема, миграции, `save_signal_as_paper`, `resolve_open_trades`, `virtual_pnl`, `paper_stats` — всё **в одном файле**.
- **Работа с БД** (SQL, миграции, `_columns`, `_placeholders`, `conn.execute`) **перемешана** с **бизнес-логикой** (PnL, статистика).

**Что сделать:**

1. **`schema_version`** (`PRAGMA user_version`).
2. **`MIGRATIONS: list[tuple[int, Callable]]`** — `init_paper_table()` применяет по порядку, в транзакции, обновляет `user_version`.
3. **`_columns/_placeholders`** — генерировать из `PRAGMA table_info` (или dataclass).
4. **Вынести работу с БД в отдельный блок** — `trader/paper_db.py` (или `storage/paper_db.py`):
   - `init_paper_table(conn)` — схема + миграции.
   - `MIGRATIONS` — список миграций.
   - `insert_paper_trade(conn, ...)` — INSERT с `_columns/_placeholders`.
   - `select_open_trades(conn, symbol)` — SELECT.
   - `update_paper_trade_resolve(conn, id, ...)` — UPDATE.
   - `_columns`, `_placeholders` — генерация.
5. **`trader/paper.py`** — **только бизнес-логика**:
   - `virtual_pnl(...)` — PnL по свечам.
   - `save_signal_as_paper(...)` — вызывает `paper_db.insert_paper_trade`.
   - `resolve_open_trades(...)` — вызывает `paper_db.select_open_trades` + `paper_db.update_paper_trade_resolve`.
   - `paper_stats(...)` — вызывает `paper_db.*` (или остаётся с SQL — **опционально** вынести в `paper_stats_db.py`).
6. **`tests/test_paper_db.py`** — тесты на миграции (идемпотентность, `user_version`), `insert`/`select`/`update`.

**Приёмка:**

- [ ] `PRAGMA user_version` растёт при миграциях.
- [ ] Новый столбец — одна строка в `MIGRATIONS`.
- [ ] `trader/paper_db.py` — **вся** работа с БД (`conn.execute`).
- [ ] `trader/paper.py` — **только** бизнес-логика (нет `conn.execute`).
- [ ] `pytest tests/test_paper*.py tests/test_paper_db.py -v` — зелёные.
- [ ] Тест идемпотентности миграций.

**Оценка:** 2 д.

---

### T-07. Pre-registration экспериментов

**Приоритет:** P1. **Оценка:** 0.5 д.
**Фикс:** `EXPERIMENTS.md` (шаблон — уже есть); `config.EXPERIMENT_ID`; `paper_trades.experiment_id`.
**Приёмка:** 1 пилотный эксперимент зарегистрирован; `experiment_id` заполнен.

---

### T-08. Ablation study фильтров

**Приоритет:** P1. **Оценка:** 1.5 д. **Зависит:** T-01b, T-02.
**Фикс:** `scripts/ablation.py --since --until --base=current_config`; ΔPF/Δexp/Δn с CI.
**Приёмка:** `ablation.py` на 11–19.11; таблица с ΔPF + CI; пересечения указаны.

---

## 🟡 P2 — архитектура и надёжность

---

### T-02b. Пересмотр фильтров (13.11: режут прибыль)

**Приоритет:** P2 (после T-01b). **Оценка:** 0.5 д.
**Симптом:** 5 фильтров отсекают 9 из 10 сигналов (+39.58 ₽ прибыльных), проходит 1 (−28.96 ₽).
**Фикс:** `verify_filters.py` на 7 днях; `normal_breakout` / `pullback_bounce` — пересмотреть (OFF?).

---

### T-12. Единый `REAL_TRADING_MODE`

**Приоритет:** P2. **Оценка:** 0.5 д.
**Фикс:** `config.REAL_TRADING_MODE`; `core/real_mode.py::check_real_mode()`; `tests/test_real_mode.py`.
**Приёмка:** один источник истины; live без флага — не запускается.

---

### T-13. `--by-score` + гипотеза «score не коррелирует с winrate»

**Приоритет:** P2. **Оценка:** 0.5 д. **Зависит:** T-04.
**Фикс:** `paper_stats.by_score` (бакеты <2, 2–3, 3–4, 4+); CI для winrate.
**Приёмка:** `--by-score` с CI; решение в `EXPERIMENTS.md`.

---

## 🟢 P3 — полировка

### T-23. ADAPTIVE_TAKE — проверить

**Приоритет:** P3. **Оценка:** 0.3 д. **Зависит:** T-04.
**Фикс:** `paper-stats --by-day-range-atr` (<2.5, 2.5–3.33, >3.33); если нет дней <3.33 — `ADAPTIVE_TAKE_ENABLED=False`.

---

## ⏸ Отложено (не сейчас)

### T-09. Heartbeat + health-check

**Причина:** не первая необходимость. Вернуться после P1.

### T-10. JSONL для уведомлений

**Причина:** не нужен сейчас. `notifications.txt` + звук — работают.

### T-11. Retention логов

**Причина:** не нужен сейчас. Диск не критичен.

### T-14. `partial_day` open vs resolve — **ОТМЕНЕНО**

Слишком много кода. **Альтернатива:** BUG-03 (`now_msk()`).

### T-01. look-ahead — **частично**

**Сделано:** `timestamp=ts`; H1/H4 `begin+duration<=ts`; `backtest.py` H1/H4; 2 теста.
**Не достигнуто:** match rate ≥ 70% (live сам look-ahead). **T-01b** — отдельно.

**Backtest (11–19.11, без look-ahead H1/H4):**
| Вариант | n | PF | exp |
|---|---|---|---|
| baseline | 17 | 0.24 | −11.8 |
| **skip_breakout** | 13 | **0.53** | **−5.8** |
| F1 ADX≥25 | 15 | 0.28 | −11.0 |
| F2 ADX<20 | 15 | 0.45 | −7.3 |
| F3 impulse | 14 | 0.47 | −7.2 |
| F4 week_trend | 17 | 0.24 | −11.8 |
| current_config | 10 | 0.45 | −7.1 |

**Все убыточны (PF < 1).** Старые цифры (0.73) — look-ahead, недостоверны.

---

## ✅ Закрыто (архив)

| ID         | Задача                               | Статус                                                                                                                           |
| ---------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| **T-01**   | Replay look-ahead — частично         | ⚠️ H1/H4 без look-ahead; M15 как live; skip_filters; direction+kind. Match rate 43.8% (17.11), 33.3% (20.11). 22.11+ — проверка. |
| **T-01b**  | Live без look-ahead M15              | ✅ analyze(): df[begin + tf <= now].                                                                                             |
| **T-01c**  | H1/H4 с историей                     | ✅ save_candles_snapshots уже 300 (не нужен).                                                                                    |
| **T-02**   | `verify_filters` `enabled=False`     | ✅ `if not f.enabled: return False`                                                                                              |
| **T-03**   | 12 failed тестов                     | ✅ не актуально (262 passed)                                                                                                     |
| **T-15**   | `vote()`                             | ✅ 19 тестов                                                                                                                     |
| **T-16**   | README → EXPERIMENTS/BRANCHES/CONFIG | ✅ README ≤ 302                                                                                                                  |
| **T-17**   | `test_filters.py`                    | ✅ 50 тестов                                                                                                                     |
| **T-18**   | NOTES.md — целостность               | ✅ проверено, всё цело                                                                                                           |
| **T-19**   | `test_instruments.py`                | ✅ 28 тестов                                                                                                                     |
| **T-20**   | pyproject markers + CI               | ✅ `ci.yml`                                                                                                                      |
| **T-21**   | Пустые заглушки                      | ✅ сделано                                                                                                                       |
| **BUG-01** | `MockInd.partial_day`                | ✅ 262 passed                                                                                                                    |
| **BUG-02** | `test_4_direct_trades`               | ✅                                                                                                                               |
| **BUG-03** | `partial_day`                        | ✅                                                                                                                               |
| **BUG-04** | `price_step` хардкод                 | ✅                                                                                                                               |
| **BUG-05** | `PAPER_MAX_OPEN`                     | ✅                                                                                                                               |
| **BUG-06** | `PAPER_TIMEOUT_BARS`                 | ✅                                                                                                                               |

---

## Сводка

| ID       | Задача                                           | P     | Оценка    |
| -------- | ------------------------------------------------ | ----- | --------- |
| BUG-02   | `test_4_direct_trades` (флаки)                   | 🟠 P1 | 0.2/0.5 д |
| T-01b    | Live без look-ahead                              | 🟠 P1 | 0.5 д     |
| T-04     | Bootstrap CI                                     | 🟠 P1 | 1 д       |
| T-05     | `paper_skipped`                                  | 🟠 P1 | 1.5 д     |
| **T-06** | **`schema_version` + миграции + рефакторинг БД** | 🟠 P1 | **2 д**   |
| T-07     | Pre-registration                                 | 🟠 P1 | 0.5 д     |
| T-08     | Ablation study                                   | 🟠 P1 | 1.5 д     |
| BUG-03   | `now_msk()`                                      | 🟡 P2 | 0.1 д     |
| T-02b    | Пересмотр фильтров                               | 🟡 P2 | 0.5 д     |
| T-12     | `REAL_TRADING_MODE`                              | 🟡 P2 | 0.5 д     |
| T-13     | `--by-score`                                     | 🟡 P2 | 0.5 д     |
| T-23     | ADAPTIVE_TAKE                                    | 🟢 P3 | 0.3 д     |

**Рекомендуемый порядок:** BUG-03 (10 мин) → BUG-02 (10 мин) → T-12 (0.5 д) → T-01b (0.5 д) → T-04 (1 д) → T-07 (0.5 д) → T-06 (2 д) → T-05 (1.5 д) → T-08 (1.5 д) → T-02b (0.5 д) → T-13 (0.5 д) → T-23 (0.3 д).

**Итого P1–P3:** ~11 дней.

**Отложено:** T-09, T-10, T-11, T-14 (отменено), T-01 (частично).

**Закрыто:** T-02, T-03, T-15, T-16, T-17, T-18, T-19, T-20, T-21, BUG-01, BUG-04, BUG-05, BUG-06.

---

## ⚠️ Важно: статистика до/после look-ahead

| Период                             | PF (skip_breakout) | Достоверность                        |
| ---------------------------------- | ------------------ | ------------------------------------ |
| **До фикса** (look-ahead H1/H4)    | 0.73               | ❌ **недостоверно**                  |
| **После фикса** (T-01, 2026-11-21) | 0.53               | ✅ реально (всё убыточно)            |
| **17.11** (live, PF 1.25)          | 1.25               | ❌ **до** фикса, **не** использовать |

**Вывод:** стратегия **убыточна** (PF < 1 без look-ahead). **Не** внедрять в live **до** T-01b + пересмотра.
