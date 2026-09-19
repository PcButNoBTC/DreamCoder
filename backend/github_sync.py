"""Atomic GitHub synchronization engine with optimistic concurrency and backups."""
from __future__ import annotations
import base64, hashlib, os
from dataclasses import dataclass
from typing import Any
import httpx

@dataclass
class GitHubSync:
    repo:str
    branch:str
    token:str
    enabled:bool=True
    timeout:float=30.0
    @classmethod
    def from_env(cls):
        token=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_APP_TOKEN") or ""
        return cls(os.getenv("DREAMCODER_GITHUB_REPO","").strip(),os.getenv("DREAMCODER_GITHUB_BRANCH","main").strip() or "main",token,os.getenv("DREAMCODER_GITHUB_AUTOSYNC","true").lower() not in {"0","false","no","off"})
    @property
    def configured(self): return bool(self.enabled and self.repo and self.token and "/" in self.repo)
    def status(self):
        return {"enabled":self.enabled,"configured":self.configured,"repo":self.repo or None,"branch":self.branch,"auth":bool(self.token),"mode":"atomic-autosync" if self.enabled else "manual","engine":"git-data-api"}
    def _headers(self):
        return {"Accept":"application/vnd.github+json","Authorization":f"Bearer {self.token}","X-GitHub-Api-Version":"2022-11-28"}
    async def _get_ref(self,client):
        u=f"https://api.github.com/repos/{self.repo}/git/ref/heads/{self.branch}"
        r=await client.get(u,headers=self._headers())
        if r.status_code!=200: return {"ok":False,"status_code":r.status_code,"error":r.text[:1000]}
        return {"ok":True,"sha":r.json()["object"]["sha"]}
    async def remote_head(self):
        if not self.configured: return {"ok":False,"reason":"not configured"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                return await self._get_ref(client)
        except Exception as e: return {"ok":False,"error":str(e)}
    async def test_connection(self):
        if not self.configured:return {"ok":False,"reason":"not configured"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r=await c.get(f"https://api.github.com/repos/{self.repo}",headers=self._headers())
                if r.status_code!=200:return {"ok":False,"status_code":r.status_code,"error":r.text[:500]}
                d=r.json(); ref=await self._get_ref(c)
                return {"ok":ref.get("ok",False),"repo":d.get("full_name"),"default_branch":d.get("default_branch"),"private":d.get("private"),"head_sha":ref.get("sha")}
        except Exception as e:return {"ok":False,"error":str(e)}
    @staticmethod
    def _path(path):
        p=path.replace("\\","/").lstrip("/")
        if not p or p.startswith(".git/") or ".." in p.split("/"): raise ValueError("invalid repository path")
        return p
    async def sync_files_atomic(self,files:list[dict[str,str]],message="DreamCoder atomic sync",expected_head:str|None=None)->dict[str,Any]:
        if not self.configured:return {"ok":False,"skipped":True,"reason":"GitHub autosync is not configured"}
        clean=[]; deletes=[]
        for item in files:
            path=self._path(item["path"])
            if item.get("deleted"): deletes.append(path)
            else: clean.append({"path":path,"content":str(item.get("content",""))})
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                ref=await self._get_ref(c)
                if not ref.get("ok"): return ref
                head=ref["sha"]
                if expected_head and expected_head!=head:
                    return {"ok":False,"conflict":True,"reason":"remote branch advanced","expected_head":expected_head,"remote_head":head}
                commit=await c.get(f"https://api.github.com/repos/{self.repo}/git/commits/{head}",headers=self._headers())
                if commit.status_code!=200:return {"ok":False,"status_code":commit.status_code,"error":commit.text[:1000]}
                base_tree=commit.json()["tree"]["sha"]
                elements=[]
                for item in clean:
                    elements.append({"path":item["path"],"mode":"100644","type":"blob","content":item["content"]})
                for path in deletes: elements.append({"path":path,"mode":"100644","type":"blob","sha":None})
                tree=await c.post(f"https://api.github.com/repos/{self.repo}/git/trees",headers=self._headers(),json={"base_tree":base_tree,"tree":elements})
                if tree.status_code!=201:return {"ok":False,"status_code":tree.status_code,"error":tree.text[:1500]}
                tree_sha=tree.json()["sha"]
                new=await c.post(f"https://api.github.com/repos/{self.repo}/git/commits",headers=self._headers(),json={"message":message,"tree":tree_sha,"parents":[head]})
                if new.status_code!=201:return {"ok":False,"status_code":new.status_code,"error":new.text[:1500]}
                new_sha=new.json()["sha"]
                update=await c.patch(f"https://api.github.com/repos/{self.repo}/git/refs/heads/{self.branch}",headers=self._headers(),json={"sha":new_sha,"force":False})
                if update.status_code!=200:
                    return {"ok":False,"conflict":update.status_code in {409,422},"status_code":update.status_code,"error":update.text[:1500],"new_commit":new_sha}
                return {"ok":True,"atomic":True,"branch":self.branch,"commit_sha":new_sha,"commit_url":new.json().get("html_url"),"changed":len(clean)+len(deletes),"deleted":deletes}
        except ValueError as e:return {"ok":False,"skipped":True,"reason":str(e)}
        except Exception as e:return {"ok":False,"error":str(e)}
    async def sync_file(self,path,content,message=None):
        return await self.sync_files_atomic([{"path":path,"content":content}],message or f"DreamCoder live sync: {path}")
    async def sync_files(self,files,message="DreamCoder live sync"):
        return await self.sync_files_atomic(files,message)
    async def sync_file_with_backup(self,root,path,content,message=None):
        result=await self.sync_file(path,content,message)
        if result.get("ok") or result.get("skipped"): return result
        if os.getenv("DREAMCODER_BACKUP_ON_SYNC_FAILURE","true").lower() in {"0","false","no","off"}: return result
        try:
            from backup_manager import write_backup
            result["backup"]=write_backup(root,path,content,reason=f"github sync failed: {result.get('error','unknown')}")
        except Exception as e: result["backup"]={"ok":False,"error":str(e)}
        return result
    async def delete_file(self,path,message=None): return await self.sync_files_atomic([{"path":path,"deleted":True}],message or f"DreamCoder live delete: {path}")
github_sync=GitHubSync.from_env()
