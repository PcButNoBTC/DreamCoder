"""Per-project model routing preferences."""
from __future__ import annotations
import time
import db
from model_lab import ROLES, route

def list_preferences(project_id: str):
    conn=db.get_conn()
    rows=conn.execute("SELECT * FROM project_model_preferences WHERE project_id=? ORDER BY role",(project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_preference(project_id: str, role: str, model_id: str = "", mode: str = "auto"):
    if role not in ROLES:
        raise ValueError("unknown role")
    if mode not in {"auto","pinned"}:
        raise ValueError("mode must be auto or pinned")
    if mode=="pinned" and not model_id.strip():
        raise ValueError("pinned mode requires model_id")
    conn=db.get_conn()
    conn.execute("""INSERT INTO project_model_preferences(project_id,role,model_id,mode,updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(project_id,role) DO UPDATE SET model_id=excluded.model_id,
                    mode=excluded.mode,updated_at=excluded.updated_at""",
                 (project_id,role,model_id.strip(),mode,time.time()))
    conn.commit(); conn.close()
    return {"project_id":project_id,"role":role,"model_id":model_id.strip(),"mode":mode}

def resolve(project_id: str, role: str):
    conn=db.get_conn()
    row=conn.execute("SELECT * FROM project_model_preferences WHERE project_id=? AND role=?",(project_id,role)).fetchone()
    conn.close()
    if row and row["mode"]=="pinned":
        return {"model_id":row["model_id"],"source":"project_pinned"}
    routed=route(role)
    return {**routed,"source":"project_auto_evidence" if routed.get("model_id") else "project_auto_fallback"}
