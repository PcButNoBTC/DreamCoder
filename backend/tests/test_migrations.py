import db
import migrations

def test_orchestration_migrations_are_versioned(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "m.db")
    monkeypatch.setattr(db, "_CANDIDATES", [tmp_path / "m.db"])
    db.init_db()
    status=migrations.status()
    assert status["current"] == migrations.CURRENT_VERSION
    conn=db.get_conn()
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"model_registry","model_benchmarks","projects","project_tasks"} <= tables
