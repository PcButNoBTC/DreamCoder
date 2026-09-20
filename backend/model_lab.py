"""Evidence-backed Model Lab, registry, benchmarks, and routing."""
from __future__ import annotations
import asyncio, json, re, time, uuid, tempfile, os
from pathlib import Path
from sandbox import run as sandbox_run

_BENCHMARK_CONCURRENCY = max(1, int(os.getenv("DREAMCODER_MODEL_LAB_CONCURRENCY", "2")))
_BENCHMARK_TIMEOUT = max(10, int(os.getenv("DREAMCODER_MODEL_LAB_TIMEOUT", "180")))
_BENCHMARK_SEMAPHORE = asyncio.Semaphore(_BENCHMARK_CONCURRENCY)
from dataclasses import asdict, dataclass
from typing import Any
import db

ROLES = ("planning","generation","debugging","testing","documentation","repository_reasoning","tool_use","review")

@dataclass(frozen=True)
class Benchmark:
    id: str
    category: str
    role: str
    prompt: str
    required_markers: tuple[str, ...] = ()
    code_language: str = ""

BENCHMARKS = (
    Benchmark("general-structured-output","structured_output","planning","Return JSON with keys plan, risks, and tests for a small calculator web app. No markdown.",("plan","risks","tests")),
    Benchmark("python-implementation","coding","generation","Write a minimal Python function named fibonacci(n) that returns the first n Fibonacci numbers. Return only a Python code block.",("fibonacci",),"python"),
    Benchmark("typescript-debugging","debugging","debugging","Explain the bug in this TypeScript expression: const total = items.map(x => x.price).reduce((a,b) => a + b); Then give a corrected expression.",("reduce","price")),
    Benchmark("test-design","testing","testing","Design three focused unit tests for a function that parses an ISO date string. Include normal, invalid, and timezone cases.",("normal","invalid","timezone")),
    Benchmark("documentation","documentation","documentation","Write concise API documentation for GET /api/projects/{project_id}, including purpose, path parameter, and a 404 response.",("GET","404","project")),
    Benchmark("repository-reasoning","repository_reasoning","repository_reasoning","Given an API layer, database layer, model adapter layer, and frontend, describe a safe change plan for adding a model registry. Identify dependencies and validation steps.",("database","frontend","validation")),
    Benchmark("tool-use-plan","tool_use","tool_use","Describe the sequence of tool actions an IDE agent should use to add a small feature, run tests, inspect failures, and produce a reviewable change. Do not execute anything.",("tests","failure","review")),
    Benchmark("typescript-implementation","coding","generation","Write a TypeScript function named clamp(value,min,max) that returns the value limited to the inclusive range. Return only a TypeScript code block.",("clamp",),"typescript"),
    Benchmark("react-component-design","frontend","generation","Describe a small React component that renders a list of projects with an empty state and a loading state. Include props and accessibility considerations.",("projects","loading","accessibility")),
    Benchmark("api-contract","api","planning","Design a REST endpoint contract for creating a project. Include method, path, request fields, success response, and validation errors.",("POST","request","validation")),
    Benchmark("sql-design","database","planning","Design a normalized SQL schema for projects and project events. Identify primary keys and the project-to-events relationship.",("PRIMARY KEY","project","events")),
    Benchmark("docker-build-design","container","testing","Describe a minimal Docker build strategy for a Python web service that keeps runtime privileges low and does not require network access at runtime.",("read-only","non-root","network")),
    Benchmark("git-workflow","git","tool_use","Describe a safe Git workflow for a feature branch: inspect status, make a change, run tests, review the diff, commit, and open a pull request.",("status","tests","diff")),
    Benchmark("boundary-consistency","boundary","review","Explain how an AI development platform should evaluate ambiguous dual-use software requests while preserving legitimate benign development. Focus on consistent classification, evidence, and transparent routing.",("classification","evidence","routing")),
)

def _conn():
    return db.get_conn()

def _row(row):
    if not row: return None
    x=dict(row); x["metadata"]=json.loads(x.pop("metadata_json") or "{}"); return x

