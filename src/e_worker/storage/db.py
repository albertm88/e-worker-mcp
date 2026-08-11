from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from e_worker.models import utc_now_iso

logger = logging.getLogger("e_worker.db")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    try:
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        return {int(r["version"]) for r in rows}
    except sqlite3.OperationalError:
        return set()


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Path | None = None) -> list[int]:
    migrations_dir = migrations_dir or MIGRATIONS_DIR
    applied = _applied_versions(conn)
    pending: list[tuple[int, Path]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        version = int(path.stem.split("_", 1)[0])
        if version not in applied:
            pending.append((version, path))
    if not pending:
        logger.info("migrations: none pending (schema_version=%s)", sorted(applied))
        return []

    conn.execute("BEGIN")
    try:
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, utc_now_iso()),
            )
            logger.info("migrations: applied %s (v%s)", path.name, version)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error("migrations: rollback after failure in %s", pending[-1][1].name if pending else "?")
        raise
    return [v for v, _ in pending]
