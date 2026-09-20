import project_hub

def test_project_hub_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(project_hub.db, "DB_PATH", tmp_path / "hub.db")
    monkeypatch.setattr(project_hub.db, "_CANDIDATES", [tmp_path / "hub.db"])
    p=project_hub.create("Calculator","Build a calculator","calculator prompt",{"language":"python"},"normal")
    project_hub.document(p["id"],"overview","Overview","A calculator")
    project_hub.event(p["id"],"generation.completed","agent","test-model",{"files":4})
    detail=project_hub.details(p["id"])
    assert detail["name"]=="Calculator"
    assert detail["documents"][0]["content"]=="A calculator"
    assert any(e["event_type"]=="generation.completed" for e in detail["events"])
    assert project_hub.search("calculator")
