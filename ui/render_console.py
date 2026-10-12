# ui/render_console.py
"""Консольный рендерер AnalysisResult."""

from core.models import AnalysisResult, Level

import config


def _stars(weight: int, max_weight: int) -> str:
    """Визуальная сила уровня по весу — 1..3 звезды."""
    if max_weight <= 0:
        return ""
    ratio = weight / max_weight
    if ratio >= 0.75:
        return "★★★"
    elif ratio >= 0.4:
        return "★★"
    else:
        return "★"


def _fmt_ago(dt) -> str:
    """'2ч назад' вместо полной даты."""
    from datetime import datetime

    if dt is None:
        return ""
    delta = datetime.now() - dt
    sec = int(delta.total_seconds())
    if sec < 3600:
        return f"{sec // 60}м"
    elif sec < 86400:
        return f"{sec // 3600}ч"
    else:
        return f"{sec // 86400}д"


def _render_indicator_state(ind) -> str:
    """Текстовая строка про индикаторы."""
    parts = []

    if ind.trend == "up":
        parts.append(f"Тренд: ВВЕРХ (EMA{config.EMA_FAST} > EMA{config.EMA_SLOW})")
    elif ind.trend == "down":
        parts.append(f"Тренд: ВНИЗ (EMA{config.EMA_FAST} < EMA{config.EMA_SLOW})")
    else:
        parts.append("Тренд: недостаточно данных")

    adx_map = {
        "strong": "сильный тренд",
        "trend": "тренд есть",
        "flat": "боковик",
        "none": "нет данных",
    }
    if ind.adx is not None:
        parts.append(f"ADX = {ind.adx:.1f} ({adx_map.get(ind.adx_state, '')})")
    else:
        parts.append("ADX: нет данных")

    rsi_map = {
        "overbought": "перекупленность",
        "oversold": "перепроданность",
        "near_overbought": "близко к перекупленности",
        "near_oversold": "близко к перепроданности",
        "neutral": "нейтрально",
        "none": "нет данных",
    }
    if ind.rsi is not None:
        parts.append(f"RSI = {ind.rsi:.1f} ({rsi_map.get(ind.rsi_state, '')})")
    else:
        parts.append("RSI: нет данных")

    return " | ".join(parts)


def _render_level_line(
    lv: Level, current_price: float, max_weight: int, is_reference: bool = False
) -> str:
    """Одна строка для уровня."""
    marker = "↑" if lv.price > current_price else "↓"

    if is_reference:
        label = lv.label or lv.type
        return f"  {lv.price:>8.3f}  {label:<10}  {marker}"

    stars = _stars(lv.weight, max_weight)
    ago = _fmt_ago(lv.last_seen)
    tfs = ",".join(sorted(lv.tf_source)) if lv.tf_source else ""
    tags = " ".join(lv.tags) if lv.tags else ""

    line = f"  {lv.price:>8.3f}  вес {lv.weight:>3}  {stars:<5}  {tfs:<8}  {ago:>4}"
    if tags:
        line += f"  {tags}"
    return line + f"  {marker}"


def render_console(result: AnalysisResult, width: int = 74) -> None:
    """Печатает дашборд в stdout."""
    print()
    print("═" * width)
    print(
        f"  {result.symbol} | {result.timestamp.strftime('%Y-%m-%d %H:%M')} "
        f"| Цена: {result.current_price:.3f}"
    )
    print("═" * width)

    # --- Индикаторы ---
    print()
    print(_render_indicator_state(result.indicators))
    print(f"ATR(H1) = {result.atr:.5f}")

    # --- Структурные уровни ---
    if result.levels:
        max_w = max(lv.weight for lv in result.levels)
        print()
        print("─ Структурные уровни " + "─" * (width - 22))
        for lv in result.levels:
            print(_render_level_line(lv, result.current_price, max_w))

    # --- Референсные уровни ---
    if result.references:
        print()
        print("─ Референсные уровни " + "─" * (width - 23))
        for r in result.references:
            print(_render_level_line(r, result.current_price, 1, is_reference=True))

    print()
    print("═" * width)


def render_console_legacy(result: AnalysisResult) -> None:
    """Старый подробный вывод — для отладки. Включается флагом --verbose."""
    render_console(result)
    # Тут можно добавить более детальный вывод: фракталы, веса и т.п.

import io
from contextlib import redirect_stdout


def render_console_to_string(result) -> str:
    """
    Возвращает тот же дашборд, что и render_console, но строкой.
    Использует redirect_stdout, чтобы не дублировать логику форматирования.
    """
    buf = io.StringIO()
    with redirect_stdout(buf):
        render_console(result)
    return buf.getvalue()