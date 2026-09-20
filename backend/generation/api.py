"""HTTP API for persistent generation jobs and change-plan inspection."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from generation.jobs import jobs
from change_plan import ChangePlan

router=APIRouter(prefix="/api/generation",tags=["generation-jobs"])

class JobRequest(BaseModel):
    prompt: str = Field(min_length=1)
    goal: str = ""
    model: str = "Local Model"

@router.post("/jobs")
async def start_generation_job(body: JobRequest):
    from main import router as ai_router
    async def runner(request, emit):
        emit("generation.plan.started")
        from generator import generate_project_with_model
        result=await generate_project_with_model(request["prompt"],request.get("goal",""),router=ai_router)
        emit("generation.completed",file_count=result.get("file_count",0),repair_count=result.get("repair_count",0))
        return result
    job_id=await jobs.start(body.model_dump(),runner)
    return {"ok":True,"job_id":job_id}

@router.get("/jobs/{job_id}")
async def get_generation_job(job_id:str):
    try:return jobs.get(job_id)
    except KeyError:raise HTTPException(404,"generation job not found")

@router.post("/jobs/{job_id}/cancel")
async def cancel_generation_job(job_id:str):
    if not jobs.cancel(job_id): raise HTTPException(404,"active generation job not found")
    return {"ok":True,"job_id":job_id,"status":"cancelling"}
