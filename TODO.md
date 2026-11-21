# TODO — исправления

Активные баги и задачи. История экспериментов — в `EXPERIMENTS.md`.
Архитектурные улучшения — в задачах T-01…T-23 (см. трекер).

---

## 🔴 BUG-01. `test_paper_bid_ask.py` — `MockInd` не имеет `partial_day`

**Обнаружено:** 2026-11-21, `pytest -m integration` на ветке `experiment/breakout-filter`.
**Тип:** баг теста (мок устарел после миграции `partial_day` в `IndicatorSnapshot`).
**Приоритет:** P0 (блокирует collection — падает весь integration-прогон).
**Реальные данные:** не нужны (фикс мока + юнит-тест).

### Симптом

!!!
tests\test_paper_bid_ask.py:53: in <module>
    created = save_signal_as_paper(conn, [sig], r, bid_vol=33992, ask_vol=33399)
trader\paper.py:445: in save_signal_as_paper
    1 if ind.partial_day else 0,
         ^^^^^^^^^^^^^^^
E   AttributeError: 'MockInd' object has no attribute 'partial_day'
!!!

### Причина

`trader/paper.py::save_signal_as_paper` читает `ind.partial_day` (добавлено в 0.11.0 вместе с `by_partial_day`). В `tests/test_paper_bid_ask.py` используется локальный `MockInd` (или `SimpleNamespace`), который **не обновлён** — в нём нет `partial_day` (а возможно, и других новых полей: `day_open`, `day_atr_base`, `day_range_atr`, `take_source`, `take_atr_value`, `day_range_atr_at_open`).

Это классический симптом того, что **T-06 (`schema_version` + идемпотентные миграции) не сделан**: при каждом новом поле `paper_trades` надо руками обновлять все моки.

### Что сделать

**Минимальный фикс (сейчас):**

1. Открыть `tests/test_paper_bid_ask.py`, найти `MockInd`.
2. Добавить недостающие поля с дефолтами, синхронно с `IndicatorSnapshot`:

   !!!
   class MockInd:
       # ... существующие поля ...
       # добавлено в 0.11.0 (partial_day):
       partial_day: bool = False
       day_open: float = 0.0
       day_atr_base: float = 0.0
       day_range_atr: float = 0.0
       # добавлено в 0.14.0 (adaptive take):
       take_source: str = "atr"
       take_atr_value: float = 0.0
       day_range_atr_at_open: float = 0.0
   !!!

3. Прогнать `pytest tests/test_paper_bid_ask.py -v` — должно быть зелёное.
4. Прогнать `pytest -m integration` — collection error уходит.

**Системный фикс (чтобы не повторилось — в рамках T-06):**

- Вынести **единый** `MockIndicator` (или `make_mock_ind(**overrides)`) в `tests/conftest.py`, собирающий поля **из реального dataclass** `IndicatorSnapshot` через `dataclasses.fields()` + `default_factory`. Тогда новое поле в `IndicatorSnapshot` автоматически появится в моке — тесты не падают при миграции.
- Пример:

  !!!
  # tests/conftest.py
  import dataclasses
  from core.models import IndicatorSnapshot

  def make_mock_ind(**overrides):
      defaults = {}
      for f in dataclasses.fields(IndicatorSnapshot):
          if f.default is not dataclasses.MISSING:
              defaults[f.name] = f.default
          elif f.default_factory is not dataclasses.MISSING:
              defaults[f.name] = f.default_factory()
          else:
              defaults[f.name] = None
      defaults.update(overrides)
      return SimpleNamespace(**defaults)
  !!!

- Заменить все локальные `MockInd`/`MockSignal` в `tests/` на `make_mock_ind(...)`. Это закроет **весь класс** багов «мок устарел после миграции», а не только этот.

### Приёмка

- [ ] `pytest tests/test_paper_bid_ask.py -v` — passed.
- [ ] `pytest -m integration` — нет collection error (даже если сетевые тесты падают по таймауту — см. BUG-02).
- [ ] `tests/conftest.py::make_mock_ind` существует, `dataclasses.fields(IndicatorSnapshot)` даёт все поля.
- [ ] `grep -rn "class MockInd" tests/` — пусто (все заменены на `make_mock_ind`).

### Оценка

- Минимальный фикс: **0.1 дня**.
- Системный фикс (conftest + замена во всех тестах): **0.5 дня**.

---

## 🟠 BUG-02. `test_iss_lag.py::test_4_direct_trades` — таймаут `iss.moex.com` (30 с)

**Обнаружено:** 2026-11-21, `pytest -m integration`.
**Тип:** флаки-тест (зависит от сети и таймаута сервера ISS).
**Приоритет:** P1 (не блокирует collection, но делает integration-прогон нестабильным — 110 с, 1 failed).
**Реальные данные:** не нужны (фикс — retry/таймаут/маркировка, а не анализ `candles_*.json`).

### Симптом

!!!
tests\test_iss_lag.py:83: in test_4_direct_trades
    r = requests.get(url, params=params, timeout=30)
E   requests.exceptions.ConnectionError: HTTPSConnectionPool(host='iss.moex.com', port=443): Read timed out.
!!!

