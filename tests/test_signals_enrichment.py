"""
Мок-тест обогащения сигналов: context, warnings, risk_reward, net_rr.
Не требует сети — использует фейковые данные.
"""

import sys
from datetime import datetime
from pathlib import Path

# Чтобы можно было запускать из корня: python tests/test_signals_enrichment.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from core.models import AnalysisResult, IndicatorSnapshot, Level, Signal
from strategy.signals import (
    _build_context,
    _build_warnings,
    _finalize_signal,
    _commission_in_price,
)


def _make_fake_df() -> pd.DataFrame:
    """Минимальный DataFrame свечей — 30 штук."""
    rows = []
    for i in range(30):
        price = 12.500 + i * 0.001
        rows.append(
            {
                "begin": pd.Timestamp("2026-10-14 09:00") + pd.Timedelta(minutes=i * 5),
                "open": price,
                "high": price + 0.003,
                "low": price - 0.003,
                "close": price + 0.001,
                "volume": 5000 + i * 100,
            }
        )
    return pd.DataFrame(rows)


def _make_fake_result() -> AnalysisResult:
    """Фейковый AnalysisResult с одним сигналом и парой уровней."""
    indicators = IndicatorSnapshot(
        ema_fast=12.53716,
        ema_slow=12.54258,
        rsi=36.27,
        adx=14.44,
        trend="down",
        adx_state="flat",
        rsi_state="near_oversold",
    )

    # Уровень-поддержка, от которого как будто отбой
    level = Level(
        price=12.500,
        type="mixed",
        weight=16,
        tf_source={"H1", "M15"},
        confirmed=True,
        first_seen=datetime(2026, 9, 15, 12, 0),
        last_seen=datetime(2026, 10, 13, 8, 15),
        tags=["+ 12.500"],
    )
    level.distance_atr = 0.28
    level.strength_score = 41.6
    level.age_days = 1.0

    return AnalysisResult(
        symbol="CNYRUBF",
        timestamp=datetime.now(),
        current_price=12.510,
        atr=0.0281,
        timeframe="M5",
        indicators=indicators,
        levels=[level],
        references=[],
        signals=[],
    )


