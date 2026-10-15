# ui/render_console.py
"""Консольный рендерер AnalysisResult."""

from datetime import datetime

from tabulate import tabulate

from core.models import AnalysisResult, Level, Signal

import config

# ============================================================
# Вспомогательные
# ============================================================


def _stars(score: float | None, max_score: float) -> str:
    """Визуальная сила уровня по strength_score."""
    if not score or max_score <= 0:
        return ""
    ratio = score / max_score
    if ratio >= 0.75:
        return "★★★"
    elif ratio >= 0.4:
        return "★★"
    return "★"


def _fmt_ago(dt: datetime | None) -> str:
    """'2ч' / '15м' / '3д' вместо полной даты."""
    if dt is None:
        return ""
    sec = int((datetime.now() - dt).total_seconds())
    if sec < 3600:
        return f"{sec // 60}м"
    elif sec < 86400:
        return f"{sec // 3600}ч"
    return f"{sec // 86400}д"


def _indicators_line(ind) -> str:
    from core.models import format_indicators

    return format_indicators(ind)


# ============================================================
# Таблицы уровней
# ============================================================


def _levels_table(levels: list[Level], current_price: float, is_reference: bool) -> str:
    """Строит таблицу уровней через tabulate."""
    if not levels:
        return "  (нет)\n"

    max_score = max((lv.strength_score or 0) for lv in levels)

    rows = []
    for lv in levels:
        pos = "↑" if lv.price > current_price else "↓"
        if is_reference:
            rows.append(
                [
                    f"{lv.price:.3f}",
                    lv.label or lv.type,
                    f"{(lv.distance_atr or 0):.2f}",
                    pos,
                ]
            )
        else:
            tfs = ",".join(sorted(lv.tf_source)) if lv.tf_source else ""
            tags = " ".join(lv.tags) if lv.tags else ""
            stars = _stars(lv.strength_score, max_score)
            rows.append(
                [
                    f"{lv.price:.5f}",
                    lv.weight,
                    lv.type,
                    tfs,
                    _fmt_ago(lv.last_seen),
                    f"{lv.strength_score:.1f}" if lv.strength_score else "",
                    stars,
                    tags,
                    pos,
                ]
            )

    if is_reference:
        headers = ["Цена", "Метка", "ΔATR", "Поз"]
        return tabulate(rows, headers=headers, tablefmt="rounded_outline")
    else:
        headers = ["Цена", "Вес", "Тип", "ТФ", "Живёт", "Score", "★", "Теги", "Поз"]
        return tabulate(rows, headers=headers, tablefmt="rounded_outline")


# ============================================================
# Таблица сигналов
# ============================================================


def _signals_table(signals: list[Signal]) -> str:
    if not signals:
        return "  Сигналов нет.\n"

    rows = []
    for s in signals:
        warn_count = len(s.warnings)
        warn_marker = f"⚠{warn_count}" if warn_count else ""

        rr = f"{s.risk_reward:.2f}" if s.risk_reward is not None else "—"
        net_rr = f"{s.net_rr:.2f}" if s.net_rr is not None else "—"

        rows.append(
            [
                s.direction.upper(),
                s.kind,
                s.strength,
                f"{s.strength_score:.1f}",
                f"{s.entry_price:.3f}",
                f"{s.stop_price:.3f}",
                f"{s.take_price:.3f}",
                rr,
                net_rr,
                warn_marker,
                ",".join(s.matched_criteria),
            ]
        )

    headers = [
        "Напр",
        "Тип",
        "Сила",
        "Score",
        "Вход",
        "Стоп",
        "Тейк",
        "R:R",
        "Net",
        "⚠",
        "Критерии",
    ]
    return tabulate(rows, headers=headers, tablefmt="rounded_outline")


def _signals_detail(signals: list[Signal]) -> str:
    if not signals:
        return ""
    lines = []
    for i, s in enumerate(signals, 1):
        lines.append(
            f"  [{i}] {s.direction.upper()} {s.kind} "
            f"({s.strength}, score={s.strength_score:.1f})"
        )
        for reason in s.reasons:
            lines.append(f"      • {reason}")
        if s.warnings:
            lines.append("      Предупреждения:")
            for w in s.warnings:
                lines.append(f"      ⚠ {w}")
    return "\n".join(lines) + "\n"


# ============================================================
# Главный рендер
# ============================================================


def render_console(result: AnalysisResult, width: int = 78) -> None:
    """Печатает дашборд в stdout."""
    print()
    print("═" * width)
    print(
        f"  {result.symbol} | {result.timestamp.strftime('%Y-%m-%d %H:%M')} "
        f"| Цена: {result.current_price:.3f}"
    )
    print("═" * width)

    # --- Индикаторы ---
    from core.models import format_indicators, format_trend_context

    print()
    print(format_indicators(result.indicators))
    print(format_trend_context(result.indicators))
    print(f"ATR(H1) = {result.atr:.5f}")

    # --- Сигналы (сверху — это самое важное) ---
    print()
    print("── СИГНАЛЫ " + "─" * (width - 11))
    print(_signals_table(result.signals))
    detail = _signals_detail(result.signals)
    if detail:
        print()
        print(detail)

    # --- Структурные уровни ---
    if result.levels:
        print("── Структурные уровни " + "─" * (width - 22))
        print(_levels_table(result.levels, result.current_price, is_reference=False))

    # --- Референсные уровни ---
    if result.references:
        print()
        print("── Референсные уровни " + "─" * (width - 22))
        print(_levels_table(result.references, result.current_price, is_reference=True))

    print()
    print("═" * width)


def render_console_to_string(result: AnalysisResult) -> str:
    """Возвращает тот же дашборд строкой."""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        render_console(result)
    return buf.getvalue()
