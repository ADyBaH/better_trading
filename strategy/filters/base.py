"""
Базовый реестр фильтров сигналов.

Каждый фильтр — функция (signal, result) -> FilterResult.
Регистрируется декоратором @register_filter.
Включается/выключается через enabled_fn (опционально) или config.PAPER_SKIP_<NAME>.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from core.models import AnalysisResult, Signal


@dataclass
class FilterResult:
    blocked: bool
    reason: str = ""


FilterFn = Callable[[Signal, AnalysisResult], FilterResult]
EnabledFn = Callable[[], bool]


@dataclass
class Filter:
    name: str
    fn: FilterFn
    description: str = ""
    enabled_fn: Optional[EnabledFn] = None
    enabled: bool = False


_FILTERS: list[Filter] = []


def register_filter(
    name: str,
    description: str = "",
    enabled_fn: Optional[EnabledFn] = None,
):
    def decorator(fn: FilterFn) -> FilterFn:
        _FILTERS.append(
            Filter(name=name, fn=fn, description=description, enabled_fn=enabled_fn)
        )
        return fn

    return decorator


def get_filters() -> list[Filter]:
    """Возвращает список фильтров с актуальными enabled."""
    import config

    for f in _FILTERS:
        if f.enabled_fn is not None:
            f.enabled = bool(f.enabled_fn())
        else:
            f.enabled = getattr(config, f"PAPER_SKIP_{f.name.upper()}", False)
    return _FILTERS


def apply_filters(signal: Signal, result: AnalysisResult) -> Optional[str]:
    """Применяет все включённые фильтры. Возвращает имя первого сработавшего или None."""
    for f in get_filters():
        if not f.enabled:
            continue
        res = f.fn(signal, result)
        if res.blocked:
            return f.name
    return None
