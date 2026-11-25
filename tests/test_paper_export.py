"""Тест экспорта paper_trades в CSV."""

import csv
import sqlite3

import pytest

from trader.paper import init_paper_table
from trader.paper_export import export_paper_trades


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_paper_table(c)
    yield c
    c.close()


@pytest.fixture
def insert_trade():
    def _insert(conn, signal_id, **kwargs):
        defaults = {
            "symbol": "CNYRUBF",
            "direction": "short",
            "kind": "breakout",
            "strength": "medium",
            "strength_score": 2.0,
            "entry_price": 12.500,
            "stop_price": 12.470,
            "take_price": 12.560,
            "created_at": "2026-10-23T10:00:00",
            "result": "win",
            "result_points": 10.0,
            "result_rub": 8.0,
            "adx_at_open": 25.5,
        }
        defaults.update(kwargs)
        conn.execute(
            """INSERT INTO paper_trades (
                signal_id, symbol, direction, kind, strength, strength_score,
                entry_price, stop_price, take_price, created_at, result,
                result_points, result_rub, adx_at_open
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal_id,
                defaults["symbol"],
                defaults["direction"],
                defaults["kind"],
                defaults["strength"],
                defaults["strength_score"],
                defaults["entry_price"],
                defaults["stop_price"],
                defaults["take_price"],
                defaults["created_at"],
                defaults["result"],
                defaults["result_points"],
                defaults["result_rub"],
                defaults["adx_at_open"],
            ),
        )
        conn.commit()

    return _insert


class TestPaperExport:
    def test_empty_db(self, conn, tmp_path):
        tmp = tmp_path / "_test_empty.csv"
        count = export_paper_trades(conn, str(tmp))
        assert count == 0

    def test_two_trades(self, conn, insert_trade, tmp_path):
        insert_trade(conn, "e1")
        insert_trade(
            conn,
            "e2",
            kind="bounce",
            strength="weak",
            strength_score=1.5,
            entry_price=12.400,
            stop_price=12.430,
            take_price=12.360,
            result="loss",
            result_points=-5.0,
            result_rub=-7.0,
            adx_at_open=18.0,
        )
        tmp = tmp_path / "_test_2trades.csv"
        count = export_paper_trades(conn, str(tmp))
        assert count == 2
        assert tmp.exists()

        with open(tmp, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["symbol"] == "CNYRUBF"
        assert rows[0]["result"] == "win"
        assert rows[0]["adx_at_open"] == "25.5"
        assert rows[0]["result_rub"] == "8.0"

    def test_filter_by_symbol(self, conn, insert_trade, tmp_path):
        insert_trade(conn, "e1")
        tmp = tmp_path / "_test_filtered.csv"
        count = export_paper_trades(conn, str(tmp), symbol="SBER")
        assert count == 0
