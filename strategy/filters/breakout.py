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


def _breakout_passes_filter(result: AnalysisResult, signal: Signal) -> bool:
    """
    Условные фильтры F1–F4 для breakout (config.BREAKOUT_FILTER).
    Возвращает True, если сигнал проходит фильтр (можно создавать).
    При BREAKOUT_FILTER == "none" — всегда True.
    """
    flt = getattr(config, "BREAKOUT_FILTER", "none")
    if flt == "none":
        return True

    ind = result.indicators
    adx = ind.adx
    direction = signal.direction

    if flt == "F1":  # ADX >= 25 (strong) только
        return adx is not None and adx >= config.ADX_STRONG
    if flt == "F2":  # ADX < 20 (flat) только
        return adx is not None and adx < config.ADX_THRESHOLD
    if flt == "F3":  # market_state == impulse только
        return ind.market_state == "impulse"
    if flt == "F4":  # week_trend не противоречит direction (neutral пропускаем)
        if ind.week_trend == "bullish" and direction == "short":
            return False
        if ind.week_trend == "bearish" and direction == "long":
            return False
        return True
    return True  # неизвестный фильтр — не блокируем


@register_filter(
    "breakout_filter",
    "F1-F4 для breakout",
    enabled_fn=lambda: getattr(config, "BREAKOUT_FILTER", "none") != "none",
)
def _filter_breakout_conditional(sig: Signal, result: AnalysisResult) -> FilterResult:
    if sig.kind != "breakout":
        return FilterResult(blocked=False)

    if not _breakout_passes_filter(result, sig):
        return FilterResult(blocked=True, reason=f"F-фильтр {config.BREAKOUT_FILTER}")
    return FilterResult(blocked=False)
