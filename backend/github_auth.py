"""GitHub App user-to-server OAuth flow with signed state."""
from __future__ import annotations
import hashlib,hmac,os,secrets,time
from urllib.parse import urlencode
import httpx\nimport jwt
import db
from credentials import set_secret,get_secret,delete_secret,available
def _cfg():
    return {"client_id":os.getenv("DREAMCODER_GITHUB_CLIENT_ID",""),"client_secret":os.getenv("DREAMCODER_GITHUB_CLIENT_SECRET",""),"callback":os.getenv("DREAMCODER_GITHUB_CALLBACK","http://127.0.0.1:8000/api/github/oauth/callback"),"secret":os.getenv("DREAMCODER_OAUTH_STATE_SECRET","")}
def configured(): c=_cfg(); return bool(c["client_id"] and c["client_secret"] and c["secret"])
def start_url():
    c=_cfg(); nonce=secrets.token_urlsafe(24); exp=int(time.time())+600; payload=f"{nonce}.{exp}"
    sig=hmac.new(c["secret"].encode(),payload.encode(),hashlib.sha256).hexdigest(); state=payload+"."+sig
    db.set_setting("github_oauth_state",state)
    return "https://github.com/login/oauth/authorize?"+urlencode({"client_id":c["client_id"],"redirect_uri":c["callback"],"state":state})
def verify_state(state):
    c=_cfg(); saved=db.get_setting("github_oauth_state","")
    if not state or not saved or not hmac.compare_digest(state,saved): return False
    try:
        payload,sig=state.rsplit(".",1); _,exp=payload.split(".",1)
        return int(exp)>=int(time.time()) and hmac.compare_digest(sig,hmac.new(c["secret"].encode(),payload.encode(),hashlib.sha256).hexdigest())
    except Exception:return False
async def exchange(code):
    c=_cfg()
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post("https://github.com/login/oauth/access_token",data={"client_id":c["client_id"],"client_secret":c["client_secret"],"code":code},headers={"Accept":"application/json"}); r.raise_for_status(); d=r.json()
    if "access_token" not in d: raise RuntimeError(d.get("error_description") or "GitHub OAuth failed")
    db.set_setting("github_oauth_token",""); set_secret("github_oauth_token",d["access_token"]) if available() else db.set_setting("github_oauth_token",d["access_token"]); db.set_setting("github_oauth_expires_at",str(time.time()+int(d.get("expires_in",28800)))); db.set_setting("github_oauth_refresh_token",d.get("refresh_token","")); db.set_setting("github_oauth_refresh_expires_at",str(time.time()+int(d.get("refresh_token_expires_in",15897600))))
    os.environ["GITHUB_TOKEN"]=d["access_token"]; return await user()
async def user():
    token=(get_secret("github_oauth_token") if available() else "") or db.get_setting("github_oauth_token","") or os.getenv("GITHUB_TOKEN","")
    if not token:return {"ok":False,"connected":False}
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get("https://api.github.com/user",headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"}); r.raise_for_status(); d=r.json()
    return {"ok":True,"connected":True,"login":d.get("login"),"avatar":d.get("avatar_url"),"token_expires_at":db.get_setting("github_oauth_expires_at","")}
async def installations():
    token=(get_secret("github_oauth_token") if available() else "") or db.get_setting("github_oauth_token","") or os.getenv("GITHUB_TOKEN","")
    if not token:return {"ok":False,"installations":[]}
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get("https://api.github.com/user/installations",headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}); r.raise_for_status(); d=r.json()
    return {"ok":True,"installations":[{"id":x["id"],"account":x.get("account",{}).get("login"),"target_type":x.get("target_type")} for x in d.get("installations",[])]}
async def repositories(installation_id=None):
    token=db.get_setting("github_oauth_token","") or os.getenv("GITHUB_TOKEN","")
    if not token:return {"ok":False,"repositories":[]}
    url=f"https://api.github.com/user/installations/{int(installation_id)}/repositories?per_page=100" if installation_id else "https://api.github.com/user/repos?per_page=100&sort=updated"
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get(url,headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"}); r.raise_for_status(); d=r.json()
    arr=d.get("repositories",d if isinstance(d,list) else [])
    return {"ok":True,"repositories":[{"full_name":x.get("full_name"),"private":x.get("private"),"default_branch":x.get("default_branch")} for x in arr]}
def disconnect():
    delete_secret("github_oauth_token") if available() else db.set_setting("github_oauth_token",""); db.set_setting("github_oauth_expires_at",""); os.environ.pop("GITHUB_TOKEN",None); return {"ok":True,"connected":False}

async def refresh():
    c=_cfg(); token=db.get_setting("github_oauth_refresh_token","")
    if not token:return {"ok":False,"error":"no refresh token"}
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post("https://github.com/login/oauth/access_token",data={"client_id":c["client_id"],"client_secret":c["client_secret"],"grant_type":"refresh_token","refresh_token":token},headers={"Accept":"application/json"}); r.raise_for_status(); d=r.json()
    if "access_token" not in d:return {"ok":False,"error":d.get("error_description","refresh failed")}
    db.set_setting("github_oauth_token",d["access_token"]); db.set_setting("github_oauth_expires_at",str(time.time()+int(d.get("expires_in",28800))))
    if d.get("refresh_token"): db.set_setting("github_oauth_refresh_token",d["refresh_token"])
    os.environ["GITHUB_TOKEN"]=d["access_token"]; return await user()

def app_configured():
    return bool(os.getenv("DREAMCODER_GITHUB_APP_ID") and (os.getenv("DREAMCODER_GITHUB_APP_PRIVATE_KEY") or os.getenv("DREAMCODER_GITHUB_APP_PRIVATE_KEY_FILE")))
def _app_jwt():
    key=os.getenv("DREAMCODER_GITHUB_APP_PRIVATE_KEY","")
    if not key:
        key=open(os.getenv("DREAMCODER_GITHUB_APP_PRIVATE_KEY_FILE"),"r",encoding="utf-8").read()
    now=int(time.time())
    return jwt.encode({"iat":now-30,"exp":now+540,"iss":os.getenv("DREAMCODER_GITHUB_APP_ID")},key,algorithm="RS256")
async def app_installation_token(installation_id:int):
    if not app_configured(): return {"ok":False,"error":"GitHub App is not configured"}
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.post(f"https://api.github.com/app/installations/{installation_id}/access_tokens",headers={"Authorization":f"Bearer {_app_jwt()}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}); r.raise_for_status(); d=r.json()
    token=d["token"]; set_secret("github_app_installation_token",token) if available() else db.set_setting("github_app_installation_token",token)
    db.set_setting("github_app_installation_id",str(installation_id)); db.set_setting("github_app_token_expires_at",d.get("expires_at",""))
    return {"ok":True,"installation_id":installation_id,"expires_at":d.get("expires_at")}
