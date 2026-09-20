"""Persistent Project Hub: living project registry, provenance, artifacts and decisions."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any
import sqlite3

import db

def _conn():
    return db.get_conn()

def create(name: str, goal: str, prompt: str, stack: dict[str, Any] | None = None, risk_level: str = "normal") -> dict[str, Any]:
    pid = uuid.uuid4().hex
    now = time.time()
    conn = _conn()
    conn.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)",
                 (pid, name, goal, prompt, "created", risk_level, json.dumps(stack or {}), now, now))
    conn.commit()
    conn.close()
    event(pid, "project.created", "system", "", {"name": name, "risk_level": risk_level})
    return get(pid)

def event(project_id: str, event_type: str, actor: str = "system", model: str = "", payload: dict[str, Any] | None = None) -> None:
    conn = _conn()
    now = time.time()
    conn.execute("INSERT INTO project_events(project_id,event_type,actor,model,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                 (project_id, event_type, actor, model, json.dumps(payload or {}), now))
    conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (now, project_id))
    conn.commit(); conn.close()

def set_status(project_id: str, status: str, risk_level: str | None = None) -> None:
    conn = _conn()
    if risk_level is None:
        conn.execute("UPDATE projects SET status=?,updated_at=? WHERE id=?", (status,time.time(),project_id))
    else:
        conn.execute("UPDATE projects SET status=?,risk_level=?,updated_at=? WHERE id=?", (status,risk_level,time.time(),project_id))
    conn.commit(); conn.close()

def document(project_id: str, kind: str, title: str, content: str) -> None:
    conn = _conn()
    now = time.time()
    conn.execute("""INSERT INTO project_documents(project_id,kind,title,content,updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(project_id,kind,title) DO UPDATE SET content=excluded.content,updated_at=excluded.updated_at""",
                 (project_id,kind,title,content,now))
    conn.commit(); conn.close()

def artifact(project_id: str, kind: str, path: str = "", metadata: dict[str, Any] | None = None) -> None:
    conn = _conn()
    conn.execute("INSERT INTO project_artifacts(project_id,kind,path,metadata_json,created_at) VALUES(?,?,?,?,?)",
                 (project_id,kind,path,json.dumps(metadata or {}),time.time()))
    conn.commit(); conn.close()

def decision(project_id: str, text: str, rationale: str = "", model: str = "") -> None:
    conn = _conn()
    conn.execute("INSERT INTO project_decisions(project_id,decision,rationale,model,created_at) VALUES(?,?,?,?,?)",
                 (project_id,text,rationale,model,time.time()))
    conn.commit(); conn.close()

def _project(row):
    if not row: return None
    x=dict(row); x["stack"]=json.loads(x.pop("stack_json") or "{}"); return x

def get(project_id: str) -> dict[str, Any] | None:
    conn=_conn(); row=conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone(); conn.close()
    return _project(row)

def list_projects(limit: int = 100) -> list[dict[str, Any]]:
    conn=_conn(); rows=conn.execute("SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?",(max(1,min(limit,500)),)).fetchall(); conn.close()
    return [_project(r) for r in rows]

def details(project_id: str) -> dict[str, Any] | None:
    p=get(project_id)
    if not p: return None
    conn=_conn()
    events=conn.execute("SELECT * FROM project_events WHERE project_id=? ORDER BY id DESC LIMIT 500",(project_id,)).fetchall()
    docs=conn.execute("SELECT id,kind,title,content,updated_at FROM project_documents WHERE project_id=? ORDER BY kind,title",(project_id,)).fetchall()
    arts=conn.execute("SELECT * FROM project_artifacts WHERE project_id=? ORDER BY id DESC",(project_id,)).fetchall()
    decisions=conn.execute("SELECT * FROM project_decisions WHERE project_id=? ORDER BY id DESC",(project_id,)).fetchall()
    conn.close()
    return {**p,
      "events":[{**dict(x),"payload":json.loads(x["payload_json"] or "{}")} for x in events],
      "documents":[dict(x) for x in docs],
      "artifacts":[{**dict(x),"metadata":json.loads(x["metadata_json"] or "{}")} for x in arts],
      "decisions":[dict(x) for x in decisions]}

def search(q: str, limit: int = 50) -> list[dict[str, Any]]:
    conn=_conn(); term=f"%{q}%"
    rows=conn.execute("SELECT * FROM projects WHERE name LIKE ? OR goal LIKE ? OR prompt LIKE ? ORDER BY updated_at DESC LIMIT ?",(term,term,term,limit)).fetchall(); conn.close()
    return [_project(r) for r in rows]
