"""SQLite persistence for project index, suggestion history, and settings."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
# Prefer local data dir; fall back to /tmp if sandbox blocks writes
_CANDIDATES = [
    DATA_DIR / "dreamcoder.db",
    Path("/tmp/dreamcoder.db"),
]
DB_PATH = _CANDIDATES[0]


def get_conn() -> sqlite3.Connection:
    global DB_PATH
    last_err = None
    for path in _CANDIDATES:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("CREATE TABLE IF NOT EXISTS _ping(x INTEGER)")
            conn.commit()
            DB_PATH = path
            return conn
        except Exception as e:
            last_err = e
            continue
    # Last resort: pure in-memory
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    DB_PATH = Path(":memory:")
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
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
        """
    )
    conn.commit()
    conn.close()


# ---------- files / symbols ----------

def upsert_file(path: str, content: str, language: str = "python") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO files(path, content, language, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET content=excluded.content, "
        "language=excluded.language, updated_at=excluded.updated_at",
        (path, content, language, time.time()),
    )
    conn.execute("DELETE FROM symbols WHERE file=?", (path,))
    conn.commit()
    conn.close()


def delete_file(path: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM symbols WHERE file=?", (path,))
    conn.execute("DELETE FROM files WHERE path=?", (path,))
    conn.commit()
    conn.close()


def get_file(path: str) -> Optional[dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_files() -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT path, language, updated_at, length(content) AS size FROM files ORDER BY path"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_symbols(symbols: list[dict[str, Any]]) -> None:
    if not symbols:
        return
    conn = get_conn()
    conn.executemany(
        "INSERT INTO symbols(name, kind, file, line, signature) VALUES(?,?,?,?,?)",
        [(s["name"], s["kind"], s["file"], s["line"], s.get("signature", "")) for s in symbols],
    )
    conn.commit()
    conn.close()


def search_symbols(query: str, limit: int = 30) -> list[dict[str, Any]]:
    conn = get_conn()
    q = f"%{query}%"
    rows = conn.execute(
        "SELECT name, kind, file, line, signature FROM symbols "
        "WHERE name LIKE ? OR signature LIKE ? ORDER BY name LIMIT ?",
        (q, q, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def symbol_stats() -> dict[str, Any]:
    conn = get_conn()
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    symbols = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    kinds = conn.execute(
        "SELECT kind, COUNT(*) AS c FROM symbols GROUP BY kind"
    ).fetchall()
    conn.close()
    return {
        "files": files,
        "symbols": symbols,
        "by_kind": {r["kind"]: r["c"] for r in kinds},
    }


def all_symbol_names(limit: int = 50) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT kind, name FROM symbols LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [f"{r['kind']}:{r['name']}" for r in rows]


# ---------- history ----------

def add_history(kind: str, model: str, prompt: str, response: str, latency_ms: int) -> None:
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO history(kind, model, prompt, response, latency_ms, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (kind, model, prompt, response, latency_ms, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # never break the API for history logging


def recent_history(limit: int = 20) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- settings ----------

def set_setting(key: str, value: Any) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: Any = None) -> Any:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except Exception:
        return row["value"]
