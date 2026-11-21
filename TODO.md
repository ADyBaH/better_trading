# TODO — активные баги и задачи

Активные баги и задачи. История экспериментов — в `EXPERIMENTS.md`.
Архитектурные улучшения — в задачах T-01…T-23 (см. трекер).
Закрытые — в `CHANGELOG.md` и в конце файла.

**Последнее обновление:** 2026-11-21
**Состояние:** `pytest` — 262+ passed, 9 deselected, 0 failed; `pytest -m integration` — 9 passed.
**⚠️ Важно:** статистика 17.11 (PF 1.25) — **до** фикса look-ahead H1/H4 (T-01). **После** фикса — **другая** (PF 0.24–0.53, убыточно). **Не** использовать старые цифры для решений.

---

## 🔴 P0 — блокирует CI / ломает тесты

_(сейчас пусто — BUG-01 закрыт, T-20 закрыт)_

---

## 🟠 P1 — нестабильный integration (флаки)

### BUG-02. `test_iss_lag.py::test_4_direct_trades` — таймаут `iss.moex.com`

**Обнаружено:** 2026-11-21, `pytest -m integration`.
**Статус:** ⚠️ **флаки** (2026-11-21 — 9/9 passed, но ранее падал).
**Тип:** флаки-тест (сеть + таймаут).
**Приоритет:** P1.
**Реальные данные:** не нужны.

### Симптом

```
tests\test_iss_lag.py:83: in test_4_direct_trades
    r = requests.get(url, params=params, timeout=30)
E   requests.exceptions.ConnectionError: HTTPSConnectionPool(host='iss.moex.com', port=443): Read timed out.
```

`test_4_direct_trades` — единственный, кто бьёт в `trades.json` (лента сделок). Остальные 4 — проходят.

### Причина

1. `timeout=30` — на `trades.json` с большим диапазоном мало.
2. Нет retry.
3. Возможен rate-limit / большой объём.

### Что сделать (минимальный фикс)

1. `timeout=60` для `trades.json`.
2. Сузить диапазон: последние 10 минут (`from = now - 10min`).
3. Обернуть в `try/except ConnectionError → pytest.skip(...)`.
4. `pytest-rerunfailures` уже в `requirements.txt` (`--reruns 2 --reruns-delay 5` в `addopts`).

### Приёмка

