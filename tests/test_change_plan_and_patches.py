from pathlib import Path
import pytest
from change_plan import ChangePlan, ChangeTask
from generation.patches import apply_patch, build_patch

def test_change_plan_round_trip(tmp_path):
    plan=ChangePlan(goal="add auth",workspace=str(tmp_path)); plan.tasks.append(ChangeTask("api","backend","Add auth endpoint"))
    restored=ChangePlan.from_dict(plan.to_dict())
    assert restored.goal==plan.goal and restored.tasks[0].id=="api"

def test_patch_requires_original_content(tmp_path):
    path=tmp_path/"app.py"; path.write_text("one\n",encoding="utf-8")
    patch=build_patch(tmp_path,"app.py","two\n"); result=apply_patch(tmp_path,patch)
    assert result["applied"] is True and path.read_text(encoding="utf-8")=="two\n"

def test_patch_rejects_stale_file(tmp_path):
    path=tmp_path/"app.py"; path.write_text("one\n",encoding="utf-8"); patch=build_patch(tmp_path,"app.py","two\n")
    path.write_text("someone else\n",encoding="utf-8")
    with pytest.raises(ValueError): apply_patch(tmp_path,patch)
