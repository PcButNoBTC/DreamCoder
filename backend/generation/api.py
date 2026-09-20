"""HTTP API for persistent generation jobs and project provenance."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from generation.jobs import jobs
from generation.safety import assess, independent_review
from project_hub import create as create_project, event as project_event, set_status as set_project_status, document as project_document, artifact as project_artifact

router=APIRouter(tags=["generation","projects"])

class JobRequest(BaseModel):
    prompt: str = Field(min_length=1)
    goal: str = ""
    model: str = "Local Model"
    safeguard_model: str = "Llama-3.1-8B-Instruct"

@router.post("/api/generation/jobs")
async def start_generation_job(body: JobRequest):
    from main import router as ai_router
    assessment=assess(body.prompt,body.safeguard_model)
    review = await independent_review(body.prompt, ai_router, body.safeguard_model) if assessment.requires_review else {"ok": True, "model": body.safeguard_model, "review": "No elevated-risk review required."}
    name="generated-project"
    project=create_project(name,body.goal or body.prompt[:200],body.prompt,{},assessment.level)
    project_event(project["id"],"generation.assessment","safety-router",body.safeguard_model,{"assessment": assessment.as_dict(), "independent_review": review})
    if assessment.action=="block":
        set_project_status(project["id"],"blocked",assessment.level)
        project_document(project["id"],"security","Security Review",
                         "Generation was stopped because the requested capability combination requires a safety boundary.\n\n"
                         + "\n".join("- "+x for x in assessment.reasons))
        return {"ok":False,"job_id":None,"project_id":project["id"],"status":"blocked","assessment":assessment.as_dict(),"independent_review":review}
    async def runner(request, emit):
        emit("generation.plan.started", project_id=project["id"], safeguard_model=body.safeguard_model)
        project_event(project["id"],"generation.started","orchestrator",request.get("model",""),{"safeguard_model":body.safeguard_model,"independent_review":review})
        from generator import generate_project_with_model
        result=await generate_project_with_model(request["prompt"],request.get("goal",""),router=ai_router)
        project_event(project["id"],"generation.completed","orchestrator",request.get("model",""),
                      {"file_count":result.get("file_count",0),"repair_count":result.get("repair_count",0)})
        set_project_status(project["id"],"generated",assessment.level)
        project_document(project["id"],"overview","Overview",result.get("summary","Generated project"))
        project_document(project["id"],"requirements","Requirements",request["prompt"])
        project_artifact(project["id"],"generated-source","",{"file_count":result.get("file_count",0)})
        return {**result,"project_id":project["id"],"safety":assessment.as_dict(),"safeguard_model":body.safeguard_model}
    job_id=await jobs.start(body.model_dump(),runner)
    return {"ok":True,"job_id":job_id,"project_id":project["id"],"safety":assessment.as_dict(),"safeguard_model":body.safeguard_model}

@router.get("/api/generation/jobs/{job_id}")
async def get_generation_job(job_id:str):
    try:return jobs.get(job_id)
    except KeyError:raise HTTPException(404,"generation job not found")

@router.post("/api/generation/jobs/{job_id}/cancel")
async def cancel_generation_job(job_id:str):
    if not jobs.cancel(job_id): raise HTTPException(404,"active generation job not found")
    return {"ok":True,"job_id":job_id,"status":"cancelling"}
