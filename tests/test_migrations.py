from __future__ import annotations

import sqlite3

import pytest

from e_worker.storage.db import apply_migrations, get_connection


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = get_connection(tmp_path / "test.db")
    yield c
    c.close()


def test_apply_migrations_creates_tables(conn):
    applied = apply_migrations(conn)
    assert applied == [1, 2]
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"items", "time_entries", "schema_version"} <= tables


def test_apply_migrations_idempotent(conn):
    apply_migrations(conn)
    applied = apply_migrations(conn)
    assert applied == []
    versions = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
    assert [v[0] for v in versions] == [1, 2]


def test_rollback_on_bad_migration(tmp_path):
    conn = get_connection(tmp_path / "bad.db")
    bad_dir = tmp_path / "migrations"
    bad_dir.mkdir()
    (bad_dir / "010_ok.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);\n"
        "CREATE TABLE t_ok (id INTEGER PRIMARY KEY);", encoding="utf-8")
    (bad_dir / "020_bad.sql").write_text("CREATE TABEL t_bad (id INTEGER);", encoding="utf-8")
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, bad_dir)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "t_ok" not in tables
    assert "t_bad" not in tables
    assert "schema_version" not in tables
    conn.close()


def test_items_check_constraints(conn):
    apply_migrations(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO items (id, title, status, category, created_at, updated_at) "
            "VALUES ('x', 't', 'bogus', 'work', 'now', 'now')")
        conn.commit()


def test_time_entries_foreign_key(conn):
    apply_migrations(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO time_entries (id, item_id, date, duration_minutes, created_at) "
            "VALUES ('t1', 'missing', '2026-08-11', 30, 'now')")
        conn.commit()
