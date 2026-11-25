import sqlite3
import pytest
from datetime import datetime
from trader.paper_db import init_db, insert_trade, get_open_trades_by_symbol
import trader.paper_db as db


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()


def test_init_db(db_conn):
    # Проверяем, что таблица создалась
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='paper_trades'"
    )
    assert cursor.fetchone() is not None


def test_insert_and_fetch_trade(db_conn):
    # Тестовые данные
    data = {
        "signal_id": "test_sig_1",
        "symbol": "CNYRUBF",
        "direction": "long",
        "kind": "bounce",
        "entry_price": 12.500,
        "stop_price": 12.400,
        "take_price": 12.700,
        "created_at": datetime.now().isoformat(),
        "result": "open",
        "rsi_at_open": 45.0,
        "mfe_source": "live",
        "mae_source": "live",
    }

    # Проверяем вставку
    assert insert_trade(db_conn, data) is True

    # Проверяем получение
    rows = db.get_open_trades_by_symbol(db_conn, "CNYRUBF")
    assert len(rows) == 1
    assert rows[0]["signal_id"] == "test_sig_1"


def test_duplicate_signal_ignore(db_conn):
    data = {
        "signal_id": "unique_id",
        "symbol": "CNYRUBF",
        "direction": "long",
        "kind": "bounce",
        "entry_price": 12.500,
        "stop_price": 12.400,
        "take_price": 12.700,
        "created_at": datetime.now().isoformat(),
        "result": "open",
    }
    insert_trade(db_conn, data)
    # Повторная попытка вставки с тем же signal_id должна вернуть False (INSERT OR IGNORE)
    assert insert_trade(db_conn, data) is False


def test_migrations_idempotent(db_conn):
    # Первый вызов создает таблицу и применяет все миграции
    db.init_db(db_conn)

    # Второй вызов (идемпотентность) не должен ничего менять или падать
    try:
        db.init_db(db_conn)
    except Exception as e:
        pytest.fail(f"Idempotency test failed: {e}")


def test_migration_version_increment(db_conn):
    from trader.db import get_version
    from trader.paper_db import MIGRATIONS

    # Проверяем, что после init_db версия базы равна последней миграции (16)
    db.init_db(db_conn)
    # T-06: версия теперь в schema_versions, а не в PRAGMA user_version
    version = get_version(db_conn, "paper_trades")
    assert version == MIGRATIONS[-1][0]


def test_dynamic_columns_insert(db_conn):
    # Тестируем, что данные вставляются динамически по списку колонок БД
    # Добавляем только часть полей из тех, что есть в БД
    data = {
        "signal_id": "test_dyn",
        "symbol": "CNYRUBF",
        "direction": "long",
        "kind": "breakout",
        "entry_price": 10.0,
        "stop_price": 9.0,
        "take_price": 11.0,
        "created_at": datetime.now().isoformat(),
        "result": "open",
        # Мы специально не передаем другие колонки,
        # insert_trade должен корректно обработать только те, что есть в базе
    }
    assert db.insert_trade(db_conn, data) is True

    # Проверяем, что запись появилась
    rows = db.get_open_trades_by_symbol(db_conn, "CNYRUBF")
    assert len(rows) == 1
