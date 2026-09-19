from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import db
from ai_router import AIRouter
from models.base import CodeContext

from .tools import ToolRegistry
from .types import AgentRequest, AgentRun, PlanStep, ToolCall

class AgentRuntime:
    """Small, persistent project-level agent loop.

    The runtime deliberately separates planning, tool execution, validation and repair.
    It never grants the model a raw shell or arbitrary Python execution primitive.
    """
    def __init__(self, router: AIRouter | None = None):
        self.router = router or AIRouter()
        self.runs: dict[str, AgentRun] = {}
        self._init_db()

    def _init_db(self):
        conn=db.get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_runs (id TEXT PRIMARY KEY, status TEXT, goal TEXT, cwd TEXT, payload TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_tool_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, tool TEXT NOT NULL, args TEXT NOT NULL, status TEXT NOT NULL, output TEXT, error TEXT, created_at REAL NOT NULL);
        """)
        conn.commit(); conn.close()

    def _persist(self, run: AgentRun):
        now=time.time(); payload=json.dumps(run.to_dict(),default=str)
        conn=db.get_conn(); conn.execute("INSERT INTO agent_runs(id,status,goal,cwd,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at",(run.id,run.status,run.goal,run.cwd,payload,now,now)); conn.commit(); conn.close(); self.runs[run.id]=run

    def _event(self, run: AgentRun, name: str, **data: Any):
        event={"type":name,"ts":time.time(),**data}; run.events.append(event)
        conn=db.get_conn(); conn.execute("INSERT INTO agent_events(run_id,event,payload,created_at) VALUES(?,?,?,?)",(run.id,name,json.dumps(data,default=str),time.time())); conn.commit(); conn.close(); self._persist(run)

    def _project_context(self, cwd: str) -> str:
        goal=db.get_setting("project_goal","") or ""
        desc=db.get_setting("project_description","") or ""
        files=[]
        root=Path(cwd)
        for p in root.rglob("*"):
            if len(files)>=30 or not p.is_file() or any(x in p.parts for x in (".git","node_modules",".venv","__pycache__")): continue
            files.append(str(p.relative_to(root)))
        return f"Project goal: {goal}\nDescription: {desc}\nFiles:\n"+"\n".join(files)

    async def _plan(self, req: AgentRequest) -> list[PlanStep]:
        ctx=self._project_context(req.cwd)
        prompt=(f"Plan a safe software-engineering task. Return concise steps, no code.\nGoal: {req.goal}\n{ctx}\n"
                "Use only these tool concepts: read_file, search, write_file, apply_patch, run, test, git_status, git_diff.")
        inf=await self.router.suggest(req.model,CodeContext(code=prompt,language="text",filename="agent-plan"),use_cache=False)
        titles=[s.title for s in inf.suggestions[:5]]
        if not titles: titles=["Inspect project", "Implement requested change", "Validate with tests", "Review git diff"]
        tools=[ ["search","read_file"], ["write_file","apply_patch"], ["run","test"], ["git_status","git_diff"] ]
        return [PlanStep(id=f"step-{i+1}",title=t,purpose="Agent step derived from project context",tools=tools[min(i,len(tools)-1)],requires_approval=any(x in tools[min(i,len(tools)-1)] for x in ("write_file","apply_patch"))) for i,t in enumerate(titles)]

    async def run(self, req: AgentRequest) -> AgentRun:
        run=AgentRun(id=uuid.uuid4().hex,status="planning",goal=req.goal,cwd=str(Path(req.cwd).resolve()))
        self._persist(run); self._event(run,"run.started",model=req.model)
        try:
            run.plan=await self._plan(req); run.status="awaiting_approval" if any(s.requires_approval for s in run.plan) and not req.auto_apply else "executing"; self._persist(run)
            self._event(run,"plan.ready",steps=[s.__dict__ for s in run.plan],approval_required=run.status=="awaiting_approval")
            if run.status=="awaiting_approval": return run
            return await self._execute(run,req)
        except Exception as exc:
            run.status="failed"; self._event(run,"run.failed",error=str(exc)); return run

    async def approve(self, run_id: str, req: AgentRequest | None = None) -> AgentRun:
        run=self.get(run_id)
        if run.status!="awaiting_approval": return run
        run.status="executing"; self._persist(run); self._event(run,"approval.granted")
        if req is None: req=AgentRequest(goal=run.goal,cwd=run.cwd,auto_apply=True)
        else: req.auto_apply=True
        return await self._execute(run,req)

    async def _execute(self, run: AgentRun, req: AgentRequest) -> AgentRun:
        tools=ToolRegistry(run.cwd,timeout=req.timeout,auto_apply=req.auto_apply)
        # Context-first actions are deterministic; model planning remains visible but does not get direct authority.
        for spec,args in [("git_status",{}),("search",{"query":req.goal,"limit":12})]:
            await self._call(run,tools,spec,args)
        run.status="validating"; self._persist(run)
        validation=await self._call(run,tools,"test",{"command":"pytest -q"})
        run.validation=validation or {}
        if not validation or not validation.get("ok",False):
            run.repair_count+=1
            self._event(run,"validation.failed",details=validation)
            if run.repair_count<=req.max_repairs:
                run.status="repair_needed"; self._persist(run)
                self._event(run,"repair.proposed",message="Tests failed; inspect the failure and propose a minimal patch.")
                # Do not silently mutate code: repair remains an approval boundary.
                return run
        diff=await self._call(run,tools,"git_diff",{})
        run.changes.append(diff or {})
        run.status="completed" if (not validation or validation.get("ok",False)) else "failed"
        self._event(run,"run.completed",status=run.status)
        return run

    async def _call(self,run:AgentRun,tools:ToolRegistry,name:str,args:dict[str,Any]):
        call=ToolCall(id=uuid.uuid4().hex[:10],tool=name,args=args,status="running"); run.tool_calls.append(call); self._persist(run); self._event(run,"tool.started",tool=name,call_id=call.id,args=args)
        try:
            out=tools.dispatch(name,args); call.status="completed"; call.output=out
            conn=db.get_conn(); conn.execute("INSERT INTO agent_tool_calls(run_id,tool,args,status,output,created_at) VALUES(?,?,?,?,?,?)",(run.id,name,json.dumps(args),call.status,json.dumps(out,default=str),time.time())); conn.commit(); conn.close(); self._persist(run); self._event(run,"tool.completed",tool=name,call_id=call.id,output=out); return out
        except Exception as exc:
            call.status="failed"; call.error=str(exc); self._persist(run); self._event(run,"tool.failed",tool=name,call_id=call.id,error=str(exc)); return {"ok":False,"error":str(exc)}

    def get(self,run_id:str)->AgentRun:
        if run_id in self.runs:return self.runs[run_id]
        conn=db.get_conn(); row=conn.execute("SELECT payload FROM agent_runs WHERE id=?",(run_id,)).fetchone(); conn.close()
        if not row: raise KeyError(run_id)
        data=json.loads(row["payload"]); run=AgentRun(**data); self.runs[run_id]=run; return run
