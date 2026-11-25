from core.models import AnalysisResult, Signal
from strategy.filters.base import FilterResult, register_filter


@register_filter("bid_heavy", "bid-heavy > 60%")
def _filter_bid_heavy(sig: Signal, result: AnalysisResult) -> FilterResult:
    ob = getattr(result, "order_book", None) or {}
    pressure = ob.get("pressure_pct")
    if pressure is not None and pressure > 60:
        return FilterResult(blocked=True, reason=f"bid-heavy {pressure:.0f}%")
    return FilterResult(blocked=False)