- [ ] `pytest tests/test_iss_lag.py::test_4_direct_trades -v` — passed или SKIPPED.
- [ ] `pytest -m integration` — 0 failed (флаки переживаются rerun'ом).
- [ ] `pytest -m integration` — < 60 с.

### Оценка

0.2 / 0.5 д.

---

### T-01b. Live без look-ahead (ALOR текущая M15)

**Обнаружено:** 2026-11-21, при фиксе T-01 (H1/H4 без look-ahead).
**Тип:** архитектурная задача (live использует текущую M15 — look-ahead).
**Приоритет:** P1.
**Реальные данные:** нужны (ALOR).

### Симптом

`runner.py` (`analyze()`) → `get_candles_tf("M15", ...)` → ALOR отдаёт **текущую** M15 (`close` = последняя цена, **не** закрытая). Live **использует** её → **look-ahead** (в replay **не** воспроизводится, match rate 0–20%).

`analysis_*.json` на `09:40` **содержит** сигнал → live **видит** `close[09:30]` (текущая). Replay **видит** `close[09:15]` (закрытая).

### Причина

ALOR WebSocket `BarsGetAndSubscribe` отдаёт **текущую** M15 (не закрытую). `runner.py` **не** фильтрует `begin + 15min <= now`.

### Что сделать (минимальный фикс)

1. `data/api_facade.py::get_candles_tf` — **добавить** `closed_only=True` (по умолчанию `False` для backward-compat).
2. `runner.py` — `get_candles_tf("M15", closed_only=True)` (только закрытые).
3. **Или** — `analyze()` — **отрезать** последнюю M15 (`df[begin + 15min <= now]`).
4. **Проверить**: `pytest -m integration` — 9 passed.
5. **Перезапустить** `verify_candles.py --date 2026-11-13` → match rate **≥ 70%** (если live **без** look-ahead).

### Приёмка

- [ ] `runner.py` — **не** использует текущую M15.
- [ ] `verify_candles.py --date 2026-11-13` — match rate **≥ 70%**.
- [ ] `pytest -m integration` — 9 passed.
- [ ] `backtest.py --compare` — **новая** таблица (сравнить с `EXPERIMENTS.md`).

### Оценка

0.5 д.

---

## 🟡 P2 — баги в коде (не тестах)

### BUG-03. `partial_day` через `datetime.now() + 3` — хрупко

**Обнаружено:** 2026-11-21, код-ревью.
**Тип:** баг кода (хрупкость, не поломка сейчас).
**Приоритет:** P2.

### Симптом

`indicators/calc.py::get_trend_context`:
```
now = datetime.now()
hour_msk = (now.utctimetuple().tm_hour + 3) % 24
partial_day = hour_msk < 18
```

**Сейчас корректно** (компенсация `+3`), но **хрупко**:
- если сервер в UTC → `datetime.now()` = UTC, `+3` = МСК ✅
- если сервер в МСК → `datetime.now()` = МСК, `utctimetuple()` = МСК−3, `+3` = МСК ✅
- **но** если кто-то поменяет на `datetime.utcnow()` → **сломается**.

### Причина

Нет единой функции `now_msk()`. `partial_day` зависит от локального времени сервера.

### Что сделать (минимальный фикс, без T-14)

1. `core/time_utils.py`:
   ```
   from datetime import datetime, timedelta, timezone
   def now_msk() -> datetime:
       return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
   ```
2. `calc.py`:
   ```
   from core.time_utils import now_msk
   now = now_msk()
   partial_day = now.hour < 18
   ```

**НЕ делать** T-14 (миграция `paper_trades`, `partial_day_at_resolve`) — **отменено**.

### Приёмка

- [ ] `pytest tests/test_partial_day.py -v` — зелёные.
- [ ] `pytest tests/test_indicators.py -v` — зелёные.
- [ ] `now_msk()` — naive datetime, близкий к реальному МСК.

### Оценка

0.1 д (10 минут).

---

### T-12. Единый `REAL_TRADING_MODE`

**Обнаружено:** 2026-11-21, код-ревью.
**Тип:** архитектурный долг (два `_MOCK_MODE`).
**Приоритет:** P2.

### Симптом

`data/api_alor_trade.py::_MOCK_MODE` и `trader/real.py::_MOCK_MODE` — **два** флага. `REAL_TRADING_MODE` **нет** в `config.py`.

### Причина

Нет **единого** источника истины. Легко **рассинхронизировать**.

### Что сделать

1. `config.py`: `REAL_TRADING_MODE = "mock"` (значения: `"mock"` | `"live"`).
2. `core/real_mode.py` (новый): `check_real_mode(cli_flag=False)` — если `"live"` без `--i-understand-risk` / `I_UNDERSTAND_RISK=1` → `sys.exit(1)`.
3. `api_alor_trade.py` / `trader/real.py` → `_is_mock()` (читает `config.REAL_TRADING_MODE`).
4. `runner.py` / `main.py` — `argparse` + `check_real_mode()`.
5. `tests/test_real_mode.py` — 7 тестов.

### Приёмка

- [ ] `grep "REAL_TRADING_MODE" config.py` — есть.
- [ ] `grep "_MOCK_MODE" data/api_alor_trade.py trader/real.py` — нет (или backward-compat).
- [ ] `pytest tests/test_real_mode.py -v` — 7 passed.
- [ ] `live` без флага → `sys.exit(1)`.

### Оценка

0.5 д.

---

## 🟢 P3 — архитектурный долг

### T-06. `schema_version` + `make_mock_ind`

**Приоритет:** P3 (не блокирует, но **класс** багов).
**Симптом:** BUG-01 (`MockInd.partial_day`, `week_trend`) — **симптом** того, что мок устаревает после каждой миграции.
**Решение:** `tests/conftest.py::make_mock_ind()` через `dataclasses.fields(IndicatorSnapshot)`.
**Оценка:** 0.5 д.

---

## ⏸ Отложено / отменено

### T-14. `partial_day` open vs resolve — **ОТМЕНЕНО**

**Причина:** слишком много кода (миграция `paper_trades`, `by_partial_day_at_resolve`, CLI, тесты). **Не стоит 0.5 дня** сейчас.
**Когда вернуться:** если `partial_day` начнёт влиять на статистику. Сейчас — **не влияет**.
**Альтернатива:** BUG-03 (`now_msk()`) — минимальный фикс таймзоны, без миграции.

### T-01. Replay look-ahead — **ЧАСТИЧНО ЗАКРЫТ**

**Сделано:**
- `core/analyzer.py`: `result.timestamp = timestamp` (не `datetime.now()`).
- `scripts/verify_candles.py::_df_before`: H1/H4 — `begin + duration <= ts` (без look-ahead); M15 — `begin < ts` (как live).
- `scripts/backtest.py`: H1/H4 — `begin + duration <= bar_ts`; M15 — `[:t+1]` (как live).
- `tests/test_no_lookahead.py`: 2 теста.

**Не достигнуто:**
- Match rate ≥ 70% — **0–20%** (live сам имеет look-ahead: ALOR отдаёт текущую M15).

**Причина:**
- Live (`runner.py`) использует `close[текущей M15]` (ALOR). Replay — `close[закрытой]`. **Не** совпадает.

**Решение:**
- Принять: H1/H4 — без look-ahead (правильные уровни). M15 — как live.
- **T-01b** (live без look-ahead) — **отдельная задача** (P1, 0.5 д).

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

**Все варианты убыточны (PF < 1).** Старые цифры (skip_breakout PF 0.73) — **look-ahead**, недостоверны.

---

## ✅ Закрыто (архив)

| ID | Задача | Статус |
|---|---|---|
| **BUG-01** | `MockInd.partial_day` / `week_trend` | ✅ (262 passed; `test_paper_bid_ask.py` собирается, 0 тестов) |
| **BUG-04** | `price_step` хардкод `0.001` в `paper_stats` | ✅ (`get_instrument` + `try/except` → unknown) |
| **BUG-05** | `PAPER_MAX_OPEN` — нет в `config.py` | ✅ (`PAPER_MAX_OPEN = 1` + `getattr`) |
| **BUG-06** | `PAPER_TIMEOUT_BARS` 20 vs 60 | ✅ (`CONFIG.md` 60 → 20) |
| **T-01** | Replay look-ahead — **частично** | ⚠️ H1/H4 без look-ahead; M15 — как live. **T-01b** — отдельно. |
| **T-15** | `vote()` в `indicators/vote.py` | ✅ (19 тестов) |
| **T-16** | README → EXPERIMENTS/BRANCHES/CONFIG | ✅ (README ≤ 302 строки) |
| **T-17** | `test_filters.py` | ✅ (50 тестов, 99% покрытие) |
| **T-19** | `test_instruments.py` | ✅ (28 тестов, 98% покрытие) |
| **T-20** | CI (pyproject + GitHub Actions) | ✅ (`ci.yml`, `pyproject.toml`, `requirements.txt`) |

---

## Сводка

| ID | Задача | P | Оценка |
|---|---|---|---|
| BUG-02 | `test_4_direct_trades` — таймаут ISS (флаки) | 🟠 P1 | 0.2 / 0.5 д |
| T-01b | Live без look-ahead (ALOR текущая M15) | 🟠 P1 | 0.5 д |
| BUG-03 | `partial_day` — `now_msk()` | 🟡 P2 | 0.1 д |
| T-12 | `REAL_TRADING_MODE` | 🟡 P2 | 0.5 д |
| T-06 | `schema_version` + `make_mock_ind` | 🟢 P3 | 0.5 д |

**Рекомендуемый порядок:** BUG-03 (10 мин) → BUG-02 (10 мин) → T-12 (0.5 д) → T-01b (0.5 д) → T-06 (0.5 д).

**Итого P1–P3:** ~2.1 дня.

---

## ⚠️ Важно: статистика до/после look-ahead

| Период | PF (skip_breakout) | Достоверность |
|---|---|---|
| **До фикса** (с look-ahead H1/H4) | 0.73 | ❌ **недостоверно** |
| **После фикса** (T-01, 2026-11-21) | 0.53 | ✅ реально (всё убыточно) |
| **17.11** (live, PF 1.25) | 1.25 | ❌ **до** фикса, **не** использовать |

**Вывод:** стратегия **убыточна** (PF < 1 во **всех** вариантах **без** look-ahead). **Не** внедрять в live **до** T-01b (live без look-ahead) и **пересмотра** стратегии.