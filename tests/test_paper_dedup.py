"""Проверка _is_duplicate и save_signal_as_paper."""

import json
import sqlite3
from datetime import datetime

import pytest

from core.models import Signal
from trader.paper import _is_duplicate, init_paper_table, save_signal_as_paper


@pytest.fixture
def conn():
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
            warnings=["тестовое предупреждение"],
            context={"test": True},
        )

    return _make


@pytest.fixture
def make_result():
    def _make(signals, timestamp, symbol="CNYRUBF", atr=0.025):
        class MockIndicator:
            trend = "up"
            adx = 25.0
            day_trend = "bullish"
            structure = "bullish"
            partial_day = False
            market_state = "normal"
            week_trend = "bearish"
            rsi = 50.0
            volume_ratio = 1.0
            day_range_atr_at_open = 2.0

        class MockResult:
            pass

        r = MockResult()
        r.symbol = symbol
        r.atr = atr
        r.timestamp = timestamp
        r.indicators = MockIndicator()
        r.signals = signals
        return r

    return _make


class TestSaveSignalAsPaper:
    def test_first_signal_created(self, conn, make_signal, make_result):
        ts = datetime(2026, 10, 17, 10, 0)
        sig = make_signal()
        created = save_signal_as_paper(
            conn, [sig], make_result([sig], ts), source_analysis_path="test1.json"
        )
        assert created == 1
        count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
        assert count == 1

    def test_echo_duplicate_by_time(self, conn, make_signal, make_result):
        ts1 = datetime(2026, 10, 17, 10, 0)
        save_signal_as_paper(conn, [make_signal()], make_result([make_signal()], ts1))
        # 10:05 — в пределах PAPER_DEDUP_MINUTES (5 мин)
        ts2 = datetime(2026, 10, 17, 10, 5)
        sig2 = make_signal()
        created = save_signal_as_paper(conn, [sig2], make_result([sig2], ts2))
        assert created == 0
        assert conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0] == 1

    def test_duplicate_by_price(self, conn, make_signal, make_result):
        ts1 = datetime(2026, 10, 17, 10, 0)
        save_signal_as_paper(conn, [make_signal()], make_result([make_signal()], ts1))
        # 10:20 — за пределами окна, но entry тот же (12.500)
        ts3 = datetime(2026, 10, 17, 10, 20)
        sig3 = make_signal()
        created = save_signal_as_paper(conn, [sig3], make_result([sig3], ts3))
        assert created == 0

    def test_new_signal_far_price(self, conn, make_signal, make_result):
        ts1 = datetime(2026, 10, 17, 10, 0)
        save_signal_as_paper(conn, [make_signal()], make_result([make_signal()], ts1))
        # закрываем первую, чтобы лимит 1 не мешал
        conn.execute("UPDATE paper_trades SET result = 'win' WHERE id = 1")
        conn.commit()
        ts4 = datetime(2026, 10, 17, 10, 25)
        sig4 = make_signal(entry=12.550)
        created = save_signal_as_paper(conn, [sig4], make_result([sig4], ts4))
        assert created == 1
        assert conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0] == 2

    def test_different_direction_not_dup(self, conn, make_signal, make_result):
        ts1 = datetime(2026, 10, 17, 10, 0)
        save_signal_as_paper(conn, [make_signal()], make_result([make_signal()], ts1))
        conn.execute("UPDATE paper_trades SET result = 'win' WHERE id = 1")
        conn.commit()
        ts6 = datetime(2026, 10, 17, 10, 30)
        sig6 = make_signal(direction="short")
        created = save_signal_as_paper(conn, [sig6], make_result([sig6], ts6))
        assert created == 1

    def test_different_kind_not_dup(self, conn, make_signal, make_result):
        ts1 = datetime(2026, 10, 17, 10, 0)
        save_signal_as_paper(conn, [make_signal()], make_result([make_signal()], ts1))
        conn.execute("UPDATE paper_trades SET result = 'win' WHERE id = 1")
        conn.commit()
        ts7 = datetime(2026, 10, 17, 10, 35)
        sig7 = make_signal(kind="breakout")
        created = save_signal_as_paper(conn, [sig7], make_result([sig7], ts7))
        assert created == 1

    def test_after_close_dup_allowed(self, conn, make_signal, make_result):
        ts1 = datetime(2026, 10, 17, 10, 0)
        save_signal_as_paper(conn, [make_signal()], make_result([make_signal()], ts1))
        conn.execute("UPDATE paper_trades SET result = 'win' WHERE id = 1")
        conn.commit()
        ts8 = datetime(2026, 10, 17, 10, 40)
        sig8 = make_signal()
        created = save_signal_as_paper(conn, [sig8], make_result([sig8], ts8))
        assert created == 1


class TestIsDuplicate:
    def test_just_created_is_dup(self, conn, make_signal, make_result):
        ts = datetime(2026, 10, 17, 10, 0)
        sig = make_signal()
        save_signal_as_paper(conn, [sig], make_result([sig], ts))
        dup = _is_duplicate(conn, sig, "CNYRUBF", atr=0.025, now=ts)
        assert dup is True


class TestContextWarnings:
    def test_context_and_warnings_saved_as_json(self, conn, make_signal, make_result):
        ts = datetime(2026, 10, 17, 10, 0)
        sig = make_signal()
        save_signal_as_paper(conn, [sig], make_result([sig], ts))
        row = conn.execute(
            "SELECT warnings, context FROM paper_trades WHERE id = 1"
        ).fetchone()
        w = json.loads(row["warnings"])
        c = json.loads(row["context"])
        assert isinstance(w, list)
        assert w[0] == "тестовое предупреждение"
        assert isinstance(c, dict)
        assert c["test"] is True
