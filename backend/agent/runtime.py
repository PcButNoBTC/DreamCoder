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
        root=Path(cwd)
        chunks=[]
        total=0
        ignored={".git","node_modules",".venv","venv","__pycache__","dist","build"}
        for p in sorted(root.rglob("*")):
            if total >= 40000 or not p.is_file() or any(x in p.parts for x in ignored):
                continue
            try:
                content=p.read_text(encoding="utf-8")
            except (UnicodeDecodeError,OSError):
                continue
            rel=str(p.relative_to(root))
            block=f"\n# --- {rel} ---\n{content[:5000]}"
            chunks.append(block)
            total += len(block)
        return f"Project goal: {goal}\nDescription: {desc}\nProject files:{''.join(chunks) or '(none)'}"

    @staticmethod
    def _extract_json(text: str) -> Any:
        cleaned=(text or "").strip()
        if cleaned.startswith("``````"):
            cleaned=cleaned.split("\n",1)[-1].rsplit("``````",1)[0].strip()
        try:
            return json.loads(cleaned)
        except Exception:
            for opener,closer in (("{","}"),("[","]")):
                start=cleaned.find(opener); end=cleaned.rfind(closer)
                if start>=0 and end>start:
                    try: return json.loads(cleaned[start:end+1])
                    except Exception: pass
        return None

    async def _generate_changes(self, req: AgentRequest, run: AgentRun) -> list[dict[str, str]]:
        project=self._project_context(req.cwd)
        plan="\n".join(f"- {s.title}: {s.purpose}" for s in run.plan)
        prompt=("You are DreamCoder's project coding agent.\n"
                "Work only inside the supplied workspace snapshot. Do not invent files or dependencies.\n"
                "Return ONLY JSON: {\"changes\":[{\"path\":\"relative/path\",\"content\":\"complete file content\",\"summary\":\"why\"}]}\n"
                f"Goal: {req.goal}\nPlan:\n{plan}\nWorkspace snapshot:\n{project}")
        from models.base import ChatContext
        result=await self.router.chat(req.model,ChatContext(message=prompt,mode="project",project_goal=db.get_setting("project_goal","") or "",project_context=project),use_cache=False)
        parsed=self._extract_json(result.content)
        changes=(parsed or {}).get("changes",[]) if isinstance(parsed,dict) else []
        valid=[]
        for item in changes:
            if not isinstance(item,dict) or not item.get("path") or "content" not in item: continue
            rel=str(Path(str(item["path"])))
            if rel.startswith("..") or Path(rel).is_absolute(): continue
            valid.append({"path":rel,"content":str(item["content"]),"summary":str(item.get("summary",""))})
        return valid[:8]

    async def run(self, req: AgentRequest) -> AgentRun:
        run=AgentRun(id=uuid.uuid4().hex,status="planning",goal=req.goal,cwd=str(Path(req.cwd).resolve()),model=req.model)
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
        if run.status not in ("awaiting_approval","repair_needed"): return run
        run.status="executing"; self._persist(run); self._event(run,"approval.granted")
        if req is None: req=AgentRequest(goal=run.goal,cwd=run.cwd,model=run.model,auto_apply=False)
        else: req.model=run.model or req.model
        return await self._execute(run,req)

    async def _execute(self, run: AgentRun, req: AgentRequest) -> AgentRun:
        tools=ToolRegistry(run.cwd,timeout=req.timeout,auto_apply=req.auto_apply)
        await self._call(run,tools,"git_status",{})
        await self._call(run,tools,"search",{"query":req.goal,"limit":12})
        changes=await self._generate_changes(req,run)
        if changes:
            run.changes=changes
            self._event(run,"changes.proposed",changes=[{"path":x["path"],"summary":x.get("summary","")} for x in changes])
            if not req.auto_apply:
                run.status="awaiting_approval"; self._persist(run); return run
            for change in changes:
                await self._call(run,tools,"write_file",{"path":change["path"],"content":change["content"]})
        else:
            self._event(run,"changes.none")
        run.status="validating"; self._persist(run)
        validation=await self._call(run,tools,"test",{"command":"pytest -q"})
        run.validation=validation or {}; self._persist(run)
        if not validation or not validation.get("ok",False):
            run.repair_count+=1
            self._event(run,"validation.failed",details=validation)
            if run.repair_count<=req.max_repairs:
                run.status="repair_needed"; self._persist(run)
                self._event(run,"repair.proposed",message="Tests failed; approve to let the selected model generate a repair.")
                return run
        diff=await self._call(run,tools,"git_diff",{})
        run.changes.extend([diff or {}])
        run.status="completed" if (not validation or validation.get("ok",False)) else "failed"
        self._event(run,"run.completed",status=run.status)
        return run
    def get(self,run_id:str)->AgentRun:
        if run_id in self.runs:return self.runs[run_id]
        conn=db.get_conn(); row=conn.execute("SELECT payload FROM agent_runs WHERE id=?",(run_id,)).fetchone(); conn.close()
        if not row: raise KeyError(run_id)
        data=json.loads(row["payload"]); run=AgentRun(**data); self.runs[run_id]=run; return run
