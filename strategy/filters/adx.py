from core.models import AnalysisResult, Signal
from strategy.filters.base import FilterResult, register_filter


@register_filter("adx_trend", "ADX 20-25")
def _filter_adx_trend(sig: Signal, result: AnalysisResult) -> FilterResult:
    ind = result.indicators
    if ind.adx is not None and 20 <= ind.adx < 25:
        return FilterResult(blocked=True, reason=f"ADX {ind.adx:.1f} в 20-25")
    return FilterResult(blocked=False)


@register_filter("adx_flat_breakout", "ADX<20 + breakout")
def _filter_adx_flat_breakout(sig: Signal, result: AnalysisResult) -> FilterResult:
    ind = result.indicators
    if sig.kind == "breakout" and ind.adx is not None and ind.adx < 20:
        return FilterResult(blocked=True, reason=f"ADX {ind.adx:.1f} flat + breakout")
    return FilterResult(blocked=False)
