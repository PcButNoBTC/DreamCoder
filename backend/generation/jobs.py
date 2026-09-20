"""Persistent background generation jobs with cancellation and event history."""
from __future__ import annotations
import asyncio,json,time,uuid
from typing import Any,Awaitable,Callable
import db
class GenerationJobManager:
    def __init__(self):
        self.tasks={}; self.cancelled=set(); self._init_db()
    def _init_db(self):
        conn=db.get_conn(); conn.executescript("""
        CREATE TABLE IF NOT EXISTS generation_jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL,request TEXT NOT NULL,result TEXT,error TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS generation_job_events(id INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT NOT NULL,event TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL);
        """); conn.commit(); conn.close()
    def _write(self,job_id,status,request,result=None,error=""):
        now=time.time(); conn=db.get_conn()
        conn.execute("INSERT INTO generation_jobs(id,status,request,result,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,result=excluded.result,error=excluded.error,updated_at=excluded.updated_at",
                     (job_id,status,json.dumps(request,default=str),json.dumps(result,default=str) if result is not None else None,error,now,now))
        conn.commit(); conn.close()
    def event(self,job_id,name,**payload):
        conn=db.get_conn(); conn.execute("INSERT INTO generation_job_events(job_id,event,payload,created_at) VALUES(?,?,?,?)",(job_id,name,json.dumps(payload,default=str),time.time())); conn.commit(); conn.close()
    async def start(self,request,runner):
        job_id=uuid.uuid4().hex; self._write(job_id,"queued",request); self.event(job_id,"job.queued")
        async def execute():
            self._write(job_id,"running",request); self.event(job_id,"job.started")
            try:
                result=await runner(request,lambda name,**data:self.event(job_id,name,**data))
                if job_id in self.cancelled: self._write(job_id,"cancelled",request,result); self.event(job_id,"job.cancelled")
                else: self._write(job_id,"completed",request,result); self.event(job_id,"job.completed")
            except asyncio.CancelledError:
                self._write(job_id,"cancelled",request); self.event(job_id,"job.cancelled")
            except Exception as exc:
                self._write(job_id,"failed",request,error=str(exc)); self.event(job_id,"job.failed",error=str(exc))
        self.tasks[job_id]=asyncio.create_task(execute()); return job_id
    def cancel(self,job_id):
        task=self.tasks.get(job_id)
        if not task:return False
        self.cancelled.add(job_id); task.cancel(); return True
    def get(self,job_id):
        conn=db.get_conn(); row=conn.execute("SELECT * FROM generation_jobs WHERE id=?",(job_id,)).fetchone(); events=conn.execute("SELECT event,payload,created_at FROM generation_job_events WHERE job_id=? ORDER BY id",(job_id,)).fetchall(); conn.close()
        if not row: raise KeyError(job_id)
        return {"id":row["id"],"status":row["status"],"request":json.loads(row["request"]),"result":json.loads(row["result"]) if row["result"] else None,"error":row["error"],"created_at":row["created_at"],"updated_at":row["updated_at"],"events":[{"event":e["event"],"payload":json.loads(e["payload"]),"created_at":e["created_at"]} for e in events]}
jobs=GenerationJobManager()