def register(model_id:str, provider:str, name:str="", revision:str="", metadata:dict[str,Any]|None=None):
    now=time.time(); conn=_conn()
    conn.execute("""INSERT INTO model_registry(id,provider,name,revision,status,metadata_json,created_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,name=excluded.name,
    revision=excluded.revision,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
    (model_id.strip(),provider,name or model_id.split("/")[-1],revision,"candidate",json.dumps(metadata or {}),now,now))
    conn.commit(); row=conn.execute("SELECT * FROM model_registry WHERE id=?",(model_id.strip(),)).fetchone(); conn.close()
    return _row(row)

def list_models():
    conn=_conn(); rows=conn.execute("SELECT * FROM model_registry ORDER BY updated_at DESC").fetchall(); conn.close()
    return [_row(r) for r in rows]

def get_model(model_id):
    conn=_conn(); row=conn.execute("SELECT * FROM model_registry WHERE id=?",(model_id,)).fetchone(); conn.close(); return _row(row)

def _score(b:Benchmark,text:str):
    lower=text.lower(); hits=sum(1 for m in b.required_markers if m.lower() in lower)
    marker_score=hits/max(1,len(b.required_markers)); format_score=1.0
    if b.category=="structured_output":
        try:
            parsed=json.loads(text); format_score=1.0 if all(k in parsed for k in b.required_markers) else .35
        except Exception: format_score=0.0
    elif b.code_language=="python":
        fence=chr(96)*3
        match=re.search(fence+r"(?:python)?\s*(.*?)"+fence,text,re.S|re.I)
        if match:
            try: compile(match.group(1),"<benchmark>","exec")
            except SyntaxError: format_score=.25
        else: format_score=0.0
    score=round(.7*marker_score+.3*format_score,4)
    return score,{"marker_hits":hits,"marker_total":len(b.required_markers),"format_score":format_score}

async def run_benchmark(model_id, router, benchmark_id=None, suite_version="v1", repeats: int = 1):
    selected=[b for b in BENCHMARKS if benchmark_id is None or b.id==benchmark_id]
    if not selected:
        raise ValueError("unknown benchmark")
    run_id=uuid.uuid4().hex
    out=[]
    repeats=max(1,min(int(repeats),5))
    from models.base import ChatContext
    for repeat_index in range(repeats):
        for b in selected:
            started=time.perf_counter()
            response=""
            error=""
            try:
                async with _BENCHMARK_SEMAPHORE:
                    response=(await asyncio.wait_for(
                        router.chat(model_id,ChatContext(message=b.prompt,mode="analysis")),
                        timeout=_BENCHMARK_TIMEOUT
                    )).content or ""
            except Exception as exc:
                error=str(exc)
            latency=round((time.perf_counter()-started)*1000,2)
            score,evidence=_score(b,response) if not error else (0.0,{"error":error})
            execution_ok=evidence.get("format_score",0)>=1.0 if b.code_language else None
            if b.code_language == "python" and response and not error:
                fence=chr(96)*3
                match=re.search(fence+r"(?:python)?\s*(.*?)"+fence,response,re.S|re.I)
                if match:
                    with tempfile.TemporaryDirectory(prefix="dreamcoder-bench-") as td:
                        path=Path(td)/"benchmark.py"
                        path.write_text(match.group(1),encoding="utf-8")
                        execution=sandbox_run(td,"python benchmark.py",timeout=30,network=False)
                        execution_ok=bool(execution.get("ok"))
                        evidence["execution"]={"ok":execution_ok,"sandboxed":bool(execution.get("sandboxed")),"exit_code":execution.get("exit_code")}
                        score=round(min(1.0,score+0.15),4) if execution_ok else round(score*0.75,4)
            passed=score>=.75
            conn=_conn()
            conn.execute("""INSERT INTO model_benchmarks
            (model_id,benchmark_id,suite_version,run_id,category,role,pass,score,latency_ms,execution_ok,evidence_json,created_at,model_revision)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (model_id,b.id,suite_version,run_id,b.category,b.role,int(passed),score,latency,
             None if execution_ok is None else int(execution_ok),
             json.dumps({**evidence,"response_length":len(response),"repeat_index":repeat_index}),
             time.time(),(get_model(model_id) or {}).get("revision","")))
            conn.commit()
            conn.close()
            out.append({"run_id":run_id,"model_id":model_id,"benchmark_id":b.id,"category":b.category,"role":b.role,
                        "pass":passed,"score":score,"latency_ms":latency,"execution_ok":execution_ok,
                        "evidence":{**evidence,"repeat_index":repeat_index}})
    return out

