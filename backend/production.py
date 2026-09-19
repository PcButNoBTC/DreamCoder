"""Production control-plane: readiness, diagnostics, migrations and operational status."""
from __future__ import annotations
import os,platform,time
from typing import Any
import db
from security import capabilities,redact
from checkpoints import list_checkpoints
from project_memory import memory
def init():
    db.init_db()
    db.set_setting("schema_version",max(int(db.get_setting("schema_version",0) or 0),2))
    return True
def readiness()->dict[str,Any]:
    root=db.get_setting("workspace_root","")
    checks={
      "database": bool(db.DB_PATH),
      "workspace": bool(root and os.path.isdir(os.path.expanduser(root))),
      "github_config": bool(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")),
      "ai_config": bool(os.getenv("HF_TOKEN") or os.getenv("OLLAMA_BASE_URL") or os.getenv("DREAMCODER_OLLAMA_PRIMARY_URL") or os.getenv("OPENAI_API_KEY")),
      "checkpoint_store": True,
    }
    return {"ok":all(checks.values()),"checks":checks,"platform":platform.platform(),"python":platform.python_version(),"schema_version":db.get_setting("schema_version",1),"capabilities":capabilities(),"time":time.time()}
def diagnostics(root:str|None=None)->dict[str,Any]:
    return {"readiness":readiness(),"db":{"path":str(db.DB_PATH),"stats":db.symbol_stats()},"memory":memory.graph(100),"checkpoints":list_checkpoints(root),"env":{"autosync":os.getenv("DREAMCODER_GITHUB_AUTOSYNC","true"),"agent_unrestricted":os.getenv("DREAMCODER_AGENT_UNRESTRICTED","0")}}
