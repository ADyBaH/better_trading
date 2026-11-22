"""
Штрафы score: EMA-конфликт, пила, late-chase.

Вынесено из strategy/signals.py (шаг 9 рефакторинга).

_apply_penalties возвращает reason (если сигнал отброшен) или None.
"""

from core.logger import get_logger
from core.models import AnalysisResult, Level, Signal
from strategy.strength import _recalc_strength

log = get_logger(__name__)


def _apply_penalties(
    s: Signal,
    result: AnalysisResult,
    level: Level | None,
    skip_filters: bool = False,
) -> str | None:
    """
    Применяет штрафы к сигналу (мутирует s.strength_score, s.reasons, s.strength).

    Возвращает:
        None — сигнал прошёл (или skip_filters=True)
        str — reason, если сигнал отброшен (strength == "none")

    skip_filters=True — для replay/backtest: штрафы не применяем.
    """
    if skip_filters:
        return None

    # --- 1. Штраф: EMA против direction ---
    ema_against = (
        s.direction == "long" and s.context.get("ema_alignment") == "bearish"
    ) or (s.direction == "short" and s.context.get("ema_alignment") == "bullish")
    if ema_against:
        penalty = 1.0
        s.strength_score = max(0.0, s.strength_score - penalty)
        s.reasons.append(f"штраф EMA-конфликт: -{penalty}")
        s.strength = _recalc_strength(s.strength_score)
        if s.strength == "none":
            return "penalty:ema_conflict"

    # --- 2. Штраф: пила (противоположный сигнал < 30 мин) ---
    recent_dir = s.context.get("recent_signal_direction")
    recent_age = s.context.get("recent_signal_age_min")
    if (
        recent_dir
        and recent_dir != s.direction
        and recent_age is not None
        and recent_age < 30
    ):
        penalty = 1.5
        s.strength_score = max(0.0, s.strength_score - penalty)
        s.reasons.append(
            f"штраф пила: -{penalty} ({recent_age} мин назад {recent_dir})"
        )
        s.strength = _recalc_strength(s.strength_score)
        if s.strength == "none":
            return "penalty:saw"

    # --- 3. Штраф: late/chase (цена прошла > 1 ATR от уровня) ---
    if (
        level is not None
        and level.distance_atr is not None
        and level.distance_atr > 1.0
    ):
        penalty = 1.0
        s.strength_score = max(0.0, s.strength_score - penalty)
        s.reasons.append(
            f"штраф late/chase: -{penalty} (distance={level.distance_atr:.1f} ATR)"
        )
        s.strength = _recalc_strength(s.strength_score)
        if s.strength == "none":
            return "penalty:late_chase"

    return None
