from __future__ import annotations
import time
_state={"hf_remaining":None,"hf_limit":None,"hf_reset_at":None,"hf_last_status":None,"last_updated":None,"requests_this_session":0}

def _header(headers,key):
    for k,v in headers.items():
        if str(k).lower()==key.lower(): return v
    return None

def record_response(headers:dict,status_code:int)->None:
    def integer(v):
        try:return int(v)
        except (TypeError,ValueError):return None
    _state["hf_remaining"]=integer(_header(headers,"x-ratelimit-remaining"))
    _state["hf_limit"]=integer(_header(headers,"x-ratelimit-limit"))
    _state["hf_reset_at"]=integer(_header(headers,"x-ratelimit-reset"))
    _state["hf_last_status"]=status_code
    _state["last_updated"]=time.time()
    _state["requests_this_session"]+=1

def snapshot()->dict:
    out=dict(_state)
    out["hf_seconds_until_reset"]=max(0,out["hf_reset_at"]-time.time()) if out["hf_reset_at"] is not None else None
    out["hf_percent_remaining"]=(out["hf_remaining"]/out["hf_limit"]*100) if out["hf_remaining"] is not None and out["hf_limit"] else None
    try: from model_race import build_lanes_from_env
    except ImportError: from backend.model_race import build_lanes_from_env
    out["local_lanes"]=[{"name":l.name,"url":l.url,"model":l.model,"unlimited":True} for l in build_lanes_from_env() if l.kind=="ollama"]
    return out
