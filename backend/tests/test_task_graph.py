import db, task_graph
def test_task_graph_assignments(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "graph.db")
    monkeypatch.setattr(db, "_CANDIDATES", [tmp_path / "graph.db"])
    db.init_db()
    conn=db.get_conn(); conn.execute("INSERT INTO projects(id,name,goal,prompt,status,risk_level,stack_json,created_at,updated_at) VALUES('p','P','','','created','normal','{}',0,0)"); conn.commit(); conn.close()
    tasks=task_graph.create("p", ["planning","generation"])
    assert len(tasks)==2
    assert tasks[1]["depends_on"] == [tasks[0]["id"]]
    assert task_graph.next_ready("p")["task_type"]=="planning"
