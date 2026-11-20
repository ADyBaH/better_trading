from core.models import AnalysisResult, Signal
from strategy.filters.base import FilterResult, register_filter


@register_filter("bullish_long", "LONG при week_trend=bullish")
def _filter_bullish_long(sig: Signal, result: AnalysisResult) -> FilterResult:
    ind = result.indicators
    if ind.week_trend == "bullish" and sig.direction == "long":
        return FilterResult(blocked=True, reason="bullish + long")
    return FilterResult(blocked=False)


@register_filter("normal_breakout", "breakout/trend_level при market_state=normal")
def _filter_normal_breakout(sig: Signal, result: AnalysisResult) -> FilterResult:
    ind = result.indicators
    if ind.market_state == "normal" and sig.kind in ("breakout", "trend_level"):
        return FilterResult(blocked=True, reason=f"normal + {sig.kind}")
    return FilterResult(blocked=False)


@register_filter("bullish_short", "SHORT при week_trend=bullish")
def _filter_bullish_short(sig: Signal, result: AnalysisResult) -> FilterResult:
    ind = result.indicators
    if ind.week_trend == "bullish" and sig.direction == "short":
        return FilterResult(blocked=True, reason="bullish + short")
    return FilterResult(blocked=False)
