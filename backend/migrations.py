"""Small, explicit SQLite migration runner with reversible schema changes."""
from __future__ import annotations

import time
from typing import Callable

Migration = tuple[int, str, Callable[[object], None], Callable[[object], None]]


def _v1(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        language TEXT DEFAULT 'python',
        updated_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS symbols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        file TEXT NOT NULL,
        line INTEGER NOT NULL,
        signature TEXT DEFAULT '',
        FOREIGN KEY(file) REFERENCES files(path) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
    CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        model TEXT,
        prompt TEXT,
        response TEXT,
        latency_ms INTEGER,
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)


def _down_v1(conn):
    conn.executescript("""
    DROP TABLE IF EXISTS symbols;
    DROP TABLE IF EXISTS files;
    DROP TABLE IF EXISTS history;
    DROP TABLE IF EXISTS settings;
    """)


def _v2(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_updated_at ON files(updated_at)")


def _down_v2(conn):
    conn.execute("DROP INDEX IF EXISTS idx_history_created_at")
    conn.execute("DROP INDEX IF EXISTS idx_files_updated_at")


MIGRATIONS: list[Migration] = [
    (1, "baseline schema", _v1, _down_v1),
    (2, "query indexes", _v2, _down_v2),
]


def _ensure_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL DEFAULT '', applied_at REAL NOT NULL)"
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(schema_migrations)").fetchall()}
    if "name" not in columns:
        conn.execute("ALTER TABLE schema_migrations ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if "applied_at" not in columns:
        conn.execute("ALTER TABLE schema_migrations ADD COLUMN applied_at REAL NOT NULL DEFAULT 0")


def current_version(conn) -> int:
    _ensure_table(conn)
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0])


def apply(conn, target: int | None = None) -> int:
    _ensure_table(conn)
    current = current_version(conn)
    wanted = max((m[0] for m in MIGRATIONS), default=0) if target is None else target
    if wanted < 0 or wanted > (MIGRATIONS[-1][0] if MIGRATIONS else 0):
        raise ValueError("invalid migration target")
    for version, name, up, _down in MIGRATIONS:
        if current < version <= wanted:
            up(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                (version, name, time.time()),
            )
            current = version
    conn.commit()
    return current


def rollback_to(conn, target: int) -> int:
    if target < 0:
        raise ValueError("invalid migration target")
    _ensure_table(conn)
    current = current_version(conn)
    for version, name, _up, down in reversed(MIGRATIONS):
        if target < version <= current:
            down(conn)
            conn.execute("DELETE FROM schema_migrations WHERE version=?", (version,))
            current = version - 1
    conn.commit()
    return current


def status(conn) -> dict:
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT version,name,applied_at FROM schema_migrations ORDER BY version"
    ).fetchall()
    applied = {int(r[0]): {"name": r[1], "applied_at": r[2]} for r in rows}
    latest = MIGRATIONS[-1][0] if MIGRATIONS else 0
    return {
        "current": current_version(conn),
        "latest": latest,
        "up_to_date": current_version(conn) == latest,
        "applied": applied,
    }
