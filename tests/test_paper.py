"""Проверка trader.paper — базовая инфраструктура."""

import sqlite3
from datetime import datetime

import pytest

from core.models import Signal
from trader.paper import _is_in_paper_hours, _signal_id, init_paper_table

# ============================================================
# Фикстуры
# ============================================================


@pytest.fixture
def conn():
    """In-memory БД с инициализированной paper_trades."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_paper_table(c)
    yield c
    c.close()


@pytest.fixture
def make_signal():
    def _make(direction="long", kind="bounce", entry=12.500):
        return Signal(
            direction=direction,
            kind=kind,
            strength="medium",
            strength_score=2.0,
            entry_price=entry,
            stop_price=entry - 0.03 if direction == "long" else entry + 0.03,
            take_price=entry + 0.06 if direction == "long" else entry - 0.06,
            matched_criteria=["A1", "A2"],
            reasons=[],
            level_price=entry - 0.001 if direction == "long" else entry + 0.001,
        )

    return _make


# ============================================================
# init_paper_table
# ============================================================


class TestInitPaperTable:
    def test_table_created(self, conn):
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        assert "paper_trades" in tables

    def test_required_columns(self, conn):
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(paper_trades)")}
        required = {
            "id",
            "signal_id",
            "source_analysis_path",
            "symbol",
            "direction",
            "kind",
            "strength",
            "strength_score",
            "entry_price",
            "stop_price",
            "take_price",
            "level_price",
            "risk_reward",
            "net_rr",
            "trend_at_open",
            "adx_at_open",
            "day_trend_at_open",
            "structure_at_open",
            "created_at",
            "closed_at",
            "exit_price",
            "result",
            "result_points",
            "result_rub",
            "bars_to_close",
            "resolution_confidence",
            "warnings",
            "context",
        }
        assert required.issubset(cols)

    def test_idempotent(self, conn):
        # Повторный вызов не падает
        init_paper_table(conn)
        assert True


# ============================================================
# _signal_id
# ============================================================


class TestSignalId:
    def test_length_16(self, make_signal):
        sid = _signal_id(make_signal(), "CNYRUBF", datetime(2026, 10, 17, 10, 0))
        assert len(sid) == 16

    def test_hex_only(self, make_signal):
        sid = _signal_id(make_signal(), "CNYRUBF", datetime(2026, 10, 17, 10, 0))
        assert all(c in "0123456789abcdef" for c in sid)

    def test_deterministic(self, make_signal):
        ts = datetime(2026, 10, 17, 10, 0)
        sid1 = _signal_id(make_signal(), "CNYRUBF", ts)
        sid2 = _signal_id(make_signal(), "CNYRUBF", ts)
        assert sid1 == sid2

    def test_different_entry_different_id(self, make_signal):
        ts = datetime(2026, 10, 17, 10, 0)
        sid1 = _signal_id(make_signal(entry=12.500), "CNYRUBF", ts)
        sid2 = _signal_id(make_signal(entry=12.510), "CNYRUBF", ts)
        assert sid1 != sid2

    def test_different_time_different_id(self, make_signal):
        sig = make_signal()
        sid1 = _signal_id(sig, "CNYRUBF", datetime(2026, 10, 17, 10, 0))
        sid2 = _signal_id(sig, "CNYRUBF", datetime(2026, 10, 17, 10, 15))
        assert sid1 != sid2


# ============================================================
# _is_in_paper_hours
# ============================================================


class TestIsInPaperHours:
    @pytest.mark.parametrize(
        "hour, minute, expected",
        [
            (10, 0, True),
            (9, 0, True),
            (17, 59, True),
            (8, 59, False),
            (18, 0, False),
            (3, 0, False),
        ],
    )
    def test_hours(self, hour, minute, expected):
        dt = datetime(2026, 10, 17, hour, minute)
        assert _is_in_paper_hours(dt) == expected
