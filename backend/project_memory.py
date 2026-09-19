"""Persistent project graph, dependency hints, symbols and architecture memory."""
from __future__ import annotations
import ast, json, re, time
from pathlib import Path
from typing import Any
import db

class ProjectMemory:
    def __init__(self): self._init()
    def _init(self):
        c=db.get_conn(); c.executescript("""
        CREATE TABLE IF NOT EXISTS project_nodes(path TEXT PRIMARY KEY, kind TEXT, language TEXT, size INTEGER, sha256 TEXT, updated_at REAL);
        CREATE TABLE IF NOT EXISTS project_edges(source TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL, UNIQUE(source,target,kind));
        CREATE TABLE IF NOT EXISTS architecture_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, content TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, kind TEXT, content TEXT NOT NULL, created_at REAL NOT NULL);
        """); c.commit(); c.close()
    def index(self, root:str)->dict[str,int]:
        import hashlib
        base=Path(root).resolve(); nodes=edges=0; seen=set()
        c=db.get_conn()
        for p in base.rglob("*"):
            if not p.is_file() or any(x in p.parts for x in {".git","node_modules","__pycache__",".venv","venv","dist","build"}): continue
            try: data=p.read_bytes()
            except OSError: continue
            rel=str(p.relative_to(base)).replace("\\","/"); lang=p.suffix.lower().lstrip(".") or "text"
            c.execute("INSERT INTO project_nodes(path,kind,language,size,sha256,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET kind=excluded.kind,language=excluded.language,size=excluded.size,sha256=excluded.sha256,updated_at=excluded.updated_at",(rel,"file",lang,len(data),hashlib.sha256(data).hexdigest(),time.time())); nodes+=1
            if p.suffix==".py":
                try:
                    tree=ast.parse(data.decode("utf-8"))
                    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module] + [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
                    for target in imports:
                        c.execute("INSERT OR IGNORE INTO project_edges(source,target,kind) VALUES(?,?,?)",(rel,target,"import")); edges+=1
                except Exception: pass
        c.commit(); c.close(); return {"nodes":nodes,"edges":edges}
    def graph(self,limit:int=500)->dict[str,Any]:
        c=db.get_conn(); nodes=[dict(r) for r in c.execute("SELECT * FROM project_nodes ORDER BY path LIMIT ?",(limit,)).fetchall()]; edges=[dict(r) for r in c.execute("SELECT * FROM project_edges LIMIT ?",(limit*3,)).fetchall()]; c.close(); return {"nodes":nodes,"edges":edges}
    def remember(self,kind:str,content:str,run_id:str|None=None)->None:
        c=db.get_conn(); table="agent_memory" if run_id else "architecture_memory"
        if run_id: c.execute("INSERT INTO agent_memory(run_id,kind,content,created_at) VALUES(?,?,?,?)",(run_id,kind,content,time.time()))
        else: c.execute("INSERT INTO architecture_memory(kind,content,created_at) VALUES(?,?,?)",(kind,content,time.time()))
        c.commit(); c.close()
memory=ProjectMemory()
