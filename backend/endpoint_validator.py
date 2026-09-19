from __future__ import annotations
from urllib.parse import urlparse
import httpx

def validate_host(url: str) -> str:
    raw=(url or "").strip()
    if not raw: raise ValueError("empty URL")
    low=raw.lower()
    for bad in ("file://","ftp://","gopher://","data:","javascript:","@"):
        if bad in low: raise ValueError(f"unsupported URL content: {bad}")
    p=urlparse(raw)
    if p.scheme not in ("http","https"): raise ValueError("URL scheme must be http or https")
    if not p.hostname: raise ValueError("URL hostname is required")
    try: port=p.port or 11434
    except ValueError as exc: raise ValueError("invalid URL port") from exc
    if not 1<=port<=65535: raise ValueError("URL port must be between 1 and 65535")
    if p.path not in ("","/"): raise ValueError("URL path must be empty or /")
    if p.query: raise ValueError("URL query strings are not allowed")
    if p.fragment: raise ValueError("URL fragments are not allowed")
    return f"{p.scheme}://{p.hostname}:{port}"

async def fetch_models(url: str, timeout: float=10.0) -> list[dict]:
    normalized=validate_host(url)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r=await client.get(normalized+"/api/tags")
            if r.status_code!=200: raise ValueError(f"Ollama returned {r.status_code}")
            return r.json().get("models",[])
    except ValueError: raise
    except httpx.HTTPError as exc: raise ValueError(f"Could not reach {normalized}: {exc}") from exc

def score_model(model: dict)->int:
    import re
    name=str(model.get("name","")); d=model.get("details",{}) or {}
    m=re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([MB])?",str(d.get("parameter_size","")),re.I)
    pb=0 if not m else (float(m.group(1))/1000 if (m.group(2) or "").upper()=="M" else float(m.group(1)))
    q=str(d.get("quantization_level","")); family=str(d.get("family","")).lower()
    score=50; n=name.lower()
    if any(k in n for k in ("coder","code","starcoder","codegen")): score+=40
    if any(k in n for k in ("embed","nomic-embed","bge","e5-","gte-")): score-=100
    if pb>=32: score+=25
    elif pb>=14: score+=20
    elif pb>=7: score+=15
    elif pb>=3: score+=5
    else: score-=10
    if q.upper().startswith(("Q8","F16","FP16")): score+=10
    elif q.upper().startswith(("Q5","Q6")): score+=5
    elif q.upper().startswith(("Q2","Q3")): score-=15
    if family in ("qwen2","llama","deepseek2","mistral"): score+=5
    if model.get("remote_model"): score+=5
    return score

def rank_models(models:list[dict])->list[dict]:
    out=[]
    for m in models:
        s=score_model(m)
        if s<0: continue
        d=m.get("details",{}) or {}
        out.append({"name":m.get("name",""),"size":m.get("size",0),"parameter_size":d.get("parameter_size",""),"quantization":d.get("quantization_level",""),"family":d.get("family",""),"remote":bool(m.get("remote_model")),"score":s})
    return sorted(out,key=lambda x:x["score"],reverse=True)

def pick_primary(ranked:list[dict])->dict|None:
    return ranked[0] if ranked else None
