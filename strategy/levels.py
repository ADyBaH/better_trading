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


def build_levels(
    symbol: str,
    tolerance: float,
    current_price: float,
    atr: float,
    min_weight: int = None,
) -> list[dict]:
    """
    Строит карту уровней по нескольким ТФ (config.LEVEL_TIMEFRAMES).
    Фильтрует по диапазону ±LEVELS_RANGE_ATR * atr вокруг current_price
    и ограничивает LEVELS_MAX_SHOW самыми весомыми.

    Возвращает список уровней, отсортированных по цене (сверху вниз).
    """
    from data.api_facade import get_candles_tf

    all_fractals = []
    for tf in config.LEVEL_TIMEFRAMES:
        df_tf = get_candles_tf(tf, count=300)
        if df_tf.empty:
            log.warning("Нет данных для ТФ %s", tf)
            continue
        fr = find_fractals(df_tf)
        weight = config.LEVEL_TF_WEIGHTS.get(tf, 1)
        for f in fr:
            f_copy = dict(f)
            f_copy["tf"] = tf
            f_copy["weight"] = weight
            all_fractals.append(f_copy)
        log.info("%s: %d фракталов (вес=%d)", tf, len(fr), weight)

    if not all_fractals:
        log.warning("Не найдено фракталов ни на одном ТФ")
        return []

    # Кластеризация общего пула
    levels = cluster_levels(all_fractals, tolerance=tolerance, min_weight=1)

    # Пересчёт весов и tf_source
    for lv in levels:
        cluster_fractals = [
            f for f in all_fractals if abs(f["price"] - lv["price"]) <= tolerance
        ]
        tfs = set(f["tf"] for f in cluster_fractals)
        lv["tf_source"] = tfs
        lv["confirmed"] = len(tfs) >= 2

        total_weight = sum(f["weight"] for f in cluster_fractals)
        if lv["confirmed"]:
            total_weight = int(total_weight * 1.3)
        lv["weight"] = total_weight

    # Фильтр по минимальному весу
    if min_weight is None:
        min_weight = config.LEVELS_MIN_WEIGHT
    levels = [lv for lv in levels if lv["weight"] >= min_weight]

    # Фильтр по диапазону вокруг текущей цены
    price_range = config.LEVELS_RANGE_ATR * atr
    before = len(levels)
    levels = [lv for lv in levels if abs(lv["price"] - current_price) <= price_range]
    log.info(
        "Фильтр по диапазону ±%.5f (%.5f ± %.5f): %d → %d уровней",
        price_range,
        current_price,
        price_range,
        before,
        len(levels),
    )

    # Жёсткий кап
    if len(levels) > config.LEVELS_MAX_SHOW:
        levels = sorted(levels, key=lambda lv: lv["weight"], reverse=True)
        levels = levels[: config.LEVELS_MAX_SHOW]
        log.info("Кап LEVELS_MAX_SHOW=%d применён", config.LEVELS_MAX_SHOW)

    levels.sort(key=lambda lv: lv["price"], reverse=True)
    return levels
