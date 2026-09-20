import db, model_lab

def test_model_starts_as_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "models.db")
    monkeypatch.setattr(db, "_CANDIDATES", [tmp_path / "models.db"])
    db.init_db()
    model=model_lab.register("example/model","huggingface",revision="abc123")
    assert model["status"]=="candidate"
    assert model["revision"]=="abc123"
    profile=model_lab.profile(model["id"])
    assert profile["eligibility"]["eligible"] is False
