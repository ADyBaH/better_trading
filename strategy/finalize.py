"""
Финализация сигнала: context, warnings, R:R.

Вынесено из strategy/signals.py (шаг 7 рефакторинга).
Не бросает исключения наружу (try/except + log).
"""

import pandas as pd

from core.instruments import commission_in_price
from core.logger import get_logger
from core.models import AnalysisResult, Level, Signal
from strategy.context import _build_context
from strategy.warnings import _build_warnings

log = get_logger(__name__)


def _finalize_signal(
    signal: Signal,
    result: AnalysisResult,
    df: pd.DataFrame,
    level: Level | None,
    recent_signal: dict | None,
    symbol: str,
) -> Signal:
    """Заполняет context, warnings, R:R. Не бросает исключения наружу."""
    try:
        signal.context = _build_context(result, df, level, recent_signal)
    except Exception as e:
        log.exception(
            "_build_context упал (signal=%s %s): %s", signal.direction, signal.kind, e
        )
        signal.context = {}

    signal.market_state = result.indicators.market_state

    try:
        signal.warnings = _build_warnings(
            signal.direction, result, level, recent_signal, df
        )
    except Exception as e:
        log.exception(
            "_build_warnings упал (signal=%s %s): %s", signal.direction, signal.kind, e
        )
        signal.warnings = []

    # --- R:R — критично, всегда заполняем ---
    try:
        signal.compute_rr(commission_round=commission_in_price(symbol))
    except Exception as e:
        log.exception(
            "compute_rr упал (signal=%s %s): %s", signal.direction, signal.kind, e
        )

    # --- Fallback: если RR всё ещё None — считаем вручную ---
    if signal.risk_reward is None or signal.net_rr is None:
        gross_risk = abs(signal.entry_price - signal.stop_price)
        gross_reward = abs(signal.take_price - signal.entry_price)
        if gross_risk > 0:
            comm = commission_in_price(symbol)
            if signal.risk_reward is None:
                signal.risk_reward = round(gross_reward / gross_risk, 2)
            if signal.net_rr is None:
                net_risk = gross_risk + comm
                net_reward = gross_reward - comm
                if net_risk > 0:
                    signal.net_rr = round(net_reward / net_risk, 2)
            log.warning(
                "RR fallback: %s %s entry=%.3f stop=%.3f take=%.3f → RR=%.2f net=%.2f",
                signal.direction,
                signal.kind,
                signal.entry_price,
                signal.stop_price,
                signal.take_price,
                signal.risk_reward,
                signal.net_rr,
            )
        else:
            log.error(
                "RR невозможно посчитать: gross_risk=0 (entry=%.3f, stop=%.3f)",
                signal.entry_price,
                signal.stop_price,
            )
            signal._rr_invalid = True

    return signal
