"""Project-level model routing preferences API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import project_models
from model_lab import ROLES

router=APIRouter(tags=["project-models"])

class ModelPreference(BaseModel):
    role:str
    model_id:str=""
    mode:str="auto"

@router.get("/api/projects/{project_id}/models")
async def list_project_models(project_id:str):
    return {"project_id":project_id,"roles":list(ROLES),"preferences":project_models.list_preferences(project_id)}

@router.post("/api/projects/{project_id}/models")
async def set_project_model(project_id:str, body:ModelPreference):
    try:
        return project_models.set_preference(project_id,body.role,body.model_id,body.mode)
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@router.get("/api/projects/{project_id}/models/{role}")
async def resolve_project_model(project_id:str, role:str):
    try:
        return {"project_id":project_id,"role":role,**project_models.resolve(project_id,role)}
    except ValueError as exc:
        raise HTTPException(400,str(exc))
