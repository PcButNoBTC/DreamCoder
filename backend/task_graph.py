"""Persistent project task graph for multi-model orchestration."""
from __future__ import annotations
import json, time, uuid
from typing import Any
import db
from model_lab import route

TASKS = (
    ("planning", "Plan project", "planning"),
    ("architecture", "Define architecture", "repository_reasoning"),
    ("requirements", "Validate requirements", "planning"),
    ("generation", "Generate implementation", "generation"),
    ("validation", "Validate generated artifacts", "testing"),
    ("testing", "Run tests", "testing"),
    ("debugging", "Repair failures", "debugging"),
    ("documentation", "Update project docs", "documentation"),
    ("review", "Review result", "review"),
)

def create(project_id: str, include: list[str] | None = None) -> list[dict[str, Any]]:
    names = set(include or [x[0] for x in TASKS])
    conn = db.get_conn()
    now = time.time()
    prev = None
    for task_type, title, role in TASKS:
        if task_type not in names:
            continue
        tid = uuid.uuid4().hex
        deps = [] if prev is None else [prev]
        conn.execute("""INSERT INTO project_tasks
            (id,project_id,task_type,title,status,role,depends_on_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (tid, project_id, task_type, title, "pending", role, json.dumps(deps), now, now))
        prev = tid
    conn.commit()
    conn.close()
    return list_tasks(project_id)

def list_tasks(project_id: str) -> list[dict[str, Any]]:
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM project_tasks WHERE project_id=? ORDER BY created_at,id", (project_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        x = dict(r)
        x["input"] = json.loads(x.pop("input_json") or "{}")
        x["output"] = json.loads(x.pop("output_json") or "{}")
        x["depends_on"] = json.loads(x.pop("depends_on_json") or "[]")
        out.append(x)
    return out

def next_ready(project_id: str) -> dict[str, Any] | None:
    tasks = list_tasks(project_id)
    done = {t["id"] for t in tasks if t["status"] == "completed"}
    return next((t for t in tasks if t["status"] in {"pending","ready"} and all(d in done for d in t["depends_on"])), None)

def assign(task_id: str, model_id: str | None = None) -> dict[str, Any]:
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM project_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError(task_id)
    chosen = model_id or route(row["role"]).get("model_id") or ""
    status = "ready" if chosen else "pending"
    conn.execute("UPDATE project_tasks SET model_id=?,status=?,updated_at=? WHERE id=?", (chosen,status,time.time(),task_id))
    conn.commit()
    conn.close()
    return next(x for x in list_tasks(row["project_id"]) if x["id"] == task_id)

def update(task_id: str, status: str, output: dict | None = None, error: str = "", attempt: int | None = None) -> dict[str, Any]:
    if status not in {"pending","ready","running","completed","failed","cancelled"}:
        raise ValueError("invalid task status")
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM project_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise KeyError(task_id)
    now = time.time()
    fields, values = ["status=?","updated_at=?","error=?"], [status,now,error]
    if output is not None:
        fields.append("output_json=?"); values.append(json.dumps(output))
    if attempt is not None:
        fields.append("attempt=?"); values.append(attempt)
    if status == "running":
        fields.append("started_at=?"); values.append(now)
    if status in {"completed","failed","cancelled"}:
        fields.append("completed_at=?"); values.append(now)
    values.append(task_id)
    conn.execute("UPDATE project_tasks SET " + ",".join(fields) + " WHERE id=?", values)
    conn.commit(); conn.close()
    return next(x for x in list_tasks(row["project_id"]) if x["id"] == task_id)

def plan(project_id: str) -> dict[str, Any]:
    if not list_tasks(project_id):
        create(project_id)
    for task in list_tasks(project_id):
        if not task["model_id"]:
            assign(task["id"])
    return {"project_id": project_id, "tasks": list_tasks(project_id), "ready": next_ready(project_id)}
