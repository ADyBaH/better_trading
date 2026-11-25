"""Единый модуль для всех БД: schema_versions + миграции.

Используется:
- trader/paper_db.py (journal.db: paper_trades, paper_skipped)
- trader/journal.py (journal.db: trades, candles_history)
- data/storage_sqlite.py (market.db: candles)

Ключевая идея: schema_versions — таблица в каждой БД, хранит версию
для каждой таблицы отдельно (не общий user_version).
"""

import sqlite3
from typing import Callable

from core.logger import get_logger

log = get_logger(__name__)


# ============================================================
# schema_versions
# ============================================================


CREATE_SCHEMA_VERSIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_versions (
    table_name TEXT PRIMARY KEY,
    version INTEGER NOT NULL DEFAULT 0
);
"""


def init_schema_versions(conn: sqlite3.Connection) -> None:
    """Создаёт таблицу schema_versions (если нет)."""
    conn.executescript(CREATE_SCHEMA_VERSIONS_SQL)


def get_version(conn: sqlite3.Connection, table_name: str) -> int:
    """Возвращает текущую версию таблицы (0, если нет)."""
    row = conn.execute(
        "SELECT version FROM schema_versions WHERE table_name = ?",
        (table_name,),
    ).fetchone()
    return row[0] if row else 0


def set_version(conn: sqlite3.Connection, table_name: str, version: int) -> None:
    """Устанавливает версию таблицы."""
    conn.execute(
        """
        INSERT INTO schema_versions (table_name, version) VALUES (?, ?)
        ON CONFLICT(table_name) DO UPDATE SET version = excluded.version
        """,
        (table_name, version),
    )


# ============================================================
# Миграции
# ============================================================


def migrate(
    conn: sqlite3.Connection,
    table_name: str,
    migrations: list[tuple[int, Callable]],
) -> int:
    """
    Применяет миграции для таблицы.

    migrations — список (version, func). func(conn) делает ALTER/CREATE.
    Возвращает новую версию (последнюю применённую).
    """
    init_schema_versions(conn)
    current = get_version(conn, table_name)

    applied = 0
    for version, func in migrations:
        if version > current:
            try:
                func(conn)
                set_version(conn, table_name, version)
                applied += 1
            except Exception as e:
                log.error(
                    "migrate: table=%s version=%d упал: %s",
                    table_name,
                    version,
                    e,
                )
                conn.rollback()
                raise

    conn.commit()
    new_version = get_version(conn, table_name)
    log.info(
        "migrate: table=%s %d → %d (применено %d)",
        table_name,
        current,
        new_version,
        applied,
    )
    return new_version


# ============================================================
# Совместимость: user_version (для старых БД)
# ============================================================


def migrate_from_user_version(
    conn: sqlite3.Connection,
    table_name: str,
    migrations: list[tuple[int, Callable]],
    *,
    legacy_user_version: bool = True,
) -> int:
    """
    Мигрирует таблицу с учётом старого PRAGMA user_version.

    Если legacy_user_version=True и user_version > 0 и schema_versions
    ещё не содержит table_name — считаем, что все миграции до
    user_version уже применены (обратная совместимость).

    Это нужно для journal.db, где paper_trades уже имеет user_version=29.
    """
    init_schema_versions(conn)

    current = get_version(conn, table_name)

    if current == 0 and legacy_user_version:
        # Проверяем legacy user_version
        legacy = conn.execute("PRAGMA user_version").fetchone()[0]
        if legacy > 0:
            # Считаем, что все миграции до legacy уже применены
            # (но только для paper_trades, у которого была legacy-версия)
            if table_name == "paper_trades":
                set_version(conn, table_name, legacy)
                current = legacy
                log.info(
                    "migrate_from_user_version: table=%s legacy user_version=%d → schema_versions",
                    table_name,
                    legacy,
                )

    return migrate(conn, table_name, migrations)
