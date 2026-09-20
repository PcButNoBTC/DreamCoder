import db, project_models

def test_project_model_preference_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(db,"DB_PATH",tmp_path/"p.db")
    monkeypatch.setattr(db,"_CANDIDATES",[tmp_path/"p.db"])
    db.init_db()
    x=project_models.set_preference("p","generation","example/model","pinned")
    assert x["mode"]=="pinned"
    assert project_models.resolve("p","generation")["source"]=="project_pinned"
