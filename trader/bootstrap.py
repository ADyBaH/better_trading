"""Bootstrap CI для статистик paper-trades (PF, exp, winrate).

T-04: решения по n=14–23 без CI невозможны (PF 0.73 при n=17 — ±0.4).
"""

import random
from typing import Callable, Sequence


def _bootstrap_ci(
    values: Sequence[float],
    stat_fn: Callable[[Sequence[float]], float | None],
    n_iter: int = 1000,
    alpha: float = 0.05,
    seed: int | None = 42,
) -> tuple[float, float] | None:
    """
    Bootstrap (1-alpha) CI для статистики stat_fn.

    values — выборка (например, result_points по win/loss).
    stat_fn — функция, считающая статистику по выборке.
    n_iter — число bootstrap-итераций.
    alpha — уровень значимости (0.05 → 95% CI).
    seed — для воспроизводимости (42 по умолчанию; None — случайно).

    Возвращает (lower, upper) или None, если values пуст / stat_fn вернул None.
    """
    if not values:
        return None

    rng = random.Random(seed)
    n = len(values)
    stats: list[float] = []

    for _ in range(n_iter):
        sample = [rng.choice(values) for _ in range(n)]
        s = stat_fn(sample)
        if s is not None:
            stats.append(s)

    if not stats:
        return None

    stats.sort()
    lo_idx = int(len(stats) * (alpha / 2))
    hi_idx = int(len(stats) * (1 - alpha / 2))
    # Защита от выхода за границы
    lo_idx = max(0, min(lo_idx, len(stats) - 1))
    hi_idx = max(0, min(hi_idx, len(stats) - 1))
    return (round(stats[lo_idx], 2), round(stats[hi_idx], 2))


def _pf_from_points(points: Sequence[float]) -> float | None:
    """PF = sum(win) / |sum(loss)| по списку points."""
    wins = sum(p for p in points if p > 0)
    losses = abs(sum(p for p in points if p < 0))
    if losses == 0:
        return None
    return wins / losses


def _exp_from_points(points: Sequence[float]) -> float | None:
    """Expectancy = sum(points) / len(points) по win+loss."""
    if not points:
        return None
    return sum(points) / len(points)


def _winrate_from_points(points: Sequence[float]) -> float | None:
    """Winrate = count(>0) / count(!=0) * 100."""
    wl = [p for p in points if p != 0]
    if not wl:
        return None
    return 100 * sum(1 for p in wl if p > 0) / len(wl)