Тест `test_4_direct_trades` — единственный, который бьёт в `trades.json` (лента сделок) напрямую. Остальные 4 теста (`test_1_current`, `test_2_today_range`, `test_3_direct_candles`, `test_5_stability`) прошли — то есть сервер жив, но `trades.json` за 30 с не ответил (тяжёлый эндпоинт, возможен rate-limit или большой объём).

### Причина

1. `timeout=30` — на `trades.json` с большим диапазоном этого мало (сервер отдаёт chunked, `_handle_chunk` таймаутит на середине).
2. Нет retry — один сетевой сбой = failed.
3. Нет `@pytest.mark.flaky` / `pytest-rerunfailures` — интеграционные тесты по определению флаки.
4. Возможно, тест запрашивает слишком широкий диапазон (весь день) — `trades.json` за день по CNYRUBF большой.

### Что сделать

**Минимальный фикс (сейчас):**

1. В `tests/test_iss_lag.py::test_4_direct_trades`:
   - Увеличить `timeout` до 60 (или 90) для `trades.json` — это тяжёлый эндпоинт.
   - Сузить диапазон: запрашивать не весь день, а **последние 5–10 минут** (`from = now - 10min`), чтобы объём ответа был маленький.
   - Оставить `requests.get(..., timeout=60)`.

2. Добавить `pytest-rerunfailures` в `requirements-dev.txt` (или `requirements.txt`):
   !!!
   pytest-rerunfailures
   !!!
   И в `pyproject.toml`:
   !!!toml
   [tool.pytest.ini_options]
   addopts = "--reruns 2 --reruns-delay 5"
   markers = ["integration: ..."]
   !!!
   Тогда любой integration-тест переживает 1–2 сетевых сбоя.

3. Пометить `test_4_direct_trades` (и вообще все сетевые) как `@pytest.mark.integration` + `@pytest.mark.flaky(reruns=2, reruns_delay=5)` — явно, чтобы при отключённом `--reruns` было видно, что тест нестабильный.

**Системный фикс (по желанию):**

- В `tests/conftest.py` — фикстура `iss_client` с retry (3 попытки, exponential backoff 1/2/4 с) и `timeout=60`. Все integration-тесты используют её, а не голый `requests.get`.
- Отдельный маркер `@pytest.mark.slow` для `trades.json` — чтобы можно было гонять `pytest -m "integration and not slow"` в CI, а `slow` — только локально/ночью.

### Приёмка

- [ ] `pytest tests/test_iss_lag.py::test_4_direct_trades -v` — passed (при живом сервере), либо `SKIPPED` при недоступности (см. ниже).
- [ ] `pytest -m integration` — 0 failed (флаки переживаются rerun'ом).
- [ ] `pytest -m integration` укладывается в разумное время (сейчас 110 с — после сужения диапазона должно быть < 60 с).
- [ ] `pyproject.toml` содержит `--reruns 2`.

**Опционально — «мягкий skip» при недоступности ISS:**

В `test_4_direct_trades` обернуть запрос:

!!!
try:
    r = requests.get(url, params=params, timeout=60)
except requests.exceptions.ConnectionError as e:
    pytest.skip(f"ISS недоступен: {e}")
!!!

Тогда в оффлайн-окружении тест не падает, а скипается — integration-прогон зелёный. Это правильно для интеграционных тестов: они проверяют **контракт**, а не доступность сервера.

### Оценка

- Минимальный фикс (timeout + сузить диапазон + rerun): **0.2 дня**.
- Системный фикс (фикстура `iss_client` + маркер `slow` + `pytest.skip` на ConnectionError): **0.5 дня**.

---

## Сводка

| ID     | Задача                                                    | P   | Оценка (мин / сист) | Реальные данные |
|--------|-----------------------------------------------------------|-----|---------------------|-----------------|
| BUG-01 | `MockInd.partial_day` — collection error в integration    | P0  | 0.1 / 0.5 д         | нет             |
| BUG-02 | `test_4_direct_trades` — таймаут `iss.moex.com`           | P1  | 0.2 / 0.5 д         | нет             |

**Рекомендуемый порядок:** BUG-01 → BUG-02. Оба — в один спринт, ~0.5–1 день с системными фиксами.

**Связь с T-06:** BUG-01 — прямое следствие того, что `schema_version` + единый `make_mock_ind` ещё не сделаны. Системный фикс BUG-01 стоит делать вместе с T-06, чтобы закрыть класс багов «мок устарел после миграции».

---

## Примечания

- **`integration`-тесты не должны быть в обязательном CI.** `pytest` по умолчанию — `-m "not integration"` (T-20). `integration` — отдельный job, `allow_failure: true` (или `continue-on-error`), потому что сеть/ISS — внешняя зависимость.
- **`test_4_direct_trades` — единственный тест, который тянет `trades.json`.** Если он нестабилен и после фикса — рассмотреть удаление (он дублирует `test_3_direct_candles` по смыслу: проверка «ISS отвечает»). Но лучше оставить со `skip` на ConnectionError — он ловит регрессии контракта `trades.json`.
- **Долгосрочно:** `requests` → `httpx` с `timeout=Timeout(connect=5, read=60)` и `transport=Retry(...)` — единая retry-политика вместо ручных `try/except` в каждом тесте. Это уже архитектурная задача, не в этом TODO.