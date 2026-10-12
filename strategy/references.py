"""
Референсные уровни (слой C):
  - round numbers (психологические круглые цены),
  - PDH / PDL  (Previous Day High / Low),
  - PWH / PWL  (Previous Week High / Low).

Эти уровни НЕ смешиваются со структурными (A+B).
Возвращаются отдельным списком и показываются отдельным блоком.
"""

import pandas as pd
from datetime import timedelta

from core.logger import get_logger
import config

log = get_logger(__name__)


# ============================================================
# Round numbers
# ============================================================

def find_round_numbers(
    current_price: float,
    step: float = None,
    n_each_side: int = 3,
) -> list[dict]:
    """
    Возвращает ближайшие round numbers вокруг текущей цены.

    current_price — текущая цена.
    step — шаг round numbers (по умолчанию config.ROUND_STEP).
    n_each_side — сколько уровней взять сверху и снизу.

    Возвращает список словарей:
        {
            "price":    float,
            "type":     "round",
            "weight":   int,   # условный вес — round numbers всегда "слабые" (1)
            "label":    str,   # человекочитаемая метка, например "12.550"
        }
    """
    step = step or config.ROUND_STEP

    # Округляем цену до ближайшего кратного step
    base = round(current_price / step) * step

    levels = []
    for i in range(-n_each_side, n_each_side + 1):
        price = round(base + i * step, 5)   # 5 знаков — под шаг CNYRUBF
        if price <= 0:
            continue
        levels.append({
            "price":  price,
            "type":   "round",
            "weight": 1,                     # у round numbers вес символический
            "label":  f"{price:.3f}",
        })

    log.info("Round numbers: %d уровней (шаг %.3f)", len(levels), step)
    return levels


# ============================================================
# PDH / PDL
# ============================================================

def find_pdh_pdl(
    df: pd.DataFrame,
    n_days: int = 1,
) -> list[dict]:
    """
    Находит Previous Day High / Low.

    df — DataFrame со свечами (любой ТФ, но лучше M15 или M5 — там точнее экстремум).
         Должен содержать колонки begin, high, low.
    n_days — за сколько прошлых дней считать (1 = только вчера).

    Возвращает список словарей:
        {
            "price":  float,
            "type":   "pdh" | "pdl",
            "weight": int,   # условный вес = n_days (свежее = важнее)
            "label":  str,   # "PDH" / "PDL" / "PDH-2" / "PDL-2" и т.п.
            "date":   date,  # дата того дня
        }
    """
    if df.empty:
        log.warning("Пустой DataFrame для PDH/PDL")
        return []

    df = df.copy()
    df["date"] = df["begin"].dt.date

    # Список уникальных дат, отсортированных
    all_dates = sorted(df["date"].unique())

    # Последняя дата — это "сегодня", нам нужны прошлые
    # (если запускаем в течение дня, "сегодня" может быть неполным)
    today = pd.Timestamp.now().date()

    past_dates = [d for d in all_dates if d < today]
    if not past_dates:
        log.warning("Нет прошлых дней для PDH/PDL")
        return []

    # Берём последние n_days
    target_dates = past_dates[-n_days:]
    target_dates.reverse()   # свежие — первыми

    levels = []
    for idx, d in enumerate(target_dates, start=1):
        day_df = df[df["date"] == d]
        if day_df.empty:
            continue

        high = float(day_df["high"].max())
        low = float(day_df["low"].min())

        suffix = "" if idx == 1 else f"-{idx}"
        # Вес: свежий день важнее. PDH весит 2, PDH-2 весит 1 и т.д.
        weight = max(1, 3 - idx)

        levels.append({
            "price":  high,
            "type":   "pdh",
            "weight": weight,
            "label":  f"PDH{suffix}",
            "date":   d,
        })
        levels.append({
            "price":  low,
            "type":   "pdl",
            "weight": weight,
            "label":  f"PDL{suffix}",
            "date":   d,
        })

    log.info("PDH/PDL: %d уровней (за %d дней)", len(levels), n_days)
    return levels


