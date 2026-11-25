"""Интеграционный тест: save_signal_as_paper с реальным AnalysisResult.

Ловит баги, когда код берёт поле из IndicatorSnapshot, которого там нет
(например, day_range_atr_at_open — оно на Signal, не на IndicatorSnapshot).
"""

import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from core.analyzer import analyze_from_df
from trader.paper import init_paper_table, save_signal_as_paper


def _make_df(n=300, base=12.50):
    """Синтетические M15-свечи (n >= 250 для индикаторов)."""
    from datetime import timedelta

    rows = []
    start = datetime(2026, 11, 23, 9, 0)
    price = base
    for i in range(n):
        # Простой тренд + шум
        price += 0.0005 * (1 if i % 5 < 3 else -1)
        high = price + 0.01
        low = price - 0.01
        rows.append(
            {
                "begin": start + timedelta(minutes=15 * i),
                "open": price,
                "high": high,
                "low": low,
                "close": price,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_paper_table(c)
    yield c
    c.close()


def test_save_signal_with_real_analysis(conn):
    """save_signal_as_paper не падает с реальным AnalysisResult.

    Регрессионный тест: paper.py брал day_range_atr_at_open из
    result.indicators (IndicatorSnapshot), а поле — на Signal.

    Синтетические свечи не дают сигналов, поэтому создаём Signal вручную
    (но result — реальный AnalysisResult, не Mock).
    """
    df = _make_df(n=300)
    ts = df["begin"].iloc[-1].to_pydatetime()

    result = analyze_from_df(
        df=df,
        df_h1=df,
        df_h4=df,
        df_atr=df,
        symbol="CNYRUBF",
        timeframe="M15",
        timestamp=ts,
        skip_age_check=True,
        write_history=False,
        skip_filters=True,
    )
    assert result is not None

    # Реальный Signal (не Mock) — day_range_atr_at_open из _compute_stops
    from core.models import Signal
    from strategy.signals import _compute_stops

    entry = result.current_price
    stop, take, meta = _compute_stops(
        entry, "long", result.atr, result.indicators.day_range_atr
    )
    sig = Signal(
        direction="long",
        kind="bounce",
        strength="medium",
        strength_score=2.0,
        entry_price=entry,
        stop_price=stop,
        take_price=take,
        matched_criteria=["A1", "A2"],
        reasons=["test"],
        level_price=entry,
    )
    # _compute_stops возвращает meta с day_range_atr_at_open
    sig.take_source = meta["take_source"]
    sig.take_atr_value = meta["take_atr_value"]
    sig.day_range_atr_at_open = meta["day_range_atr_at_open"]
    sig.context = {}  # минимальный
    sig.warnings = []

    # ВАЖНО: result — реальный AnalysisResult (не Mock).
    # save_signal_as_paper берёт day_range_atr_at_open из sig (не из indicators).
    created = save_signal_as_paper(
        conn,
        [sig],
        result,
        source_analysis_path="test_real_analysis.json",
    )
    assert isinstance(created, int)
    assert created >= 1, "Сигнал должен создаться (нет дублей, лимит 1)"

    row = conn.execute("SELECT * FROM paper_trades ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    # Колонка есть (значение может быть None, если day_range_atr=0)
    assert "day_range_atr_at_open" in row.keys()
    # Проверить, что значение совпадает с meta (не AttributeError)
    if meta["day_range_atr_at_open"] is not None:
        assert row["day_range_atr_at_open"] == meta["day_range_atr_at_open"]


def test_day_range_atr_at_open_on_signal_not_indicators():
    """Документирует контракт: day_range_atr_at_open — на Signal, не на IndicatorSnapshot.

    Если кто-то добавит поле в IndicatorSnapshot — тест напомнит,
    что paper.py должен брать из sig.
    """
    from core.models import IndicatorSnapshot, Signal

    # Signal — поле есть
    assert hasattr(Signal, "__dataclass_fields__")
    assert "day_range_atr_at_open" in Signal.__dataclass_fields__

    # IndicatorSnapshot — поля НЕТ (это правильно, оно на Signal)
    assert hasattr(IndicatorSnapshot, "__dataclass_fields__")
    assert "day_range_atr_at_open" not in IndicatorSnapshot.__dataclass_fields__

    # В IndicatorSnapshot есть day_range_atr (без _at_open)
    assert "day_range_atr" in IndicatorSnapshot.__dataclass_fields__
