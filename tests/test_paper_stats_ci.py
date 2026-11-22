"""T-13: by_score с bootstrap CI."""

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


def _insert(conn, score, result, points):
    conn.execute(
        """INSERT INTO paper_trades
           (signal_id, symbol, direction, kind, strength, strength_score,
            entry_price, stop_price, take_price, created_at, result, result_points)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"t-{score}-{result}-{points}",
            "CNYRUBF",
            "long",
            "bounce",
            "medium",
            score,
            12.5,
            12.47,
            12.56,
            "2026-11-22T10:00:00",
            result,
            points,
        ),
    )


class TestByScoreCI:
    def test_ci_for_bucket(self, conn):
        # 3.0+: 5 win, 2 loss → CI есть
        for p in (30, 40, 50, 60, 70):
            _insert(conn, 3.5, "win", p)
        for p in (-10, -20):
            _insert(conn, 3.5, "loss", p)
        conn.commit()
        s = paper_stats(conn)
        b = s["by_score"]["3.0+"]
        assert b["total"] == 7
        assert b["pf_ci"] is not None
        assert b["exp_ci"] is not None
        assert b["winrate_ci"] is not None
        # PF ~ (250 / 30) = 8.33 — CI широкий
        assert b["pf_ci"][0] <= 8.33 <= b["pf_ci"][1]

    def test_no_ci_for_small_bucket(self, conn):
        # 1.0: 2 win, 1 loss → CI None (n < 5)
        _insert(conn, 1.0, "win", 30)
        _insert(conn, 1.0, "win", 40)
        _insert(conn, 1.0, "loss", -10)
        conn.commit()
        s = paper_stats(conn)
        b = s["by_score"]["1.0"]
        assert b["total"] == 3
        assert b["pf_ci"] is None
        assert b["exp_ci"] is None
        assert b["winrate_ci"] is None
