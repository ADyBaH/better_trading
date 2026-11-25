"""
Статистика по журналу сделок.
Считает winrate, PnL, разбивки по сигналам и тегам.
"""

from dataclasses import dataclass, field
from collections import defaultdict

from core.logger import get_logger
from trader.journal import Trade, list_trades

import config

log = get_logger(__name__)


# ============================================================
# Модель результата
# ============================================================


@dataclass
class StatsResult:
    """Результат статистики по набору сделок."""

    total: int = 0  # всего сделок
    closed: int = 0  # закрытых
    open: int = 0  # открытых
    wins: int = 0
    losses: int = 0
    breakeven: int = 0

    total_points: float = 0.0
    total_rub: float = 0.0
    avg_win_points: float = 0.0
    avg_loss_points: float = 0.0
    best_points: float = 0.0
    worst_points: float = 0.0

    winrate: float = 0.0  # 0..100

    # Разбивки
    by_signal_kind: dict = field(default_factory=dict)
    by_signal_strength: dict = field(default_factory=dict)
    by_tags: dict = field(default_factory=dict)


# ============================================================
# Расчёт
# ============================================================


def _empty_bucket() -> dict:
    return {"total": 0, "wins": 0, "losses": 0, "points": 0.0, "rub": 0.0}


def _add_to_bucket(bucket: dict, trade: Trade) -> None:
    bucket["total"] += 1
    pts = trade.result_points or 0.0
    bucket["points"] += pts
    bucket["rub"] += trade.result_rub or 0.0
    if pts > 0:
        bucket["wins"] += 1
    elif pts < 0:
        bucket["losses"] += 1


def compute_stats(limit: int = 1000) -> StatsResult:
    """Считает статистику по последним `limit` сделкам."""
    trades = list_trades(limit=limit, only_open=False)
    result = StatsResult()

    wins_points = []
    losses_points = []

    for t in trades:
        result.total += 1

        if not t.is_closed:
            result.open += 1
            continue

        result.closed += 1
        pts = t.result_points or 0.0

        if pts > 0:
            result.wins += 1
            wins_points.append(pts)
        elif pts < 0:
            result.losses += 1
            losses_points.append(pts)
        else:
            result.breakeven += 1

        result.total_points += pts
        result.total_rub += t.result_rub or 0.0

        # --- Разбивки ---
        if t.signal_kind:
            key = t.signal_kind
            result.by_signal_kind.setdefault(key, _empty_bucket())
            _add_to_bucket(result.by_signal_kind[key], t)

        if t.signal_strength:
            key = t.signal_strength
            result.by_signal_strength.setdefault(key, _empty_bucket())
            _add_to_bucket(result.by_signal_strength[key], t)

        for tag in t.tags:
            result.by_tags.setdefault(tag, _empty_bucket())
            _add_to_bucket(result.by_tags[tag], t)

    # Итоговые метрики
    if result.closed > 0:
        result.winrate = round(100 * result.wins / result.closed, 1)

    if wins_points:
        result.avg_win_points = round(sum(wins_points) / len(wins_points), 1)
    if losses_points:
        result.avg_loss_points = round(sum(losses_points) / len(losses_points), 1)

    all_points = [
        t.result_points for t in trades if t.is_closed and t.result_points is not None
    ]
    if all_points:
        result.best_points = round(max(all_points), 1)
        result.worst_points = round(min(all_points), 1)

    result.total_points = round(result.total_points, 1)
    result.total_rub = round(result.total_rub, 2)

    return result
