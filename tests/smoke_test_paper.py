import sqlite3
from datetime import datetime
from trader.paper_db import init_db
from trader.paper import save_signal_as_paper, paper_stats
from dataclasses import dataclass


# Заглушка для объекта сигнала (чтобы не импортировать всю стратегию)
@dataclass
class MockSignal:
    direction: str
    kind: str
    entry_price: float
    stop_price: float
    take_price: float
    strength: str
    strength_score: float
    level_price: float
    risk_reward: float
    net_rr: float
    take_source: str
    take_atr_value: float
    day_range_atr_at_open: float
    warnings: dict
    context: dict


def test_full_flow():
    conn = sqlite3.connect(":memory:")
    init_db(conn)

    # 1. Создаем фейковый результат анализа
    class MockResult:
        timestamp = datetime.now()
        symbol = "CNYRUBF"
        indicators = type(
            "obj",
            (object,),
            {
                "trend": "up",
                "adx": 25.0,
                "day_trend": "up",
                "structure": "bullish",
                "partial_day": False,
                "week_trend": "bullish",
                "market_state": "impulse",
                "rsi": 50.0,
                "volume_ratio": 1.0,
                "day_range_atr_at_open": 2.0,
            },
        )

    res = MockResult()
    sig = MockSignal(
        direction="long",
        kind="bounce",
        entry_price=12.0,
        stop_price=11.8,
        take_price=12.4,
        strength="strong",
        strength_score=3.0,
        level_price=12.0,
        risk_reward=2.0,
        net_rr=2.0,
        take_source="atr",
        take_atr_value=0.8,
        day_range_atr_at_open=2.0,
        warnings={},
        context={},
    )

    # 2. Сохраняем (тест записи)
    count = save_signal_as_paper(conn, [sig], res, market_price_at_open=12.0)
    assert count == 1
    print("✅ Запись в БД прошла успешно")

    # 3. Считаем статистику (тест чтения и группировки)
    stats = paper_stats(conn, known_only=True)
    assert stats["total"] == 1
    assert stats["by_kind"]["bounce"]["total"] == 1
    print("✅ Статистика рассчитана корректно")


if __name__ == "__main__":
    test_full_flow()
