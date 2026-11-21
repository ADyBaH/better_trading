# TODO — активные баги и задачи

Активные баги и задачи. История экспериментов — в `EXPERIMENTS.md`.
Архитектурные улучшения — в задачах T-01…T-23 (см. трекер).
Закрытые — в `CHANGELOG.md` и в конце файла.

**Последнее обновление:** 2026-11-21
**Состояние:** `pytest` — 262 passed, 9 deselected, 0 failed; `pytest -m integration` — 9 passed.

---

## 🔴 P0 — блокирует CI / ломает тесты

_(сейчас пусто — BUG-01 закрыт, T-20 почти закрыт)_

---

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

## 🟢 P3 — архитектурный долг

### T-06. `schema_version` + `make_mock_ind`

**Приоритет:** P3 (не блокирует, но **класс** багов).
**Симптом:** BUG-01 (`MockInd.partial_day`, `week_trend`) — **симптом** того, что мок устаревает после каждой миграции.
**Решение:** `tests/conftest.py::make_mock_ind()` через `dataclasses.fields(IndicatorSnapshot)`.
**Оценка:** 0.5 д.

---

### T-12. Единый `REAL_TRADING_MODE`

**Приоритет:** P2.
**Симптом:** `data/api_alor_trade.py::_MOCK_MODE` и `trader/real.py::_MOCK_MODE` — два флага. `REAL_TRADING_MODE` **нет** в `config.py`.
**Решение:**

1. `config.py`: `REAL_TRADING_MODE = "mock"`.
2. `core/real_mode.py`: `check_real_mode()` — `live` без `--i-understand-risk` / `I_UNDERSTAND_RISK=1` → `sys.exit(1)`.
3. `api_alor_trade.py` / `trader/real.py` → `_is_mock()`.
4. `tests/test_real_mode.py`.
   **Оценка:** 0.5 д.

---

## ⏸ Отложено / отменено

### T-14. `partial_day` open vs resolve — **ОТМЕНЕНО**

**Причина:** слишком много кода (миграция `paper_trades`, `by_partial_day_at_resolve`, CLI, тесты). **Не стоит 0.5 дня** сейчас.
**Когда вернуться:** если `partial_day` начнёт влиять на статистику. Сейчас — **не влияет** (2 теста в `test_partial_day.py` покрывают базовое поведение).
**Альтернатива:** BUG-03 (`now_msk()`) — минимальный фикс таймзоны, без миграции.

### T-01. replay-гейт (match rate) — **отложено**

**Причина:** match rate 0–10% (look-ahead M15). Нужен M1. Отложено до накопления данных.

---