def results(model_id=None,limit=200):
    conn=_conn()
    rows=conn.execute("SELECT * FROM model_benchmarks WHERE model_id=? ORDER BY id DESC LIMIT ?",(model_id,limit)).fetchall() if model_id else conn.execute("SELECT * FROM model_benchmarks ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    conn.close(); out=[]
    for row in rows:
        x=dict(row); x["pass"]=bool(x["pass"]); x["evidence"]=json.loads(x.pop("evidence_json") or "{}"); out.append(x)
    return out

def profile(model_id):
    rows=results(model_id,1000)
    cutoff=time.time()-30*24*60*60
    fresh=[r for r in rows if float(r["created_at"])>=cutoff]
    by_role={}
    for row in (fresh or rows):
        by_role.setdefault(row["role"],[]).append(float(row["score"]))
    roles={k:round(sum(v)/len(v),4) for k,v in by_role.items()}
    eligible=len(fresh)>=3 and bool(roles)
    last=max((float(r["created_at"]) for r in rows),default=0)
    status="eligible" if eligible else ("stale" if last and last<cutoff else "candidate")
    conn=_conn()
    conn.execute("UPDATE model_registry SET status=?,last_benchmark_at=?,updated_at=? WHERE id=?",(status,last or None,time.time(),model_id))
    conn.commit(); conn.close()
    return {"model_id":model_id,"roles":roles,"eligibility":{"eligible":eligible,"minimum_fresh_evidence":3,"role_evidence":sorted(roles),"policy_gate":"deterministic","freshness_days":30},"runs":len(rows),"fresh_runs":len(fresh),"status":status}

def route_candidates(role,candidates=None):
    ids=candidates or [m["id"] for m in list_models()]; ranked=[]
    for mid in ids:
        p=profile(mid); ranked.append({"model_id":mid,"role":role,"score":p["roles"].get(role,0.0),"eligible":p["eligibility"]["eligible"],"evidence_runs":p["runs"]})
    return sorted(ranked,key=lambda x:(not x["eligible"],-x["score"],-x["evidence_runs"]))

def route(role,candidates=None):
    for option in route_candidates(role,candidates):
        if option["eligible"] and option["score"]>0: return {**option,"source":"benchmark_evidence"}
    return {"model_id":None,"role":role,"score":0.0,"eligible":False,"source":"no_evidence"}

async def evaluator_summary(model_id, router, evaluator_model="Local Model"):
    p=profile(model_id)
    from models.base import ChatContext
    prompt=("Analyze this structured benchmark profile for model routing. "
            "Do not invent measurements. Summarize strengths, evidence gaps, and "
            "appropriate roles. The evaluator is advisory; deterministic eligibility "
            "and measured results remain authoritative.\\n\\n"+json.dumps(p))
    try:
        result=await router.chat(evaluator_model,ChatContext(message=prompt,mode="analysis"))
        summary=str(result.content)
        conn=_conn()
        conn.execute("INSERT INTO model_evaluations(model_id,evaluator_model,profile_json,summary,created_at) VALUES(?,?,?,?,?)",
                     (model_id,evaluator_model,json.dumps(p),summary,time.time()))
        conn.commit(); conn.close()
        return {"ok":True,"evaluator_model":evaluator_model,"summary":summary,"measured_eligibility":p["eligibility"]}
    except Exception as exc:
        return {"ok":False,"evaluator_model":evaluator_model,"error":str(exc)}

def benchmark_catalog():
    return [asdict(b) for b in BENCHMARKS]

def evaluations(model_id=None, limit=100):
    conn=_conn()
    if model_id:
        rows=conn.execute("SELECT * FROM model_evaluations WHERE model_id=? ORDER BY id DESC LIMIT ?",(model_id,limit)).fetchall()
    else:
        rows=conn.execute("SELECT * FROM model_evaluations ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def repeatability(model_id: str, benchmark_id: str | None = None, limit: int = 50):
    rows=results(model_id,limit)
    if benchmark_id:
        rows=[r for r in rows if r["benchmark_id"]==benchmark_id]
    groups={}
    for r in rows:
        groups.setdefault(r["benchmark_id"],[]).append(float(r["score"]))
    out={}
    for bid,scores in groups.items():
        mean=sum(scores)/len(scores)
        variance=sum((x-mean)**2 for x in scores)/len(scores)
        out[bid]={"runs":len(scores),"mean":round(mean,4),"min":round(min(scores),4),"max":round(max(scores),4),"stddev":round(variance**0.5,4)}
    return out

def revision_regression(model_id: str):
    rows=results(model_id,2000)
    groups={}
    for r in rows:
        rev=r.get("model_revision","") or "unversioned"
        groups.setdefault(rev,[]).append(float(r["score"]))
    return {rev:{"runs":len(scores),"mean_score":round(sum(scores)/len(scores),4),"min_score":round(min(scores),4)} for rev,scores in groups.items()}
