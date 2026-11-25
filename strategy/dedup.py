"""
Дедупликация сигналов.

Вынесено из strategy/signals.py (шаг 9 рефакторинга).
"""

from core.models import Signal


def _deduplicate_signals(
    signals: list[Signal],
    atr: float,
) -> list[Signal]:
    """
    Дедуп по (direction, entry_price, level_price) в пределах 0.5 ATR.

    Сортирует по strength_score (убывание), оставляет первый (сильнейший).
    """
    dedup_window = 0.5 * atr if atr > 0 else 0.0
    best: list[Signal] = []
    for s in sorted(signals, key=lambda x: x.strength_score, reverse=True):
        is_dup = False
        for b in best:
            if b.direction != s.direction:
                continue
            if abs(b.entry_price - s.entry_price) < dedup_window:
                is_dup = True
                break
            if abs((b.level_price or 0) - (s.level_price or 0)) < dedup_window:
                is_dup = True
                break
        if not is_dup:
            best.append(s)
    return best
