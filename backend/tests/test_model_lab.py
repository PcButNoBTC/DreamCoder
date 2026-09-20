import model_lab

def test_benchmark_catalog_is_role_based():
    ids={b["id"] for b in model_lab.benchmark_catalog()}
    assert "python-implementation" in ids
    assert "boundary-consistency" in ids

def test_profile_requires_evidence(monkeypatch,tmp_path):
    monkeypatch.setattr(model_lab.db,"DB_PATH",tmp_path/"lab.db")
    monkeypatch.setattr(model_lab.db,"_CANDIDATES",[tmp_path/"lab.db"])
    p=model_lab.register("test/model","huggingface")
    profile=model_lab.profile(p["id"])
    assert profile["eligibility"]["eligible"] is False

def test_route_uses_measured_evidence(monkeypatch,tmp_path):
    monkeypatch.setattr(model_lab.db,"DB_PATH",tmp_path/"lab.db")
    monkeypatch.setattr(model_lab.db,"_CANDIDATES",[tmp_path/"lab.db"])
    model_lab.register("test/model","local")
    assert model_lab.route("generation")["model_id"] is None
