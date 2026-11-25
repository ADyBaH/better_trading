"""
T-01: нет look-ahead в replay.

- analyze_from_df(df[:t]) не смотрит в df[t:].
- result.timestamp — из аргумента, не datetime.now().
"""

from datetime import datetime

import pandas as pd
import pytest

from core.analyzer import analyze_from_df
from strategy.signals import detect_signals


def _make_df(n=60, close=12.50):
    """Синтетические M15-свечи."""
    base = datetime(2026, 11, 13, 9, 0)
    return pd.DataFrame(
        {
            "begin": [base + pd.Timedelta(minutes=15 * i) for i in range(n)],
            "open": [close] * n,
            "high": [close + 0.01] * n,
            "low": [close - 0.01] * n,
            "close": [close] * n,
            "volume": [1000] * n,
        }
    )


def test_result_timestamp_from_argument():
    """
    result.timestamp == переданный timestamp, а не datetime.now().
    """
    df = _make_df()
    ts = datetime(2026, 11, 13, 10, 30)

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
    assert result.timestamp == ts, (
        f"result.timestamp={result.timestamp}, ожидалось {ts}. "
        f"Это look-ahead: replay использует datetime.now()."
    )


def test_no_future_in_signals():
    """
    analyze_from_df(df[:t]) не зависит от df[t:] — меняем будущее, сигналы те же.
    """
    df = _make_df(n=40)
    t = 30
    ts = datetime(2026, 11, 13, 9, 0) + pd.Timedelta(minutes=15 * t)

    df1 = df.copy()
    df2 = df.copy()
    # Меняем будущее (после t)
    df2.loc[t:, "close"] = 99.0
    df2.loc[t:, "high"] = 99.01
    df2.loc[t:, "low"] = 98.99

    r1 = analyze_from_df(
        df=df1.iloc[:t],
        df_h1=df1.iloc[:t],
        df_h4=df1.iloc[:t],
        df_atr=df1.iloc[:t],
        symbol="CNYRUBF",
        timeframe="M15",
        timestamp=ts,
        skip_age_check=True,
        write_history=False,
        skip_filters=True,
    )
    r2 = analyze_from_df(
        df=df2.iloc[:t],
        df_h1=df2.iloc[:t],
        df_h4=df2.iloc[:t],
        df_atr=df2.iloc[:t],
        symbol="CNYRUBF",
        timeframe="M15",
        timestamp=ts,
        skip_age_check=True,
        write_history=False,
        skip_filters=True,
    )

    assert r1 is not None and r2 is not None
    assert len(r1.signals) == len(r2.signals)
    for a, b in zip(r1.signals, r2.signals):
        assert a.direction == b.direction
        assert a.kind == b.kind
        assert a.entry_price == b.entry_price


def test_drop_unclosed_m15():
    """T-01b: незакрытая M15 отбрасывается."""
    from core.analyzer import _drop_unclosed

    base = datetime(2026, 11, 13, 9, 0)
    df = pd.DataFrame(
        {
            "begin": [
                base,
                base + pd.Timedelta(minutes=15),
                base + pd.Timedelta(minutes=30),
            ],
            "open": [12.5] * 3,
            "high": [12.51] * 3,
            "low": [12.49] * 3,
            "close": [12.5] * 3,
            "volume": [1000] * 3,
        }
    )
    # now = 9:20 → закрыты только 9:00 (9:00+15=9:15 <= 9:20)
    # 9:15 + 15 = 9:30 > 9:20 → не закрыта; 9:30 тоже
    now = base + pd.Timedelta(minutes=20)
    result = _drop_unclosed(df, "M15", now)
    assert len(result) == 1
    assert result["begin"].iloc[0] == base

    # now = 9:30 → закрыты 9:00 и 9:15
    now = base + pd.Timedelta(minutes=30)
    result = _drop_unclosed(df, "M15", now)
    assert len(result) == 2
