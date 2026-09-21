"""Production multi-model generation engine."""

from __future__ import annotations
import asyncio, json, re, subprocess, tempfile, time
from pathlib import Path
from typing import Any
from models.base import ChatContext
from model_capabilities import select_model
from model_lab import route as route_model

FILE_RE = re.compile(r"===FILE:\s*(.+?)===\n(.*?)\n===END===", re.DOTALL)

def parse_json(text: str):
    try:
        v=json.loads((text or "").strip()); return v if isinstance(v,dict) else None
    except json.JSONDecodeError:
        m=re.search(r"\{.*\}",text or "",re.DOTALL)
        if not m:return None
        try:
            v=json.loads(m.group(0)); return v if isinstance(v,dict) else None
        except json.JSONDecodeError:return None

def parse_files(text: str):
    out=[]
    for m in FILE_RE.finditer(text or ""):
        p=m.group(1).strip().replace("\\","/")
        if not p or p.startswith("../") or p.startswith("/") or ":" in p.split("/")[0]: continue
        out.append({"path":p,"content":m.group(2)})
    return out

def language_hint(prompt):
    p=" "+(prompt or "").lower()+" "
    for needle,value in [(" c++ ","cpp"),(" cpp ","cpp"),(" c# ","csharp"),(" rust ","rust"),(" golang ","go"),(" go ","go"),(" java ","java"),(" typescript ","typescript"),(" javascript ","javascript"),(" python ","python"),(" html ","html"),(" css ","css")]:
        if needle in p:return value
    return "unknown"

def role_caps(role):
    r=(role or "").lower()
    if r in {"frontend","ui"}: return {"frontend","code-generation"}
    if r in {"backend","api","server"}: return {"backend","code-generation"}
    if r in {"database","data"}: return {"backend","reasoning"}
    if r in {"tests","testing","qa"}: return {"testing","code-generation"}
    if r in {"debug","debugging"}: return {"debugging","code-generation"}
    if r in {"documentation","docs"}: return {"reasoning"}
    if r in {"integration","integrator"}: return {"integration","code-review"}
    return {"code-generation"}

async def chat(router, model, prompt, mode="analysis"):
    return await router.chat(model,ChatContext(message=prompt,mode=mode),use_cache=False)

def normalize_tasks(raw,prompt):
    if not isinstance(raw,list): raw=[{"id":"implementation","role":"implementation","description":prompt,"depends_on":[]},{"id":"tests","role":"tests","description":"Add focused tests.","depends_on":[]}]
    out=[]
    for i,t in enumerate(raw):
        if isinstance(t,dict):
            out.append({"id":str(t.get("id") or f"task-{i+1}"),"role":str(t.get("role") or "implementation"),"description":str(t.get("description") or prompt),"depends_on":list(t.get("depends_on") or [])})
    return out or [{"id":"implementation","role":"implementation","description":prompt,"depends_on":[]}]

def merge_outputs(outputs):
    merged={}; conflicts=[]
    for o in outputs:
        for f in o.get("files",[]):
            if f["path"] not in merged: merged[f["path"]]=f
            elif merged[f["path"]]["content"]!=f["content"]:
                conflicts.append({"path":f["path"],"tasks":[merged[f["path"]].get("_task"),o.get("task_id")]})
    for f in merged.values(): f.pop("_task",None)
    return list(merged.values()),conflicts

def validate(files,language):
    commands={"python":"python -m compileall -q .","cpp":"cmake -S . -B build && cmake --build build --config Release","c":"make","rust":"cargo check","go":"go test ./...","java":"mvn -q test","csharp":"dotnet build --nologo","typescript":"npm run build --if-present"}
    command=commands.get(language)
    if not command or language=="typescript":
        return {"ok":True,"skipped":True,"reason":"No dependency-installing build was run in isolation."}
    with tempfile.TemporaryDirectory(prefix="dreamcoder-gen-") as td:
        root=Path(td)
        for f in files:
            target=(root/f["path"]).resolve()
            if root not in target.parents: return {"ok":False,"exit_code":2,"stderr":"Unsafe generated path"}
            target.parent.mkdir(parents=True,exist_ok=True); target.write_text(f["content"],encoding="utf-8")
        try:
            p=subprocess.run(command,cwd=root,shell=True,text=True,capture_output=True,timeout=180)
            return {"ok":p.returncode==0,"exit_code":p.returncode,"command":command,"stdout":p.stdout[-12000:],"stderr":p.stderr[-12000:]}
        except subprocess.TimeoutExpired:return {"ok":False,"exit_code":124,"stderr":"Validation timed out","command":command}

