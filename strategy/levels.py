"""
Поиск уровней на свечах.

Текущая реализация:
  - find_fractals       — поиск фракталов (Bill Williams)
  - cluster_levels      — кластеризация фракталов в уровни
  - _merge_nearby_clusters — вспомогательная склейка близких кластеров
"""

import pandas as pd

from core.logger import get_logger
import config

log = get_logger(__name__)


# ============================================================
# Фракталы
# ============================================================


def find_fractals(df: pd.DataFrame, period: int = None) -> list[dict]:
    """
    Находит фракталы в DataFrame со свечами.

    df — DataFrame с колонками: begin, open, high, low, close, volume.
    period — сколько свечей слева и справа проверять (по умолчанию из config).

    Возвращает список словарей:
        {
            "begin":  Timestamp,
            "price":  float,
            "type":   "up" | "down",
            "index":  int,
        }
    """
    period = period or config.FRACTAL_PERIOD

    if len(df) < 2 * period + 1:
        log.warning(
            "Слишком мало свечей для фракталов: %d (нужно ≥%d)",
            len(df),
            2 * period + 1,
        )
        return []

    fractals = []
    highs = df["high"].values
    lows = df["low"].values

    for i in range(period, len(df) - period):
        # --- Фрактал вверх ---
        window_high = highs[i - period : i + period + 1]
        if highs[i] == window_high.max() and (window_high == highs[i]).sum() == 1:
            fractals.append(
                {
                    "begin": df["begin"].iloc[i],
                    "price": float(highs[i]),
                    "type": "up",
                    "index": i,
                }
            )

        # --- Фрактал вниз ---
        window_low = lows[i - period : i + period + 1]
        if lows[i] == window_low.min() and (window_low == lows[i]).sum() == 1:
            fractals.append(
                {
                    "begin": df["begin"].iloc[i],
                    "price": float(lows[i]),
                    "type": "down",
                    "index": i,
                }
            )

    fractals.sort(key=lambda f: f["begin"])
    log.info("Найдено фракталов: %d (period=%d)", len(fractals), period)
    return fractals


# ============================================================
# Кластеризация
# ============================================================


def _merge_nearby_clusters(
    clusters: list[list[dict]],
    tolerance: float,
) -> list[list[dict]]:
    """
    Склеивает соседние кластеры, центры которых ближе, чем tolerance.
    Вход — список кластеров (каждый = список фракталов), отсортированных по цене.
    """
    if not clusters:
        return []

    def center(cluster: list[dict]) -> float:
        return sum(f["price"] for f in cluster) / len(cluster)

    merged = [clusters[0]]
    for cluster in clusters[1:]:
        prev = merged[-1]
        if abs(center(cluster) - center(prev)) <= tolerance:
            prev.extend(cluster)
        else:
            merged.append(cluster)

    return merged


def cluster_levels(
    fractals: list[dict],
    tolerance: float,
    type_filter: str = None,
    min_weight: int = 1,
    merge_tolerance: float = None,
) -> list[dict]:
    """
    Кластеризует фракталы в уровни.

    tolerance — абсолютный допуск для первой кластеризации.
    type_filter — None (все) / "up" / "down".
    min_weight — минимальный вес уровня, чтобы попасть в результат.
    merge_tolerance — допуск для склейки близких кластеров между собой.
                      Если None — используется tolerance.

    Возвращает список уровней, отсортированных по цене.
    """
    if not fractals:
        return []

    items = [f for f in fractals if type_filter is None or f["type"] == type_filter]
    if not items:
        return []

    items.sort(key=lambda f: f["price"])

    # --- Первый проход: кластеризация по tolerance ---
    clusters = []
    current = [items[0]]
    for f in items[1:]:
        if f["price"] - current[0]["price"] <= tolerance:
            current.append(f)
        else:
            clusters.append(current)
            current = [f]
    clusters.append(current)

    # --- Второй проход: склейка близких кластеров ---
    if merge_tolerance is None:
        merge_tolerance = tolerance
    clusters = _merge_nearby_clusters(clusters, merge_tolerance)

    # --- Формируем результат ---
    result = []
    for cluster in clusters:
        if len(cluster) < min_weight:
            continue

        prices = [f["price"] for f in cluster]
        types = set(f["type"] for f in cluster)
        begins = [f["begin"] for f in cluster]

        if types == {"up"}:
            ctype = "up"
        elif types == {"down"}:
            ctype = "down"
        else:
            ctype = "mixed"

        result.append(
            {
                "price": sum(prices) / len(prices),
                "weight": len(cluster),
                "type": ctype,
                "last_seen": max(begins),
                "first_seen": min(begins),
            }
        )

    log.info(
        "Кластеризация: %d фракталов → %d уровней "
        "(tolerance=%.5f, merge=%.5f, min_weight=%d)",
        len(items),
        len(result),
        tolerance,
        merge_tolerance,
        min_weight,
    )
    return result
