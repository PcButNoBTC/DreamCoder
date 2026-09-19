import subprocess

import db
import workspace


def test_workspace_status_without_root(tmp_path):
    db.set_setting("workspace_root", "")
    assert workspace.status()["configured"] is False


def test_workspace_write_is_confined(tmp_path):
    workspace.set_root(str(tmp_path))
    workspace.write_file("src/app.py", "print('ok')\n")
    assert (tmp_path / "src" / "app.py").read_text() == "print('ok')\n"
    try:
        workspace.write_file("../escape.py", "bad")
        assert False
    except ValueError:
        pass


def test_workspace_git_runtime(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    workspace.set_root(str(tmp_path))
    status = workspace.git(["status", "--short", "--branch"])
    assert status["ok"] is True
