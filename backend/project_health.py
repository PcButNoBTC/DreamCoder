"""Evidence-based project health signals."""
from __future__ import annotations
from pathlib import Path
import subprocess
import workspace, db

IGNORED={".git","node_modules",".venv","venv","__pycache__","dist","build"}

def _count_tests(root:Path)->int:
    return sum(1 for p in root.rglob("*") if p.is_file() and not any(x in p.parts for x in IGNORED) and (p.name.startswith("test_") or p.name.endswith("_test.py")))

def health(root_path:str|None=None)->dict:
    root=Path(root_path or workspace.root() or Path.cwd()).resolve()
    result={"workspace":str(root),"signals":{}}
    result["signals"]["workspace_exists"]=root.exists()
    if not root.exists(): return result
    git=workspace.git(["status","--porcelain=v1","--branch"])
    result["signals"]["git_clean"]=bool(git.get("ok")) and len([x for x in git.get("stdout","").splitlines() if not x.startswith("##")])==0
    result["signals"]["tests_discovered"]=_count_tests(root)
    pyproject=(root/"pyproject.toml").exists()
    package=(root/"package.json").exists()
    result["signals"]["python_project"]=pyproject or (root/"requirements.txt").exists()
    result["signals"]["node_project"]=package
    result["signals"]["project_commands"]=db.get_setting("project_commands",[]) or []
    result["score_inputs"]={
        "git_clean":result["signals"]["git_clean"],
        "tests":result["signals"]["tests_discovered"],
        "python_project":result["signals"]["python_project"],
        "node_project":result["signals"]["node_project"],
    }
    return result
