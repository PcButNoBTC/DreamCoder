"""Model Lab and benchmark-driven routing API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
import os
import model_lab as _model_lab_impl
from pydantic import BaseModel, Field
import model_lab

router=APIRouter(tags=["model-lab"])

def _admin_guard(request: Request) -> None:
    expected=(os.getenv("DREAMCODER_MODEL_LAB_ADMIN_TOKEN") or "").strip()
    if not expected:
        return
    if request.headers.get("X-DreamCoder-Admin-Token","") != expected:
        raise HTTPException(403,"model lab admin token required")

class ModelRegister(BaseModel):
    model_id:str
    provider:str="huggingface"
    name:str=""
    revision:str=""
    metadata:dict=Field(default_factory=dict)

class BenchmarkRun(BaseModel):
    model_id:str
    benchmark_id:str|None=None
    suite_version:str="v1"
    repeats:int=1

class RouteRequest(BaseModel):
    role:str
    candidates:list[str]=Field(default_factory=list)

@router.get("/api/models/registry")
async def registry():
    return {"models":model_lab.list_models(),"roles":list(model_lab.ROLES)}

@router.post("/api/models/registry")
async def register_model(request: Request, body:ModelRegister):
    _admin_guard(request)
    if body.provider not in {"huggingface","ollama","openai-compatible","local","mock"}:
        raise HTTPException(400,"unsupported provider")
    return model_lab.register(body.model_id,body.provider,body.name,body.revision,body.metadata)

@router.get("/api/models/benchmarks")
async def benchmarks():
    return {"suite_version":"v1","benchmarks":model_lab.benchmark_catalog()}

@router.post("/api/models/benchmarks/run")
async def run_benchmarks(request: Request, body:BenchmarkRun):
    _admin_guard(request)
    from main import router as ai_router
    try:
        model_lab.register(body.model_id, body.model_id.split(":",1)[0] if ":" in body.model_id else ("huggingface" if "/" in body.model_id else "local"))
        return {"ok":True,"results":await model_lab.run_benchmark(body.model_id,ai_router,body.benchmark_id,body.suite_version,body.repeats)}
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except Exception as exc:
        raise HTTPException(502,f"benchmark failed: {exc}")

@router.post("/api/models/evaluate")
async def evaluate_model(request: Request, body:dict):
    _admin_guard(request)
    from main import router as ai_router
    model_id=str(body.get("model_id","")).strip()
    if not model_id: raise HTTPException(400,"model_id required")
    return await model_lab.evaluator_summary(model_id,ai_router,str(body.get("evaluator_model","Local Model")))

@router.get("/api/models/benchmarks/results")
async def benchmark_results(model_id:str|None=None,limit:int=200):
    return {"results":model_lab.results(model_id,max(1,min(limit,1000)))}

@router.get("/api/models/{model_id:path}/profile")
async def model_profile(model_id:str):
    return model_lab.profile(model_id)

@router.post("/api/models/route")
async def route_model(body:RouteRequest):
    if body.role not in model_lab.ROLES:
        raise HTTPException(400,"unknown routing role")
    return model_lab.route(body.role,body.candidates or None)

@router.get("/api/models/evaluations")
async def evaluations(model_id: str | None = None, limit: int = 100):
    return {"evaluations": model_lab.evaluations(model_id, max(1, min(limit, 500)))}

@router.get("/api/models/observability")
async def observability():
    return {
        "registry": model_lab.list_models(),
        "recent_results": model_lab.results(limit=100),
        "evaluations": model_lab.evaluations(limit=50),
        "resource_limits": {"benchmark_concurrency": _model_lab_impl._BENCHMARK_CONCURRENCY, "benchmark_timeout_seconds": _model_lab_impl._BENCHMARK_TIMEOUT},
    }

@router.get("/api/models/repeatability")
async def model_repeatability(model_id: str, benchmark_id: str | None = None):
    return {"model_id":model_id,"repeatability":model_lab.repeatability(model_id,benchmark_id)}

@router.get("/api/models/regression")
async def model_regression(model_id: str):
    return {"model_id":model_id,"revisions":model_lab.revision_regression(model_id)}

@router.post("/api/models/discover")
async def discover_models(request: Request):
    _admin_guard(request)
    from main import router as ai_router
    discovered=await ai_router.list_models()
    registered=[]
    for item in discovered:
        model_id=str(item.get("id","")).strip()
        if not model_id:
            continue
        registered.append(model_lab.register(
            model_id,
            str(item.get("provider","mock")),
            str(item.get("name","")),
            "",
            {"status":item.get("status"),"real":bool(item.get("real"))}
        ))
    return {"models":registered,"discovered":discovered}

@router.get("/api/models/{model_id:path}/health")
async def model_health(model_id:str):
    from main import router as ai_router
    model=ai_router.get_model(model_id)
    return {"model_id":model_id,"health":await model.health_check()}
