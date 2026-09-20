"""HTTP API for project task graphs and role assignments."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import task_graph

router = APIRouter(tags=["orchestration"])

class TaskPlanRequest(BaseModel):
    include: list[str] = Field(default_factory=list)

class TaskAssignRequest(BaseModel):
    model_id: str = ""

@router.get("/api/projects/{project_id}/tasks")
async def tasks(project_id: str):
    return {"project_id": project_id, "tasks": task_graph.list_tasks(project_id), "ready": task_graph.next_ready(project_id)}

@router.post("/api/projects/{project_id}/tasks/plan")
async def plan(project_id: str, body: TaskPlanRequest):
    if body.include:
        return {"project_id":project_id,"tasks":task_graph.create(project_id,body.include),"ready":task_graph.next_ready(project_id)}
    return task_graph.plan(project_id)

@router.post("/api/projects/{project_id}/tasks/{task_id}/assign")
async def assign(project_id: str, task_id: str, body: TaskAssignRequest):
    try:
        task = task_graph.assign(task_id, body.model_id.strip() or None)
    except KeyError:
        raise HTTPException(404, "task not found")
    if task["project_id"] != project_id:
        raise HTTPException(404, "task not found")
    return task

@router.post("/api/projects/{project_id}/tasks/{task_id}/status")
async def status(project_id: str, task_id: str, body: dict):
    try:
        task = task_graph.update(task_id, str(body.get("status","pending")), body.get("output"), str(body.get("error","")), body.get("attempt"))
    except KeyError:
        raise HTTPException(404, "task not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if task["project_id"] != project_id:
        raise HTTPException(404, "task not found")
    return task
