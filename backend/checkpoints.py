"""Crash-safe local checkpoints for DreamCoder workspaces."""
from __future__ import annotations
import hashlib, json, os, time, zipfile
from pathlib import Path
from typing import Any

IGNORED={".git","node_modules","__pycache__",".venv","venv","dist","build",".idea",".vscode"}
def _root(root:str|Path)->Path:
    p=Path(root).expanduser().resolve()
    if not p.is_dir(): raise ValueError("workspace does not exist")
    return p
def _files(root:Path):
    for p in root.rglob("*"):
        if not p.is_file() or any(part in IGNORED or part == ".git" for part in p.relative_to(root).parts): continue
        try: yield p
        except OSError: pass
def create(root:str|Path, reason:str="checkpoint")->dict[str,Any]:
    rootp=_root(root); base=Path(os.getenv("DREAMCODER_CHECKPOINT_DIR","~/.dreamcoder/checkpoints")).expanduser()/hashlib.sha256(str(rootp).encode()).hexdigest()[:16]
    base.mkdir(parents=True,exist_ok=True); stamp=time.strftime("%Y%m%d-%H%M%S")+f"-{int(time.time()*1000)%1000:03d}"
    out=base/f"{stamp}.zip"; manifest={"root":str(rootp),"reason":reason,"created_at":time.time(),"files":[]}
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for p in _files(rootp):
            rel=str(p.relative_to(rootp)).replace("\\","/")
            data=p.read_bytes(); z.writestr(rel,data)
            manifest["files"].append({"path":rel,"sha256":hashlib.sha256(data).hexdigest(),"size":len(data)})
        z.writestr("MANIFEST.json",json.dumps(manifest,indent=2))
    return {"ok":True,"path":str(out),"reason":reason,"file_count":len(manifest["files"])}
def list_checkpoints(root:str|Path|None=None)->list[dict[str,Any]]:
    base=Path(os.getenv("DREAMCODER_CHECKPOINT_DIR","~/.dreamcoder/checkpoints")).expanduser()
    if root: base=base/hashlib.sha256(str(_root(root)).encode()).hexdigest()[:16]
    if not base.exists(): return []
    return [{"path":str(p),"size":p.stat().st_size,"created_at":p.stat().st_mtime} for p in sorted(base.glob("*.zip"),key=lambda x:x.stat().st_mtime,reverse=True)]
def restore(root:str|Path, checkpoint:str, dry_run:bool=False)->dict[str,Any]:
    rootp=_root(root); zpath=Path(checkpoint).expanduser().resolve()
    if not zpath.is_file(): raise ValueError("checkpoint not found")
    with zipfile.ZipFile(zpath) as z:
        names=[n for n in z.namelist() if n and n!="MANIFEST.json" and not n.startswith("/") and ".." not in Path(n).parts]
        if not dry_run:
            for n in names:
                target=(rootp/n).resolve()
                if rootp not in target.parents: raise ValueError("checkpoint path escapes workspace")
                target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(n))
    return {"ok":True,"restored":len(names),"dry_run":dry_run}
