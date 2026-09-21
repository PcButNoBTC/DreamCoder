"""Execution queue API and task-graph worker integration."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import execution_queue, task_graph

router=APIRouter(tags=["execution"])

class EnqueueRequest(BaseModel):
    kind: str = "task"
    payload: dict = Field(default_factory=dict)
    priority: int = 100
    max_attempts: int = 3

async def _handle(job:dict)->dict:
    kind=job["kind"]
    if kind == "task":
        task_id=job.get("task_id") or job["payload"].get("task_id")
        if not task_id: raise ValueError("task_id required")
        tasks=task_graph.list_tasks(job.get("project_id","") or job["payload"].get("project_id",""))
        task=next((x for x in tasks if x["id"]==task_id),None)
        if not task: raise ValueError("task not found")
        if not task["model_id"]: task=task_graph.assign(task_id)
        from main import router as ai_router
        from models.base import ChatContext
        prompt=str(job["payload"].get("prompt") or task["input"].get("prompt") or
                   f"Project task: {task['title']}. Return a concise implementation plan or result for the assigned role.")
        task_graph.update(task_id,"running",attempt=job["attempt"])
        result=await ai_router.chat(task["model_id"],ChatContext(message=prompt,mode="project"))
        output={"content":result.content,"model":result.model,"backend":result.backend,"latency_ms":result.latency_ms}
        task_graph.update(task_id,"completed",output=output,attempt=job["attempt"])
        return output
    if kind == "model_chat":
        from main import router as ai_router
        from models.base import ChatContext
        model=str(job["payload"].get("model","Local Model"))
        message=str(job["payload"].get("message",""))
        if not message: raise ValueError("message required")
        result=await ai_router.chat(model,ChatContext(message=message,mode=str(job["payload"].get("mode","general"))))
        return {"content":result.content,"model":result.model,"backend":result.backend,"latency_ms":result.latency_ms}
    raise ValueError(f"unsupported job kind: {kind}")

@router.get("/api/execution/jobs")
async def jobs(status:str|None=None, project_id:str|None=None, limit:int=100):
    return {"jobs":execution_queue.list_jobs(status,project_id,limit)}

@router.get("/api/execution/jobs/{job_id}")
async def job(job_id:str):
    found=execution_queue.get(job_id)
    if not found: raise HTTPException(404,"job not found")
    return found

@router.post("/api/execution/jobs")
async def enqueue(request:Request, body:EnqueueRequest):
    job=execution_queue.enqueue(body.kind,body.payload, str(body.payload.get("project_id","")), str(body.payload.get("task_id","")), body.priority, body.max_attempts)
    return job

@router.post("/api/execution/jobs/{job_id}/cancel")
async def cancel(job_id:str):
    try: return execution_queue.cancel(job_id)
    except KeyError: raise HTTPException(404,"job not found")

@router.post("/api/projects/{project_id}/tasks/{task_id}/execute")
async def execute_task(project_id:str,task_id:str):
    tasks=task_graph.list_tasks(project_id)
    task=next((x for x in tasks if x["id"]==task_id),None)
    if not task: raise HTTPException(404,"task not found")
    deps=set(task["depends_on"])
    done={x["id"] for x in tasks if x["status"]=="completed"}
    if not deps.issubset(done): raise HTTPException(409,"task dependencies are not complete")
    return execution_queue.enqueue("task",{"project_id":project_id,"task_id":task_id},project_id,task_id)

async def start_worker():
    await execution_queue.start(_handle)

async def stop_worker():
    await execution_queue.stop()
