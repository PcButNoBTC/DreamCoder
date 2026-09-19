from __future__ import annotations
import httpx,os,workspace,git_workflow
def changed_files():
    r=workspace.git(["status","--porcelain=v1"])
    rows=[]
    for line in (r.get("stdout","") if r.get("ok") else "").splitlines():
        if len(line)>=4: rows.append({"index":line[0],"worktree":line[1],"path":line[3:]})
    return {"ok":r.get("ok",False),"files":rows,"raw":r.get("stdout","")}
async def create_agent_pr(repo,branch,title,body=""):
    token=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_APP_TOKEN")
    if not token:return {"ok":False,"error":"GitHub token unavailable"}
    async with httpx.AsyncClient(timeout=30) as c:
        r=await c.post(f"https://api.github.com/repos/{repo}/pulls",headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},json={"title":title,"head":branch,"base":os.getenv("DREAMCODER_GITHUB_BRANCH","main"),"body":body})
        return {"ok":r.status_code==201,"status_code":r.status_code,**r.json()}
