"""Реестр фильтров сигналов."""

from strategy.filters.base import (
    Filter,
    FilterResult,
    apply_filters,
    get_filters,
    register_filter,
)

# --- Импорт модулей, чтобы декораторы @register_filter сработали ---
from strategy.filters import (  # noqa: F401
    adx,
    bounce,
    breakout,
    orderbook,
    trend,
)

__all__ = [
    "Filter",
    "FilterResult",
    "apply_filters",
    "get_filters",
    "register_filter",
]
