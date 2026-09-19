from __future__ import annotations
import re
import workspace
def run(args,timeout=180):
    if not args:return {"ok":False,"error":"missing git operation"}
    return workspace.git(args,timeout=timeout)
def status(): return run(["status","--porcelain=v1","--branch"])
def branches(): return run(["branch","--all","--no-color"])
def stage(paths): return run(["add","--",*paths])
def unstage(paths): return run(["restore","--staged","--",*paths])
def commit(message): return run(["commit","-m",message])
def create_branch(name,switch=True):
    if not re.fullmatch(r"[A-Za-z0-9._/-]+",name or ""): return {"ok":False,"error":"invalid branch name"}
    return run(["switch","-c",name] if switch else ["branch",name])
def switch_branch(name): return run(["switch",name])
def fetch(remote="origin"): return run(["fetch",remote])
def pull(remote="origin",branch=""): return run(["pull",remote,*([branch] if branch else [])])
def push(remote="origin",branch=""): return run(["push",remote,*([branch] if branch else [])])
def stash(action="push",message=""): return run(["stash",action,*([message] if message and action=="push" else [])])
def merge(branch): return run(["merge",branch],timeout=300)
def conflicts(): return run(["diff","--name-only","--diff-filter=U"])

def conflict_data(path):
    current=workspace.read_file(path)
    head=workspace.git(["show","HEAD:"+path])
    merge_head=workspace.git(["show","MERGE_HEAD:"+path])
    return {"path":path,"current":current,"base":head.get("stdout",""),"incoming":merge_head.get("stdout",""),"base_ok":head.get("ok",False),"incoming_ok":merge_head.get("ok",False)}
