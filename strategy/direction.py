"""
Проверка направления сигнала против тренда.

Вынесено из strategy/signals.py (шаг 8.0 рефакторинга).
"""


def _is_direction_allowed(direction: str, trend: str, kind: str) -> bool:
    """
    Проверяет, можно ли торговать в эту сторону при данном тренде.

    Правило:
    - trend_level — не трогаем (уже согласован).
    - bounce/breakout при up/strong_up → нет SHORT.
    - bounce/breakout при down/strong_down → нет LONG.
    - при transition — разрешено (штраф применяется отдельно).
    """
    if kind == "trend_level":
        return True

    if trend in ("up", "strong_up") and direction == "short":
        return False
    if trend in ("down", "strong_down") and direction == "long":
        return False

    return True
