import pytest
import pandas as pd
import numpy as np
from trader.paper import virtual_pnl


def test_virtual_pnl_win():
    # Создаем мок данных для выигрышной сделки
    data = {
        "high": [10.1, 10.2, 10.3],
        "low": [9.9, 9.8, 9.7],
        "close": [10.1, 10.2, 10.3],
        "begin": pd.to_datetime(
            ["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 00:10"]
        ),
    }
    df = pd.DataFrame(data)

    # Тейк 10.3, Стоп 9.5
    res = virtual_pnl(
        df, direction="long", entry=10.0, stop=9.5, take=10.3, price_step=0.001
    )
    assert res["result"] == "win"
    assert res["exit_price"] == 10.3


def test_virtual_pnl_loss():
    data = {
        "high": [9.9, 9.8, 9.7],
        "low": [9.0, 9.1, 9.2],
        "close": [9.9, 9.8, 9.7],
        "begin": pd.to_datetime(
            ["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 00:10"]
        ),
    }
    df = pd.DataFrame(data)

    # Тейк 11.0, Стоп 9.5
    res = virtual_pnl(
        df, direction="long", entry=10.0, stop=9.5, take=11.0, price_step=0.001
    )
    assert res["result"] == "loss"
    assert res["exit_price"] == 9.5
