"""Persistent execution queue for DreamCoder orchestration.

The queue owns durable job state; workers may execute model/task work without
losing cancellation, retry, or provenance state on process restarts.
"""
from __future__ import annotations
import asyncio, json, os, time, uuid
from typing import Any, Awaitable, Callable
import db

VALID = {"queued","running","completed","failed","cancelled"}
_worker_task: asyncio.Task | None = None
_worker_stop = asyncio.Event()

def _row(row):
    if not row: return None
    x=dict(row)
    x["payload"]=json.loads(x.pop("payload_json") or "{}")
    x["result"]=json.loads(x.pop("result_json") or "{}")
    return x

def enqueue(kind:str, payload:dict|None=None, project_id:str="", task_id:str="", priority:int=100, max_attempts:int=3)->dict:
    jid=uuid.uuid4().hex; now=time.time()
    conn=db.get_conn()
    conn.execute("""INSERT INTO execution_jobs
      (id,project_id,task_id,kind,payload_json,status,priority,attempt,max_attempts,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
      (jid,project_id,task_id,kind,json.dumps(payload or {}),"queued",int(priority),0,max(1,int(max_attempts)),now,now))
    conn.commit(); conn.close()
    return get(jid)

def get(job_id:str)->dict|None:
    conn=db.get_conn(); row=conn.execute("SELECT * FROM execution_jobs WHERE id=?",(job_id,)).fetchone(); conn.close()
    return _row(row)

def list_jobs(status:str|None=None, project_id:str|None=None, limit:int=100)->list[dict]:
    conn=db.get_conn()
    clauses=[]; args=[]
    if status: clauses.append("status=?"); args.append(status)
    if project_id: clauses.append("project_id=?"); args.append(project_id)
    where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
    rows=conn.execute("SELECT * FROM execution_jobs"+where+" ORDER BY priority ASC, created_at ASC LIMIT ?",(*args,max(1,min(limit,500)))).fetchall()
    conn.close(); return [_row(r) for r in rows]

def cancel(job_id:str)->dict:
    conn=db.get_conn()
    conn.execute("UPDATE execution_jobs SET status='cancelled',updated_at=?,completed_at=? WHERE id=? AND status IN ('queued','running')",(time.time(),time.time(),job_id))
    conn.commit(); conn.close()
    job=get(job_id)
    if not job: raise KeyError(job_id)
    return job

def _claim():
    conn=db.get_conn()
    row=conn.execute("SELECT * FROM execution_jobs WHERE status='queued' AND attempt < max_attempts ORDER BY priority ASC, created_at ASC LIMIT 1").fetchone()
    if not row: conn.close(); return None
    now=time.time()
    conn.execute("UPDATE execution_jobs SET status='running',attempt=attempt+1,started_at=?,updated_at=? WHERE id=? AND status='queued'",(now,now,row["id"]))
    conn.commit(); conn.close()
    return get(row["id"])

async def run_once(handler:Callable[[dict],Awaitable[dict]])->dict|None:
    job=_claim()
    if not job: return None
    try:
        result=await handler(job)
        conn=db.get_conn()
        conn.execute("UPDATE execution_jobs SET status='completed',result_json=?,error='',updated_at=?,completed_at=? WHERE id=?",
                     (json.dumps(result or {}),time.time(),time.time(),job["id"]))
        conn.commit(); conn.close()
    except asyncio.CancelledError: raise
    except Exception as exc:
        conn=db.get_conn()
        retry=job["attempt"] < job["max_attempts"]
        conn.execute("UPDATE execution_jobs SET status=?,error=?,updated_at=?,completed_at=? WHERE id=?",
                     ("queued" if retry else "failed",str(exc)[:2000],time.time(),None if retry else time.time(),job["id"]))
        conn.commit(); conn.close()
    return get(job["id"])

async def worker(handler:Callable[[dict],Awaitable[dict]]):
    while not _worker_stop.is_set():
        job=await run_once(handler)
        if job is None:
            try: await asyncio.wait_for(_worker_stop.wait(),timeout=float(os.getenv("DREAMCODER_QUEUE_POLL_SECONDS","1")))
            except asyncio.TimeoutError: pass

async def start(handler):
    global _worker_task
    if _worker_task and not _worker_task.done(): return
    _worker_stop.clear()
    _worker_task=asyncio.create_task(worker(handler))

async def stop():
    global _worker_task
    _worker_stop.set()
    if _worker_task: await _worker_task
    _worker_task=None
