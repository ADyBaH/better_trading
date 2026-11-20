"""Проверка paper_stats."""

import sqlite3

import pytest

from trader.paper import init_paper_table, paper_stats


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_paper_table(c)
    yield c
    c.close()


@pytest.fixture
def insert_trade():
    def _insert(
        conn,
        signal_id,
        direction="long",
        kind="bounce",
        score=2.0,
        trend="up",
        day_trend="bullish",
        result="win",
        points=30.0,
        rub=27.94,
        created_at="2026-10-17T10:00:00",
        symbol="CNYRUBF",
        entry_price=12.500,
        stop_price=12.470,
        take_price=12.560,
    ):
        conn.execute(
            """
            INSERT INTO paper_trades (
                signal_id, symbol, direction, kind, strength, strength_score,
                entry_price, stop_price, take_price,
                trend_at_open, day_trend_at_open, structure_at_open,
                created_at, result, result_points, result_rub
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                symbol,
                direction,
                kind,
                "medium",
                score,
                entry_price,
                stop_price,
                take_price,
                trend,
                day_trend,
                "bullish",
                created_at,
                result,
                points,
                rub,
            ),
        )

    return _insert


class TestPaperStats:
    def test_empty_db(self, conn):
        s = paper_stats(conn)
        assert s["total"] == 0
        assert s["winrate"] is None
        assert s["total_points"] == 0.0

    def test_win_loss_open(self, conn, insert_trade):
        insert_trade(conn, "s1", result="win", points=30.0, rub=27.94)
        insert_trade(conn, "s2", result="loss", points=-20.0, rub=-22.06)
        insert_trade(conn, "s3", result="open", points=None, rub=None)
        conn.commit()
        s = paper_stats(conn)
        assert s["total"] == 3
        assert s["open"] == 1
        assert s["win"] == 1
        assert s["loss"] == 1
        assert s["winrate"] == 50.0
        assert s["total_points"] == 10.0
        assert s["total_rub"] == 5.88
        assert s["avg_win_points"] == 30.0
        assert s["avg_loss_points"] == -20.0

    def test_winrate_no_timeout(self, conn, insert_trade):
        insert_trade(conn, "t1", result="win", points=30.0, rub=27.94)
        insert_trade(conn, "t2", result="loss", points=-20.0, rub=-22.06)
        insert_trade(conn, "t3", result="timeout", points=5.0, rub=2.94)
        conn.commit()
        s = paper_stats(conn)
        assert s["total"] == 3
        assert s["winrate"] == 50.0
        assert s["timeout"] == 1
        assert s["total_points"] == 15.0

    def test_by_kind(self, conn, insert_trade):
        insert_trade(conn, "k1", kind="breakout", result="win", points=30.0, rub=27.94)
        insert_trade(conn, "k2", kind="breakout", result="win", points=40.0, rub=37.94)
        insert_trade(
            conn, "k3", kind="breakout", result="loss", points=-20.0, rub=-22.06
        )
        insert_trade(
            conn, "k4", kind="trend_level", result="loss", points=-15.0, rub=-17.06
        )
        conn.commit()
        s = paper_stats(conn)
        assert s["by_kind"]["breakout"]["total"] == 3
        assert s["by_kind"]["breakout"]["win"] == 2
        assert s["by_kind"]["breakout"]["loss"] == 1
        assert s["by_kind"]["breakout"]["points"] == 50.0
        assert s["by_kind"]["trend_level"]["total"] == 1

    def test_by_score(self, conn, insert_trade):
        insert_trade(conn, "sc1", score=1.0, result="win", points=10.0, rub=7.94)
        insert_trade(conn, "sc2", score=1.5, result="loss", points=-10.0, rub=-12.06)
        insert_trade(conn, "sc3", score=2.0, result="win", points=20.0, rub=17.94)
        insert_trade(conn, "sc4", score=2.5, result="win", points=25.0, rub=22.94)
        insert_trade(conn, "sc5", score=3.0, result="loss", points=-30.0, rub=-32.06)
        insert_trade(conn, "sc6", score=3.5, result="win", points=35.0, rub=32.94)
        conn.commit()
        s = paper_stats(conn)
        assert s["by_score"]["1.0"]["total"] == 1
        assert s["by_score"]["1.5"]["total"] == 1
        assert s["by_score"]["2.0"]["total"] == 1
        assert s["by_score"]["2.5"]["total"] == 1
        assert s["by_score"]["3.0+"]["total"] == 2

    def test_filter_by_symbol(self, conn, insert_trade):
        insert_trade(conn, "sym1", result="win")
        insert_trade(conn, "sym2", symbol="SBER", result="win", points=20.0, rub=18.0)
        conn.commit()
        s_all = paper_stats(conn)
        s_cny = paper_stats(conn, symbol="CNYRUBF")
        assert s_all["total"] == 2
        assert s_cny["total"] == 1

    def test_filter_by_since(self, conn, insert_trade):
        insert_trade(conn, "d1", created_at="2026-10-16T10:00:00", result="win")
        insert_trade(conn, "d2", created_at="2026-10-17T10:00:00", result="win")
        conn.commit()
        s = paper_stats(conn, since="2026-10-17")
        assert s["total"] == 1
