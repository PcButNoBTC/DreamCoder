from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_github_routes_are_declared_once():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert source.count('@app.get("/api/github/oauth/config")') == 1
    assert source.count('@app.get("/api/github/me")') == 1
    assert source.count('@app.get("/api/github/repositories")') == 1
    assert source.count('@app.post("/api/github/disconnect")') == 1
    assert source.count('@app.post("/api/github/select-repository")') == 1


def test_workflow_state_endpoint_and_ui_exist():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert '"/api/workflow/state"' in source
    assert "Goal → Git workflow UI" in source
    assert "Phase 4: visible creation workflow" in frontend
