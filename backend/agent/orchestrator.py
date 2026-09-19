"""Autonomous implementation loop: plan -> checkpoint -> implement -> build/test -> repair -> verify."""
from __future__ import annotations
import asyncio, json, subprocess, time
from pathlib import Path
from typing import Any
import db, workspace
from checkpoints import create
from security import audit, redact
class AgentOrchestrator:
    def __init__(self, runtime): self.runtime=runtime
    async def run_verified(self, req, max_repairs:int=3)->dict[str,Any]:
        cp=create(req.cwd,"agent-run-start"); audit("agent.start",goal=req.goal,cwd=req.cwd)
        run=await self.runtime.run(req)
        history=[run.to_dict()]
        command=db.get_setting("project_test_command","") or db.get_setting("project_build_command","")
        if not command:
            command=self._detect_command(req.cwd)
        repairs=0
        while repairs<max_repairs:
            if run.status=="completed" and run.validation.get("ok",False): break
            if not command: break
            result=workspace.run_shell(command,timeout=max(30,req.timeout*3))
            run.validation=result
            history.append({"phase":"verify","result":result})
            if result.get("ok"): run.status="completed"; break
            repairs+=1
            audit("agent.repair",attempt=repairs,error=redact((result.get("stderr") or result.get("error") or "")[:1000]))
            repair_req=type(req)(goal=f"{req.goal}\nFix this build/test failure and preserve all existing behavior:\n{redact(str(result))}",cwd=req.cwd,model=req.model,max_repairs=1,auto_apply=True,timeout=req.timeout)
            run=await self.runtime.run(repair_req); history.append(run.to_dict())
        return {"ok":run.status=="completed" and bool(run.validation.get("ok",True)),"run":run.to_dict(),"checkpoint":cp,"history":history,"repairs":repairs,"verify_command":command}
    def _detect_command(self,root):
        p=Path(root)
        if (p/"pyproject.toml").exists() or (p/"pytest.ini").exists() or (p/"tests").exists(): return "python -m pytest -q"
        if (p/"package.json").exists(): return "npm test -- --runInBand"
        if (p/"Cargo.toml").exists(): return "cargo test"
        if (p/"go.mod").exists(): return "go test ./..."
        if (p/"CMakeLists.txt").exists(): return "cmake -S . -B build && cmake --build build"
        if (p/"Makefile").exists(): return "make"
        if (p.suffix==".sln"): return "dotnet test"
        return ""
