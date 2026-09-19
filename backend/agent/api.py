from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .runtime import AgentRuntime
from .orchestrator import AgentOrchestrator
from .types import AgentRequest
import workspace

router=APIRouter(prefix="/api/agent",tags=["agent"])
runtime=AgentRuntime()
orchestrator=AgentOrchestrator(runtime)

class RunBody(BaseModel):
    goal:str=Field(min_length=1)
    cwd:str="."
    model:str="Llama-3.1-8B-Instruct"
    max_repairs:int=2
    auto_apply:bool=False
    timeout:int=60

class ApprovalBody(BaseModel):
    auto_apply:bool=False

@router.post("/run")
async def run_agent(body:RunBody):
    configured = workspace.root()
    requested = Path(body.cwd).expanduser() if body.cwd and body.cwd != "." else (configured or Path(__file__).resolve().parents[2])
    cwd=str(requested.resolve())
    if configured is not None:
        base=configured.resolve()
        if Path(cwd) != base and base not in Path(cwd).parents:
            raise HTTPException(400,"Agent workspace must stay inside the active workspace")
    if not Path(cwd).exists(): raise HTTPException(400,f"Workspace does not exist: {cwd}")
    run=await runtime.run(AgentRequest(**body.model_dump(),cwd=cwd))
    return run.to_dict()

@router.get("/runs/{run_id}")
async def get_run(run_id:str):
    try:return runtime.get(run_id).to_dict()
    except KeyError:raise HTTPException(404,"Agent run not found")

@router.post("/runs/{run_id}/approve")
async def approve(run_id:str,body:ApprovalBody):
    try:return (await runtime.approve(run_id,AgentRequest(goal=runtime.get(run_id).goal,cwd=runtime.get(run_id).cwd,auto_apply=body.auto_apply))).to_dict()
    except KeyError:raise HTTPException(404,"Agent run not found")


@router.post("/run/verified")
async def run_agent_verified(body:RunBody):
    configured = workspace.root()
    requested = Path(body.cwd).expanduser() if body.cwd and body.cwd != "." else (configured or Path.cwd())
    cwd = requested.resolve()
    if configured is not None:
        base=configured.resolve()
        if cwd != base and base not in cwd.parents:
            raise HTTPException(400,"Agent workspace must stay inside the active workspace")
    if not cwd.exists(): raise HTTPException(400,f"Workspace does not exist: {cwd}")
    req=AgentRequest(**body.model_dump(),cwd=str(cwd),auto_apply=True)
    return await orchestrator.run_verified(req,max_repairs=max(0,min(body.max_repairs,5)))
