"""Тесты для virtual_pnl: end_of_day закрывает по close."""

import sys
from datetime import datetime, time
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.paper import virtual_pnl


def _df(begin_list, high, low, close):
    return pd.DataFrame(
        {
            "begin": [pd.Timestamp(b) for b in begin_list],
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": [1] * len(begin_list),
        }
    )


def test_end_of_day_closes_at_close():
    # 3 свечи: 18:45, 19:00, 19:15. end_of_day = 19:00.
    # stop/take не задеты — но 19:00 >= end_of_day → timeout по close.
    df = _df(
        ["2026-11-06T18:45", "2026-11-06T19:00", "2026-11-06T19:15"],
        high=[12.26, 12.27, 12.28],
        low=[12.24, 12.25, 12.26],
        close=[12.25, 12.26, 12.27],
    )
    pnl = virtual_pnl(
        df,
        "long",
        entry=12.25,
        stop=12.20,
        take=12.40,
        max_bars=100,
        end_of_day=time(19, 0),
    )
    assert pnl["result"] == "timeout"
    assert pnl["reason"] == "end_of_day"
    assert pnl["bars"] == 2  # 18:45 — нет, 19:00 — да
    assert pnl["exit_price"] == pytest.approx(12.26)


def test_end_of_day_does_not_override_take():
    # take задета ДО end_of_day — win, не timeout.
    df = _df(
        ["2026-11-06T18:45", "2026-11-06T19:00"],
        high=[12.45, 12.46],  # take 12.40 задета на 18:45
        low=[12.24, 12.25],
        close=[12.44, 12.45],
    )
    pnl = virtual_pnl(
        df,
        "long",
        entry=12.25,
        stop=12.20,
        take=12.40,
        max_bars=100,
        end_of_day=time(19, 0),
    )
    assert pnl["result"] == "win"
    assert pnl["reason"] == "take"
    assert pnl["bars"] == 1


def test_end_of_day_does_not_override_stop():
    # stop задета ДО end_of_day — loss, не timeout.
    df = _df(
        ["2026-11-06T18:45", "2026-11-06T19:00"],
        high=[12.26, 12.27],
        low=[12.18, 12.19],  # stop 12.20 пробит на 18:45
        close=[12.19, 12.20],
    )
    pnl = virtual_pnl(
        df,
        "long",
        entry=12.25,
        stop=12.20,
        take=12.40,
        max_bars=100,
        end_of_day=time(19, 0),
    )
    assert pnl["result"] == "loss"
    assert pnl["reason"] == "stop"
    assert pnl["bars"] == 1


def test_end_of_day_none_keeps_old_behavior():
    # Без end_of_day — старый timeout по max_bars.
    df = _df(
        ["2026-11-06T18:45", "2026-11-06T19:00", "2026-11-06T19:15"],
        high=[12.26, 12.27, 12.28],
        low=[12.24, 12.25, 12.26],
        close=[12.25, 12.26, 12.27],
    )
    pnl = virtual_pnl(
        df,
        "long",
        entry=12.25,
        stop=12.20,
        take=12.40,
        max_bars=3,
        end_of_day=None,
    )
    assert pnl["result"] == "timeout"
    assert pnl["reason"] == "max_bars"
    assert pnl["bars"] == 3


def test_end_of_day_max_bars_wins_if_earlier():
    # max_bars=1 < end_of_day — timeout по max_bars, не end_of_day.
    df = _df(
        ["2026-11-06T18:45", "2026-11-06T19:00", "2026-11-06T19:15"],
        high=[12.26, 12.27, 12.28],
        low=[12.24, 12.25, 12.26],
        close=[12.25, 12.26, 12.27],
    )
    pnl = virtual_pnl(
        df,
        "long",
        entry=12.25,
        stop=12.20,
        take=12.40,
        max_bars=1,
        end_of_day=time(19, 0),
    )
    assert pnl["result"] == "timeout"
    assert pnl["reason"] == "max_bars"
    assert pnl["bars"] == 1


def test_open_when_no_candles_after_end_of_day():
    # Все свечи ДО end_of_day, ни stop, ни take — open.
    df = _df(
        ["2026-11-06T10:00", "2026-11-06T10:15"],
        high=[12.26, 12.27],
        low=[12.24, 12.25],
        close=[12.25, 12.26],
    )
    pnl = virtual_pnl(
        df,
        "long",
        entry=12.25,
        stop=12.20,
        take=12.40,
        max_bars=100,
        end_of_day=time(19, 0),
    )
    assert pnl["result"] == "open"
    assert pnl["reason"] is None
