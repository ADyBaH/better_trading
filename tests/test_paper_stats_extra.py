"""Тесты на новые группировки paper_stats: by_adx, by_session, by_hour, by_weekday."""

import sqlite3

import pytest

from trader.paper import init_paper_table
from trader.analytics import paper_stats


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
        result,
        created_at,
        adx_at_open=None,
        points=0.0,
        rub=0.0,
    ):
        conn.execute(
            """
            INSERT INTO paper_trades (
                signal_id, symbol, direction, kind, strength, strength_score,
                entry_price, stop_price, take_price,
                trend_at_open, adx_at_open, day_trend_at_open, structure_at_open,
                created_at, result, result_points, result_rub
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                "CNYRUBF",
                "short",
                "breakout",
                "medium",
                2.0,
                12.500,
                12.470,
                12.560,
                "down",
                adx_at_open,
                "bearish",
                "bearish",
                created_at,
                result,
                points,
                rub,
            ),
        )
        conn.commit()

    return _insert


class TestByAdx:
    def test_buckets(self, conn, insert_trade):
        insert_trade(
            conn, "a1", "win", "2026-10-23T10:00:00", adx_at_open=15.0, points=10, rub=8
        )
        insert_trade(
            conn,
            "a2",
            "loss",
            "2026-10-23T11:00:00",
            adx_at_open=15.0,
            points=-5,
            rub=-7,
        )
        insert_trade(
            conn,
            "a3",
            "win",
            "2026-10-23T12:00:00",
            adx_at_open=22.0,
            points=20,
            rub=18,
        )
        insert_trade(
            conn,
            "a4",
            "win",
            "2026-10-23T13:00:00",
            adx_at_open=30.0,
            points=30,
            rub=28,
        )
        insert_trade(
            conn,
            "a5",
            "loss",
            "2026-10-23T14:00:00",
            adx_at_open=35.0,
            points=-10,
            rub=-12,
        )
        insert_trade(
            conn, "a6", "win", "2026-10-23T15:00:00", adx_at_open=None, points=5, rub=3
        )

        s = paper_stats(conn)
        assert s["by_adx"]["flat (<20)"]["total"] == 2
        assert s["by_adx"]["flat (<20)"]["win"] == 1
        assert s["by_adx"]["flat (<20)"]["loss"] == 1
        assert s["by_adx"]["trend (20-25)"]["total"] == 1
        assert s["by_adx"]["strong (>25)"]["total"] == 2
        assert s["by_adx"]["strong (>25)"]["win"] == 1
        assert s["by_adx"]["strong (>25)"]["loss"] == 1
        assert s["by_adx"]["unknown"]["total"] == 1


class TestBySession:
    def test_buckets(self, conn, insert_trade):
        insert_trade(conn, "s1", "win", "2026-10-23T10:00:00", points=10, rub=8)
        insert_trade(conn, "s2", "win", "2026-10-23T14:00:00", points=20, rub=18)
        insert_trade(conn, "s3", "loss", "2026-10-23T18:00:00", points=-10, rub=-12)
        insert_trade(conn, "s4", "win", "2026-10-23T21:00:00", points=5, rub=3)

        s = paper_stats(conn)
        assert s["by_session"]["morning (09-12)"]["total"] == 1
        assert s["by_session"]["day (12-17)"]["total"] == 1
        assert s["by_session"]["evening (17-20)"]["total"] == 1
        assert s["by_session"]["night (20-09)"]["total"] == 1


class TestByHour:
    def test_buckets(self, conn, insert_trade):
        insert_trade(conn, "h1", "win", "2026-10-23T09:15:00", points=10, rub=8)
        insert_trade(conn, "h2", "win", "2026-10-23T09:45:00", points=5, rub=3)
        insert_trade(conn, "h3", "loss", "2026-10-23T17:30:00", points=-10, rub=-12)

        s = paper_stats(conn)
        assert s["by_hour"]["09:00"]["total"] == 2
        assert s["by_hour"]["09:00"]["win"] == 2
        assert s["by_hour"]["17:00"]["total"] == 1
        assert s["by_hour"]["17:00"]["loss"] == 1


class TestByWeekday:
    def test_buckets(self, conn, insert_trade):
        # 2026-10-19 — Monday, 2026-10-20 — Tuesday, 2026-10-21 — Wednesday
        insert_trade(conn, "w1", "win", "2026-10-19T10:00:00", points=10, rub=8)
        insert_trade(conn, "w2", "win", "2026-10-20T10:00:00", points=20, rub=18)
        insert_trade(conn, "w3", "win", "2026-10-21T10:00:00", points=30, rub=28)
        insert_trade(conn, "w4", "loss", "2026-10-21T14:00:00", points=-10, rub=-12)

        s = paper_stats(conn)
        assert s["by_weekday"]["Mon"]["total"] == 1
        assert s["by_weekday"]["Tue"]["total"] == 1
        assert s["by_weekday"]["Wed"]["total"] == 2
        assert s["by_weekday"]["Wed"]["win"] == 1
        assert s["by_weekday"]["Wed"]["loss"] == 1


class TestByDayRangeAtr:
    def test_buckets(self, conn, insert_trade):
        insert_trade(conn, "dr1", "win", "2026-10-23T10:00:00", points=10, rub=8)
        insert_trade(conn, "dr2", "loss", "2026-10-23T11:00:00", points=-5, rub=-7)
        # Обновить day_range_atr_at_open вручную
        conn.execute(
            "UPDATE paper_trades SET day_range_atr_at_open = 2.0 WHERE signal_id = 'dr1'"
        )
        conn.execute(
            "UPDATE paper_trades SET day_range_atr_at_open = 3.0 WHERE signal_id = 'dr2'"
        )
        conn.commit()

        s = paper_stats(conn)
        assert s["by_day_range_atr"]["<2.5 (низкая)"]["total"] == 1
        assert s["by_day_range_atr"]["2.5-3.33 (средняя)"]["total"] == 1
