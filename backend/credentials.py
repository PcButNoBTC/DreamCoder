"""OS credential storage abstraction. Uses keyring when installed; never returns secrets to the UI."""
from __future__ import annotations
import os
from typing import Any
try:
    import keyring
except Exception:
    keyring=None
SERVICE="DreamCoder"
def available()->bool: return keyring is not None
def set_secret(name:str,value:str)->dict[str,Any]:
    if not name or "/" in name: return {"ok":False,"error":"invalid credential name"}
    if keyring is None:
        return {"ok":False,"error":"keyring package is not installed"}
    keyring.set_password(SERVICE,name,value)
    return {"ok":True,"name":name,"stored":True}
def get_secret(name:str)->str:
    return keyring.get_password(SERVICE,name) if keyring else ""
def has_secret(name:str)->bool:
    return bool(keyring and keyring.get_password(SERVICE,name))
def delete_secret(name:str)->dict[str,Any]:
    if not keyring:return {"ok":False,"error":"keyring package is not installed"}
    try:keyring.delete_password(SERVICE,name)
    except Exception:pass
    return {"ok":True,"name":name}
def status()->dict[str,Any]:
    return {"available":available(),"github_token":has_secret("github_token") if keyring else False,"hf_token":has_secret("hf_token") if keyring else False}
