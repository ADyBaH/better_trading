"""T-05: paper_skipped."""

import sqlite3

import pytest

from trader.paper_db import init_db, insert_skipped, get_skipped_stats


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


class TestInsert:
    def test_insert_one(self, conn):
        ok = insert_skipped(
            conn,
            {
                "signal_id": "abc",
                "symbol": "CNYRUBF",
                "direction": "long",
                "kind": "bounce",
                "entry_price": 12.5,
                "strength_score": 2.0,
                "reason": "filter:bullish_long",
                "context": None,
                "created_at": "2026-11-22T10:00:00",
            },
        )
        assert ok is True
        n = conn.execute("SELECT COUNT(*) FROM paper_skipped").fetchone()[0]
        assert n == 1


class TestStats:
    def test_empty(self, conn):
        s = get_skipped_stats(conn)
        assert s["total"] == 0
        assert s["by_reason"] == {}

    def test_by_reason(self, conn):
        for reason in ("filter:bullish_long", "filter:bullish_long", "data_age:20"):
            insert_skipped(
                conn,
                {
                    "signal_id": "x",
                    "symbol": "CNYRUBF",
                    "direction": "long",
                    "kind": "bounce",
                    "entry_price": 12.5,
                    "strength_score": 2.0,
                    "reason": reason,
                    "context": None,
                    "created_at": "2026-11-22T10:00:00",
                },
            )
        conn.commit()
        s = get_skipped_stats(conn)
        assert s["total"] == 3
        assert s["by_reason"]["filter:bullish_long"]["total"] == 2
        assert s["by_reason"]["filter:bullish_long"]["pct"] == 66.7
        assert s["by_reason"]["data_age:20"]["total"] == 1