def test_context():
    print("\n=== Тест 1: context ===")
    df = _make_fake_df()
    result = _make_fake_result()
    level = result.levels[0]

    ctx = _build_context(result, df, level, recent_signal=None)

    expected_keys = {
        "adx",
        "adx_state",
        "rsi",
        "rsi_state",
        "trend",
        "ema_alignment",
        "price_vs_ema_fast",
        "price_vs_ema_slow",
        "atr",
        "atr_percentile",
        "volatility_state",
        "level_price",
        "level_type",
        "level_strength_score",
        "level_tags",
        "distance_to_level_atr",
        "recent_signal_direction",
        "recent_signal_age_min",
        "session",
        "hour_utc",
    }
    actual_keys = set(ctx.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        print(f"  ❌ Отсутствуют ключи: {missing}")
        return False
    if extra:
        print(f"  ⚠ Лишние ключи: {extra}")

    print(f"  ✓ Все {len(expected_keys)} полей на месте")
    print(f"  adx_state = {ctx['adx_state']}")
    print(f"  rsi_state = {ctx['rsi_state']}")
    print(f"  ema_alignment = {ctx['ema_alignment']}")
    print(f"  session = {ctx['session']}, hour_utc = {ctx['hour_utc']}")
    print(f"  level_tags = {ctx['level_tags']}")
    print(f"  distance_to_level_atr = {ctx['distance_to_level_atr']}")
    return True


def test_warnings():
    print("\n=== Тест 2: warnings ===")
    df = _make_fake_df()
    result = _make_fake_result()
    level = result.levels[0]

    # Сценарий: SHORT при тренде down, RSI 36 (near_oversold), уровень сильный
    warnings = _build_warnings("short", result, level, recent_signal=None)

    print(f"  Всего warnings: {len(warnings)}")
    for w in warnings:
        print(f"    ⚠ {w}")

    # Ожидаемые срабатывания:
    # - ADX 14.44 < 20 → "ADX flat"
    # - RSI 36.27 < 40 → "near_oversold"
    # - level_strength_score 41.6 > 40 → "Уровень сильный"
    # - level.tags → "Совпадение референсов"
    checks = [
        ("ADX flat", any("ADX" in w and "flat" in w for w in warnings)),
        (
            "RSI near_oversold",
            any("RSI" in w and "near_oversold" in w for w in warnings),
        ),
        ("Уровень сильный", any("Уровень сильный" in w for w in warnings)),
        ("Совпадение референсов", any("Совпадение" in w for w in warnings)),
    ]

    all_ok = True
    for name, ok in checks:
        mark = "✓" if ok else "❌"
        print(f"  {mark} {name}")
        if not ok:
            all_ok = False
    return all_ok


def test_cooldown_warning():
    print("\n=== Тест 3: cooldown warning ===")
    df = _make_fake_df()
    result = _make_fake_result()
    level = result.levels[0]

    recent = {"direction": "long", "kind": "bounce", "age_min": 98}

    # SHORT при недавнем LONG — должно быть предупреждение
    warnings = _build_warnings("short", result, level, recent_signal=recent)
    has_cooldown = any("мин назад был LONG" in w for w in warnings)

    if has_cooldown:
        print("  ✓ Cooldown-предупреждение есть")
    else:
        print("  ❌ Cooldown-предупреждение не сработало")

    # Тот же direction — не должно быть
    warnings2 = _build_warnings("long", result, level, recent_signal=recent)
    has_wrong_cooldown = any("мин назад был LONG" in w for w in warnings2)
    if not has_wrong_cooldown:
        print("  ✓ При совпадении direction — нет ложного предупреждения")
    else:
        print("  ❌ Ложное предупреждение при совпадении direction")

    return has_cooldown and not has_wrong_cooldown


def test_rr():
    print("\n=== Тест 4: risk_reward и net_rr ===")
    signal = Signal(
        direction="short",
        kind="bounce",
        strength="weak",
        strength_score=1.0,
        entry_price=12.510,
        stop_price=12.540,  # риск 30 пунктов
        take_price=12.450,  # цель 60 пунктов
        level_price=12.500,
    )
    commission_price = _commission_in_price("CNYRUBF")

    # Ожидаемое: gross R:R = 60/30 = 2.0
    # commission: 2.06 ₽ / 1.0 (step_cost) = 2.06 пунктов = 0.00206 в цене
    # net_risk = 30 + 2.06 = 32.06 пунктов → 0.03206
    # net_reward = 60 - 2.06 = 57.94 пунктов → 0.05794
    # net_rr = 57.94 / 32.06 ≈ 1.81

    signal.compute_rr(commission_round=commission_price)

    print(
        f"  Вход: {signal.entry_price:.3f}, Стоп: {signal.stop_price:.3f}, Тейк: {signal.take_price:.3f}"
    )
    print(f"  Комиссия в цене: {commission_price:.5f}")
    print(f"  risk_reward (gross) = {signal.risk_reward}")
    print(f"  net_rr (с комиссией) = {signal.net_rr}")

    ok_gross = signal.risk_reward is not None and abs(signal.risk_reward - 2.0) < 0.01
    ok_net = signal.net_rr is not None and 1.75 < signal.net_rr < 1.90

    print(f"  {'✓' if ok_gross else '❌'} gross R:R ≈ 2.0")
    print(f"  {'✓' if ok_net else '❌'} net R:R в диапазоне 1.75–1.90")
    return ok_gross and ok_net


def test_finalize():
    print("\n=== Тест 5: _finalize_signal ===")
    df = _make_fake_df()
    result = _make_fake_result()
    level = result.levels[0]

    signal = Signal(
        direction="short",
        kind="bounce",
        strength="weak",
        strength_score=1.0,
        entry_price=12.510,
        stop_price=12.540,
        take_price=12.450,
        level_price=12.500,
    )

    _finalize_signal(signal, result, df, level, recent_signal=None, symbol="CNYRUBF")

    checks = [
        ("context заполнен", bool(signal.context) and len(signal.context) >= 15),
        ("warnings заполнены", len(signal.warnings) > 0),
        ("risk_reward посчитан", signal.risk_reward is not None),
        ("net_rr посчитан", signal.net_rr is not None),
    ]

    all_ok = True
    for name, ok in checks:
        mark = "✓" if ok else "❌"
        print(f"  {mark} {name}")
        if not ok:
            all_ok = False
    return all_ok


def main():
    print("=" * 60)
    print("Мок-тест обогащения сигналов (Шаг 1)")
    print("=" * 60)

    results = []
    results.append(("context", test_context()))
    results.append(("warnings", test_warnings()))
    results.append(("cooldown", test_cooldown_warning()))
    results.append(("R:R", test_rr()))
    results.append(("finalize", test_finalize()))

    print("\n" + "=" * 60)
    print("ИТОГ")
    print("=" * 60)
    all_ok = True
    for name, ok in results:
        mark = "✓" if ok else "❌"
        print(f"  {mark} {name}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n✓ Все тесты прошли.")
        return 0
    else:
        print("\n❌ Есть провалы — смотри выше.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
