import db, model_lab

def test_repeatability_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"e.db")
    monkeypatch.setattr(db,"_CANDIDATES",[tmp_path/"e.db"])
    db.init_db()
    model_lab.register("example/model","huggingface",revision="r1")
    conn=db.get_conn()
    for i,score in enumerate((0.8,0.9,0.7)):
        conn.execute("""INSERT INTO model_benchmarks
        (model_id,benchmark_id,suite_version,run_id,category,role,pass,score,latency_ms,execution_ok,evidence_json,created_at,model_revision)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",("example/model","python-implementation","v1",str(i),"coding","generation",1,score,10,1,"{}",float(i+1),"r1"))
    conn.commit(); conn.close()
    summary=model_lab.repeatability("example/model","python-implementation")
    assert summary["python-implementation"]["runs"]==3
    assert summary["python-implementation"]["max"]==0.9

def test_revision_regression_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"r.db")
    monkeypatch.setattr(db,"_CANDIDATES",[tmp_path/"r.db"])
    db.init_db()
    model_lab.register("example/model","huggingface",revision="r2")
    conn=db.get_conn()
    for rev,score in (("r1",0.8),("r1",0.9),("r2",0.7)):
        conn.execute("""INSERT INTO model_benchmarks
        (model_id,benchmark_id,suite_version,run_id,category,role,pass,score,latency_ms,execution_ok,evidence_json,created_at,model_revision)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",("example/model","general-structured-output","v1",rev,"structured_output","planning",1,score,10,None,"{}",1,rev))
    conn.commit(); conn.close()
    data=model_lab.revision_regression("example/model")
    assert data["r1"]["runs"]==2
    assert data["r2"]["runs"]==1
