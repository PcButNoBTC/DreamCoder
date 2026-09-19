from generator import generate_project


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
