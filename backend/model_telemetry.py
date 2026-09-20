"""Lightweight persistent model/provider telemetry for explainable routing."""
from __future__ import annotations
import json,time
from typing import Any
import db

def init():
    conn=db.get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS model_telemetry(
        id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT NOT NULL, provider TEXT NOT NULL,
        operation TEXT NOT NULL, ok INTEGER NOT NULL, latency_ms REAL NOT NULL,
        validation_ok INTEGER, repair_count INTEGER, error TEXT, created_at REAL NOT NULL)""")
    conn.commit(); conn.close()

def record(model:str,provider:str,operation:str,ok:bool,latency_ms:float,validation_ok:bool|None=None,repair_count:int|None=None,error:str=""):
    init()
    conn=db.get_conn()
    conn.execute("INSERT INTO model_telemetry(model,provider,operation,ok,latency_ms,validation_ok,repair_count,error,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                 (model,provider,operation,int(ok),float(latency_ms),None if validation_ok is None else int(validation_ok),repair_count,error[:1000],time.time()))
    conn.commit(); conn.close()

def snapshot(model:str|None=None)->dict[str,Any]:
    init(); conn=db.get_conn()
    if model:
        rows=conn.execute("SELECT model,provider,operation,COUNT(*) n,AVG(latency_ms) latency,AVG(ok) success FROM model_telemetry WHERE model=? GROUP BY model,provider,operation",(model,)).fetchall()
    else:
        rows=conn.execute("SELECT model,provider,operation,COUNT(*) n,AVG(latency_ms) latency,AVG(ok) success FROM model_telemetry GROUP BY model,provider,operation ORDER BY n DESC").fetchall()
    conn.close()
    return {"models":[dict(r) for r in rows]}

def score(model:str,base:float=0.0)->float:
    init(); conn=db.get_conn()
    row=conn.execute("SELECT AVG(ok) success,AVG(latency_ms) latency,COUNT(*) n FROM model_telemetry WHERE model=?",(model,)).fetchone(); conn.close()
    if not row or not row["n"]: return base
    success=float(row["success"] or 0); latency=float(row["latency"] or 0)
    return base + success*2.0 + (1.0 if latency < 3000 else 0.0)
