"""
Подсчёт силы сигнала (score + strength).

Вынесено из strategy/signals.py (шаг 2 рефакторинга).
"""


def _compute_strength(matched: list[str]) -> tuple[float, str]:
    """
    Считает score и strength по matched criteria (A/B/C/D/E).
    Логика НЕ меняется (см. signals.py до рефакторинга).
    """
    groups = {"A": [], "B": [], "C": [], "D": [], "E": []}
    for c in matched:
        g = c[0]
        if g in groups:
            groups[g].append(c)

    effective = []
    for g, items in groups.items():
        limit = 3 if g == "A" else 2
        effective.extend(items[:limit])

    has_a = len(groups["A"]) > 0
    has_c_or_d = len(groups["C"]) > 0 or len(groups["D"]) > 0
    score = float(len(effective))

    if not has_a or score < 1:
        return 0.0, "none"
    elif score == 1:
        return score, "weak"
    elif score == 2:
        return score, "medium"
    elif score >= 3 and has_c_or_d:
        return score, "strong"
    else:
        return score, "medium"


def _recalc_strength(score: float) -> str:
    """
    Пересчитывает strength по score (после штрафов).
    """
    if score < 1.0:
        return "none"
    elif score < 2.0:
        return "weak"
    elif score < 3.0:
        return "medium"
    return "strong"
