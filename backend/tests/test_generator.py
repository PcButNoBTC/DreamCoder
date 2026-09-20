from pathlib import Path

from fastapi.testclient import TestClient

import main
from generator import generate_project


def test_generate_project_build_survives_missing_sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(main.workspace, "root", lambda: tmp_path)
    monkeypatch.setattr(main, "sandbox_available", lambda: False)
    monkeypatch.setattr(main, "create_checkpoint", lambda *args, **kwargs: {"ok": True, "path": "checkpoint.zip"})

    client = TestClient(main.app)
    response = client.post(
        "/api/ai/generate-project/build",
        json={
            "name": "demo-app",
            "stack": {"language": "python"},
            "files": [{"path": "main.py", "content": "print('hello from dreamcoder')\n"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "warning" in payload["validation"]
    assert "sandbox" in payload["validation"]["warning"].lower()


def test_task_app_generation_includes_real_logic():
    project = generate_project("Build a todo app with tasks, priorities, and completion tracking")

    files = {f["path"]: f["content"] for f in project["files"]}
    joined = "\n".join(files.values())

    assert project["file_count"] >= 5
    assert "TaskManager" in joined or "add_task" in joined
    assert "complete_task" in joined or "toggle_task" in joined
    assert "priority" in joined.lower()


def test_budget_app_generation_includes_domain_logic():
    project = generate_project("Create a budget tracker for expenses and monthly summaries")

    files = {f["path"]: f["content"] for f in project["files"]}
    joined = "\n".join(files.values())

    assert "Budget" in joined or "Expense" in joined or "add_expense" in joined
    assert "monthly" in joined.lower() or "summary" in joined.lower()
