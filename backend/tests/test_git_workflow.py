import subprocess
import workspace
from git_agent import changed_files

def test_git_workflow_stage_unstage_commit(tmp_path):
    subprocess.run(["git","init"],cwd=tmp_path,check=True,capture_output=True)
    subprocess.run(["git","config","user.email","test@example.com"],cwd=tmp_path,check=True)
    subprocess.run(["git","config","user.name","DreamCoder Test"],cwd=tmp_path,check=True)
    workspace.set_root(str(tmp_path))
    (tmp_path/"a.txt").write_text("one")
    assert changed_files()["files"]
