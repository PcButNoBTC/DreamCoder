from __future__ import annotations
import json,os,re,time,zipfile
from datetime import datetime
from pathlib import Path

def backup_root()->Path:
    p=Path(os.getenv("DREAMCODER_BACKUP_DIR","~/DreamCoder-backups")).expanduser(); p.mkdir(parents=True,exist_ok=True); return p

def slugify(text:str)->str:
    return re.sub(r"[^A-Za-z0-9]+","_",text).strip("_")[:60] or "file"

def write_backup(root:str,rel_path:str,content:str,reason:str)->dict:
    try:
        now=datetime.utcnow(); p=backup_root()/f"{now:%Y-%m-%d_%H%M%S}_{slugify(rel_path)}.zip"
        manifest={"rel_path":rel_path,"reason":reason,"timestamp":now.isoformat()+"Z","source_root":root}
        with zipfile.ZipFile(p,"w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("content",content.encode("utf-8")); z.writestr("manifest.json",json.dumps(manifest,indent=2))
        return {"ok":True,"path":str(p),"size":p.stat().st_size}
    except Exception as exc:return {"ok":False,"error":str(exc)}

def list_backups()->list[dict]:
    try:return [{"name":p.name,"path":str(p),"size":p.stat().st_size,"created_at":p.stat().st_mtime} for p in sorted(backup_root().glob("*.zip"),key=lambda x:x.stat().st_mtime,reverse=True)]
    except Exception:return []

def audit_log_path()->Path:return backup_root()/"agent-commands.log"

def log_command(command:str,cwd:str,exit_code:int,run_id:str="")->None:
    try:
        with audit_log_path().open("a",encoding="utf-8") as f:f.write(json.dumps({"ts":time.time(),"command":command,"cwd":cwd,"exit_code":exit_code,"run_id":run_id})+"\n")
    except Exception:pass

def read_audit_log(limit:int=200)->list[dict]:
    try:
        lines=audit_log_path().read_text(encoding="utf-8").splitlines(); out=[]
        for line in lines[-max(1,min(int(limit),1000)):]:
            try:out.append(json.loads(line))
            except json.JSONDecodeError:pass
        return list(reversed(out))
    except Exception:return []
