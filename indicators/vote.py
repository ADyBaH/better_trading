"""
Голосование источников: сумма голосов + breakdown + label по порогам.

Используется в indicators/calc.py:
- get_main_trend — 4 источника (ema, day, structure, price_direction)
- get_week_trend — 3 источника (ema50/200, close vs close-5d, close vs open-5d)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VoteResult:
    """Результат голосования."""

    total: float
    breakdown: dict[str, float] = field(default_factory=dict)
    label: str = ""


def vote_raw(
    conditions: list[tuple[str, bool]],
    weights: Optional[dict[str, float]] = None,
) -> VoteResult:
    """
    Считает сумму голосов без маппинга в label.

    conditions: [(source_name, condition_bool), ...]
        condition_bool=True  → +weight
        condition_bool=False → -weight
    weights: {source_name: weight}. Если None — все 1.0.
            Если source_name нет в weights — 1.0.

    Возвращает VoteResult(total, breakdown, label="").
    """
    if weights is None:
        weights = {}

    breakdown: dict[str, float] = {}
    total = 0.0

    for name, cond in conditions:
        w = weights.get(name, 1.0)
        if cond is None:
            v = 0.0
        elif cond:
            v = w
        else:
            v = -w
        breakdown[name] = v
        total += v

    return VoteResult(total=total, breakdown=breakdown, label="")


def vote(
    conditions: list[tuple[str, bool]],
    weights: Optional[dict[str, float]] = None,
    thresholds: Optional[list[tuple[float, str]]] = None,
    default: str = "neutral",
) -> VoteResult:
    """
    Голосование с маппингом суммы в label.

    thresholds: [(min_sum, label), ...] — проверяются по порядку,
        первый threshold, где total >= min_sum, даёт label.
        Пример: [(3, "strong_up"), (2, "up"), (-2, "down"), (-3, "strong_down")]
        Для total=2.5: 3? нет. 2? да → "up".
        Для total=-3.5: 3? нет. 2? нет. -2? нет. -3? да (>= -3) → "strong_down".
        Для total=-1.5: 3? нет. 2? нет. -2? нет (-1.5 >= -2? да) → "down".

    default: label, если ни один threshold не сработал.
    """
    result = vote_raw(conditions, weights)

    if thresholds is None:
        return result

    for op, value, label in thresholds:
        if op == ">=" and result.total >= value:
            result.label = label
            return result
        if op == "<=" and result.total <= value:
            result.label = label
            return result

    result.label = default
    return result
