from core.models import AnalysisResult, Signal
from strategy.filters.base import FilterResult, register_filter


@register_filter("pullback_bounce", "pullback + bounce")
def _filter_pullback_bounce(sig: Signal, result: AnalysisResult) -> FilterResult:
    ind = result.indicators
    if ind.market_state == "pullback" and sig.kind == "bounce":
        return FilterResult(blocked=True, reason="pullback + bounce")
    return FilterResult(blocked=False)
