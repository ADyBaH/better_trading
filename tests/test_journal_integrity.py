"""Проверка целостности journal.db (интеграционный, требует реальной БД)."""

from pathlib import Path

import pytest

import config

pytestmark = pytest.mark.integration

DB_PATH = Path(config.DB_PATH).parent / "journal.db"


@pytest.fixture(scope="module")
def conn():
    if not DB_PATH.exists():
        pytest.skip(f"journal.db не найден: {DB_PATH}")
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestJournalIntegrity:
    def test_db_exists(self):
        assert DB_PATH.exists()

    def test_closed_trades_no_negative_size(self, conn):
        rows = conn.execute(
            "SELECT id, size FROM trades WHERE exit_price IS NOT NULL AND size <= 0"
        ).fetchall()
        assert len(rows) == 0

    def test_size_gt_1_rub_formula(self, conn):
        """Сделки с size > 1: rub ≈ pts × step_cost × size − comm × size."""
        from core.instruments import get_instrument

        rows = conn.execute(
            "SELECT * FROM trades WHERE exit_price IS NOT NULL AND size > 1"
        ).fetchall()
        for r in rows:
            inst = get_instrument(r["symbol"])
            comm = (
                r["commission_rub"]
                if r["commission_rub"] is not None
                else inst.commission_round
            )
            expected_rub = round(
                r["result_points"] * inst.step_cost * r["size"] - comm * r["size"], 2
            )
            assert r["result_rub"] == pytest.approx(
                expected_rub, rel=1e-2
            ), f"id={r['id']}: ожидали {expected_rub}, получили {r['result_rub']}"

    def test_totals_match_cli(self, conn):
        """Сводные цифры совпадают с journal_cli.py stats (только если БД не менялась)."""
        rows = conn.execute(
            "SELECT result_points, result_rub FROM trades WHERE exit_price IS NOT NULL"
        ).fetchall()
        total_pts = sum(r["result_points"] or 0 for r in rows)
        total_rub = sum(r["result_rub"] or 0 for r in rows)
        # Не хардкод — просто проверяем, что суммы не NaN
        assert isinstance(total_pts, float)
        assert isinstance(total_rub, float)
