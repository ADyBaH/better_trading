"""
Проверка штрафов и блокировок за конфликты тренда.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from core.models import AnalysisResult, IndicatorSnapshot, Level
from strategy.signals import _build_warnings, detect_trend_level, detect_breakout


def _make_indicator(**kwargs) -> IndicatorSnapshot:
    """Фейковый IndicatorSnapshot с нужными полями."""
    defaults = dict(
        ema_fast=12.46,
        ema_slow=12.54,
        rsi=38.0,
        adx=55.0,
        trend="transition",
        adx_state="strong",
        rsi_state="near_oversold",
        day_trend="bullish",
        day_change_atr=4.1,
        structure="bullish",
        price_direction="up",
        vote_sum=2,
        vote_breakdown={"ema": -1, "day": 1, "structure": 1, "price_direction": 1},
    )
    defaults.update(kwargs)
    return IndicatorSnapshot(**defaults)


def test_warnings_conflict():
    print("\n=== Тест 1: warnings про конфликт ===")
    ind = _make_indicator()
    result = AnalysisResult(
        symbol="CNYRUBF",
        timestamp=datetime.now(),
        current_price=12.437,
        atr=0.024,
        timeframe="M15",
        indicators=ind,
        levels=[],
        references=[],
    )
    import pandas as pd

    df = pd.DataFrame(
        {"begin": [pd.Timestamp.now()], "open": [12.44], "close": [12.437]}
    )

    warnings = _build_warnings("short", result, None, None, df)
    print(f"  warnings: {len(warnings)}")
    for w in warnings:
        print(f"    {w}")

    has_day = any("День бычий" in w for w in warnings)
    has_struct = any("Структура бычья" in w for w in warnings)
    has_conflict = any("Конфликт" in w for w in warnings)
    has_transition = any("transition" in w for w in warnings)

    checks = [
        ("день бычий", has_day),
        ("структура бычья", has_struct),
        ("конфликт EMA/day", has_conflict),
        ("transition", has_transition),
    ]
    ok = True
    for name, c in checks:
        print(f"  {'✓' if c else '❌'} {name}")
        if not c:
            ok = False
    return ok


def test_trend_level_block():
    print("\n=== Тест 2: блокировка trend_level ===")
    ind = _make_indicator(trend="transition", day_trend="bullish")
    level = Level(price=12.437, type="mixed", weight=10, tf_source={"M15"})
    result = AnalysisResult(
        symbol="CNYRUBF",
        timestamp=datetime.now(),
        current_price=12.437,
        atr=0.024,
        timeframe="M15",
        indicators=ind,
        levels=[level],
        references=[],
    )
    import pandas as pd

    df = pd.DataFrame(
        {
            "begin": [pd.Timestamp.now()] * 30,
            "open": [12.45] * 30,
            "high": [12.46] * 30,
            "low": [12.44] * 30,
            "close": [12.437] * 30,
            "volume": [1000] * 30,
        }
    )

    signals = detect_trend_level(result, df)
    print(f"  Сигналов: {len(signals)} (ожидалось 0)")
    ok = len(signals) == 0
    print(f"  {'✓' if ok else '❌'} SHORT trend_level заблокирован")
    return ok


def main():
    print("=" * 60)
    print("Тест штрафов и блокировок тренда")
    print("=" * 60)

    results = [
        ("warnings", test_warnings_conflict()),
        ("trend_level block", test_trend_level_block()),
    ]
    print("\n" + "=" * 60)
    print("ИТОГ")
    print("=" * 60)
    all_ok = True
    for name, ok in results:
        print(f"  {'✓' if ok else '❌'} {name}")
        if not ok:
            all_ok = False
    print(f"\n{'✓ Все тесты прошли.' if all_ok else '❌ Есть провалы.'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
