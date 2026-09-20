"""Project Hub HTTP API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from project_hub import list_projects, get, details, search, create, document, decision, artifact, event, set_status
from generation.safety import assess

router=APIRouter(tags=["projects"])

class ProjectCreate(BaseModel):
    name: str = "generated-app"
    goal: str = ""
    prompt: str = ""
    stack: dict = Field(default_factory=dict)
    risk_level: str = "normal"

class SafetyRequest(BaseModel):
    prompt: str
    review_model: str = "Llama-3.1-8B-Instruct"

@router.get("/api/projects")
async def projects(q: str = "", limit: int = 100):
    return search(q,limit) if q.strip() else list_projects(limit)

@router.get("/api/projects/{project_id}")
async def project(project_id: str):
    value=details(project_id)
    if not value: raise HTTPException(404,"project not found")
    return value

@router.post("/api/projects")
async def project_create(body: ProjectCreate):
    return create(body.name,body.goal,body.prompt,body.stack,body.risk_level)

@router.get("/api/projects/{project_id}/timeline")
async def project_timeline(project_id: str):
    value=details(project_id)
    if not value: raise HTTPException(404,"project not found")
    return {"project_id":project_id,"events":value["events"]}

@router.post("/api/projects/{project_id}/documents")
async def project_document(project_id: str, body: dict):
    if not get(project_id): raise HTTPException(404,"project not found")
    document(project_id,str(body.get("kind","notes")),str(body.get("title","Untitled")),str(body.get("content","")))
    event(project_id,"document.updated","user","",{"kind":body.get("kind","notes"),"title":body.get("title","Untitled")})
    return {"ok":True}

@router.post("/api/projects/{project_id}/decisions")
async def project_decision(project_id: str, body: dict):
    if not get(project_id): raise HTTPException(404,"project not found")
    decision(project_id,str(body.get("decision","")),str(body.get("rationale","")),str(body.get("model","")))
    event(project_id,"decision.recorded","user",str(body.get("model","")),body)
    return {"ok":True}

@router.post("/api/projects/{project_id}/artifacts")
async def project_artifact(project_id: str, body: dict):
    if not get(project_id): raise HTTPException(404,"project not found")
    artifact(project_id,str(body.get("kind","artifact")),str(body.get("path","")),body.get("metadata") or {})
    return {"ok":True}

@router.post("/api/projects/{project_id}/status")
async def project_status(project_id: str, body: dict):
    if not get(project_id): raise HTTPException(404,"project not found")
    set_status(project_id,str(body.get("status","active")),str(body.get("risk_level")) if body.get("risk_level") else None)
    return get(project_id)

@router.post("/api/safety/assess")
async def safety_assess(body: SafetyRequest):
    return assess(body.prompt,body.review_model).as_dict()
