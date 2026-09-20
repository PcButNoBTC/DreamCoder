"""Formal SQLite migrations for DreamCoder orchestration data."""
from __future__ import annotations
import sqlite3, time

CURRENT_VERSION = 4

MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS model_registry (
      id TEXT PRIMARY KEY, provider TEXT NOT NULL, name TEXT NOT NULL,
      revision TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'candidate',
      metadata_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL,
      last_benchmark_at REAL
    );
    CREATE TABLE IF NOT EXISTS model_benchmarks (
      id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT NOT NULL, benchmark_id TEXT NOT NULL,
      suite_version TEXT NOT NULL, run_id TEXT NOT NULL, category TEXT NOT NULL, role TEXT NOT NULL,
      pass INTEGER NOT NULL, score REAL NOT NULL, latency_ms REAL NOT NULL DEFAULT 0,
      evaluator_score REAL, execution_ok INTEGER, evidence_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_model_benchmarks_model ON model_benchmarks(model_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_model_benchmarks_role ON model_benchmarks(role, model_id, created_at);
    CREATE TABLE IF NOT EXISTS model_routing_profiles (
      model_id TEXT PRIMARY KEY, eligibility_json TEXT NOT NULL DEFAULT '{}',
      roles_json TEXT NOT NULL DEFAULT '{}', rationale TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL
    );
    """,
    2: """
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, goal TEXT NOT NULL DEFAULT '',
      prompt TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'created',
      risk_level TEXT NOT NULL DEFAULT 'normal', stack_json TEXT NOT NULL DEFAULT '{}',
      created_at REAL NOT NULL, updated_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS project_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
      event_type TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'system',
      model TEXT NOT NULL DEFAULT '', payload_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS project_documents (
      id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
      kind TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
      updated_at REAL NOT NULL, UNIQUE(project_id, kind, title)
    );
    CREATE TABLE IF NOT EXISTS project_artifacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
      kind TEXT NOT NULL, path TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS project_decisions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
      decision TEXT NOT NULL, rationale TEXT NOT NULL DEFAULT '',
      model TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_project_events_project ON project_events(project_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_project_docs_project ON project_documents(project_id);
    """,
    4: """
    ALTER TABLE model_benchmarks ADD COLUMN model_revision TEXT NOT NULL DEFAULT '';
    CREATE INDEX IF NOT EXISTS idx_model_benchmarks_revision ON model_benchmarks(model_id, model_revision, created_at);
    """,
    3: """
    CREATE TABLE IF NOT EXISTS project_tasks (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL, task_type TEXT NOT NULL,
      title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', role TEXT NOT NULL,
      model_id TEXT NOT NULL DEFAULT '', input_json TEXT NOT NULL DEFAULT '{}',
      output_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
      attempt INTEGER NOT NULL DEFAULT 0, depends_on_json TEXT NOT NULL DEFAULT '[]',
      created_at REAL NOT NULL, updated_at REAL NOT NULL, started_at REAL, completed_at REAL
    );
    CREATE INDEX IF NOT EXISTS idx_project_tasks_project ON project_tasks(project_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_project_tasks_status ON project_tasks(status, role);
    CREATE TABLE IF NOT EXISTS model_evaluations (
      id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT NOT NULL, evaluator_model TEXT NOT NULL,
      profile_json TEXT NOT NULL, summary TEXT NOT NULL, created_at REAL NOT NULL
    );
    """,
}

def apply(conn: sqlite3.Connection | None = None) -> int:
    own = conn is None
    if own:
        from db import get_conn
        conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)")
    current = int(conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
    for version in range(current + 1, CURRENT_VERSION + 1):
        conn.executescript(MIGRATIONS[version])
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?,?)", (version, time.time()))
        conn.commit()
    if own:
        conn.close()
    return CURRENT_VERSION

def status(conn: sqlite3.Connection | None = None) -> dict:
    own = conn is None
    if own:
        from db import get_conn
        conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)")
    rows = conn.execute("SELECT version, applied_at FROM schema_migrations ORDER BY version").fetchall()
    if own:
        conn.close()
    current = rows[-1][0] if rows else 0
    return {"current": current, "target": CURRENT_VERSION, "pending": max(0, CURRENT_VERSION-current),
            "applied": [{"version": r[0], "applied_at": r[1]} for r in rows]}
