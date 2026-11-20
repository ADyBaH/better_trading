import config
from core.models import AnalysisResult, Signal
from strategy.filters.base import FilterResult, register_filter


@register_filter(
    "breakout",
    "kill-switch для breakout",
    enabled_fn=lambda: getattr(config, "PAPER_SKIP_BREAKOUT", False),
)
def _filter_breakout_killswitch(sig: Signal, result: AnalysisResult) -> FilterResult:
    if sig.kind == "breakout":
        return FilterResult(blocked=True, reason="PAPER_SKIP_BREAKOUT")
    return FilterResult(blocked=False)


@register_filter(
    "breakout_filter",
    "F1-F4 для breakout",
    enabled_fn=lambda: getattr(config, "BREAKOUT_FILTER", "none") != "none",
)
def _filter_breakout_conditional(sig: Signal, result: AnalysisResult) -> FilterResult:
    if sig.kind != "breakout":
        return FilterResult(blocked=False)

    from strategy.signals import _breakout_passes_filter

    if not _breakout_passes_filter(result, sig):
        return FilterResult(blocked=True, reason=f"F-фильтр {config.BREAKOUT_FILTER}")
    return FilterResult(blocked=False)