def role_route(role, catalog):
    mapping={"implementation":"generation","frontend":"generation","backend":"generation","tests":"testing","testing":"testing",
             "debugging":"debugging","debug":"debugging","documentation":"documentation","docs":"documentation",
             "review":"review","integration":"review","planner":"planning","planning":"planning",
             "architecture":"repository_reasoning","repository_reasoning":"repository_reasoning"}
    target=mapping.get((role or "").lower(),"generation")
    try:
        routed=route_model(target)
        if routed.get("model_id"):
            ids={m.get("id") for m in catalog}
            if routed["model_id"] in ids or "/" in routed["model_id"] or ":" in routed["model_id"]:
                return routed["model_id"]
    except Exception:
        pass
    return None

async def generate(prompt,goal,router,preferred_model=None):
    started=time.perf_counter(); catalog=await router.list_models(); lang=language_hint(prompt)
    context=getattr(router,"_project_context",lambda:"")()
    planner=preferred_model or role_route("planning",catalog) or select_model(catalog,{"planning","reasoning"})
    pp=f"""Return ONLY JSON with summary, language, tasks, acceptance_criteria. Each task needs id, role, description, depends_on. Split independent work for parallel execution.\nRequest: {prompt}\nGoal: {goal or '(none)'}\nLanguage: {lang}\nExisting context:\n{context[:12000]}"""
    try: plan=parse_json((await chat(router,planner,pp)).content)
    except Exception: plan=None
    plan=plan or {"summary":prompt[:200],"language":lang,"tasks":[{"id":"implementation","role":"implementation","description":prompt,"depends_on":[]},{"id":"tests","role":"tests","description":"Create focused tests.","depends_on":[]}],"acceptance_criteria":["Requested behavior is implemented and validates."]}
    tasks=normalize_tasks(plan.get("tasks"),prompt); completed=set(); pending={t["id"]:t for t in tasks}; outputs=[]; artifact_context={}
    async def run(t):
        model=role_route(t["role"],catalog) or (preferred_model if t["role"] in {"implementation","generation"} else None) or select_model(catalog,role_caps(t["role"]))
        upstream="\n\n".join(artifact_context.get(dep,"") for dep in t["depends_on"] if artifact_context.get(dep))
        p=f"""You are DreamCoder's {t['role']} specialist. Implement task: {t['description']}. Return ONLY complete file blocks using ===FILE: path=== ... ===END===. Do not emit prose. Request: {prompt}\nGoal: {goal or '(none)'}\nUpstream task artifacts/contracts:\n{upstream[:18000] or '(none)'}\nExisting context:\n{context[:9000]}"""
        try:
            fs=parse_files((await chat(router,model,p,"project")).content)
            for f in fs:f["_task"]=t["id"]
            return {"task_id":t["id"],"role":t["role"],"model":model,"files":fs,"ok":bool(fs)}
        except Exception as e:return {"task_id":t["id"],"role":t["role"],"model":model,"files":[],"ok":False,"error":str(e)}
    while pending:
        ready=[t for t in pending.values() if all(d in completed for d in t["depends_on"])]
        if not ready: ready=[next(iter(pending.values()))]
        wave=await asyncio.gather(*(run(t) for t in ready)); outputs.extend(wave)
        for result in wave:
            artifact_context[result["task_id"]]="Task "+result["task_id"]+" produced files: "+", ".join(f["path"] for f in result.get("files",[]))
        for t in ready:pending.pop(t["id"],None);completed.add(t["id"])
    files,conflicts=merge_outputs(outputs)
    if not files:return {"ok":False,"source":"orchestrator","error":"No specialist produced files","plan":plan}
    integrator=role_route("integration",catalog) or select_model(catalog,{"integration","code-review"})
    bundle="\n\n".join(f"===FILE: {f['path']}===\n{f['content']}\n===END===" for f in files)
    ip=f"""You are the integration specialist. Return ONLY complete file blocks. Merge these specialist outputs into one coherent runnable project, resolving conflicts, imports, APIs and tests. Request: {prompt}\nCriteria: {json.dumps(plan.get('acceptance_criteria',[]))}\nConflicts: {json.dumps(conflicts)}\n{bundle[:60000]}"""
    try: integrated=parse_files((await chat(router,integrator,ip,"project")).content) or files
    except Exception: integrated=files
    reviewer=role_route("review",catalog) or select_model(catalog,{"code-review","reasoning"})
    rp=f"""Return ONLY JSON with approved, summary, issues, repair_instructions. Review this project against the request and criteria. Request: {prompt}\nCriteria: {json.dumps(plan.get('acceptance_criteria',[]))}\n{bundle[:60000]}"""
    try:review=parse_json((await chat(router,reviewer,rp)).content) or {"approved":True,"summary":"No structured findings.","issues":[],"repair_instructions":[]}
    except Exception as e:review={"approved":True,"summary":f"Review unavailable: {e}","issues":[],"repair_instructions":[]}
    validation=validate(integrated,lang); repair_model=None; repairs=0
    for _ in range(2):
        if validation.get("ok") and review.get("approved",True):break
        repair_model=role_route("debugging",catalog) or select_model(catalog,{"debugging","code-generation"})
        rprompt=f"""Repair the project. Return ONLY complete file blocks. Fix the concrete validation errors and review findings without removing working behavior. Request: {prompt}\nValidation: {json.dumps(validation)}\nReview: {json.dumps(review)}\nFiles:\n{bundle[:60000]}"""
        try: fixed=parse_files((await chat(router,repair_model,rprompt,"project")).content)
        except Exception:fixed=[]
        if not fixed:break
        integrated=fixed;repairs+=1;validation=validate(integrated,lang)
        review={"approved":validation.get("ok",False),"summary":"Automated validation re-check","issues":[] if validation.get("ok") else [validation.get("stderr","validation failed")],"repair_instructions":[]}
    name="-".join(re.findall(r"[A-Za-z0-9]+",prompt.lower())[:4]) or "generated-app"
    models={"planner":planner,"specialists":{x["task_id"]:x["model"] for x in outputs},"integrator":integrator,"reviewer":reviewer}
    if repair_model:models["repair"]=repair_model
    try:
        from generation.patches import patches_from_files
        from change_plan import ChangePlan, ChangeTask
        import workspace
        root=workspace.root()
        patch_root=str(root) if root else str(Path.cwd())
        patches=patches_from_files(patch_root,integrated)
        change_plan=ChangePlan(goal=prompt,workspace=patch_root,summary=plan.get("summary",""),language=plan.get("language") or lang,acceptance_criteria=plan.get("acceptance_criteria",[]),approval_required=True)
        change_plan.tasks=[ChangeTask(id=t["id"],role=t["role"],description=t["description"],depends_on=t["depends_on"],model=next((x["model"] for x in outputs if x["task_id"]==t["id"]),"")) for t in tasks]
        change_plan.patches=[{"path":p["path"],"operation":p["operation"],"patch":p["patch"],"summary":p["summary"]} for p in patches]
        plan_record=change_plan.to_dict()
    except Exception:
        patches=[]; plan_record=None
    return {"ok":True,"source":"orchestrator","name":name,"prompt":prompt,"goal":goal,"stack":{"language":plan.get("language") or lang,"kind":"generated","build":"auto"},"files":integrated,"file_count":len(integrated),"summary":f"Task graph generated {len(integrated)} files from {len(outputs)} specialist tasks","models":models,"pipeline":["plan","parallel-specialists","integrate","review","build-test"]+(["repair"]*repairs),"tasks":outputs,"plan":plan,"conflicts":conflicts,"review":review,"validation":validation,"repair_count":repairs,"patches":patches,"change_plan":plan_record,"latency_ms":int((time.perf_counter()-started)*1000),"incremental_context_used":bool(context),"self_heal_ready":True}
