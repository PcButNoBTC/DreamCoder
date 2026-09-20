"""Minimal, reviewable patch generation and application helpers."""
from __future__ import annotations
import difflib
from pathlib import Path
from typing import Any
from security import safe_path
def unified_diff(path: str,before: str,after: str)->str:
    return "".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=path,tofile=path))
def build_patch(root: str|Path,path: str,after: str)->dict[str,Any]:
    target=safe_path(root,path,allow_missing=True)
    before=target.read_text(encoding="utf-8") if target.exists() else ""
    operation="create" if not target.exists() else ("delete" if after=="" else "modify")
    return {"path":str(Path(path).as_posix()),"operation":operation,"before":before,"after":after,"patch":unified_diff(path,before,after),"summary":f"{operation} {path}"}
def apply_patch(root: str|Path,patch: dict[str,Any])->dict[str,Any]:
    target=safe_path(root,str(patch["path"]),allow_missing=True)
    before=target.read_text(encoding="utf-8") if target.exists() else ""
    if before != patch.get("before",""): raise ValueError(f"Patch precondition failed for {patch['path']}; file changed since planning")
    if patch.get("operation")=="delete":
        if target.exists(): target.unlink()
    else:
        target.parent.mkdir(parents=True,exist_ok=True); target.write_text(str(patch.get("after","")),encoding="utf-8")
    return {**patch,"applied":True,"diff":unified_diff(str(patch["path"]),before,str(patch.get("after","")))}
def patches_from_files(root: str|Path,files:list[dict[str,str]])->list[dict[str,Any]]:
    return [build_patch(root,str(item["path"]),str(item.get("content",""))) for item in files]