# ============================================================
# PWH / PWL
# ============================================================

def find_pwh_pwl(
    df: pd.DataFrame,
    n_weeks: int = 1,
) -> list[dict]:
    """
    Находит Previous Week High / Low.

    df — DataFrame со свечами. Лучше H1 или выше — там неделя видна точно.
    n_weeks — за сколько прошлых недель (1 = только прошлая).

    Возвращает список словарей:
        {
            "price":  float,
            "type":   "pwh" | "pwl",
            "weight": int,
            "label":  str,
            "week":   str,   # ISO-неделя, например "2026-W41"
        }
    """
    if df.empty:
        log.warning("Пустой DataFrame для PWH/PWL")
        return []

    df = df.copy()
    df["week"] = df["begin"].dt.isocalendar().week
    df["year"] = df["begin"].dt.isocalendar().year

    # Текущая ISO-неделя
    now = pd.Timestamp.now()
    current_year = now.isocalendar().year
    current_week = now.isocalendar().week

    # Прошлые недели
    df["iso_year_week"] = df["year"].astype(str) + "-W" + df["week"].astype(str).str.zfill(2)
    current_key = f"{current_year}-W{str(current_week).zfill(2)}"

    past = df[df["iso_year_week"] < current_key]
    if past.empty:
        log.warning("Нет прошлых недель для PWH/PWL")
        return []

    past_weeks = sorted(past["iso_year_week"].unique())
    target_weeks = past_weeks[-n_weeks:]
    target_weeks.reverse()

    levels = []
    for idx, wk in enumerate(target_weeks, start=1):
        wk_df = past[past["iso_year_week"] == wk]
        if wk_df.empty:
            continue

        high = float(wk_df["high"].max())
        low = float(wk_df["low"].min())

        suffix = "" if idx == 1 else f"-{idx}"
        weight = max(1, 3 - idx)

        levels.append({
            "price":  high,
            "type":   "pwh",
            "weight": weight,
            "label":  f"PWH{suffix}",
            "week":   wk,
        })
        levels.append({
            "price":  low,
            "type":   "pwl",
            "weight": weight,
            "label":  f"PWL{suffix}",
            "week":   wk,
        })

    log.info("PWH/PWL: %d уровней (за %d недель)", len(levels), n_weeks)
    return levels


# ============================================================
# Агрегатор
# ============================================================

def build_references(
    current_price: float,
    atr: float,
    df_intraday: pd.DataFrame,
    df_h1: pd.DataFrame,
) -> list[dict]:
    """
    Собирает все референсные уровни в один список.

    current_price — текущая цена.
    atr — ATR(H1), для фильтра по диапазону.
    df_intraday — свечи M15 или M5 (для PDH/PDL).
    df_h1 — свечи H1 (для PWH/PWL).
    """
    levels = []

    # Round numbers
    if config.ROUND_STEP:
        levels.extend(find_round_numbers(current_price, step=config.ROUND_STEP))

    # PDH/PDL
    if config.SHOW_PDH_PDL:
        levels.extend(find_pdh_pdl(df_intraday, n_days=1))

    # PWH/PWL
    if config.SHOW_PWH_PWL:
        levels.extend(find_pwh_pwl(df_h1, n_weeks=1))

    # Фильтр по диапазону вокруг текущей цены
    price_range = config.LEVELS_RANGE_ATR * atr
    before = len(levels)
    levels = [
        lv for lv in levels
        if abs(lv["price"] - current_price) <= price_range
    ]
    log.info(
        "Референсные уровни: %d → %d (диапазон ±%.5f)",
        before, len(levels), price_range,
    )

    # Сортируем по цене, сверху вниз
    levels.sort(key=lambda lv: lv["price"], reverse=True)
    return levels